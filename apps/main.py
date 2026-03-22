import uasyncio as asyncio
from manager import PopApp, run, launch, exit_app
import input_manager
from input_keys import *
import utils.trace as trace
from audio_player import AudioPlayer
import utils.res as res
from utils.trace import *

import tft_config

from gui.core.gui import Screen
from gui.widgets.label import Label
from gui.widgets.progressbar import ProgressBar
from gui.widgets.image import ImageWidget
from gui.core.colors import *
from gui.fonts import font14, arial_50, icons


class GameMainApp(PopApp):
    def __init__(self):
        super().__init__()
        self.screen = Screen(GRAY)
        image = ImageWidget(60, 60, "res/images/pingpong.rgb")
        self.screen.add(image)

    def on_enter(self):
        dprint(DEBUG_INFO, "GameMainApp on_enter")
        self.screen.invalidate()

    def on_pause(self):
        dprint(DEBUG_INFO, "GameMainApp on_pause")

    def on_resume(self):
        dprint(DEBUG_INFO, "GameMainApp on_resume")

    def on_exit(self):
        dprint(DEBUG_INFO, "GameMainApp on_exit")
    
    def on_event(self, evt):
        dprint(DEBUG_INFO, "GameMainApp on_event: {evt}")

    def on_input(self, key, status):
        if key in (GPIO_KEY_ENTER, BLE_KEY_ENTER):
            if status == KEY_S_PRESSED:
                launch(GamePinPong())

    def render(self):
        self.screen.show()


class TableTennisScoreboard:
    def __init__(self, player1="Player1", player2="Player2", win_score=11, win_margin=2):
        self.win_score = win_score
        self.win_margin = win_margin
        self.current_game = 1
        self.player1_name = player1
        self.player2_name = player2
        self.player1_score = 0
        self.player2_score = 0
        self.games_player1 = 0
        self.games_player2 = 0
        self.game_ended = False          # 新增：当前局是否已结束（分数冻结）

    def reset_game(self):
        """重置当前局分数（不改变局分），并清除结束标志"""
        self.player1_score = 0
        self.player2_score = 0
        self.game_ended = False

    def start_new_game(self):
        """开始新的一局（同 reset_game，用于外部调用）"""
        self.reset_game()

    def score_point(self, player):
        if player == 1:
            self.player1_score += 1
        elif player == 2:
            self.player2_score += 1
        else:
            print("无效的玩家，请输入 1 或 2")
            return False, self.player1_score, self.player2_score

        # 检查是否一局结束（仅在未结束状态下判断）
        if not self.game_ended and self.is_game_won():
            self.end_game()
            return True, self.player1_score, self.player2_score   # 返回 True 表示一局结束，分数为结束时的比分
        return False, self.player1_score, self.player2_score

    def is_game_won(self):
        if (self.player1_score >= self.win_score and
            self.player1_score - self.player2_score >= self.win_margin):
            return True
        if (self.player2_score >= self.win_score and
            self.player2_score - self.player1_score >= self.win_margin):
            return True
        return False

    def end_game(self):
        """记录胜者，增加局分，但不清除当前分数（用于显示结束比分）"""
        if self.player1_score > self.player2_score:
            self.games_player1 += 1
        else:
            self.games_player2 += 1
        self.current_game += 1
        self.game_ended = True          # 标记当前局已结束，分数冻结

    def get_score(self):
        return self.player1_score, self.player2_score

    def get_game_status(self):
        return self.current_game, self.games_player1, self.games_player2

    def start_new_match(self):
        """开始新比赛：重置所有数据"""
        self.current_game = 1
        self.games_player1 = 0
        self.games_player2 = 0
        self.reset_game()               # 重置分数并清除结束标志

class GamePinPong(PopApp):
    def __init__(self):
        super().__init__()
        dprint(DEBUG_INFO, "GamePinPong init")
        self.scoreboard = TableTennisScoreboard(player1="Qiang", player2="Ciya")
        self.screen = Screen(bgcolor=GRAY)
        screen_width = self.screen.w
        screen_height = self.screen.h
        self.title = Label(screen_width // 2 , 2, "PingPong", font14, GREEN, align="center")
        self.server1_label = Label(20, 40, "*", font14, BLUE)
        self.player1_label = Label(20 + self.server1_label.w, 40, "Qiang", font14, BLUE)
        self.server2_label = Label(20 + screen_width // 2, 40, "*", font14, RED)
        self.player2_label = Label(20 + screen_width // 2 + self.server2_label.w, 40, "Ciya", font14, RED)

        self.score1_label = Label(screen_width // 2 - 20, 80, "00", arial_50, BLUE, align="right")
        self.score_split_label = Label(120, 80, ":", arial_50, GRAY, align="center")
        self.score2_label = Label(screen_width // 2 + 20, 80, "00", arial_50, RED)

        self.p1_win_set = Label(screen_width//4, screen_height - 80, "0", font14, BLUE, align='center')
        self.p2_win_set = Label(int(screen_width//4 * 3), screen_height - 80, "0", font14, RED, align="center")
        self.progress_bar = ProgressBar(20, screen_height - 40 ,
                                       screen_width - 40, 10, GREEN, BLUE, RED, 50)

        # 提示标签（用于显示“按ENTER开始下一局”）
        self.prompt_label = Label(screen_width // 2, screen_height // 2, "", font14, YELLOW, align="center")
        self.prompt_label.visible = False

        self.screen.add_list([self.title, self.player1_label, self.player2_label,
                              self.server1_label, self.server2_label,
                              self.score1_label, self.score_split_label, self.score2_label,
                              self.p1_win_set, self.p2_win_set,
                              self.progress_bar,
                              self.prompt_label])
        
        # 游戏状态标志
        self.game_active = True       # 当前局是否进行中
        self.waiting_for_next_set = False   # 是否等待按 ENTER 开始新一局

        self.update_score_display()

    def update_score_display(self):
        """根据计分板更新所有显示标签"""
        s1, s2 = self.scoreboard.get_score()
        self.score1_label.set_text(f"{s1:02d}")
        self.score2_label.set_text(f"{s2:02d}")

        _, g1, g2 = self.scoreboard.get_game_status()
        self.p1_win_set.set_text(str(g1))
        self.p2_win_set.set_text(str(g2))
        if g1 + g2 == 0:
            rate = 50
        else:
            rate = int(g1/(g1 + g2)*100)
            if rate < 1:
                rate = 1
            elif rate > 99:
                rate = 99
        self.progress_bar.set_value(rate)

        # 可选：发球指示器（根据总分奇偶）
        if not self.waiting_for_next_set:  # 仅游戏进行中显示发球指示器
            total = s1 + s2
            server = 1 if (total // 2) % 2 == 0 else 2
            self.server1_label.visible = (server == 1)
            self.server2_label.visible = (server == 2)
        else:
            # 等待下一局时隐藏发球指示器
            self.server1_label.visible = False
            self.server2_label.visible = False

    def set_game_active(self, active):
        """设置游戏是否允许加分"""
        self.waiting_for_next_set = not active
        self.prompt_label.visible = not active
        if active:
            self.prompt_label.set_text("")
        else:
            self.prompt_label.set_text("Press ENTER")

    def start_next_set(self):
        """开始新的一局（重置当前局分数）"""
        if self.waiting_for_next_set:
            self.scoreboard.start_new_game()   # 重置分数为 0:0
            self.update_score_display()
            self.set_game_active(True)         # 激活游戏（waiting_for_next_set 变为 False）

    def start_new_match(self):
        """开始全新的比赛"""
        self.scoreboard.start_new_match()
        self.update_score_display()
        self.set_game_active(True)

    def on_enter(self):
        dprint(DEBUG_INFO, "GamePinPong on_enter")
        self.screen.invalidate()

    def on_pause(self):
        dprint(DEBUG_INFO, "GamePinPong on_pause")

    def on_resume(self):
        dprint(DEBUG_INFO, "GamePinPong on_resume")
        self.screen.invalidate()

    def on_exit(self):
        dprint(DEBUG_INFO, "GamePinPong on_exit")
    
    def on_event(self, evt):
        dprint(DEBUG_INFO, "GamePinPong on_event: {evt}")

    def on_timer(self, timer_id):
        dprint(DEBUG_INFO, "timer {} enter".format(timer_id))
        if timer_id == 1:
            dprint(DEBUG_INFO, "Quit game")
            exit_app()
        elif timer_id == 2:
            dprint(DEBUG_INFO, "start new match")
            self.start_new_match()

    def on_input(self, key, status):
        dprint(DEBUG_INFO, "Key: {}, Status: {}".format(key, status))
        new_set = False
        s1 = s2 = 0
        score_change = False

        # 处理长按菜单返回（退出）
        if key in (GPIO_KEY_BACK, BLE_KEY_MENU):
            if status == KEY_S_PRESSED:
                self.set_timer(1, 3000)
            elif status == KEY_S_RELEASED:
                self.cancel_timer(1)
            return
        
        # 处理 ENTER 键：短按开始下一局，长按开始新比赛
        if key in (GPIO_KEY_ENTER, BLE_KEY_ENTER):
            if status == KEY_S_PRESSED:
                self.set_timer(2, 2000)          # 长按计时
            elif status == KEY_S_RELEASED:
                self.cancel_timer(2)
                if self.waiting_for_next_set:
                    # 短按：开始新的一局
                    self.start_next_set()
            return
        
        # 只有在游戏进行中（waiting_for_next_set == False）才处理加分
        if self.waiting_for_next_set:
            return

        # 加分逻辑
        score_change = False
        new_set = False
        s1 = s2 = 0

        if status == KEY_S_PRESSED:
            if key in (GPIO_KEY_PREV, BLE_KEY_UP):
                new_set, s1, s2 = self.scoreboard.score_point(1)
                score_change = True
            elif key in (GPIO_KEY_NEXT, BLE_KEY_DOWN):
                new_set, s1, s2 = self.scoreboard.score_point(2)
                score_change = True

        if score_change:
            # play audio
            audio_files = res.build_score_files(s1, s2)
            if new_set:
                audio_files.append(res.SET_FINISH)
                _set_number, player1_sets_won, player2_sets_won = self.scoreboard.get_game_status()
                audio_files.extend(res.build_score_files(player1_sets_won, player2_sets_won))
            audio_files = ['res/wav/' + filename for filename in audio_files]
            get_audio().play_files(audio_files)

            # 刷新UI显示
            self.update_score_display()

            # 如果一局结束，停用游戏，等待下一局
            if new_set:
                self.set_game_active(False)


    def render(self):
        dprint(DEBUG_INFO, "GamePinPong render")
        self.screen.show()
        dprint(DEBUG_INFO, "GamePinPong render end")

def get_audio():
    global audio
    return audio

# ------------------ 主程序 ------------------
async def main():
    global audio
    trace.DEBUG_LEVEL = trace.DEBUG_INFO | trace.DEBUG_ERROR
    input_manager.start()
    audio = AudioPlayer()
    audio.start()
    await run(GameMainApp())

asyncio.run(main())

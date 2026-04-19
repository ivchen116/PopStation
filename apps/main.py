import tft_config

import uasyncio as asyncio
from manager import PopApp, run, launch, exit_app
import input_manager
from input_keys import *
import utils.trace as trace
from audio_player import AudioPlayer
import utils.res as res
from utils.trace import *

from gui.core.gui import Screen
from gui.widgets.label import Label
from gui.widgets.progressbar import ProgressBar
from gui.widgets.shape import Rectangle, Line
from gui.widgets.image import ImageWidget
from gui.core.colors import *
from gui.fonts import font10, arial_50, icon_font16, icon_font24, arial35, freesans20, icon_font36
from config import config


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
        self.screen.invalidate()

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

class GamePinPong(PopApp):
    def __init__(self):
        super().__init__()

        # load from config
        players = config.get('players')
        p1_name = players[0] if len(players) > 0 else "Player1"
        p2_name = players[1] if len(players) > 1 else "Player2"
        ball_bgcolors = config.get('ball_bgcolors')
        p1_color = ball_bgcolors[0] if len(ball_bgcolors) > 0 else GREEN
        p2_color = ball_bgcolors[1] if len(ball_bgcolors) > 1 else BLUE

        dprint(DEBUG_INFO, "GamePinPong init")
        from score_board import Scoreboard, TableTennisRule
        self.scoreboard = Scoreboard(TableTennisRule())
        self.screen = Screen(bgcolor=GRAY)
        screen_width = self.screen.w
        screen_height = self.screen.h

        # TOP HEADER BAR
        toolbar_h = 40
        toolbar = Rectangle(0, 0, screen_width, toolbar_h, GRAY)
        cfg_icon = Label(20, 10, icon_font24.MENU, icon_font24, WHITE)
        p1_add = Label(80, 10, icon_font24.ADD, icon_font24, WHITE)
        start_stop = Label(140, 10, icon_font24.REFRESH, icon_font24, WHITE)
        p2_add = Label(200, 10, icon_font24.ADD, icon_font24, WHITE)
        toolbar.add_list([cfg_icon, p1_add, start_stop, p2_add])

        # MAIN PART
        scorbar_h = 40
        mainpart_h = screen_height - toolbar_h - scorbar_h
        mainpart = Rectangle(0, 40, screen_width, mainpart_h)

        # 左侧分数板
        part1 = Rectangle(0, 0, screen_width//2, mainpart_h, p1_color)
        self.p1_server = Label(10, 19, icon_font16.PINGPONG, icon_font16, WHITE)
        self.p1_server.visible = False
        self.p1_win_set = Label(screen_width//4 - 10, 10, "0", arial35, WHITE, w=screen_width//4, h=40, align='right')
        self.score1_label = Label(0, 50, "00", arial_50, WHITE, w=screen_width//2, align="center")
        self.player1_label = Label(0, 120, p1_name, freesans20, WHITE, w=screen_width//2, align="center")
        self.winer1_flag = Label(2, 120, icon_font24.SPORTS_SCORE, icon_font24, RED)
        self.winer1_flag.visible = False
        part1.add_list([self.p1_server, self.p1_win_set, self.player1_label, self.score1_label, self.winer1_flag])

        # 右侧分数板
        part2 = Rectangle(screen_width//2, 0, screen_width//2, mainpart_h, p2_color)
        self.p2_server = Label(screen_width//2 - icon_font16.max_width() - 10, 19, icon_font16.PINGPONG, icon_font16, WHITE)
        self.p2_server.visible = False
        self.p2_win_set = Label(10, 10, "0", arial35, WHITE, w=screen_width//4, align="left")
        self.score2_label = Label(0, 50, "00", arial_50, WHITE, w=screen_width//2, align="center")
        self.player2_label = Label(0, 120, p2_name, freesans20, WHITE, w=screen_width//2, align="center")
        self.winer2_flag = Label(2, 120, icon_font24.SPORTS_SCORE, icon_font24, RED)
        self.winer2_flag.visible = False
        part2.add_list([self.p2_server, self.p2_win_set, self.player2_label, self.score2_label, self.winer2_flag])

        mainpart.add_list([part1, part2])

        # 状态标签/结算界面
        self.prompt_label = Label(0, 120, icon_font36.NOT_STARTED, icon_font36, RED,
                                  w=screen_width, h=80,
                                  align="center", valign="middle")
        # self.prompt_label = Label(0, 80, "Press ENTER to start", font10,
        #                           WHITE, bgcolor=YELLOW,
        #                           w=screen_width, h=80,
        #                           align="center", valign="middle")
        self.prompt_label.visible = False

        # 历史计分板
        self.scorebar = Rectangle(0, screen_height - scorbar_h, screen_width, scorbar_h, GRAY)
        p1_sb_name = Label(0, 0, p1_name, font10, WHITE, w=60, h=scorbar_h//2, valign="middle")
        p2_sb_name = Label(0, scorbar_h//2, p2_name, font10, WHITE, w=60, h=scorbar_h//2, valign="middle")
        sb_split_line = Line(0, scorbar_h//2, screen_width, scorbar_h//2, WHITE)
        self.scorebar.add_list([p1_sb_name, sb_split_line, p2_sb_name])

        # 历史比分记录
        self.history_records = []
        self.history_records_labels = []
        self.history_records_show_n = 0

        for i in range(7):
            new_label1 = Label(60 + 25 *i, 0, "0", font10, WHITE, w=20, h=20, align="center", valign="middle")
            new_label2 = Label(60 + 25 *i, 20, "0", font10, WHITE, w=20, h=20, align="center", valign="middle")
            new_label1.set_visible(False)
            new_label2.set_visible(False)
            self.history_records_labels.append((new_label1, new_label2))
            self.scorebar.add(new_label1)
            self.scorebar.add(new_label2)

        self.screen.add_list([toolbar, mainpart, self.scorebar, self.prompt_label])
        
        # 游戏状态标志
        self.game_active = True       # 当前局是否进行中
        self.waiting_for_next_set = False   # 是否等待按 ENTER 开始新一局

        self.update_score_display()

    def update_score_display(self):
        """根据计分板更新所有显示标签"""
        server = self.scoreboard.get_server()
        if server == 1:
            self.p1_server.set_visible(True)
            self.p2_server.set_visible(False)
        else:
            self.p1_server.set_visible(False)
            self.p2_server.set_visible(True)

        end_status = self.scoreboard.get_end_status()
        s1, s2 = self.scoreboard.get_score()
        if end_status:
            #self.prompt_label.set_visible(True)
            if s1 > s2:
                self.winer1_flag.set_visible(True)
            else:
                self.winer2_flag.set_visible(True)
        else:
            #self.prompt_label.set_visible(False)
            self.winer1_flag.set_visible(False)
            self.winer2_flag.set_visible(False)

        self.score1_label.set_text(f"{s1:02d}")
        self.score2_label.set_text(f"{s2:02d}")

        _, g1, g2 = self.scoreboard.get_game_status()
        self.p1_win_set.set_text(str(g1))
        self.p2_win_set.set_text(str(g2))

        # 是否增加显示
        score_history_n = len(self.history_records)
        if score_history_n > len(self.history_records_labels):
            score_history_n = len(self.history_records_labels)
        if self.history_records_show_n < score_history_n:
            for i in range(self.history_records_show_n, score_history_n):
                p1_score, p2_score = self.history_records[i]
                p1_label, p2_label = self.history_records_labels[i]
                # update label
                p1_label.set_text(f"{p1_score}")
                p1_label.set_visible(True)
                p2_label.set_text(f"{p2_score}")
                p2_label.set_visible(True)
            self.history_records_show_n = score_history_n
        elif self.history_records_show_n > score_history_n:
            for i in range(score_history_n, self.history_records_show_n):
                p1_label, p2_label = self.history_records_labels[i]
                p1_label.set_visible(False)
                p2_label.set_visible(False)
            self.history_records_show_n = score_history_n

    def set_game_active(self, active):
        """设置游戏是否允许加分"""
        self.waiting_for_next_set = not active
        #self.prompt_label.set_visible(not active)

    def start_next_set(self):
        """开始新的一局（重置当前局分数）"""
        if self.waiting_for_next_set:
            self.scoreboard.start_new_game()   # 重置分数为 0:0
            self.update_score_display()
            self.set_game_active(True)         # 激活游戏（waiting_for_next_set 变为 False）

    def start_new_match(self):
        """开始全新的比赛"""
        self.history_records = []
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
        if key in (GPIO_KEY_MENU, BLE_KEY_MENU):
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
            if key in (GPIO_KEY_PREV, BLE_KEY_LEFT):
                new_set, s1, s2 = self.scoreboard.score_point(1)
                score_change = True
            elif key in (GPIO_KEY_NEXT, BLE_KEY_RIGHT):
                new_set, s1, s2 = self.scoreboard.score_point(2)
                score_change = True

        if score_change:
            if config.get('tts_enable'):
                # play tts
                audio_files = res.build_score_files(s1, s2)
                if new_set:
                    audio_files.append(res.SET_FINISH)
                    #_set_number, player1_sets_won, player2_sets_won = self.scoreboard.get_game_status()
                    #audio_files.extend(res.build_score_files(player1_sets_won, player2_sets_won))
                audio_files = ['res/wav/' + filename for filename in audio_files]
                get_audio().play_files(audio_files)

            # 如果一局结束，停用游戏，等待下一局
            if new_set:
                self.set_game_active(False)
                self.history_records.append((s1, s2))

            # 刷新UI显示
            self.update_score_display()


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

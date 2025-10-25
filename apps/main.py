import uasyncio as asyncio
from manager import PopApp, run, launch, exit_app, set_dc
import input_manager
from input_keys import *
import display_manager
import utils.trace as trace
import struct
import framebuf
from audio_player import AudioPlayer
import utils.res as res

def draw_bin(dc, filename, x=0, y=0):
    with open(filename, "rb") as f:
        header = f.read(4)
        w, h = struct.unpack("<HH", header)
        data = bytearray(f.read())
        fb = framebuf.FrameBuffer(data, w, h, framebuf.MONO_HLSB)
        dc.blit(fb, x, y)

class GameMainApp(PopApp):
    def on_enter(self):
        print(f"[DEBUG] GameMainApp on_enter")

    def on_pause(self):
        print("[DEBUG] GameMainApp on_pause")

    def on_resume(self):
        print("[DEBUG] GameMainApp on_resume")

    def on_exit(self):
        print(f"[DEBUG] GameMainApp on_exit")
    
    def on_event(self, evt):
        print(f"[DEBUG] GameMainApp on_event: {evt}")

    def on_input(self, key, status):
        if key == GPIO_KEY_ENTER or key == BLE_KEY_ENTER:
            if status == KEY_S_PRESSED:
                launch(GamePinPong())

    def render(self, dc):
        dc.fill(0)
        draw_bin(dc, "res/pingpong64.bin", 32, 0)
        dc.show()


class TableTennisScoreboard:
    def __init__(self, player1="Player1", player2="Player2", win_score=11, win_margin=2):
        """
        初始化计分板
        :param win_score: 每局比赛的获胜分数，默认是 11
        :param win_margin: 获胜者必须领先的最小分数，默认是 2
        """
        self.win_score = win_score      # 每局获胜分数
        self.win_margin = win_margin    # 获胜者必须领先的分数
        self.current_game = 1           # 当前比赛局数
        self.player1_name = player1
        self.player2_name = player2
        self.player1_score = 0          # 玩家 1 得分
        self.player2_score = 0          # 玩家 2 得分
        self.games_player1 = 0         # 玩家 1 赢得的局数
        self.games_player2 = 0         # 玩家 2 赢得的局数

    def reset_game(self):
        """重置当前局数，开始新的局"""
        self.player1_score = 0
        self.player2_score = 0
        #print(f"开始第 {self.current_game} 局比赛...")

    def score_point(self, player):
        """
        为指定的玩家加分
        :param player: 1 或 2，指定哪个玩家得分
        """
        if player == 1:
            self.player1_score += 1
        elif player == 2:
            self.player2_score += 1
        else:
            print("无效的玩家，请输入 1 或 2")
            return

        set_score1 = self.player1_score
        set_score2 = self.player2_score
        # 判断是否结束当前局
        if self.is_game_won():
            self.end_game()
            return True, set_score1, set_score2
        return False, set_score1, set_score2

    def is_game_won(self):
        """
        判断当前局是否有人获胜
        """
        if (self.player1_score >= self.win_score and
            self.player1_score - self.player2_score >= self.win_margin):
            return True
        if (self.player2_score >= self.win_score and
            self.player2_score - self.player1_score >= self.win_margin):
            return True
        return False

    def end_game(self):
        """
        结束当前局，记录胜者，并开始新的一局
        """
        if self.player1_score > self.player2_score:
            #print(f"玩家 1 获胜，当前比分：{self.player1_score}-{self.player2_score}")
            self.games_player1 += 1
        else:
            #print(f"玩家 2 获胜，当前比分：{self.player2_score}-{self.player1_score}")
            self.games_player2 += 1
        
        self.current_game += 1
        self.reset_game()

    def get_player(self):
        return self.player1_name, self.player2_name

    def get_score(self):
        """
        获取当前局的比分
        """
        #print(f"当前比分：玩家 1 - {self.player1_score} | 玩家 2 - {self.player2_score}")
        return self.player1_score, self.player2_score

    def get_game_status(self):
        """
        获取目前为止的比赛状态
        """
        return self.current_game, self.games_player1, self.games_player2

    def start_new_match(self):
        """
        开始一场新的比赛，重置所有数据
        """
        self.current_game = 1
        self.games_player1 = 0
        self.games_player2 = 0
        self.reset_game()
        #print("新比赛开始！")

# ======================
# 工具函数
# ======================
def text_size(text, scale=1):
    """计算字符串宽高（假设每字8x8）"""
    return len(text) * 8 * scale, 8 * scale


def draw_text_scaled(fb, text, x, y, scale=1, color=1):
    """在framebuf上绘制可缩放字体"""
    w, h = len(text)*8, 8
    buf = bytearray(w*h//8)
    tmp = framebuf.FrameBuffer(buf, w, h, framebuf.MONO_HLSB)
    tmp.fill(0)
    tmp.text(text, 0, 0, color)
    for yy in range(h):
        for xx in range(w):
            if tmp.pixel(xx, yy):
                fb.fill_rect(x+xx*scale, y+yy*scale, scale, scale, color)

class GamePinPong(PopApp):
    def __init__(self):
        super().__init__()
        self.scoreboard = TableTennisScoreboard(player1="Qiang", player2="Ciya")

    def on_enter(self):
        print("[DEBUG] GamePinPong on_enter")

    def on_pause(self):
        print("[DEBUG] GamePinPong on_pause")

    def on_resume(self):
        print("[DEBUG] GamePinPong on_resume")

    def on_exit(self):
        print("[DEBUG] GamePinPong on_exit")
    
    def on_event(self, evt):
        print(f"[DEBUG] GamePinPong on_event: {evt}")

    def on_timer(self, timer_id):
        print("timer {} enter".format(timer_id))
        if timer_id == 1:
            print("Quit game")
            exit_app()
        elif timer_id == 2:
            print("start new match")
            self.scoreboard.start_new_match()
            self.update()

    def on_input(self, key, status):
        print("Key: {}, Status: {}".format(key, status))
        new_set = False
        s1 = s2 = 0
        score_change = False

        if key == GPIO_KEY_BACK or key == BLE_KEY_MENU:
            if status == KEY_S_PRESSED:
                self.set_timer(1, 3000)
            elif status == KEY_S_RELEASED:
                self.cancel_timer(1)
        elif key == GPIO_KEY_ENTER or key == BLE_KEY_ENTER:
            if status == KEY_S_PRESSED:
                self.set_timer(2, 2000)
            elif status == KEY_S_RELEASED:
                self.cancel_timer(2)
        if status == KEY_S_PRESSED and (key == GPIO_KEY_PREV or key == BLE_KEY_UP):
            new_set, s1, s2 = self.scoreboard.score_point(1)
            score_change = True
        elif status == KEY_S_PRESSED and (key == GPIO_KEY_NEXT or key == BLE_KEY_DOWN):
            new_set, s1, s2 = self.scoreboard.score_point(2)
            score_change = True
        else:
            pass

        if score_change:
            # play audio
            audio_files = res.build_score_files(s1, s2)
            if new_set:
                audio_files.append(res.SET_FINISH)
                _set_number, player1_sets_won, player2_sets_won = self.scoreboard.get_game_status()
                audio_files.extend(res.build_score_files(player1_sets_won, player2_sets_won))
            audio_files = ['res/wav/' + filename for filename in audio_files]
            get_audio().play_files(audio_files)

            # flush screen
            self.update()

    def render(self, dc):
        sb = self.scoreboard
        screen_width = dc.width
        screen_height = dc.height

        fb_buf = bytearray(screen_width * screen_height // 8)
        fb = framebuf.FrameBuffer(fb_buf, screen_width, screen_height, framebuf.MONO_HLSB)
        fb.fill(0)

        # 模拟数据
        player1, player2 = sb.get_player()
        set_number, p1_sets, p2_sets = sb.get_game_status()
        p1_score, p2_score = sb.get_score()

        # 字体缩放
        small, middle, large = 1, 2, 2

        # 左上角：Player1 名字
        draw_text_scaled(fb, player1, 0, 0, small)

        # 右上角：Player2 名字
        text_w, text_h = text_size(player2, small)
        draw_text_scaled(fb, player2, screen_width - text_w - 2, 0, small)

        # 上中：第几局
        round_name = "Set {}".format(set_number)
        round_w, _ = text_size(round_name, small)
        draw_text_scaled(fb, round_name, (screen_width - round_w)//2, 0, small)

        # 中间比分
        colon_w, _ = text_size(":", large)
        p1_w, _ = text_size(str(p1_score), large)
        total_w = p1_w*2 + colon_w
        x_start = (screen_width - total_w)//2
        y_start = 20
        draw_text_scaled(fb, f"{p1_score}:{p2_score}", x_start, y_start, large)

        # 左下角
        p1_sets_text = str(p1_sets)
        draw_text_scaled(fb, p1_sets_text, 0, screen_height - 28, middle)

        # 右下角
        p2_sets_text = str(p2_sets)
        t_w, _ = text_size(p2_sets_text, middle)
        draw_text_scaled(fb, p2_sets_text, screen_width - t_w - 2, screen_height - 28, middle)

        # 底部进度条
        bar_height = 10
        top_y = screen_height - bar_height - 2
        fb.rect(0, top_y, screen_width, bar_height, 1)
        total = p1_sets + p2_sets
        percent = 50 if total == 0 else int(p1_sets * 100 / total)
        fb.fill_rect(0, top_y, int(screen_width * percent / 100), bar_height, 1)

        # 显示到屏幕
        dc.blit(fb, 0, 0)
        dc.show()

def get_audio():
    global audio
    return audio

# ------------------ 主程序 ------------------
async def main():
    global audio
    trace.DEBUG_LEVEL = trace.DEBUG_INFO | trace.DEBUG_ERROR
    input_manager.start()
    display_manager.init()
    audio = AudioPlayer()
    audio.start()
    set_dc(display_manager.get_oled())
    await run(GameMainApp())

asyncio.run(main())

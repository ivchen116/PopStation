import utils.res as res
from app_context import get_audio
from config import config
from gui.core.colors import BLUE, GRAY, GREEN, RED, WHITE
from gui.core.gui import Screen
from gui.fonts import arial35, arial_50, font10, freesans20, icon_font16, icon_font24, icon_font36
from gui.widgets.label import Label
from gui.widgets.shape import Line, Rectangle
from input_keys import BLE_KEY_ENTER, BLE_KEY_LEFT, BLE_KEY_MENU, BLE_KEY_RIGHT, GPIO_KEY_ENTER, GPIO_KEY_MENU, GPIO_KEY_NEXT, GPIO_KEY_PREV, KEY_S_PRESSED, KEY_S_RELEASED
from manager import PopApp, exit_app
from score_board import BadmintonRule, Scoreboard, TableTennisRule
from utils.trace import DEBUG_INFO, dprint


PINGPONG_DEF = {
    "name": "PingPong",
    "menu_icon_image": "res/images/pingpong.png565",
    "rule_factory": TableTennisRule,
    "server_icon": icon_font16.PINGPONG,
    "toolbar_icon": icon_font24.PINGPONG,
}

BADMINTON_DEF = {
    "name": "Badminton",
    "menu_icon_image": "res/images/badminton.png565",
    "rule_factory": BadmintonRule,
    "server_icon": icon_font16.BADMINTON,
    "toolbar_icon": icon_font24.BADMINTON,
}


class ScoreGameApp(PopApp):
    TIMER_EXIT = 1
    TIMER_NEW_MATCH = 2
    EXIT_HOLD_MS = 1200
    NEW_MATCH_HOLD_MS = 2000

    def __init__(self, game_def):
        super().__init__()
        self.game_def = game_def

        players = config.get("players")
        p1_name = players[0] if len(players) > 0 else "Player1"
        p2_name = players[1] if len(players) > 1 else "Player2"
        ball_bgcolors = config.get("ball_bgcolors")
        p1_color = ball_bgcolors[0] if len(ball_bgcolors) > 0 else GREEN
        p2_color = ball_bgcolors[1] if len(ball_bgcolors) > 1 else BLUE

        dprint(DEBUG_INFO, "{} init".format(game_def["name"]))

        self.scoreboard = Scoreboard(game_def["rule_factory"]())
        self.screen = Screen(bgcolor=GRAY)
        screen_width = self.screen.w
        screen_height = self.screen.h

        toolbar_h = 40
        toolbar = Rectangle(0, 0, screen_width, toolbar_h, GRAY)
        game_icon = Label(20, 10, game_def["toolbar_icon"], icon_font24, WHITE)
        p1_add = Label(80, 10, icon_font24.ADD, icon_font24, WHITE)
        start_stop = Label(140, 10, icon_font24.REFRESH, icon_font24, WHITE)
        p2_add = Label(200, 10, icon_font24.ADD, icon_font24, WHITE)
        toolbar.add_list([game_icon, p1_add, start_stop, p2_add])

        scorbar_h = 40
        mainpart_h = screen_height - toolbar_h - scorbar_h
        mainpart = Rectangle(0, 40, screen_width, mainpart_h)

        part1 = Rectangle(0, 0, screen_width // 2, mainpart_h, p1_color)
        self.p1_server = Label(10, 19, game_def["server_icon"], icon_font16, WHITE)
        self.p1_server.visible = False
        self.p1_win_set = Label(screen_width // 4 - 10, 10, "0", arial35, WHITE, w=screen_width // 4, h=40, align="right")
        self.score1_label = Label(0, 50, "00", arial_50, WHITE, w=screen_width // 2, align="center")
        self.player1_label = Label(0, 120, p1_name, freesans20, WHITE, w=screen_width // 2, align="center")
        self.winer1_flag = Label(2, 120, icon_font24.SPORTS_SCORE, icon_font24, RED)
        self.winer1_flag.visible = False
        part1.add_list([self.p1_server, self.p1_win_set, self.player1_label, self.score1_label, self.winer1_flag])

        part2 = Rectangle(screen_width // 2, 0, screen_width // 2, mainpart_h, p2_color)
        self.p2_server = Label(screen_width // 2 - icon_font16.max_width() - 10, 19, game_def["server_icon"], icon_font16, WHITE)
        self.p2_server.visible = False
        self.p2_win_set = Label(10, 10, "0", arial35, WHITE, w=screen_width // 4, align="left")
        self.score2_label = Label(0, 50, "00", arial_50, WHITE, w=screen_width // 2, align="center")
        self.player2_label = Label(0, 120, p2_name, freesans20, WHITE, w=screen_width // 2, align="center")
        self.winer2_flag = Label(2, 120, icon_font24.SPORTS_SCORE, icon_font24, RED)
        self.winer2_flag.visible = False
        part2.add_list([self.p2_server, self.p2_win_set, self.player2_label, self.score2_label, self.winer2_flag])

        mainpart.add_list([part1, part2])

        self.prompt_label = Label(0, 120, icon_font36.NOT_STARTED, icon_font36, RED, w=screen_width, h=80, align="center", valign="middle")
        self.prompt_label.visible = False

        self.scorebar = Rectangle(0, screen_height - scorbar_h, screen_width, scorbar_h, GRAY)
        p1_sb_name = Label(0, 0, p1_name, font10, WHITE, w=60, h=scorbar_h // 2, valign="middle")
        p2_sb_name = Label(0, scorbar_h // 2, p2_name, font10, WHITE, w=60, h=scorbar_h // 2, valign="middle")
        sb_split_line = Line(0, scorbar_h // 2, screen_width, scorbar_h // 2, WHITE)
        self.scorebar.add_list([p1_sb_name, sb_split_line, p2_sb_name])

        self.history_records = []
        self.history_records_labels = []
        self.history_records_show_n = 0

        for i in range(7):
            new_label1 = Label(60 + 25 * i, 0, "0", font10, WHITE, w=20, h=20, align="center", valign="middle")
            new_label2 = Label(60 + 25 * i, 20, "0", font10, WHITE, w=20, h=20, align="center", valign="middle")
            new_label1.set_visible(False)
            new_label2.set_visible(False)
            self.history_records_labels.append((new_label1, new_label2))
            self.scorebar.add(new_label1)
            self.scorebar.add(new_label2)

        self.screen.add_list([toolbar, mainpart, self.scorebar, self.prompt_label])
        self.waiting_for_next_set = False
        self.update_score_display()

    def update_score_display(self):
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
            if s1 > s2:
                self.winer1_flag.set_visible(True)
            else:
                self.winer2_flag.set_visible(True)
        else:
            self.winer1_flag.set_visible(False)
            self.winer2_flag.set_visible(False)

        self.score1_label.set_text(f"{s1:02d}")
        self.score2_label.set_text(f"{s2:02d}")

        _, g1, g2 = self.scoreboard.get_game_status()
        self.p1_win_set.set_text(str(g1))
        self.p2_win_set.set_text(str(g2))

        score_history_n = len(self.history_records)
        if score_history_n > len(self.history_records_labels):
            score_history_n = len(self.history_records_labels)
        if self.history_records_show_n < score_history_n:
            for i in range(self.history_records_show_n, score_history_n):
                p1_score, p2_score = self.history_records[i]
                p1_label, p2_label = self.history_records_labels[i]
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
        self.waiting_for_next_set = not active

    def start_next_set(self):
        if self.waiting_for_next_set:
            self.scoreboard.start_new_game()
            self.update_score_display()
            self.set_game_active(True)

    def start_new_match(self):
        self.history_records = []
        self.scoreboard.start_new_match()
        self.update_score_display()
        self.set_game_active(True)

    def on_enter(self):
        dprint(DEBUG_INFO, "{} on_enter".format(self.game_def["name"]))
        self.screen.invalidate()

    def on_pause(self):
        dprint(DEBUG_INFO, "{} on_pause".format(self.game_def["name"]))

    def on_resume(self):
        dprint(DEBUG_INFO, "{} on_resume".format(self.game_def["name"]))
        self.screen.invalidate()

    def on_exit(self):
        dprint(DEBUG_INFO, "{} on_exit".format(self.game_def["name"]))

    def on_event(self, evt):
        dprint(DEBUG_INFO, "{} on_event: {evt}".format(self.game_def["name"]))

    def on_timer(self, timer_id):
        dprint(DEBUG_INFO, "timer {} enter".format(timer_id))
        if timer_id == self.TIMER_EXIT:
            dprint(DEBUG_INFO, "Quit game")
            exit_app()
        elif timer_id == self.TIMER_NEW_MATCH:
            dprint(DEBUG_INFO, "start new match")
            self.start_new_match()

    def on_input(self, key, status):
        dprint(DEBUG_INFO, "Key: {}, Status: {}".format(key, status))
        new_set = False
        s1 = s2 = 0
        score_change = False

        if key in (GPIO_KEY_MENU, BLE_KEY_MENU):
            if status == KEY_S_PRESSED:
                self.set_timer(self.TIMER_EXIT, self.EXIT_HOLD_MS)
            elif status == KEY_S_RELEASED:
                self.cancel_timer(self.TIMER_EXIT)
            return

        if key in (GPIO_KEY_ENTER, BLE_KEY_ENTER):
            if status == KEY_S_PRESSED:
                self.set_timer(self.TIMER_NEW_MATCH, self.NEW_MATCH_HOLD_MS)
            elif status == KEY_S_RELEASED:
                self.cancel_timer(self.TIMER_NEW_MATCH)
                if self.waiting_for_next_set:
                    self.start_next_set()
            return

        if self.waiting_for_next_set:
            return

        if status == KEY_S_PRESSED:
            if key in (GPIO_KEY_PREV, BLE_KEY_LEFT):
                new_set, s1, s2 = self.scoreboard.score_point(1)
                score_change = True
            elif key in (GPIO_KEY_NEXT, BLE_KEY_RIGHT):
                new_set, s1, s2 = self.scoreboard.score_point(2)
                score_change = True

        if score_change:
            if config.get("tts_enable"):
                audio_files = res.build_score_files(s1, s2)
                if new_set:
                    audio_files.append(res.SET_FINISH)
                audio_files = ["res/wav/" + filename for filename in audio_files]
                get_audio().play_files(audio_files)

            if new_set:
                self.set_game_active(False)
                self.history_records.append((s1, s2))

            self.update_score_display()

    def render(self):
        dprint(DEBUG_INFO, "{} render".format(self.game_def["name"]))
        self.screen.show()
        dprint(DEBUG_INFO, "{} render end".format(self.game_def["name"]))


class PingPongApp(ScoreGameApp):
    def __init__(self):
        super().__init__(PINGPONG_DEF)


class BadmintonApp(ScoreGameApp):
    def __init__(self):
        super().__init__(BADMINTON_DEF)

from gui.core.colors import GRAY, WHITE, YELLOW
from gui.core.gui import Screen
from gui.fonts import arial35, freesans20
from gui.widgets.image import ImageWidget
from gui.widgets.label import Label
from input_keys import BLE_KEY_ENTER, BLE_KEY_LEFT, BLE_KEY_RIGHT, GPIO_KEY_POWER, GPIO_KEY_ENTER, GPIO_KEY_NEXT, GPIO_KEY_PREV, KEY_S_PRESSED
from manager import PopApp, launch
from score_game_app import BADMINTON_DEF, BadmintonApp, PINGPONG_DEF, PingPongApp
from setting_app import SettingApp
from snake_app import SNAKE_DEF, SnakeApp
from player_app import PLAYER_DEF, PlayerApp
from net_player_app import NET_PLAYER_DEF, NetPlayerApp
from utils.trace import DEBUG_INFO, dprint
from machine import Pin


class GameMainApp(PopApp):
    TIMER_SHUTDOWN = 10
    SHUTDOWN_TIMES  = 4

    def __init__(self):
        super().__init__()
        self.screen = Screen(GRAY)
        screen_width = self.screen.w
        self.shutdown_cnt = 0

        self.apps = [
            {
                "name": PINGPONG_DEF["name"],
                "factory": PingPongApp,
                "menu_icon_image": PINGPONG_DEF.get("menu_icon_image"),
            },
            {
                "name": BADMINTON_DEF["name"],
                "factory": BadmintonApp,
                "menu_icon_image": BADMINTON_DEF.get("menu_icon_image"),
            },
            {
                "name": SNAKE_DEF["name"],
                "factory": SnakeApp,
                "menu_icon_image": SNAKE_DEF.get("menu_icon_image"),
            },
            {
                "name": PLAYER_DEF["name"],
                "factory": PlayerApp,
                "menu_icon_image": PLAYER_DEF.get("menu_icon_image"),
            },
            {
                "name": NET_PLAYER_DEF["name"],
                "factory": NetPlayerApp,
                "menu_icon_image": NET_PLAYER_DEF.get("menu_icon_image"),
            },
            {
                "name": "Setting",
                "factory": SettingApp,
                "menu_icon_image": "res/images/setting.png565",
            },
        ]
        self.selected_index = 0

        self.title_label = Label(0, 18, "Select App", freesans20, WHITE, w=screen_width, align="center")
        self.icon_widget = ImageWidget(56, 55, self.apps[0]["menu_icon_image"])
        self.name_label = Label(0, 194, self.apps[0]["name"], arial35, WHITE, w=screen_width, align="center")
        self.left_arrow = Label(24, 194, "<", arial35, WHITE)
        self.right_arrow = Label(screen_width - 44, 194, ">", arial35, WHITE)

        self.notice = Label(0, 90, "Shutdown countdown: 3s", freesans20, WHITE, 
                            w=screen_width, h=60, align="center", valign="middle", bgcolor=YELLOW)
        self.notice.visible = False

        self.screen.add_list(
            [
                self.title_label,
                self.icon_widget,
                self.name_label,
                self.left_arrow,
                self.right_arrow,
                self.notice,
            ]
        )
        self._refresh_selection()

    def _refresh_selection(self):
        app_info = self.apps[self.selected_index]
        self.name_label.set_text(app_info["name"])
        self.icon_widget.set_image(app_info["menu_icon_image"], cache=False)

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
        # 长按电源键3秒后关机
        if key == GPIO_KEY_POWER:
            if status == KEY_S_PRESSED:
                self.shutdown_cnt = 0
                self.set_timer(self.TIMER_SHUTDOWN, 1000, repeat=True)
                print("Shutdown timer started")
            else:
                self.notice.set_visible(False)
                self.cancel_timer(self.TIMER_SHUTDOWN)
                print("Shutdown timer canceled")

        if status != KEY_S_PRESSED:
            return

        if key in (GPIO_KEY_PREV, BLE_KEY_LEFT):
            self.selected_index = (self.selected_index - 1) % len(self.apps)
            self._refresh_selection()
        elif key in (GPIO_KEY_NEXT, BLE_KEY_RIGHT):
            self.selected_index = (self.selected_index + 1) % len(self.apps)
            self._refresh_selection()
        elif key in (GPIO_KEY_ENTER, BLE_KEY_ENTER):
            launch(self.apps[self.selected_index]["factory"]())

    def on_timer(self, timer_id):
        if timer_id == self.TIMER_SHUTDOWN:
            self.shutdown_cnt += 1
            self.notice.set_text(f"Shutdown countdown: {self.SHUTDOWN_TIMES - self.shutdown_cnt}s")
            self.notice.set_visible(True)
            print("shutdown cnt:", self.shutdown_cnt)
            if self.shutdown_cnt >= self.SHUTDOWN_TIMES:
                self.notice.set_text(f"Release to shutdown.")
                self.cancel_timer(self.TIMER_SHUTDOWN)

                # do shutdown
                print("Shutdown...")
                power_hold = Pin(18, Pin.OUT)
                power_hold.value(0)

    def render(self):
        self.screen.show()

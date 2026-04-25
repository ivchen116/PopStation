from gui.core.colors import GRAY, WHITE
from gui.core.gui import Screen
from gui.fonts import arial35, freesans20
from gui.widgets.image import ImageWidget
from gui.widgets.label import Label
from input_keys import BLE_KEY_ENTER, BLE_KEY_LEFT, BLE_KEY_RIGHT, GPIO_KEY_ENTER, GPIO_KEY_NEXT, GPIO_KEY_PREV, KEY_S_PRESSED
from manager import PopApp, launch
from score_game_app import BADMINTON_DEF, BadmintonApp, PINGPONG_DEF, PingPongApp
from setting_app import SettingApp
from snake_app import SNAKE_DEF, SnakeApp
from utils.trace import DEBUG_INFO, dprint


class GameMainApp(PopApp):
    def __init__(self):
        super().__init__()
        self.screen = Screen(GRAY)
        screen_width = self.screen.w

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

        self.screen.add_list(
            [
                self.title_label,
                self.icon_widget,
                self.name_label,
                self.left_arrow,
                self.right_arrow,
            ]
        )
        self._refresh_selection()

    def _refresh_selection(self):
        app_info = self.apps[self.selected_index]
        self.name_label.set_text(app_info["name"])

        old_icon = self.icon_widget
        new_icon = ImageWidget(old_icon.x, old_icon.y, app_info["menu_icon_image"])
        if old_icon in self.screen.root.children:
            idx = self.screen.root.children.index(old_icon)
            self.screen.root.children[idx] = new_icon
            new_icon.parent = self.screen.root
            new_icon.on_add_to_screen(self.screen)
            old_icon.invalidate()
            new_icon.invalidate()
        self.icon_widget = new_icon

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

    def render(self):
        self.screen.show()

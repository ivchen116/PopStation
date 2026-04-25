from config import config
from gui.core.colors import GRAY, WHITE
from gui.core.gui import Screen
from gui.fonts import arial35, freesans20
from gui.widgets.image import ImageWidget
from gui.widgets.label import Label
from input_keys import BLE_KEY_ENTER, BLE_KEY_LEFT, BLE_KEY_MENU, BLE_KEY_RIGHT, GPIO_KEY_ENTER, GPIO_KEY_MENU, GPIO_KEY_NEXT, GPIO_KEY_PREV, KEY_S_PRESSED
from manager import PopApp, exit_app
from utils.trace import DEBUG_INFO, dprint


class SettingApp(PopApp):
    def __init__(self):
        super().__init__()
        self.screen = Screen(bgcolor=GRAY)
        screen_width = self.screen.w

        self.items = ["volume", "tts_enable"]
        self.selected_index = 0

        self.title_label = Label(0, 16, "Settings", freesans20, WHITE, w=screen_width, align="center")
        self.icon_widget = ImageWidget(92, 42, "res/images/setting.png565")
        self.volume_label = Label(20, 120, "", arial35, WHITE, w=200)
        self.tts_label = Label(20, 162, "", arial35, WHITE, w=200)

        self.screen.add_list(
            [
                self.title_label,
                self.icon_widget,
                self.volume_label,
                self.tts_label,
            ]
        )
        self._update_labels()

    def _update_labels(self):
        volume_prefix = ">" if self.selected_index == 0 else " "
        tts_prefix = ">" if self.selected_index == 1 else " "

        self.volume_label.set_text("{} Volume: {}".format(volume_prefix, config.get("volume")))
        self.tts_label.set_text("{} TTS: {}".format(tts_prefix, "ON" if config.get("tts_enable") else "OFF"))

    def _adjust_current(self, delta):
        current_item = self.items[self.selected_index]
        if current_item == "volume":
            new_volume = config.get("volume") + delta
            if new_volume < 0:
                new_volume = 0
            elif new_volume > 10:
                new_volume = 10
            config.set("volume", new_volume)
        elif current_item == "tts_enable":
            config.set("tts_enable", delta > 0)

        self._update_labels()

    def on_enter(self):
        dprint(DEBUG_INFO, "SettingApp on_enter")
        self.screen.invalidate()

    def on_pause(self):
        dprint(DEBUG_INFO, "SettingApp on_pause")

    def on_resume(self):
        dprint(DEBUG_INFO, "SettingApp on_resume")
        self.screen.invalidate()

    def on_exit(self):
        dprint(DEBUG_INFO, "SettingApp on_exit")
        config.save()

    def on_input(self, key, status):
        if status != KEY_S_PRESSED:
            return

        if key in (GPIO_KEY_PREV, BLE_KEY_LEFT):
            self._adjust_current(-1)
        elif key in (GPIO_KEY_NEXT, BLE_KEY_RIGHT):
            self._adjust_current(1)
        elif key in (GPIO_KEY_ENTER, BLE_KEY_ENTER):
            self.selected_index = (self.selected_index + 1) % len(self.items)
            self._update_labels()
        elif key in (GPIO_KEY_MENU, BLE_KEY_MENU):
            config.save()
            exit_app()

    def render(self):
        self.screen.show()

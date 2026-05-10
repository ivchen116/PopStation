import os
import time

from app_context import get_audio
from config import config
from gui.core.colors import GRAY, WHITE, YELLOW
from gui.core.gui import Screen
from gui.fonts import arial35, freesans20
from gui.widgets.label import Label
from gui.widgets.progressbar import ProgressBar
from input_keys import (
    BLE_KEY_ENTER,
    BLE_KEY_LEFT,
    BLE_KEY_MENU,
    BLE_KEY_DOWN,
    BLE_KEY_RIGHT,
    BLE_KEY_UP,
    GPIO_KEY_ENTER,
    GPIO_KEY_MENU,
    GPIO_KEY_NEXT,
    GPIO_KEY_PREV,
    KEY_S_PRESSED,
)
from manager import PopApp, min_app
from utils.trace import DEBUG_INFO, dprint


PLAYER_DEF = {
    "name": "Player",
    # No dedicated icon asset yet; reuse Settings icon for now.
    "menu_icon_image": "res/images/music.png565",
}


def _is_dir(path):
    try:
        st = os.stat(path)
        # Micropython: stat tuple, directory bit may vary; simplest: listdir works.
        return True
    except Exception:
        return False


def ensure_sd_mounted(mount_point="/sd"):
    try:
        os.listdir(mount_point)
        return True, "SD: mounted"
    except Exception:
        pass

    # Best-effort mount. Different Micropython ports expose different SD APIs.
    try:
        from machine import SDCard  # type: ignore
        from machine import Pin

        cd = Pin(21, Pin.IN, Pin.PULL_UP) 
        sd = SDCard(
            slot=3,
            sck=Pin(13),
            mosi=Pin(12),
            miso=Pin(14),
            cs=Pin(11),
            cd=cd,
            #freq=20_000_000  # SPI 时钟可根据卡调节
        )
        os.mount(sd, mount_point)
        os.listdir(mount_point)
        return True, "SD: mounted"
    except Exception as e:
        return False, "SD mount failed: {}".format(e)


def scan_wavs(mount_point="/sd"):
    wavs = []

    # Common layout: /sd/*.wav or /sd/wav/*.wav
    candidates = [mount_point, mount_point + "/wav"]
    for base in candidates:
        try:
            for name in os.listdir(base):
                low = name.lower()
                print(low)
                if low.endswith(".wav"):
                    wavs.append(base + "/" + name)
        except Exception:
            print("scan_wavs: failed to listdir {}".format(base))
            continue

    wavs.sort()
    return wavs


class PlayerApp(PopApp):
    TIMER_PROGRESS = 31
    ENTER_LONG_PRESS_MS = 700
    MODE_SINGLE = 0
    MODE_ONE = 1
    MODE_LIST = 2
    MODE_TEXT = ("Single", "One", "List")

    def __init__(self):
        super().__init__()
        if getattr(self, "_player_inited", False):
            return
        self.screen = Screen(bgcolor=GRAY)
        screen_width = self.screen.w

        self.files = []
        self.selected_index = 0
        self.playing = False
        self._handle = None
        self._playing_file = None
        self._resume_offsets = {}
        self._file_total_bytes = {}
        saved_mode = config.get("player_loop_mode")
        if saved_mode in (self.MODE_SINGLE, self.MODE_ONE, self.MODE_LIST):
            self.play_mode = saved_mode
        else:
            # backward compatibility for old bool config
            self.play_mode = self.MODE_ONE if bool(saved_mode) else self.MODE_SINGLE
        self._enter_down_ms = None

        self.title_label = Label(0, 16, "WAV Player", freesans20, WHITE, w=screen_width, align="center")
        self.status_label = Label(
            0, 44, "", freesans20, YELLOW, w=screen_width, h=28, align="center", valign="middle"
        )
        self.mode_label = Label(10, 72, "", freesans20, WHITE, w=screen_width - 20, align="left")
        self.progress_bar = ProgressBar(10, 204, screen_width - 20, 12, border_color=WHITE, fill_color=YELLOW, empty_color=WHITE, value=0)

        # Simple list view (5 lines)
        self.item_labels = []
        y0 = 96
        for i in range(5):
            lbl = Label(10, y0 + i * 28, "", freesans20, WHITE, w=screen_width - 20)
            self.item_labels.append(lbl)

        self.screen.add_list([self.title_label, self.status_label, self.mode_label, self.progress_bar] + self.item_labels)
        self._player_inited = True

    def _refresh(self):
        if not self.files:
            self.status_label.set_text("No wav found on SD (/sd or /sd/wav)")
        else:
            # Keep status line compact; playback state is shown by list item color.
            self.status_label.set_text("")
        self.mode_label.set_text("Mode: " + self.MODE_TEXT[self.play_mode])

        start = max(0, self.selected_index - 2)
        end = min(len(self.files), start + 5)
        window = self.files[start:end]

        for i in range(5):
            if i < len(window):
                idx = start + i
                prefix = ">" if idx == self.selected_index else " "
                name = window[i].split("/")[-1]
                self.item_labels[i].set_text("{} {}".format(prefix, name))
                # Highlight the currently playing track in yellow.
                item_file = window[i]
                new_color = YELLOW if (self.playing and self._playing_file == item_file) else WHITE
                if self.item_labels[i].color != new_color:
                    self.item_labels[i].color = new_color
                    self.item_labels[i].invalidate()
            else:
                self.item_labels[i].set_text("")
                if self.item_labels[i].color != WHITE:
                    self.item_labels[i].color = WHITE
                    self.item_labels[i].invalidate()

        #self.screen.invalidate()

    def _sync_playback_state(self):
        # Keep UI state aligned with actual audio handle state, including
        # re-entering app after background playback/minimize.
        if self._handle is None:
            self.playing = False
            self._playing_file = None
            self.cancel_timer(self.TIMER_PROGRESS)
            self._update_progress()
            return

        try:
            st = self._handle.state
        except Exception:
            st = None

        if st == self._handle.DONE or st == self._handle.STOPPED:
            cur_file = self._playing_file
            if cur_file is not None:
                self._resume_offsets[cur_file] = 0
            self._handle = None
            self._playing_file = None
            self.playing = False
            self.cancel_timer(self.TIMER_PROGRESS)
            self._update_progress()
            return

        # PLAYING/PAUSED are both treated as active session for UI continuity.
        self.playing = True
        if self._playing_file and self.files and self._playing_file in self.files:
            self.selected_index = self.files.index(self._playing_file)
        self.set_timer(self.TIMER_PROGRESS, 200, repeat=True)
        self._update_progress()

    def _update_progress(self):
        if not self.playing or self._handle is None or not self.files:
            self.progress_bar.set_value(0)
            return
        cur_file = self.files[self.selected_index]
        total = self._file_total_bytes.get(cur_file, 0)
        if total <= 0:
            self.progress_bar.set_value(0)
            return
        played = 0
        try:
            played = int(self._handle.bytes_played)
        except Exception:
            played = 0
        if played < 0:
            played = 0
        if played > total:
            played = total
        self.progress_bar.set_value(int((played * 100) / total))

    def _select(self, delta):
        if not self.files:
            return
        # If switching selection while playing, stop current playback and keep offset.
        if self.playing:
            self._stop()
        self.selected_index = (self.selected_index + delta) % len(self.files)
        self._refresh()

    def _stop(self):
        cur_file = None
        if self.files and 0 <= self.selected_index < len(self.files):
            cur_file = self.files[self.selected_index]

        # Capture current playback offset before stopping.
        if self._handle is not None and cur_file is not None:
            try:
                offset = int(self._handle.bytes_played)
                if offset > 0:
                    self._resume_offsets[cur_file] = offset
            except Exception:
                pass

        audio = get_audio()
        if audio:
            try:
                audio.stop_fg()
            except Exception:
                pass
        self._handle = None
        self._playing_file = None
        self.playing = False
        self.cancel_timer(self.TIMER_PROGRESS)
        self._update_progress()

    def _play_selected(self):
        if not self.files:
            return

        audio = get_audio()
        if not audio:
            self.status_label.set_text("Audio not ready")
            return

        self._stop()
        cur_file = self.files[self.selected_index]
        offset = self._resume_offsets.get(cur_file, 0)
        self._handle = audio.play_file(cur_file, offset_bytes=offset)
        self._playing_file = cur_file
        self.playing = True
        self.set_timer(self.TIMER_PROGRESS, 200, repeat=True)
        self._update_progress()
        self._refresh()

    def _play_index_from_head(self, idx):
        if not self.files:
            return
        if idx < 0 or idx >= len(self.files):
            return
        audio = get_audio()
        if not audio:
            return
        self.selected_index = idx
        cur_file = self.files[idx]
        self._handle = audio.play_file(cur_file, offset_bytes=0)
        self._playing_file = cur_file
        self.playing = True
        self.set_timer(self.TIMER_PROGRESS, 200, repeat=True)
        self._update_progress()
        self._refresh()

    def _toggle_loop_mode(self):
        self.play_mode = (self.play_mode + 1) % 3
        config.set("player_loop_mode", self.play_mode)
        config.save()
        self._refresh()

    def on_enter(self):
        dprint(DEBUG_INFO, "PlayerApp on_enter")
        ok, msg = ensure_sd_mounted("/sd")
        if not ok:
            self.files = []
            self.status_label.set_text(msg)
            self._refresh()
            return

        self.files = scan_wavs("/sd")
        self._file_total_bytes = {}
        for f in self.files:
            try:
                size = os.stat(f)[6]
                self._file_total_bytes[f] = size - 44 if size > 44 else 0
            except Exception:
                self._file_total_bytes[f] = 0
        if not self.files:
            self.selected_index = 0
        elif self._playing_file in self.files:
            self.selected_index = self.files.index(self._playing_file)
        elif self.selected_index >= len(self.files):
            self.selected_index = 0

        self._sync_playback_state()
        self._update_progress()
        self._refresh()

    def on_pause(self):
        dprint(DEBUG_INFO, "PlayerApp on_pause")
        self.cancel_timer(self.TIMER_PROGRESS)

    def on_resume(self):
        dprint(DEBUG_INFO, "PlayerApp on_resume")
        self._sync_playback_state()
        self._refresh()
        self.screen.invalidate()

    def on_exit(self):
        dprint(DEBUG_INFO, "PlayerApp on_exit")
        # Minimize behavior: keep playback running in background.
        self.cancel_timer(self.TIMER_PROGRESS)

    def on_timer(self, timer_id):
        if timer_id == self.TIMER_PROGRESS:
            self._update_progress()

    def on_input(self, key, status):
        # GPIO ENTER: short press play/pause, long press toggle mode.
        if key == GPIO_KEY_ENTER:
            if status == KEY_S_PRESSED:
                self._enter_down_ms = time.ticks_ms()
                return
            # treat release as action point
            if self._enter_down_ms is not None:
                held = time.ticks_diff(time.ticks_ms(), self._enter_down_ms)
                self._enter_down_ms = None
                if held >= self.ENTER_LONG_PRESS_MS:
                    self._toggle_loop_mode()
                    return
                # short press -> play/stop toggle
                if self.playing:
                    self._stop()
                    self._refresh()
                else:
                    self._play_selected()
                return

        # Be tolerant: some non-GPIO sources may only emit RELEASED.
        if status not in (KEY_S_PRESSED,):
            if key not in (GPIO_KEY_MENU, BLE_KEY_MENU):
                return

        if key in (GPIO_KEY_PREV, BLE_KEY_LEFT):
            self._select(-1)
        elif key in (GPIO_KEY_NEXT, BLE_KEY_RIGHT):
            self._select(1)
        elif key in (GPIO_KEY_ENTER, BLE_KEY_ENTER):
            # Toggle play/stop on the same selection.
            if self.playing:
                self._stop()
                self._refresh()
            else:
                self._play_selected()
        elif key in (BLE_KEY_UP, BLE_KEY_DOWN):
            self._toggle_loop_mode()
        elif key in (GPIO_KEY_MENU, BLE_KEY_MENU):
            # Minimize to main menu, keep background playback.
            self.cancel_timer(self.TIMER_PROGRESS)
            min_app(self)

    def render(self):
        self._sync_playback_state()
        # Auto clear resume offset when track naturally reaches end.
        if self.playing and self._handle is not None:
            try:
                if self._handle.state == self._handle.DONE:
                    cur_file = self.files[self.selected_index] if self.files else None
                    if cur_file is not None and self.play_mode == self.MODE_ONE:
                        self._resume_offsets[cur_file] = 0
                        self._play_index_from_head(self.selected_index)
                    elif cur_file is not None and self.play_mode == self.MODE_LIST and self.files:
                        self._resume_offsets[cur_file] = 0
                        next_idx = (self.selected_index + 1) % len(self.files)
                        self._play_index_from_head(next_idx)
                    else:
                        if cur_file is not None:
                            self._resume_offsets[cur_file] = 0
                        self._handle = None
                        self._playing_file = None
                        self.playing = False
                        self.cancel_timer(self.TIMER_PROGRESS)
                    self._update_progress()
                    self._refresh()
            except Exception:
                pass
        self.screen.show()

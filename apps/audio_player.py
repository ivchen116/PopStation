import uasyncio as asyncio
import random
from machine import Pin, I2S
from utils.queue import EventQueue
import board_config as hw
from config import config

# ------------------ I2S 引脚配置 ------------------
SCK_PIN = hw.AUDIO_I2S_SCK   # BCLK
WS_PIN  = hw.AUDIO_I2S_WS   # LRCLK
SD_PIN  = hw.AUDIO_I2S_SD   # DIN
SHUTDOWN = hw.AUDIO_I2S_SHUTDOWN

# SCK_PIN = 16   # BCLK
# WS_PIN  = 17   # LRCLK
# SD_PIN  = 15   # DIN
# SHUTDOWN = 7

# 0~10 → 0~256（指数曲线 gamma≈2.0）
VOLUME_TABLE = [
    0,    # 0
    3,    # 1
    10,   # 2
    23,   # 3
    41,   # 4
    64,   # 5
    92,   # 6
    125,  # 7
    164,  # 8
    207,  # 9
    256   # 10
]

def volume_user_to_hw(volume):
    volume = max(0, min(10, volume))
    return VOLUME_TABLE[volume]

def volume_hw_to_user(hw):
    closest = 0
    min_diff = 999

    for i, v in enumerate(VOLUME_TABLE):
        diff = abs(v - hw)
        if diff < min_diff:
            min_diff = diff
            closest = i

    return closest

@micropython.viper
def adjust_volume_viper(buf: ptr8, length: int, volume: int):
    for i in range(0, length, 2):
        sample = buf[i] | (buf[i+1] << 8)
        if sample >= 32768:
            sample -= 65536

        sample = (sample * volume) >> 8

        if sample > 32767:
            sample = 32767
        elif sample < -32768:
            sample = -32768

        buf[i] = sample & 0xFF
        buf[i+1] = (sample >> 8) & 0xFF

@micropython.viper
def fade_in_viper(buf: ptr8, length: int):
    samples = length // 2
    for i in range(samples):
        idx = i * 2
        sample = buf[idx] | (buf[idx+1] << 8)
        if sample >= 32768:
            sample -= 65536

        sample = (sample * i) // samples

        if sample > 32767:
            sample = 32767
        elif sample < -32768:
            sample = -32768

        buf[idx] = sample & 0xFF
        buf[idx+1] = (sample >> 8) & 0xFF

# ------------------ WAV 文件解析 ------------------
def parse_wav_header(f):
    f.seek(22)
    num_channels = int.from_bytes(f.read(2), "little")
    sample_rate = int.from_bytes(f.read(4), "little")
    f.seek(34)
    bits_per_sample = int.from_bytes(f.read(2), "little")
    f.seek(44)
    #print(f"[DEBUG] WAV Header: channels={num_channels}, rate={sample_rate}, bits={bits_per_sample}")
    return num_channels, sample_rate, bits_per_sample, 44

i2s_inited = False

BUF_SIZE = 4096
SILENCE_SIZE = 0

# ------------------ 音频播放器 ------------------
class AudioPlayer:
    def __init__(self):
        self.queue = EventQueue()
        self.bg_playlist = []
        self.bg_index = 0
        self.bg_pos = 0
        self.bg_paused = True
        self.loop_mode = True
        self.random_mode = False
        self._buf = bytearray(BUF_SIZE)
        self._silence = bytes(SILENCE_SIZE)

        # 初始化 I2S
        self.i2s = I2S(
            0,
            sck=Pin(SCK_PIN),
            ws=Pin(WS_PIN),
            sd=Pin(SD_PIN),
            mode=I2S.TX,
            bits=16,
            format=I2S.MONO,
            rate=16000,
            ibuf=20000
        )
        self.shutdown = Pin(SHUTDOWN, Pin.OUT)
        self.shutdown.value(0)
        self.swriter = asyncio.StreamWriter(self.i2s, {})
        print("[DEBUG] I2S initialized with default parameters")

    def set_bg_playlist(self, files, loop=True, random_order=False):
        self.bg_playlist = files
        self.bg_index = 0
        self.bg_pos = 0
        self.loop_mode = loop
        self.random_mode = random_order
        if self.random_mode:
            random.shuffle(self.bg_playlist)
        print(f"[DEBUG] Background playlist set: {self.bg_playlist}, loop={loop}, random={random_order}")

    async def play_task(self):
        while True:
            if not self._bg_ready() or not self.queue.empty():
                cmd, arg = await self.queue.get()
                print(f"[DEBUG] Handling command: {cmd}, arg={arg}")
                await self._handle_command(cmd, arg)
            elif self._bg_ready():
                await self._play_bg()

    def start(self):
        asyncio.create_task(self.play_task())

    def play_files(self, file_list):
        self.queue.put(("PLAY", file_list))

    def play_file(self, file):
        self.queue.put(("PLAY", [file]))

    def _bg_ready(self):
        return self.bg_playlist and self.bg_paused is False

    async def _handle_command(self, cmd, arg):
        if cmd == "PLAY":
            await self._play_files(arg)
        elif cmd == "PLAY_BG":
            self.bg_paused = False
            print(f"[DEBUG] Starting background playback")
        elif cmd == "NEXT_BG":
            self._select_next_bg()
        elif cmd == "PREV_BG":
            self._select_prev_bg()
        elif cmd == "PAUSE_BG":
            self.bg_paused = True
            print("[DEBUG] Background paused")
        elif cmd == "RESUME_BG":
            if not self.bg_playlist:
                self.bg_paused = False
                print("[DEBUG] Background resumed")
        elif cmd == "STOP_BG":
            self.bg_playlist = []
            self.bg_pos = 0
            self.bg_index = 0
            print("[DEBUG] Background stopped")

    def _select_next_bg(self):
        if not self.bg_playlist:
            return
        self.bg_index = (self.bg_index + 1) % len(self.bg_playlist)
        self.bg_pos = 0
        print(f"[DEBUG] Next background track index: {self.bg_index}")

    def _select_prev_bg(self):
        if not self.bg_playlist:
            return
        self.bg_index = (self.bg_index - 1) % len(self.bg_playlist)
        self.bg_pos = 0
        print(f"[DEBUG] Previous background track index: {self.bg_index}")

    async def _play_bg(self):
        if not self._bg_ready():
            return

        while self.queue.empty():
            if self.bg_index >= len(self.bg_playlist):
                self.bg_index = 0
                if self.loop_mode is False:
                    self.bg_paused = True
                    print(f"[DEBUG] Play list play finished.")
                    break
                if self.random_mode:
                    random.shuffle(self.bg_playlist)
            fname = self.bg_playlist[self.bg_index]
            print(f"[DEBUG] Playing background index:{self.bg_index} track: {fname}")
            finish, offset = await self._play_file(fname, start=self.bg_pos)
            if finish:
                self.bg_pos = 0
                self.bg_index = self.bg_index + 1
            else:
                self.bg_pos = offset
                break

    async def _play_files(self, filelist):
        """连续播放多个 WAV 文件，只初始化一次 I2S，并在全部播放结束后静音"""
        finish = False
        i2s_initialized = False

        try:
            for idx, file in enumerate(filelist):
                filename = file
                print(f"[DEBUG] Start file: {filename}")

                with open(file, "rb") as f:
                    ch, rate, bits, data_start = parse_wav_header(f)

                    # ---- 仅第一次初始化 I2S ----
                    if not i2s_initialized:
                        self.i2s.init(
                            sck=Pin(SCK_PIN),
                            ws=Pin(WS_PIN),
                            sd=Pin(SD_PIN),
                            mode=I2S.TX,
                            bits=bits,
                            format=I2S.STEREO if ch == 2 else I2S.MONO,
                            rate=rate,
                            ibuf=20000
                        )
                        i2s_initialized = True
                        self.shutdown.value(1)
                        #print(f"[DEBUG] I2S initialized: rate={rate}, bits={bits}, ch={ch}")

                    f.seek(data_start)
                    
                    # --- 首文件预热静音(实测无效果?) ---
                    if idx == 0 and len(self._silence):
                        await self.swriter.awrite(self._silence)

                    # --- 渐入处理，处理文件首'啵'音（fade-in）---
                    fade_ms = 60
                    frame_size = (bits // 8) * ch

                    fade_frames = int(rate * fade_ms / 1000)
                    fade_bytes = fade_frames * frame_size
                    #print(f"[DEBUG] fade_frames:{fade_frames}, fade_bytes:{fade_bytes}")

                    n = f.readinto(memoryview(self._buf)[:fade_bytes])
                    if bits == 16 and n > 0:
                        fade_in_viper(self._buf, n)

                    audio_volume = config.get('volume')
                    if audio_volume != 10:
                        adjust_volume_viper(self._buf, n, volume_user_to_hw(audio_volume))
                    
                    await self.swriter.awrite(memoryview(self._buf)[:n])

                    # --- 主播放循环 ---
                    while True:
                        # 可随时中断
                        if not self.queue.empty():
                            print(f"[DEBUG] Playback interrupted at {filename}")
                            finish = True
                            break

                        n = f.readinto(self._buf)
                        if not n:
                            break

                        audio_volume = config.get('volume')
                        if audio_volume != 10:
                            adjust_volume_viper(self._buf, n, volume_user_to_hw(audio_volume))

                        await self.swriter.awrite(memoryview(self._buf)[:n])
                        await asyncio.sleep_ms(0)

                if finish:
                    break

            # --- 所有文件播放完毕后，发送静音 ---
            #print("[DEBUG] All files done, sending silence tail")
            if len(self._silence):
                await self.swriter.awrite(self._silence)

        except Exception as e:
            print(f"[DEBUG] Error in _play_files: {e}")
            finish = True

        finally:
            # try:
            #     self.i2s.deinit()
            #     print("[DEBUG] I2S deinitialized")
            # except Exception as e:
            #     print(f"[DEBUG] I2S deinit failed: {e}")

            return finish


# ------------ TEST START ------------
async def button_task(audio_player):
    # ------------------ 按钮控制测试 ------------------
    btn_prev = Pin(1, Pin.IN, Pin.PULL_UP)
    btn_next = Pin(2, Pin.IN, Pin.PULL_UP)
    btn_pause = Pin(3, Pin.IN, Pin.PULL_UP)

    while True:
        if not btn_prev.value():
            await audio_player.queue.put(("PREV_BG", None))
            await asyncio.sleep(0.3)
        if not btn_next.value():
            await audio_player.queue.put(("NEXT_BG", None))
            await asyncio.sleep(0.3)
        if not btn_pause.value():
            if audio_player.bg_paused:
                await audio_player.queue.put(("RESUME_BG", None))
            else:
                await audio_player.queue.put(("PAUSE_BG", None))
            await asyncio.sleep(0.3)
        await asyncio.sleep(0.05)

# ------------------ 主测试程序 ------------------
async def main():
    audio = AudioPlayer()
    #audio.set_bg_playlist(["0123456789.wav", "0123456789.wav"], loop=False, random_order=False)

    asyncio.create_task(audio.play_task())
    audio.play_file("0123456789.wav")
    #asyncio.create_task(button_task(audio))

    #await audio.queue.put(("PLAY_BG", ""))

    # 模拟插播音效
    #await asyncio.sleep(10)
    # await audio.queue.put(("PLAY", ["beep-08b.wav"]))

    while True:
        await asyncio.sleep(5)
        audio.play_file("0123456789.wav")

if __name__ == "__main__":
    asyncio.run(main())
# ------------ TEST END ------------

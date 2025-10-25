import uasyncio as asyncio
import os
import random
from machine import Pin, I2S
from utils.queue import EventQueue
import borad_config as hw

# ------------------ I2S 引脚配置 ------------------
SCK_PIN = hw.I2S_SCK   # BCLK
WS_PIN  = hw.I2S_WS   # LRCLK
SD_PIN  = hw.I2S_SD   # DIN
SHUTDOWN = hw.I2S_SHUTDOWN

# ------------------ WAV 文件解析 ------------------
def parse_wav_header(f):
    f.seek(22)
    num_channels = int.from_bytes(f.read(2), "little")
    sample_rate = int.from_bytes(f.read(4), "little")
    f.seek(34)
    bits_per_sample = int.from_bytes(f.read(2), "little")
    f.seek(44)
    print(f"[DEBUG] WAV Header: channels={num_channels}, rate={sample_rate}, bits={bits_per_sample}")
    return num_channels, sample_rate, bits_per_sample, 44

i2s_inited = False
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
            for file in arg:
                await self._play_file(file)
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

    async def _play_file(self, filename, start=0):
        finish = False
        offset = start
        try:
            with open(filename, "rb") as f:
                ch, rate, bits, data_start = parse_wav_header(f)

                global i2s_inited
                # 初始化 I2S 参数
                #self.i2s.deinit()
                #if i2s_inited is not True:
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
                #print(f"[DEBUG] I2S re-initialized: rate={rate}, bits={bits}, channels={ch}")
                i2s_inited = True

                f.seek(offset + data_start)
                print(f"[DEBUG] Start playback from byte: {data_start + start}")
                #await self.swriter.awrite(b"\x00" * 4096)
                            # --- 1) 写静音预热 ---
                await self.swriter.awrite(b"\x00" * 4096)  # 50~100ms 静音
                self.shutdown.value(1)

                # --- 2) 首段渐入（fade-in）避免突变 click）---
                fade_ms = 50
                fade_samples = int(rate * fade_ms / 1000)
                fade_bytes = fade_samples * (bits // 8) * ch
                head = f.read(fade_bytes)
                import array
                if bits == 16:
                    arr = array.array('h', head)
                    for i in range(len(arr)):
                        arr[i] = int(arr[i] * i / len(arr))  # 线性渐入
                    await self.swriter.awrite(bytes(arr))
                else:
                    # 其他位深直接写
                    await self.swriter.awrite(head)

                offset += fade_bytes
                
                while True:
                    if not self.queue.empty():
                        print(f"[DEBUG] Playback interrupted: {filename}, offset={offset}")
                        break

                    data = f.read(4096)
                    if not data:
                        print(f"[DEBUG] End of file reached: {filename}")
                        finish  = True
                        break

                    await self.swriter.awrite(data)
                    #await self.swriter.awrite(b"\x00" * 1024)
                    offset += len(data)
                    #await asyncio.sleep(0)

                await self.swriter.awrite(b"\x00" * 2048)
                print(f"[DEBUG] Stop playback: {filename}")

        except Exception as e:
            print(f"[DEBUG] Error playing file {filename}: {e}")
            finish = True
        finally:
            #self.i2s.deinit()
            self.shutdown.value(0)
            return finish, offset

# ------------------ 按钮控制 ------------------
btn_prev = Pin(1, Pin.IN, Pin.PULL_UP)
btn_next = Pin(2, Pin.IN, Pin.PULL_UP)
btn_pause = Pin(3, Pin.IN, Pin.PULL_UP)

async def button_task(audio_player):
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

# ------------------ 主程序 ------------------
async def main():
    audio = AudioPlayer()
    audio.set_bg_playlist(["0123456789.wav", "0123456789.wav"], loop=False, random_order=False)

    asyncio.create_task(audio.play_task())
    asyncio.create_task(button_task(audio))

    await audio.queue.put(("PLAY_BG", ""))

    # 模拟插播音效
    await asyncio.sleep(10)
    await audio.queue.put(("PLAY", ["beep-08b.wav"]))

    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())

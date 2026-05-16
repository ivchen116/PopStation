import sys

if "/apps" not in sys.path:
    sys.path.append("/apps")

import time
import uasyncio as asyncio
from machine import Pin, I2S
from utils.queue import EventQueue
import board_config as hw
from config import config
from audio_sources.file_wav_source import FileWavSource
from audio_sources.http_wav_source import HttpWavSource


I2S_ID = hw.AUDIO_I2S_ID
SCK_PIN = hw.AUDIO_I2S_SCK
WS_PIN = hw.AUDIO_I2S_WS
SD_PIN = hw.AUDIO_I2S_SD
SHUTDOWN = hw.AUDIO_I2S_SHUTDOWN


VOLUME_TABLE = [0, 3, 10, 23, 41, 64, 92, 125, 164, 207, 256]


def volume_user_to_hw(volume):
    volume = max(0, min(10, volume))
    return VOLUME_TABLE[volume]


@micropython.viper
def adjust_volume_viper(buf: ptr8, length: int, volume: int):
    for i in range(0, length, 2):
        sample = buf[i] | (buf[i + 1] << 8)
        if sample >= 32768:
            sample -= 65536
        sample = (sample * volume) >> 8
        if sample > 32767:
            sample = 32767
        elif sample < -32768:
            sample = -32768
        buf[i] = sample & 0xFF
        buf[i + 1] = (sample >> 8) & 0xFF


@micropython.viper
def fade16_in_viper(buf: ptr8, length: int):
    samples = length // 2
    if samples <= 1:
        return
    for i in range(samples):
        idx = i * 2
        sample = buf[idx] | (buf[idx + 1] << 8)
        if sample >= 32768:
            sample -= 65536
        sample = (sample * i) // samples
        if sample > 32767:
            sample = 32767
        elif sample < -32768:
            sample = -32768
        buf[idx] = sample & 0xFF
        buf[idx + 1] = (sample >> 8) & 0xFF


@micropython.viper
def fade_out_viper(buf: ptr8, length: int):
    samples = length // 2
    if samples <= 1:
        return
    for i in range(samples):
        idx = i * 2
        sample = buf[idx] | (buf[idx + 1] << 8)
        if sample >= 32768:
            sample -= 65536
        gain = samples - i
        sample = (sample * gain) // samples
        if sample > 32767:
            sample = 32767
        elif sample < -32768:
            sample = -32768
        buf[idx] = sample & 0xFF
        buf[idx + 1] = (sample >> 8) & 0xFF


@micropython.viper
def fade_out_tail_viper(buf: ptr8, start: int, length: int):
    samples = length // 2
    if samples <= 1:
        return
    for i in range(samples):
        idx = start + i * 2
        sample = buf[idx] | (buf[idx + 1] << 8)
        if sample >= 32768:
            sample -= 65536
        gain = samples - i
        sample = (sample * gain) // samples
        if sample > 32767:
            sample = 32767
        elif sample < -32768:
            sample = -32768
        buf[idx] = sample & 0xFF
        buf[idx + 1] = (sample >> 8) & 0xFF


def parse_wav_header_bytes(b):
    if b is None or len(b) < 44:
        raise ValueError("wav header too short")
    num_channels = int.from_bytes(b[22:24], "little")
    sample_rate = int.from_bytes(b[24:28], "little")
    bits_per_sample = int.from_bytes(b[34:36], "little")
    return num_channels, sample_rate, bits_per_sample, 44


class PlaybackHandle:
    IDLE = 0
    PLAYING = 1
    PAUSED = 2
    STOPPED = 3
    DONE = 4

    MODE_NORMAL = 0
    MODE_INSERT = 1

    def __init__(self, service, source_list, mode=MODE_NORMAL):
        self._service = service
        self.source_list = source_list
        self.state = self.IDLE
        self.mode = mode
        self.bytes_played = 0
        self.source_index = 0
        self.start_offset_bytes = 0
        self.interrupted = False

    def pause(self):
        self._service.pause_handle(self)

    def resume(self):
        self._service.resume_handle(self)

    def stop(self):
        self._service.stop_handle(self)


async def _read_exact(source, mv, quit_cond=None, timeout=None):
    total_read = 0
    length = len(mv)
    start = time.ticks_ms() if timeout else None

    while total_read < length:
        if quit_cond and quit_cond():
            break
        if timeout:
            if time.ticks_diff(time.ticks_ms(), start) > timeout * 1000:
                raise asyncio.TimeoutError(f"read_exact timeout after {total_read}/{length} bytes")

        n = await source.readinto(mv[total_read:])
        if n == 0:  # EOF
            break
        total_read += n
    return total_read

class AudioService:
    IBUF_SIZE = 40000
    BUF_SIZE = 8192
    FADE_MS = 60

    def __init__(self):
        self.queue = EventQueue()
        self.current_handle = None
        self.wait_resume = None
        self._buf = bytearray(self.BUF_SIZE)

        self.sample_rate = 16000
        self.channels = 2
        self.bits_per_sample = 16
        self.i2s = I2S(
            I2S_ID,
            sck=Pin(SCK_PIN),
            ws=Pin(WS_PIN),
            sd=Pin(SD_PIN),
            mode=I2S.TX,
            bits=self.bits_per_sample,
            format=I2S.STEREO if self.channels == 2 else I2S.MONO,
            rate=self.sample_rate,
            ibuf=self.IBUF_SIZE,
        )
        self.shutdown = Pin(SHUTDOWN, Pin.OUT)
        self.shutdown.value(1)
        self.swriter = asyncio.StreamWriter(self.i2s, {})
        self._last_write_tick = 0

    def start(self):
        asyncio.create_task(self._task())

    def play_file(self, filepath, offset_bytes=0, emerge=False):
        handle = PlaybackHandle(self, [FileWavSource(filepath, offset_bytes=offset_bytes)], mode=PlaybackHandle.MODE_NORMAL if not emerge else PlaybackHandle.MODE_INSERT)
        handle.bytes_played = offset_bytes if offset_bytes and offset_bytes > 0 else 0
        handle.start_offset_bytes = handle.bytes_played
        self.queue.put(("PLAY", handle))
        return handle

    def play_files(self, file_list, emerge=False):
        sources = [FileWavSource(f) for f in file_list]
        handle = PlaybackHandle(self, sources, mode=PlaybackHandle.MODE_NORMAL if not emerge else PlaybackHandle.MODE_INSERT)
        self.queue.put(("PLAY", handle))
        return handle

    def play_http_wav(self, url):
        handle = PlaybackHandle(self, [HttpWavSource(url)], mode=PlaybackHandle.MODE_NORMAL)
        self.queue.put(("PLAY", handle))
        return handle

    def stop_fg(self):
        if self.current_handle is not None:
            self.current_handle.state = PlaybackHandle.STOPPED
            self.current_handle = None
        self.queue.put(("NOP", None))

    def pause_handle(self, handle):
        if self.current_handle == handle:
            self.queue.put(("PAUSE", None))

    def resume_handle(self, handle):
        self.queue.put(("RESUME", handle))

    def stop_handle(self, handle):
        if self.current_handle == handle:
            self.queue.put(("STOP", None))

    async def _task(self):
        while True:
            # Resume interrupted normal playback only when command queue is idle.
            if self.queue.empty() \
                and (self.wait_resume is not None or self.current_handle is not None):
                next = None
                if self.current_handle is not None:
                    next = self.current_handle
                    self.current_handle = None
                    print("restore current_handle playback")
                elif self.wait_resume is not None:
                    next = self.wait_resume
                    self.wait_resume = None
                    print("restore wait resume playback")

                if next is not None:
                    print(f"resume interrupted playback: {next}")
                    await self._play_handle(next)
                    continue

            cmd, arg = await self.queue.get()
            await self._handle_command(cmd, arg)

    async def _handle_command(self, cmd, arg):
        if cmd == "PLAY":
            await self._play_handle(arg)
        elif cmd == "PAUSE":
            handle = self.current_handle if arg is None else arg
            if handle:
                handle.state = PlaybackHandle.PAUSED
                self.current_handle = None
        elif cmd == "RESUME":
            if arg is not None:
                await self._play_handle(arg)
        elif cmd == "STOP":
            handle = self.current_handle if arg is None else arg
            if handle:
                handle.state = PlaybackHandle.STOPPED
                self.current_handle = None
        elif cmd == "NOP":
            return

    async def _play_handle(self, handle):
        print(f"[DEBUG] Playing handle: {handle}")
        if self.current_handle is not None \
         and self.current_handle.mode == handle.mode:
            # same mode: stop current and set new
            self.current_handle.state = PlaybackHandle.STOPPED
            self.current_handle = handle
            print("replace current with new handle")
        elif self.wait_resume is not None \
         and self.wait_resume.mode == handle.mode:
            # normal interrupt, save to resume handle
            self.wait_resume.state = PlaybackHandle.STOPPED
            self.wait_resume = handle
            print("save new handle to wait_resume")
            return
        elif handle.mode == PlaybackHandle.MODE_INSERT \
            and self.current_handle is not None \
            and self.current_handle.mode != PlaybackHandle.MODE_INSERT:
            # insert mode: resume current playback
            self.wait_resume = self.current_handle
            self.current_handle = handle
            print("save current to wait_resume")
        elif handle.mode == PlaybackHandle.MODE_NORMAL \
            and self.current_handle is not None \
            and self.current_handle.mode == PlaybackHandle.MODE_INSERT:
            # current play insert, then save to resume handle
            if self.wait_resume is not None:
                self.wait_resume.state = PlaybackHandle.STOPPED
            self.wait_resume = handle
            print("save new handle to wait_resume")
        else:
            self.current_handle = handle
            print("set new handle")

        if self.current_handle is None:
            return

        handle.state = PlaybackHandle.PLAYING

        for i in range(handle.source_index, len(handle.source_list)):
            handle.source_index = i
            src = handle.source_list[i]
            if handle.state == PlaybackHandle.STOPPED:
                break
            ok = await self._play_source(src, handle)
            if not ok:
                handle.start_offset_bytes = handle.bytes_played
                break
            # Track boundary: for the next source, start from head.
            handle.source_index = i + 1
            handle.bytes_played = 0
            handle.start_offset_bytes = 0

        # All tracks played
        if handle.source_index == len(handle.source_list):
            handle.state = PlaybackHandle.STOPPED
            print("all tracks played")

        # reset current to None
        if handle.state == PlaybackHandle.STOPPED:
            self.current_handle = None
            print("playback stopped")

    async def _drain_i2s(self):
        bytes_per_sec = (
            self.sample_rate *
            self.channels *
            (self.bits_per_sample // 8)
        )

        max_buffer_ms = (self.IBUF_SIZE * 1000) // bytes_per_sec

        elapsed = time.ticks_diff(
            time.ticks_ms(),
            self._last_write_tick
        )

        remain = max_buffer_ms - elapsed
        print(f"[DEBUG] Drain I2S: elapsed={elapsed}ms, remain={remain}ms")

        if remain > 0:
            await asyncio.sleep_ms(remain)

    def _get_drain_i2s_ms(self):
        bytes_per_sec = (
            self.sample_rate *
            self.channels *
            (self.bits_per_sample // 8)
        )

        max_buffer_ms = (self.IBUF_SIZE * 1000) // bytes_per_sec

        elapsed = time.ticks_diff(
            time.ticks_ms(),
            self._last_write_tick
        )

        remain = max_buffer_ms - elapsed

        return remain if remain > 0 else 0

    async def _play_source(self, source, handle):

        finish = False
        try:
            await source.open()
            # Apply resume offset only for the current source, not for every track in a list.
            resume_offset = handle.start_offset_bytes if (handle.start_offset_bytes and handle.start_offset_bytes > 0) else 0

            header = bytearray(44)
            total = await _read_exact(source, memoryview(header),
                                      lambda: handle.state == PlaybackHandle.STOPPED)
            if handle.state == PlaybackHandle.STOPPED:
                return True
            if not self.queue.empty():
                return False

            if total < 44:
                raise ValueError("Incomplete WAV header")

            ch, rate, bits, _ = parse_wav_header_bytes(header)
            if bits != 16:
                raise ValueError("only 16-bit wav supported")

            # For local file sources: parse header first, then seek into data area.
            if resume_offset and hasattr(source, "seek_data_offset"):
                await source.seek_data_offset(44, resume_offset)
                handle.bytes_played = resume_offset

            if self.sample_rate != rate or self.channels != ch or self.bits_per_sample != bits:
                if handle.mode == PlaybackHandle.MODE_NORMAL:
                    drain_ms = self._get_drain_i2s_ms()
                    if drain_ms > 0:
                        print(f"[DEBUG] Drain I2S: {drain_ms}ms")
                        while time.ticks_diff(time.ticks_ms(), self._last_write_tick) < drain_ms:
                            if not self.queue.empty():
                                return False
                            await asyncio.sleep_ms(100)
                    #await self._drain_i2s()
                self.sample_rate = rate
                self.channels = ch
                self.bits_per_sample = bits
                self.i2s.init(
                    sck=Pin(SCK_PIN),
                    ws=Pin(WS_PIN),
                    sd=Pin(SD_PIN),
                    mode=I2S.TX,
                    bits=bits,
                    format=I2S.STEREO if ch == 2 else I2S.MONO,
                    rate=rate,
                    ibuf=self.IBUF_SIZE,
                )

            # fade in for 16-bit audio
            frame_bytes = (bits // 8) * ch
            fade_frames = int(rate * self.FADE_MS / 1000)
            fade_bytes = fade_frames * frame_bytes

            n = await _read_exact(source, memoryview(self._buf)[:fade_bytes],
                                    lambda: handle.state == PlaybackHandle.STOPPED or not self.queue.empty())
            if handle.state == PlaybackHandle.STOPPED:
                return True
            if not self.queue.empty():
                return False

            if n > 0:
                if bits == 16:
                    fade16_in_viper(self._buf, n)
                else:
                    pass # TODO support

                audio_volume = config.get('volume')
                if audio_volume != 10:
                    adjust_volume_viper(self._buf, n, volume_user_to_hw(audio_volume))

                await self.swriter.awrite(memoryview(self._buf)[:n])
                handle.bytes_played += n

            while True:
                start = time.ticks_ms()
                n = await _read_exact(source, memoryview(self._buf),
                                      lambda: handle.state == PlaybackHandle.STOPPED or not self.queue.empty())
                if handle.state == PlaybackHandle.STOPPED:
                    return True
                if not self.queue.empty():
                    return False

                #print(f"[DEBUG] swriter read: {n} bytes cost { time.ticks_ms() - start}")
                if not n:
                    return True

                audio_volume = config.get('volume')
                if audio_volume != 10:
                    adjust_volume_viper(self._buf, n, volume_user_to_hw(audio_volume))

                self.swriter.out_buf = memoryview(self._buf)[:n]
                start = time.ticks_ms()
                await self.swriter.drain()
                #print(f"[DEBUG] swriter after drain: {n} bytes cost { time.ticks_ms() - start}")
                self._last_write_tick = time.ticks_ms()
                handle.bytes_played += n

        except Exception as e:
            print("[AudioService] play error:", e)
            return True
        finally:
            await source.close()

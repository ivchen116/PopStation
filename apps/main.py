import sys

if "/apps" not in sys.path:
    sys.path.append("/apps")

# 1.boot screen show
import tft_config

# 2. board early init
def board_early_init():
    # 1.shutdown ws2812
    import board_config
    import neopixel
    from machine import Pin

    np = neopixel.NeoPixel(Pin(board_config.WS2812_PIN), board_config.WS2812_NUM)
    for i in range(board_config.WS2812_NUM):
        np[i] = (0, 0, 0)
    np.write()

    # 2.led on
    led = Pin(8, Pin.OUT)
    led.value(1)

board_early_init()

# 3. run main
import uasyncio as asyncio

import input_manager
import utils.trace as trace
from app_context import set_audio
from audio_service import AudioService
from manager import run
from menu_app import GameMainApp


# async def watchdog_task():
#     import time
#     from machine import WDT
#     wdt = WDT(timeout=5000)

#     max_feed = 0
#     while True:
        
#         delta = time.ticks_diff(time.ticks_ms(), last_tick)
#         if delta > max_feed:
#             print("Watchdog max feed {}ms".format(delta))
#             max_feed = delta
#         last_tick = time.ticks_ms()
#         wdt.feed()
#         await asyncio.sleep(1)


async def main():
    #asyncio.create_task(watchdog_task())

    trace.DEBUG_LEVEL = trace.DEBUG_INFO | trace.DEBUG_ERROR
    input_manager.start()

    audio = AudioService()
    set_audio(audio)
    audio.start()

    await run(GameMainApp())


asyncio.run(main())

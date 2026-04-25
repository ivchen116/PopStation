import sys

if "/apps" not in sys.path:
    sys.path.append("/apps")

import tft_config

import uasyncio as asyncio

import input_manager
import utils.trace as trace
from app_context import set_audio
from audio_player import AudioPlayer
from manager import run
from menu_app import GameMainApp


async def main():
    trace.DEBUG_LEVEL = trace.DEBUG_INFO | trace.DEBUG_ERROR
    input_manager.start()

    audio = AudioPlayer()
    set_audio(audio)
    audio.start()

    await run(GameMainApp())


asyncio.run(main())

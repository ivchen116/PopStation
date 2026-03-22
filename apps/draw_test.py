from utils.trace import *

import tft_config

from gui.core.gui import Screen
from gui.widgets.label import Label
from gui.widgets.rectwidget import RectWidget
from gui.widgets.progressbar import ProgressBar
from gui.core.colors import *
from gui.fonts import font14, arial_50, icons
import time
import random

def main():
    screen = Screen(BLACK)

    rect = RectWidget(0, 0, 240, 240, BLUE)

    screen.add(rect)

    screen.invalidate()
    
    count = 0
    start_time = time.ticks_ms()
    while True:
        # if count == 0:
        #     start_time = time.ticks_ms()
        rect.set_bgcolor(random.randint(0, 0xFFFF))
        #rect.invalidate()

        start_time = time.ticks_ms()
        screen.show()
        end_time = time.ticks_ms()
        print(f"Frame time: {end_time - start_time} ms")
        #print(f"fps: {1000 / (end_time - start_time)}")
        count = count + 1
        time.sleep(1)
        # if count == 5:
        #     end_time = time.ticks_ms()
        #     print(f"fps: {5000 / (end_time - start_time)}")
        #     count = 0

main()
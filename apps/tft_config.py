
from drivers.st7789 import st7789py as st7789
from gui.core.gui import Display

from machine import Pin, SPI

import board_config as hw

# ---------------------------
# SPI 初始化
# ---------------------------
spi = SPI(
    hw.TFT_SPI_ID,
    baudrate=40_000_000,
    polarity=1,
    phase=1,
    sck=Pin(hw.TFT_SPI_SCK),
    mosi=Pin(hw.TFT_SPI_MOSI),
    miso=None
)

# ---------------------------
# ST7789 初始化
# ---------------------------
tft = st7789.ST7789(
    spi,
    240, 240,
    reset=Pin(hw.TFT_GPIO_RESET, Pin.OUT),
    dc=Pin(hw.TFT_GPIO_DC, Pin.OUT),
    rotation=1,
    color_order=st7789.BGR
)

display = Display(tft)
print('display init success')
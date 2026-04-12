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

backlight=Pin(hw.TFT_GPIO_BLK, Pin.OUT)
backlight.value(0)
# ---------------------------
# ST7789 初始化
# ---------------------------
from drivers.st7789 import st7789py as st7789
tft = st7789.ST7789(
    spi,
    240, 240,
    reset=Pin(hw.TFT_GPIO_RESET, Pin.OUT),
    dc=Pin(hw.TFT_GPIO_DC, Pin.OUT),
    rotation=1,
    color_order=st7789.BGR
)

# boot screen
try:
    with open("res/images/boot_screen.rgb", "rb") as f:
        header = f.read(6)
        magic = (header[1] << 8) | header[0]
        w = (header[3] << 8) | header[2]
        h = (header[5] << 8) | header[4]
        data = f.read()
        
        x = y = 0
        if w < tft.width:
            x = (tft.width - w) // 2
        if h < tft.height:
            y = (tft.height - h) // 2
        tft.blit_buffer(data, x, y, w, h)
except OSError as e:
    tft.fill_rect(90, 90, 60, 60, st7789.WHITE)

backlight.value(1)

# ---------------------------
# 显示框架初始化
# ---------------------------
from gui.core.gui import Display
display = Display(tft)
print('display init success')
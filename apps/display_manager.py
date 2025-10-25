from machine import Pin, I2C
import ssd1306
import time
from utils.trace import *
import borad_config as hw

def init():
    global oled
    # ---------------------------
    # 初始化 I2C
    # ---------------------------
    i2c = I2C(hw.I2C_OLED_NUM, scl=Pin(hw.I2C_OLED_SCL), sda=Pin(hw.I2C_OLED_SDA), freq=hw.I2C_OLED_FREQ)

    # 扫描 I2C 设备
    devices = i2c.scan()
    dprint(DEBUG_INFO, "I2C devices found:", devices)

    if len(devices) == 0:
        dprint(DEBUG_ERROR, "没有找到 I2C 设备，请检查接线！")
    else:
        addr = devices[0]
        dprint(DEBUG_INFO, "SSD1306 I2C 地址:", hex(addr))

    # ---------------------------
    # 初始化 SSD1306
    # ---------------------------
    oled_width = 128
    oled_height = 64
    oled = ssd1306.SSD1306_I2C(oled_width, oled_height, i2c)

def display_test():
    global oled
    # ---------------------------
    # 显示内容
    # ---------------------------
    oled.fill(0)  # 清屏

    oled.text("Hello, World!", 0, 0)
    oled.text("MicroPython", 0, 16)
    oled.text("SSD1306 OLED", 0, 32)

    oled.show()

    # ---------------------------
    # 动态演示
    # ---------------------------
    for i in range(0, 128):
        oled.fill(0)
        oled.text("Move -->", i - 64, 40)
        oled.show()
        time.sleep(0.05)

def get_oled():
    global oled
    return oled

if __name__ == "__main__":
    init()
    display_test()
    
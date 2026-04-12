# ==================================
# ESP32-S3 Board 硬件引脚配置集中定义
# ==================================

# GPIO KEY
GPIO_KEY_0 = 3 # DEC
GPIO_KEY_1 = 9 # MODE
GPIO_KEY_2 = 0 # INC
GPIO_KEY_3 = 10 # POWER

# Audio I2S
AUDIO_I2S_SCK = 16   # BCLK
AUDIO_I2S_WS = 17   # LRCLK
AUDIO_I2S_SD = 15   # DIN
AUDIO_I2S_SHUTDOWN = 7

# TFT Pins
TFT_SPI_ID = 2
TFT_SPI_SCK = 42
TFT_SPI_MOSI = 41
TFT_SPI_MISO = None
TFT_SPI_FREQ = 40_000_000
TFT_GPIO_RESET = 40
TFT_GPIO_DC = 39
TFT_GPIO_BLK = 38

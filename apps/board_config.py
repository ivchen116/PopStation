# ==================================
# ESP32-S3 Board 硬件引脚配置集中定义
# ==================================

# GPIO KEY
GPIO_KEY_0 = 3
GPIO_KEY_1 = 9
GPIO_KEY_2 = 10
GPIO_KEY_3 = 0

# Audio I2S
AUDIO_I2S_SCK = 5   # BCLK
AUDIO_I2S_WS = 4   # LRCLK
AUDIO_I2S_SD = 6   # DIN
AUDIO_I2S_SHUTDOWN = 3

# TFT Pins
TFT_SPI_ID = 2
TFT_SPI_SCK = 42
TFT_SPI_MOSI = 41
TFT_SPI_MISO = None
TFT_SPI_FREQ = 40_000_000
TFT_GPIO_RESET = 40
TFT_GPIO_DC = 39

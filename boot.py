# This file is executed on every boot (including wake-boot from deepsleep)
#import esp
#esp.osdebug(None)
#import webrepl
#webrepl.start()
from machine import Pin

power_hold = Pin(18, Pin.OUT)
power_hold.value(1)

print("boot.py holding power")
import time

DEBUG_NONE = 0
DEBUG_DBG = 1
DEBUG_INFO = 2
DEBUG_ERROR = 4

DEBUG_LEVEL = DEBUG_ERROR | DEBUG_INFO | DEBUG_DBG

def dprint(level, *args):
    if DEBUG_LEVEL & level:
        prefixes = {DEBUG_ERROR: "[ERR]", DEBUG_INFO: "[INF]", DEBUG_DBG: "[DBG]"}
        timestamp = time.ticks_ms()
        print(timestamp, prefixes.get(level, "[DBG]"), *args)
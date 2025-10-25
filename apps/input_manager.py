from button_manager import ButtonManager
import ble_keyboard as BleKeyboard
from manager import send_input_event
import borad_config as hw
from input_keys import *
from utils.trace import *


def send_input_event_wrapper(key_id, key_status):
    dprint(DEBUG_INFO, f"send_input_event: {key_id}, {key_status}")
    send_input_event(key_id, key_status)

def btn_key_to_event(key_event):
    GPIO_KEY_MAP = {
        hw.GPIO_KEY_0: GPIO_KEY_PREV,
        hw.GPIO_KEY_1: GPIO_KEY_NEXT,
        hw.GPIO_KEY_2: GPIO_KEY_BACK,
        hw.GPIO_KEY_3: GPIO_KEY_ENTER
    }
    key_id = GPIO_KEY_MAP.get(key_event["pin"], None)
    if key_id is None:
        dprint(DEBUG_ERROR, f"Unknown key: {key_event}")
        return

    key_status = KEY_S_PRESSED if key_event["state"] == "pressed" else KEY_S_RELEASED
    send_input_event_wrapper(key_id, key_status)

_last_status = 0
_last_pos_x = 0
_last_pos_y = 0
_last_key_id = None

def ble_key_adapter_to_event(input_id, input_data):
    global _last_status, _last_pos_x, _last_pos_y, _last_key_id
    if input_id == 1:
        status, x, y = input_data
        dprint(DEBUG_DBG, f"ble key1: {status}, x: {x}, y: {y}")
        if _last_status == 0:
            # button down
            if status != _last_status:
                _last_pos_x = x
                _last_pos_y = y
            # enter: Status: 7, X: 437, Y: 368, W: 910, H: 910
            if x == 437 and y == 368: 
                send_input_event_wrapper(BLE_KEY_ENTER, KEY_S_PRESSED)
                _last_key_id = BLE_KEY_ENTER
        else:
            # press
            if status != 0 and _last_key_id is None:
                if x > _last_pos_x:
                    _last_key_id = BLE_KEY_LEFT
                elif x < _last_pos_x:
                    _last_key_id = BLE_KEY_RIGHT
                else:
                    if y > _last_pos_y:
                        _last_key_id = BLE_KEY_UP
                    else:
                        _last_key_id = BLE_KEY_DOWN
                send_input_event_wrapper(_last_key_id, KEY_S_PRESSED)
            elif status == 0:
                if _last_key_id is not None: # release
                    send_input_event_wrapper(_last_key_id, KEY_S_RELEASED)
                    _last_key_id = None
            else:
                pass # ignore
        _last_status = status

    elif input_id == 2:
        status = input_data
        dprint(DEBUG_DBG, f"ble key2: {status}")
        send_input_event_wrapper(BLE_KEY_MENU, KEY_S_PRESSED if status else KEY_S_RELEASED)
    else:
        # unknown
        dprint(DEBUG_ERROR, f"Unknown input id: {input_id}")

def start():
    # 初始化 GPIO 键盘
    btn_mgr = ButtonManager(pins=[hw.GPIO_KEY_0, hw.GPIO_KEY_1, hw.GPIO_KEY_2, hw.GPIO_KEY_3], callback=btn_key_to_event)
    btn_mgr.start()

    # 初始化 BLE 键盘
    BleKeyboard.start(ble_key_adapter_to_event)

def stop():
    pass

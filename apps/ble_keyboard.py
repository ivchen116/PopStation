import asyncio
import aioble
import bluetooth
from utils.trace import *


# UUIDs for HID
_UUID_HID_SERVICE     = bluetooth.UUID(0x1812)
_UUID_REPORT_MAP      = bluetooth.UUID(0x2A4B)
_UUID_REPORT          = bluetooth.UUID(0x2A4D)
_UUID_REPORT_REF_DESC = bluetooth.UUID(0x2908)
_UUID_CCC_DESC        = bluetooth.UUID(0x2902)

# Report Reference types
_REPORT_TYPE_INPUT   = 1
_REPORT_TYPE_OUTPUT  = 2
_REPORT_TYPE_FEATURE = 3

TARGET_NAME = "NSKJ-D2"

_callback = None # callback(report_id, data)

async def find_hid_device(device_name):
    dprint(DEBUG_INFO, "Scanning for HID device...")
    async with aioble.scan(duration_ms=10000, interval_us=30000, window_us=30000) as scanner:
        async for result in scanner:
            name = result.name() or "?"
            # if _UUID_HID_SERVICE in result.services():
            #     print("Found HID:", name, result.device)
            #     return result.device
            if name == device_name:
                dprint(DEBUG_INFO, "Found:", name, result.device)
                return result.device
    return None


async def connect_and_discover(device):
    dprint(DEBUG_INFO, "Connecting to:", device)
    connection = await device.connect()
    dprint(DEBUG_INFO, "Connected:", connection.device)

    mtu = await connection.exchange_mtu()
    dprint(DEBUG_DBG, "MTU:", mtu)

    # Need Paired
    await connection.pair()

    # Discover HID service
    service = await connection.service(_UUID_HID_SERVICE)
    dprint(DEBUG_DBG, "HID service found:", service)

    # --- 1. Read Report Map (Characteristic 0x2A4B) ---
    try:
        char_map = await service.characteristic(_UUID_REPORT_MAP)
        report_map = await char_map.read()
        if len(report_map) == mtu - 1:
            report_map = await char_map.read_long(mtu - 1, 5000)
        dprint(DEBUG_DBG, "Report Map (hex):", report_map.hex())
    except Exception as e:
        dprint(DEBUG_ERROR, "Failed to read Report Map:", e)

    # --- 2. Find all Report characteristics (0x2A4D) ---
    report_chars = []
    async for char in service.characteristics():
        if char.uuid == _UUID_REPORT:
            report_chars.append(char)

    input_reports = []
    for char in report_chars:
        # Each Report has a Report Reference descriptor (0x2908)
        try:
            desc = await char.descriptor(_UUID_REPORT_REF_DESC)
            ref_val = await desc.read()
            report_id = ref_val[0]
            report_type = ref_val[1]
            dprint(DEBUG_DBG, "Report Char handle=", char.uuid, 
                  "ReportID=", report_id, 
                  "Type=", report_type)

            if report_type == _REPORT_TYPE_INPUT:
                input_reports.append((char, report_id))

        except Exception as e:
            dprint(DEBUG_ERROR, "No Report Reference for char", char, e)

    # --- 3. Subscribe to Input Report notifications ---
    async def handle_input(char, report_id):
        #await char.subscribe(notify=True)
        dprint(DEBUG_DBG, "Subscribed to Input Report:", report_id)
        try:
            while True:
                data = await char.notified()
                dprint(DEBUG_DBG, f"[Input Report {report_id}] Data:", data.hex())
                if report_id == 1:
                    status = data[0]
                    x = data[1] | (data[2] << 8)
                    y = data[3] | (data[4] << 8)
                    w = data[5] | (data[6] << 8)
                    h = data[7] | (data[8] << 8) if len(data) >= 9 else None
                    dprint(DEBUG_DBG, "Status: {}, X: {}, Y: {}, W: {}, H: {}".format(status, x, y, w, h))

                    if _callback:
                        _callback(report_id, (status, x, y))
                elif report_id == 2:
                    CONSUMER_USAGE_MAP = {
                        1: "Volume Up",
                        2: "Volume Down",
                        3: "Mute",
                        4: "Scan Next Track",
                        5: "Scan Previous Track",
                        6: "AC Back",
                        7: "Play/Pause",
                        8: "Power",
                        9: "AC Home",
                        10: "Menu",
                        11: "Reserved",
                        12: "Reserved"
                    }
                    # 取出 16-bit 数值（小端序）
                    value = data[0] | (data[1] << 8)

                    # 映射到 usage 名称
                    dprint(DEBUG_DBG, CONSUMER_USAGE_MAP.get(value, f"Unknown Usage ({value})"))

                    if _callback:
                        _callback(report_id, value)
                else:
                    dprint(DEBUG_INFO, "Unsupport report id:", report_id)
        except Exception as e:
            dprint(DEBUG_ERROR, "Notification loop stopped:", e)

    # Start tasks for each input report
    for char, report_id in input_reports:
        await char.subscribe(notify=True)
        asyncio.create_task(handle_input(char, report_id))

    return connection


async def loop_task():
    while True:
        try:
            dev = await find_hid_device(TARGET_NAME)
            if not dev:
                dprint(DEBUG_INFO, "Retry scanning...")
                await asyncio.sleep(2)
                continue

            conn = await connect_and_discover(dev)

            # Keep running
            while conn.is_connected():
                await asyncio.sleep(1)
            dprint(DEBUG_INFO, "Disconnected, restarting scan...")

        except Exception as e:
            dprint(DEBUG_ERROR, "Main loop error:", e)

        # 确保断开连接，避免资源泄漏
        try:
            if conn and conn.is_connected():
                await conn.disconnect()
        except Exception as e:
            dprint(DEBUG_ERROR, "Disconnect error:", e)

        await asyncio.sleep(2)  # 延时后再扫描

def start(callback):
    global _callback
    _callback = callback
    asyncio.create_task(loop_task())

def stop():
    pass

if __name__ == "__main__":
    asyncio.run(loop_task())

import uasyncio as asyncio
from machine import Pin
import time
from utils.queue import EventQueue

# ---------------------------
# 按键管理器
# ---------------------------
class ButtonManager:
    def __init__(self, pins, debounce_ms=50, poll_ms=10, callback=None):
        self.buttons = {p: Pin(p, Pin.IN, Pin.PULL_UP) for p in pins}
        self.states = {p: self.buttons[p].value() for p in pins}
        self.last_change_time = {p: time.ticks_ms() for p in pins}
        self.debounce_ms = debounce_ms
        self.poll_ms = poll_ms
        self.event_queue = EventQueue()
        self.callback = callback   # 可选回调函数

    def set_callback(self, cb):
        """动态设置/替换回调函数"""
        self.callback = cb

    async def _poll_task(self):
        """后台轮询任务：检测多个按键并投递事件"""
        while True:
            now = time.ticks_ms()
            for pin_num, btn in self.buttons.items():
                current_state = btn.value()
                last_state = self.states[pin_num]

                if current_state != last_state:
                    if time.ticks_diff(now, self.last_change_time[pin_num]) > self.debounce_ms:
                        self.states[pin_num] = current_state
                        self.last_change_time[pin_num] = now
                        event = {
                            "pin": pin_num,
                            "state": "pressed" if current_state == 0 else "released",
                            "time": now
                        }
                        # --- 核心逻辑：两种处理方式 ---
                        if self.callback:
                            try:
                                self.callback(event)
                            except Exception as e:
                                print("Callback error:", e)
                        else:
                            self.event_queue.put(event)

            await asyncio.sleep_ms(self.poll_ms)

    def start(self):
        asyncio.create_task(self._poll_task())

    async def get_event(self):
        """阻塞等待事件"""
        return await self.event_queue.get()

    def get_event_nowait(self):
        """非阻塞取事件"""
        return self.event_queue.get_nowait()


# ---------------------------
# 示例：外部读取
# ---------------------------
async def example_polling():
    print("== Polling Example ==")
    btn_mgr = ButtonManager(pins=[5, 6])  # 改成你真实的引脚
    btn_mgr.start()

    while True:
        evt = await btn_mgr.get_event()
        print("polled:", evt)


# ---------------------------
# 示例：回调函数
# ---------------------------
def my_button_callback(evt):
    print("callback:", evt)


async def example_callback():
    print("== Callback Example ==")
    btn_mgr = ButtonManager(pins=[5, 6], callback=my_button_callback)
    btn_mgr.start()
    while True:
        await asyncio.sleep(1)  # 主循环里就不需要主动取事件了


# ---------------------------
# 入口
# ---------------------------
async def main():
    # 选一种运行
    await example_polling()
    # await example_callback()

if __name__ == "__main__":
    asyncio.run(main())

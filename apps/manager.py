import uasyncio as asyncio
from utils.queue import EventQueue
import time
import heapq

# ---------------------------
# 常量定义
# ---------------------------
class AppEventType:
    EventTimer = 100
    EventSys = 101
    EventInput = 102
    EventUsr = 103

class EventSysID:
    Quit = 0

class PopApp:
    _instances = {}
    def __new__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__new__(cls)
        return cls._instances[cls]

    def __init__(self):
        self.dirty = False
        self._entered = False
        self.is_background = False

    def on_enter(self): pass
    def on_pause(self): pass
    def on_resume(self): pass
    def on_event(self, evt): pass
    def on_input(self, key, status): pass
    def on_timer(self, timer_id): pass
    def on_exit(self): pass
    def render(self, dc): pass

    def update(self):
        self.dirty = True

    def set_timer(self, timer_id, interval, repeat=False):
        AppManager.instance().set_timer(self, timer_id, interval, repeat)

    def cancel_timer(self, timer_id):
        AppManager.instance().cancel_timer(self, timer_id)

# ---------------------------
# App 管理器（核心）
# ---------------------------
class AppManager:
    _inst = None

    @classmethod
    def instance(cls):
        if cls._inst is None:
            cls._inst = AppManager()
        return cls._inst

    def __init__(self):
        self.app_stack = []          # 前台 App 栈
        self.bg_apps = []            # 后台 App 列表
        self.remove_pending = []
        self.current_app = None
        self.queue = EventQueue()
        self.timers = {}
        self.heap = []
        self._running = False
        self.dc = None

    # ---------- App 管理 ----------
    def launch(self, app):
        if app in self.app_stack:
            self.app_stack.remove(app)
        self.app_stack.append(app)

    def kill(self, app):
        self.remove_pending.append(app)

    def exit_top(self):
        if self.app_stack:
            self.remove_pending.append(self.app_stack[-1])

    def set_dc(self, dc):
        self.dc = dc

    def get_dc(self):
        return self.dc

    def add_background(self, app):
        if app not in self.bg_apps:
            app.is_background = True
            self.bg_apps.append(app)

    def remove_background(self, app):
        if app in self.bg_apps:
            self.bg_apps.remove(app)

    def is_active(self, app):
        return app in self.app_stack or app in self.bg_apps

    def is_top(self, app):
        return bool(self.app_stack) and self.app_stack[-1] == app

    # ---------- 定时器 ----------
    def set_timer(self, owner, timer_id, interval, repeat=False):
        if not isinstance(owner, PopApp):
            raise ValueError("timer owner must be a PopApp instance")
        key = (owner, timer_id)
        expire_tick = time.ticks_add(time.ticks_ms(), interval)
        
        # 存储到字典
        self.timers[key] = (interval, repeat)
        # 添加到堆
        heapq.heappush(self.heap, (expire_tick, key))

    def cancel_timer(self, owner, timer_id):
        key = (owner, timer_id)
        if key in self.timers:
            del self.timers[key]

    def timer_expire_ms(self):
        if self.heap:
            return max(0, time.ticks_diff(self.heap[0][0], time.ticks_ms()))
        else:
            return None

    def timer_do_expires(self):
        now = time.ticks_ms()
        while self.heap and time.ticks_diff(self.heap[0][0], now) <= 0:
            expire_tick, key = heapq.heappop(self.heap)
            if key not in self.timers:
                continue
            
            owner, timer_id = key
            interval, repeat = self.timers[key]
            
            try:
                owner.on_timer(timer_id)
            except Exception as e:
                print(f"Timer error for {key}: {e}")
                repeat = 0 # delete if error
            
            if repeat != 0:  # -1 表示无限重复，>0 表示剩余次数
                if repeat > 0:
                    repeat -= 1
                
                # 重新调度
                new_expire = time.ticks_add(now, interval)
                self.timers[key] = (interval, repeat)
                heapq.heappush(self.heap, (new_expire, key))
            else:
                del self.timers[key]

    # ---------- 事件 ----------
    def send_user_event(self, receiver, evt):
        self.queue.put((AppEventType.EventUsr, receiver, evt))

    def send_input_event(self, key, status):
        self.queue.put((AppEventType.EventInput, None, (key, status)))

    def stop(self):
        self.queue.put_head((AppEventType.EventSys, None, EventSysID.Quit))

    # ---------- 主循环 ----------
    async def run(self, root_app):
        self._running = True

        self.app_stack = [root_app]
        root_app._entered = True
        root_app.on_enter()
        root_app.render(self.dc)

        print("[AppManager] running...")

        while self._running and self.app_stack:
            next_expire = self.timer_expire_ms()
            _evt_data = await self.queue.wait_for_ms(next_expire)
            top_app = self.app_stack[-1]
            if _evt_data is not None:
                evt_type, owner, evt_data = _evt_data
                # try:
                if evt_type == AppEventType.EventSys:
                    if evt_data == EventSysID.Quit:
                        break

                elif evt_type == AppEventType.EventTimer:
                    if self.is_active(owner):
                        owner.on_timer(evt_data)

                elif evt_type == AppEventType.EventUsr:
                    if self.is_active(owner):
                        owner.on_event(evt_data)

                elif evt_type == AppEventType.EventInput:
                    if self.app_stack:
                        key, status = evt_data
                        self.app_stack[-1].on_input(key, status)

                # except Exception as e:
                #     print("[AppManager] event dispatch error:", e)
            else:
                # 处理定时器
                self.timer_do_expires()

            # 处理退出 pending
            for app in list(self.remove_pending):
                if app in self.app_stack:
                    app.on_pause()
                    self.app_stack.remove(app)
                    try:
                        app.on_exit()
                    except Exception as e:
                        print("[AppManager] on_exit error:", e)
            self.remove_pending.clear()

            # 切换后 app 渲染
            next_app = self.app_stack[-1]
            if top_app != next_app:
                if self.is_active(top_app):
                    top_app.on_pause()
                #try:
                if not next_app._entered:
                    next_app._entered = True
                    next_app.on_enter()
                else:
                    next_app.on_resume()
                next_app.render(self.dc)
                #except Exception as e:
                #    print("[AppManager] on_enter/on_resume/render exception:", e)
            elif top_app.dirty: # 重新渲染
                top_app.dirty = False
                try:
                    top_app.render(self.dc)
                except Exception as e:
                    print("[AppManager] render exception:", e)

        print("[AppManager] exiting...")

        # 退出所有 app
        for app in reversed(self.app_stack):
            try:
                app.on_exit()
            except Exception as e:
                print("[AppManager] final exit error:", e)
        self.app_stack.clear()

        self._running = False


# ---------------------------
# 兼容旧接口
# ---------------------------
def launch(app): AppManager.instance().launch(app)
def kill(app): AppManager.instance().kill(app)
def exit_app(): AppManager.instance().exit_top()
def send_user_event(receiver, evt): AppManager.instance().send_user_event(receiver, evt)
def send_input_event(key, status): AppManager.instance().send_input_event(key, status)
def set_dc(dc): AppManager.instance().set_dc(dc)
def get_dc(): AppManager.instance().get_dc()
async def run(root_app): await AppManager.instance().run(root_app)
def stop(): AppManager.instance().stop()

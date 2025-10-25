import uasyncio as asyncio
from .Queue import EventQueue


class AppEventType:
    EventTimer = 100
    EventSys = 101
    EventInput = 102
    EventUsr = 103

class EventSysID:
    Quit = 0

# ---------------------------
# 基础 App 定义
# ---------------------------
class PopApp:
    _instances = {}
    def __new__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__new__(cls)
        return cls._instances[cls]

    def __init__(self):
        self.dirty = False
        self._entered = False

    def on_enter(self):
        pass

    def on_pause(self):
        pass

    def on_resume(self):
        pass

    def on_event(self, evt):
        pass

    def on_timer(self, timer_id):
        pass

    def on_exit(self):
        pass

    def render(self):
        pass

    def set_timer(self, timer_id, interval, repeat = False):
        set_timer(timer_id, interval, repeat, self)

    def cancel_timer(self, timer_id):
        cancel_timer(timer_id, self)

    def update(self):
        self.dirty = True


# ------------------ 定时器服务 ------------------
class TimerService:
    def __init__(self, tick_ms=10):
        self.tick_ms = tick_ms
        # timers: key -> [period_ticks, remain_ticks, repeat_bool, callback]
        self.timers = {}
        self.quit = False
        self._task = None

    def set_timer(self, timer_id, period_ms, repeat, callback):
        """添加定时器，period_ms 必须是 tick_ms 的倍数"""
        if period_ms % self.tick_ms != 0:
            raise ValueError("period_ms must be multiple of tick_ms")
        timer = [period_ms // self.tick_ms, period_ms // self.tick_ms, repeat, callback]
        self.timers[timer_id] = timer

    def remove_timer(self, timer_id):
        """删除定时器"""
        if timer_id in self.timers:
            del self.timers[timer_id]

    async def run(self):
        """后台调度任务"""
        try:
            while not self.quit:
                await asyncio.sleep_ms(self.tick_ms)
                # 遍历当前快照，允许在回调中修改 self.timers
                for timer_id in list(self.timers.keys()):
                    entry = self.timers.get(timer_id)
                    if entry is None:
                        continue
                    entry[1] -= 1
                    if entry[1] <= 0:
                        period, remain, repeat, callback = entry
                        # 如果重复，重装载；否则先删除再回调（避免回调再次触发时重复存在）
                        if repeat:
                            self.timers[timer_id][1] = period
                        else:
                            # 删除一次性定时器
                            try:
                                del self.timers[timer_id]
                            except KeyError:
                                pass
                        # 执行回调，保护异常
                        try:
                            callback()
                            # debug 打印放在正常路径
                            # print("Timer callback:", timer_id)
                        except Exception as e:
                            # 打印错误，但不自动删除定时器（避免因为回调错误丢失定时器）
                            print("[TimerService] callback error for", timer_id, ":", e)
        finally:
            # run 退出后保留状态为已停止
            self._task = None

    def start(self):
        """启动定时器"""
        if self._task is None:
            self.quit = False
            self._task = asyncio.create_task(self.run())

    async def stop(self):
        """停止定时器并等待 run 退出"""
        self.quit = True
        # 等待任务结束
        if self._task is not None:
            try:
                await self._task
            except Exception as e:
                # 捕获 run 中可能抛出的异常，防止顶层崩溃
                print("[TimerService] stop: run task ended with exception:", e)
            finally:
                self._task = None


# ---------- 全局函数与管理 ----------
def launch(app):
    global _app_list
    if _app_list and _app_list[-1] == app:
        return  # 已经是 top，不操作
    if app in _app_list:
        _app_list.remove(app)
    _app_list.append(app)

def kill(app):
    global _app_remove_pending_list
    _app_remove_pending_list.append(app)

# 注意：这个函数名会覆写内建 exit()，为了兼容你现有调用我保留它。
def exit():
    global _app_remove_pending_list
    global _current_app
    _app_remove_pending_list.append(_current_app)


def is_app_active(app):
    global _app_list
    return app in _app_list

def is_top_app(app):
    global _app_list
    return bool(_app_list) and app == _app_list[-1]

def _send_emergency_event(type, receiver, evt):
    global _evt_queue
    _evt_queue.put_head((type, receiver, evt))

def _send_event(type, receiver, evt):
    global _evt_queue
    _evt_queue.put((type, receiver, evt))

def send_user_event(receiver, evt):
    _send_event(AppEventType.EventUsr, receiver, evt)

def send_input_event(key, status):
    _send_event(AppEventType.EventInput, None, (key, status))

def _on_global_timer(owner, timer_id):
    _send_event(AppEventType.EventTimer, owner, timer_id)

def set_timer(timer_id, interval, repeat, owner):
    global _timer_svr
    # key 用 (owner, timer_id) 会比较直观，但保持你当前 key 排列 (owner, timer_id)
    _timer_svr.set_timer((owner, timer_id), interval, repeat, lambda: _on_global_timer(owner, timer_id))

def cancel_timer(timer_id, owner):
    global _timer_svr
    _timer_svr.remove_timer((owner, timer_id))


async def run(root_app):
    global _app_list, _evt_queue, _timer_svr, _app_remove_pending_list, _current_app

    # 初始化
    _app_list = [root_app]
    _app_remove_pending_list = []
    _evt_queue = EventQueue()

    # 启动定时器
    _timer_svr = TimerService()
    _timer_svr.start()

    print("[AppManager] app manager enter")
    root_app._entered = True
    root_app.on_enter()
    root_app.render()

    while len(_app_list) != 0:
        active_app = _app_list[-1]

        # 等待并处理事件
        evt = await _evt_queue.get()
        evt_type, event_owner, evt_data = evt

        # sys event handler: frame
        if evt_type == AppEventType.EventSys:
            if evt_data == EventSysID.Quit:
                break

        # timer handler: specified app
        elif evt_type == AppEventType.EventTimer:
            timer_id = evt_data
            # debug
            # print(f"[DEBUG] timer_owner: {event_owner}, timer_id: {timer_id}")
            if event_owner in _app_list:
                _current_app = event_owner
                try:
                    event_owner.on_timer(timer_id)
                except Exception as e:
                    print("[AppManager] on_timer exception:", e)
            else:
                print(f"[ERROR] timer_owner not in _app_list: {event_owner}")

        elif evt_type == AppEventType.EventUsr:
            # usr event handler: specified app
            if event_owner in _app_list:
                _current_app = event_owner
                try:
                    event_owner.on_event(evt_data)
                except Exception as e:
                    print("[AppManager] on_event (usr) exception:", e)
            else:
                print(f"[ERROR] msg_owner not in _app_list: {event_owner}")

        elif evt_type == AppEventType.EventInput:
            # input handler: current app
            if not _app_list:
                # 如果堆栈为空，丢弃输入
                continue
            _current_app = active_app
            try:
                active_app.on_event(evt_data)
            except Exception as e:
                print("[AppManager] on_event (input) exception:", e)

        else:
            print(f"[ERROR] unknown evt_type: {evt_type}")

        # 处理退出 pending
        for app in list(_app_remove_pending_list):
            if app in _app_list:
                if app == _app_list[-1]:
                    app.on_pause()
                _app_list.remove(app)
                _current_app = app
                try:
                    app.on_exit()
                except Exception as e:
                    print("[AppManager] on_exit exception:", e)
        _app_remove_pending_list.clear()

        # 如果已经没有 app，安全退出主循环
        if not _app_list:
            break

        # app 切换或重绘
        next_app = _app_list[-1]
        if active_app != next_app:
            if active_app in _app_list:
                active_app.on_pause()
            _current_app = next_app
            try:
                if not next_app._entered:
                    next_app._entered = True
                    next_app.on_enter()
                else:
                    next_app.on_resume()
                next_app.render()
            except Exception as e:
                print("[AppManager] on_enter/on_resume/render exception:", e)
        elif active_app.dirty: # 重新渲染
            _current_app = active_app
            active_app.dirty = False
            try:
                active_app.render()
            except Exception as e:
                print("[AppManager] render exception:", e)

    print("[AppManager] app manager exit")

    # 停止定时器（等待 run 结束）
    await _timer_svr.stop()

    # 退出所有 app
    for app in reversed(_app_list):
        try:
            app.on_exit()
        except Exception as e:
            print("[AppManager] final on_exit exception:", e)
    _app_list.clear()

def stop():
    _send_emergency_event(AppEventType.EventSys, None, EventSysID.Quit)



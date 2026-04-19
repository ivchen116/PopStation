from gui.core.geom import Rect
import time

# Globally available singleton objects
display = None  # Singleton instance

# Wrapper for global ssd object providing framebuf compatible methods.
class Display:
    def __init__(self, tftobj):
        global display
        self.tft = tftobj
        self.w = tftobj.width
        self.h = tftobj.height
        # 全局buffer
        self.buffer = bytearray(self.w * self.h * 2) # RGB565, 2byte

        display = self

    # 全屏幕填充
    def fill(self, color):
        self.tft.fill(color)

    # 获取单次刷写buffer
    def get_region_view(self, rect):

        size = rect.w * rect.h * 2 #RGB565

        return memoryview(self.buffer)[:size]

    # PUT
    def put_region_view(self):
        pass

    # 区域写DATA，底层可set_windows，再write数据
    # 最重要的接口，利用此接口实现区域刷新
    def blit_buffer(self, rect, buffer):
        self.tft.blit_buffer(buffer, rect.x, rect.y, rect.w, rect.h)


class Widget:
    def __init__(self, x=0, y=0, w=0, h=0, bgcolor=None):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.bgcolor = bgcolor
        self.visible = True

        self.parent = None
        self.children = []
        self.screen = None

    def add(self, child):
        child.parent = self
        child.screen = self.screen
        self.children.append(child)
        if self.screen:  # 如果已经在屏幕上
            child.on_add_to_screen(self.screen)
        self.invalidate()

    def on_add_to_screen(self, screen):
        self.screen = screen
        # 递归通知子控件
        for child in self.children:
            child.on_add_to_screen(screen)

    def add_list(self, w):
        for child in w:
            self.add(child)

    def is_visible(self):
        if not self.visible:
            return False

        if self.parent:
            return self.parent.is_visible()

        return True

    def set_visible(self, v):
        if v == self.visible:
            return
        self.visible = v
        self.invalidate()

    @property
    def rect(self):
        """返回局部坐标矩形"""
        return Rect(self.x, self.y, self.w, self.h)

    def global_rect(self):
        """返回屏幕绝对坐标矩形"""
        if self.parent:
            parent_rect = self.parent.global_rect()
            return Rect(
                parent_rect.x + self.x,
                parent_rect.y + self.y,
                self.w,
                self.h
            )
        elif self.screen:
            return Rect(self.x, self.y, self.w, self.h)
        else:
            return self.rect

    def invalidate(self):
        """标记整个控件区域为脏"""
        if self.screen:
            self.screen.invalid_rect(self.global_rect())

    def move(self, dx, dy):
        """
        相对移动控件
        :param dx: 水平偏移量
        :param dy: 垂直偏移量
        """
        if dx == 0 and dy == 0:
            return
        # 标记旧位置
        if self.screen:
            self.invalidate()
        self.x += dx
        self.y += dy
        # 标记新位置
        if self.screen:
            self.invalidate()

    def move_to(self, x, y):
        """
        绝对设置控件位置
        :param x: 新x坐标
        :param y: 新y坐标
        """
        self.move(x - self.x, y - self.y)

    def draw(self, draw_ctx):
        if not self.visible:
            return
        # 使用全局坐标绘制背景
        gr = self.global_rect()
        if self.bgcolor is not None:
            draw_ctx.fill_rect(gr.x, gr.y, gr.w, gr.h, self.bgcolor)

        # 调用子类实现的绘制逻辑（子类应使用全局坐标）
        self.on_draw(draw_ctx)

        # 绘制子控件前，压入父控件的裁剪区域
        #draw_ctx.push_clip(gr)

        # 绘制子控件
        for child in self.children:
            if child.visible:
                child.draw(draw_ctx)

        # 恢复裁剪区域
        #draw_ctx.pop_clip()

    # 子类可重写此方法实现自定义绘制
    def on_draw(self, draw_ctx):
        pass

from gui.core.draw import DrawContext

class Screen:
    # 借鉴 LVGL 的缓冲区大小限制
    INV_BUF_SIZE = 32  # 可根据内存调整

    def __init__(self, bgcolor = 0xFFFF):
        self.display = display
        self.w = display.w
        self.h = display.h

        self.root = Widget(0, 0, self.w, self.h)
        self.root.screen = self
        self.bgcolor = bgcolor

        self._dirty = []      # 脏区域列表
        self._full_refresh = False  # 全屏刷新标志

    def add(self, w):
        w.parent = self.root
        w.screen = self
        #print('Add child to root.')
        self.root.add(w)

    def add_list(self, w):
        for child in w:
            self.add(child)

    def invalid_rect(self, r):
        #print(f'Invalid rect:{r.x},{r.y},{r.w},{r.h}')
        """添加脏区域，自动去重及溢出保护"""
        # 确保区域在屏幕范围内
        r = r.intersect(Rect(0, 0, self.w, self.h))
        if not r:
            return

        # 如果已标记全屏刷新，则无需再添加
        if self._full_refresh:
            return

        # 检查是否已被现有区域完全包含
        for area in self._dirty:
            if area.contains(r):   # 假设 Rect 有 contains 方法
                return

        # 检查是否超过缓冲区大小
        if len(self._dirty) >= self.INV_BUF_SIZE:
            # 达到上限，转为全屏刷新
            self._full_refresh = True
            self._dirty.clear()
            return

        self._dirty.append(r)

    def invalidate(self):
        """强制全屏刷新"""
        self._full_refresh = True
        self._dirty.clear()

    def _areas_touch(self, a, b):
        """判断两个区域是否相邻或重叠（带5像素容差）"""
        # 水平方向是否接近
        horiz = (abs(a.x - b.x) <= 5 or 
                 abs((a.x + a.w) - (b.x + b.w)) <= 5 or
                 (a.x <= b.x + b.w and b.x <= a.x + a.w))  # 重叠
        # 垂直方向是否接近
        vert = (abs(a.y - b.y) <= 5 or 
                abs((a.y + a.h) - (b.y + b.h)) <= 5 or
                (a.y <= b.y + b.h and b.y <= a.y + a.h))
        return horiz and vert

    def _merge_rects(self, rects):
        """LVGL 风格的面积成本合并"""
        n = len(rects)
        if n <= 1:
            return rects

        joined = [False] * n   # 标记已被合并的区域
        result = []

        for i in range(n):
            if joined[i]:
                continue
            current = rects[i]

            for j in range(i + 1, n):
                if joined[j]:
                    continue
                other = rects[j]

                # 判断是否相邻或重叠
                if self._areas_touch(current, other):
                    # 计算合并后的矩形
                    merged = Rect(
                        min(current.x, other.x),
                        min(current.y, other.y),
                        max(current.x + current.w, other.x + other.w) - min(current.x, other.x),
                        max(current.y + current.h, other.y + other.h) - min(current.y, other.y)
                    )

                    # 计算面积成本
                    area_current = current.w * current.h
                    area_other = other.w * other.h
                    area_merged = merged.w * merged.h

                    if area_merged < area_current + area_other:
                        # 合并是划算的
                        current = merged
                        joined[j] = True

            result.append(current)

        return result

    def is_dirty(self):
        if not self._dirty and not self._full_refresh:
            return False
        return True

    def show(self):
        """刷新显示，包含合并优化"""
        if not self.is_dirty():
            return

        # 如果全屏刷新标志为真，使用整个屏幕作为脏区域
        if self._full_refresh:
            dirty_rects = [Rect(0, 0, self.w, self.h)]
            self._full_refresh = False
        else:
            # 合并脏区域
            dirty_rects = self._merge_rects(self._dirty)

        draw_ctx = DrawContext(self.display)

        for dirty_rect in dirty_rects:
            print(f'Show dirty rect:{dirty_rect.x},{dirty_rect.y},{dirty_rect.w},{dirty_rect.h}')
            draw_ctx.set_clip(dirty_rect)

            start_time = time.ticks_ms()

            # 0. 填充背景色(不使用root的file_rect，减少一次裁剪渲染)
            buf = draw_ctx.buf
            draw_ctx.fill(self.bgcolor)
            end_time = time.ticks_ms()
            print(f'fill cost:{end_time - start_time}ms')

            start_time = time.ticks_ms()
            # 1. 绘制子控件
            self.root.draw(draw_ctx)
            end_time = time.ticks_ms()
            print(f'draw cost:{end_time - start_time}ms')

            # 2. 显示到屏幕(阻塞)
            start_time = time.ticks_ms()
            self.display.blit_buffer(dirty_rect, buf)
            end_time = time.ticks_ms()
            print(f'blit_buffer cost:{end_time - start_time}ms')

        self._dirty.clear()

    def draw_background(self, draw_ctx):
        if self.bgcolor:
            draw_ctx.fill(self.bgcolor)
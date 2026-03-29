# draw.py

from gui.core.geom import Rect
import struct
import micropython

@micropython.viper
def fill_fast(buf, w:int, h:int, color:int):
    b = ptr8(buf)
    hi = color >> 8
    lo = color & 0xff

    stride = w * 2
    i = 0
    total = stride * h

    while i < total:
        b[i] = hi
        b[i+1] = lo
        i += 2

@micropython.viper
def blit_line(dst, dst_idx: int, src, src_idx: int, length: int):
    d = ptr8(dst)
    s = ptr8(src)

    for i in range(length):
        d[dst_idx + i] = s[src_idx + i]

@micropython.viper
def fill_rect_fast(buf, buf_w: int,
                   x: int, y: int,
                   w: int, h: int,
                   color: int):

    b = ptr8(buf)

    hi = color >> 8
    lo = color & 0xFF

    stride = buf_w * 2
    start = (y * buf_w + x) * 2

    for yy in range(h):
        idx = start + yy * stride
        end = idx + w * 2

        while idx < end:
            b[idx] = hi
            b[idx + 1] = lo
            idx += 2

class DrawContext:

    def __init__(self, display):
        self.disp = display
        self.clip = None

        self.buf = None
        self.w = 0
        self.h = 0
        
        self._clip_stack = []      # 裁剪区域栈，用于嵌套恢复

    def set_clip(self, rect):
        self.clip = rect
        self.buf = self.disp.get_region_view(rect)
        self.w = rect.w
        self.h = rect.h

    def get_clip(self):
        return self.clip

    def push_clip(self, rect):
        """压入新的裁剪区域（与当前裁剪区域取交集）"""
        self._clip_stack.append(self.clip)
        if self.clip and rect:
            new_clip = self.clip.intersect(rect)
        else:
            new_clip = rect or self.clip
        self.set_clip(new_clip)

    def pop_clip(self):
        """恢复上一个裁剪区域"""
        if self._clip_stack:
            self.set_clip(self._clip_stack.pop())

    def fill(self, color):
        fill_fast(self.buf, self.w, self.h, color)

    def pixel(self, x, y, color):
        """绘制单个像素"""
        if (x < self.clip.x or x >= self.clip.x + self.clip.w or
            y < self.clip.y or y >= self.clip.y + self.clip.h):
            return

        lx = x - self.clip.x
        ly = y - self.clip.y

        idx = (ly * self.w + lx) * 2
        self.buf[idx] = color >> 8
        self.buf[idx+1] = color & 0xff

    def rect(self, x, y, width, height, color):
        """绘制矩形边框"""
        # 上边
        self.hline(x, y, width, color)
        # 下边
        self.hline(x, y + height - 1, width, color)
        # 左边
        self.vline(x, y, height, color)
        # 右边
        self.vline(x + width - 1, y, height, color)

    def fill_rect(self, x, y, w, h, color):
        r = Rect(x, y, w, h)
        r = r.intersect(self.clip)
        if not r:
            return

        local_x = r.x - self.clip.x
        local_y = r.y - self.clip.y
        fill_rect_fast(self.buf, self.w, local_x, local_y, r.w, r.h, color)

    def fill_rect_normal(self, x, y, width, height, color):
        in_rect = Rect(x, y, width, height)
        draw_rect = in_rect.intersect(self.clip)
        if not draw_rect:
            return

        hi = color >> 8
        lo = color & 0xff

        buffer_x = draw_rect.x - self.clip.x
        buffer_y = draw_rect.y - self.clip.y

        row_bytes = draw_rect.w * 2

        row = bytearray(row_bytes)
        for i in range(0, row_bytes, 2):
            row[i] = hi
            row[i+1] = lo

        stride = self.w * 2

        for y_offset in range(draw_rect.h):
            start = ((buffer_y + y_offset) * self.w + buffer_x) * 2
            self.buf[start:start + row_bytes] = row

    def hline(self, x, y, length, color):
        self.fill_rect(x, y, length, 1, color)

    def vline(self, x, y, length, color):
        self.fill_rect(x, y, 1, length, color)

    def line(self, x0, y0, x1, y1, color):
        if x0 == x1:
            self.vline(x0, y0, y1 - y0, color)
        elif y0 == y1:
            self.hline(x0, y0, x1 - x0, color)
        else:
            self.line_bresenham(x0, y0, x1, y1, color)

    def line_bresenham(self, x0, y0, x1, y1, color):
        """绘制任意直线（Bresenham算法）"""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            if (x0 >= self.clip.x and x0 < self.clip.x + self.clip.w and
                y0 >= self.clip.y and y0 < self.clip.y + self.clip.h):
                self.pixel(x0, y0, color)
            
            if x0 == x1 and y0 == y1:
                break
                
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    # def fill_hline(self, x, y0, y1, data):
    #     blit_line()


    def draw_buffer(self, buffer, x, y, width, height):
        """绘制外部缓冲区（位图）"""
        bitmap_rect = Rect(x, y, width, height)
        draw_rect = bitmap_rect.intersect(self.clip)
        if not draw_rect:
            return
        
        src_x = draw_rect.x - x
        src_y = draw_rect.y - y
        copy_w = draw_rect.w
        copy_h = draw_rect.h
        
        dst_x = draw_rect.x - self.clip.x
        dst_y = draw_rect.y - self.clip.y
                
        for y_offset in range(copy_h):
            src_start = ((src_y + y_offset) * width + src_x) * 2
            #src_end = src_start + copy_w * 2
            dst_start = ((dst_y + y_offset) * self.w + dst_x) * 2
            
            #self.buf[dst_start:dst_start + copy_w * 2] = buffer[src_start:src_end]

            blit_line(self.buf, dst_start, buffer, src_start, copy_w * 2)

    def draw_glyph(self, font_module, ch, x, y, color):
        glyph_data, glyph_height, glyph_width = font_module.get_ch(ch)

        char_rect = Rect(x, y, glyph_width, glyph_height)
        draw_rect = char_rect.intersect(self.clip)
        if not draw_rect:
            return

        hi = color >> 8
        lo = color & 0xff

        src_x = draw_rect.x - x
        src_y = draw_rect.y - y
        copy_w = draw_rect.w
        copy_h = draw_rect.h

        dst_x = draw_rect.x - self.clip.x
        dst_y = draw_rect.y - self.clip.y

        row_bytes = (glyph_width + 7) // 8

        for row in range(copy_h):
            src_row = src_y + row
            row_start = src_row * row_bytes

            dst_idx = ((dst_y + row) * self.w + dst_x) * 2

            for col in range(copy_w):
                src_col = src_x + col
                byte_idx = row_start + (src_col // 8)
                bit_idx = 7 - (src_col % 8)

                if (glyph_data[byte_idx] >> bit_idx) & 1:
                    idx = dst_idx + col * 2
                    self.buf[idx] = hi
                    self.buf[idx+1] = lo

    def text(self, font_module, text, x, y, color):
        """
        绘制文本
        :param font_module: 字体模块（包含 get_ch 方法）
        :param text: 要绘制的字符串
        :param x, y: 起始坐标（屏幕绝对坐标）
        :param color: 颜色值
        """
        cursor_x = x
        
        for ch in text:
            # 获取字符数据（只为了获取宽度）
            _, _, char_width = font_module.get_ch(ch)
            
            # 绘制字符
            self.draw_glyph(font_module, ch, cursor_x, y, color)
            
            # 移动到下一个字符位置
            cursor_x += char_width
            
            # 如果超出裁剪区域，可以提前退出
            if cursor_x > self.clip.x + self.clip.w:
                break

    def text_with_spacing(self, font_module, text, x, y, color, spacing=1):
        """
        绘制文本（可设置字符间距）
        :param spacing: 字符之间的额外间距（像素）
        """
        cursor_x = x
        
        for ch in text:
            _, _, char_width = font_module.get_ch(ch)
            self.draw_glyph(font_module, ch, cursor_x, y, color)
            cursor_x += char_width + spacing
            
            if cursor_x > self.clip.x + self.clip.w:
                break

    def text_limited(self, font_module, text, x, y, color, max_width):
        """
        绘制文本（限制最大宽度）
        :param max_width: 最大允许的绘制宽度
        :return: 实际绘制的字符数
        """
        cursor_x = x
        count = 0
        
        for ch in text:
            _, _, char_width = font_module.get_ch(ch)
            
            if cursor_x + char_width > x + max_width:
                break
                
            self.draw_glyph(font_module, ch, cursor_x, y, color)
            cursor_x += char_width
            count += 1
            
            if cursor_x > self.clip.x + self.clip.w:
                break
        
        return count

    def get_text_width(self, font_module, text):
        """
        计算文本的总宽度
        :param font_module: 字体模块
        :param text: 文本字符串
        :return: 总宽度（像素）
        """
        total_width = 0
        for ch in text:
            _, _, char_width = font_module.get_ch(ch)
            total_width += char_width
        return total_width

    # 其他辅助方法...

    def fill_circle(self, center_x, center_y, radius, color):
        """填充圆形"""
        circle_rect = Rect(center_x - radius, center_y - radius, 
                          radius * 2 + 1, radius * 2 + 1)
        
        draw_rect = circle_rect.intersect(self.clip)
        if not draw_rect:
            return
        
        color_bytes = struct.pack('>H', color)
        
        for y in range(draw_rect.y, draw_rect.y + draw_rect.h):
            dy = y - center_y
            if abs(dy) > radius:
                continue
            
            dx = int((radius**2 - dy**2) ** 0.5)
            line_start_x = max(center_x - dx, draw_rect.x)
            line_end_x = min(center_x + dx, draw_rect.x + draw_rect.w - 1)
            
            if line_start_x <= line_end_x:
                buffer_y = y - self.clip.y
                buffer_start_x = line_start_x - self.clip.x
                buffer_end_x = line_end_x - self.clip.x
                
                start_idx = (buffer_y * self.w + buffer_start_x) * 2
                line_length = buffer_end_x - buffer_start_x + 1
                self.buf[start_idx:start_idx + line_length * 2] = color_bytes * line_length

    def fill_rounded_rect(self, x, y, width, height, radius, color):
        """填充圆角矩形"""
        self.fill_rect(x + radius, y, width - 2 * radius, height, color)
        self.fill_rect(x, y + radius, width, height - 2 * radius, color)
        
        if radius > 0:
            self._fill_corner(x + radius, y + radius, radius, 0, 0, color)
            self._fill_corner(x + width - radius - 1, y + radius, radius, 1, 0, color)
            self._fill_corner(x + radius, y + height - radius - 1, radius, 0, 1, color)
            self._fill_corner(x + width - radius - 1, y + height - radius - 1, radius, 1, 1, color)
    
    def _fill_corner(self, cx, cy, radius, quadrant_x, quadrant_y, color):
        """填充一个圆角象限"""
        color_bytes = struct.pack('>H', color)
        
        for dy in range(radius):
            for dx in range(radius):
                dist_sq = dx*dx + dy*dy
                if dist_sq <= radius*radius:
                    if quadrant_x == 0:
                        x = cx - dx
                    else:
                        x = cx + dx
                    
                    if quadrant_y == 0:
                        y = cy - dy
                    else:
                        y = cy + dy
                    
                    if (x >= self.clip.x and x < self.clip.x + self.clip.w and
                        y >= self.clip.y and y < self.clip.y + self.clip.h):
                        buffer_x = x - self.clip.x
                        buffer_y = y - self.clip.y
                        idx = (buffer_y * self.w + buffer_x) * 2
                        self.buf[idx:idx+2] = color_bytes

    # 在 DrawContext 类中添加以下方法
    def stroke_rect(self, x, y, width, height, color, line_width=1):
        """
        绘制矩形边框
        :param x, y: 左上角坐标（屏幕绝对坐标）
        :param width, height: 矩形尺寸
        :param color: 边框颜色（16位RGB565）
        :param line_width: 边框宽度（像素），默认为1
        """
        if line_width <= 0:
            return

        # 如果线宽为1，直接复用现有的 rect 方法（它使用 hline/vline）
        if line_width == 1:
            self.rect(x, y, width, height, color)
        else:
            # 线宽大于1时，通过绘制四个填充矩形条来实现
            # 上边框
            self.fill_rect(x, y, width, line_width, color)
            # 下边框
            self.fill_rect(x, y + height - line_width, width, line_width, color)
            # 左边框
            self.fill_rect(x, y + line_width, line_width, height - 2 * line_width, color)
            # 右边框
            self.fill_rect(x + width - line_width, y + line_width, line_width, height - 2 * line_width, color)


    def stroke_rounded_rect(self, x, y, width, height, radius, color, line_width=1):
        """
        绘制圆角矩形边框
        :param x, y: 左上角坐标（屏幕绝对坐标）
        :param width, height: 矩形尺寸
        :param radius: 圆角半径
        :param color: 边框颜色
        :param line_width: 边框宽度（像素），目前仅支持1（因圆角复杂，简化实现）
        """
        if line_width != 1:
            # 此处可扩展支持更宽边框，但为简化，若线宽不为1则降级为普通矩形边框
            self.stroke_rect(x, y, width, height, color, line_width)
            return

        # 先绘制四条直线（避开圆角区域）
        # 上边直线（从 x+radius 到 x+width-radius）
        if width > 2 * radius:
            self.hline(x + radius, y, width - 2 * radius, color)
        # 下边直线
        if width > 2 * radius:
            self.hline(x + radius, y + height - 1, width - 2 * radius, color)
        # 左边直线
        if height > 2 * radius:
            self.vline(x, y + radius, height - 2 * radius, color)
        # 右边直线
        if height > 2 * radius:
            self.vline(x + width - 1, y + radius, height - 2 * radius, color)

        # 绘制四个圆弧（每个圆弧为四分之一圆）
        # 左上角圆弧：圆心 (x+radius, y+radius)，半径 radius，角度范围 90°~180°
        self._draw_arc(x + radius, y + radius, radius, 90, 180, color)
        # 右上角圆弧：圆心 (x+width-radius-1, y+radius)，半径 radius，角度范围 0°~90°
        self._draw_arc(x + width - radius - 1, y + radius, radius, 0, 90, color)
        # 左下角圆弧：圆心 (x+radius, y+height-radius-1)，半径 radius，角度范围 180°~270°
        self._draw_arc(x + radius, y + height - radius - 1, radius, 180, 270, color)
        # 右下角圆弧：圆心 (x+width-radius-1, y+height-radius-1)，半径 radius，角度范围 270°~360°
        self._draw_arc(x + width - radius - 1, y + height - radius - 1, radius, 270, 360, color)


    def _draw_arc(self, cx, cy, radius, start_angle, end_angle, color):
        """
        绘制圆弧（仅支持90°整数倍起始和结束）
        :param cx, cy: 圆心坐标（屏幕绝对坐标）
        :param radius: 半径
        :param start_angle, end_angle: 起始和结束角度（度数，0°为右侧，逆时针）
        :param color: 颜色
        """
        # 使用中点圆算法，仅绘制指定角度范围内的点
        x = 0
        y = radius
        d = 1 - radius
        # 计算角度边界对应的 x/y 阈值
        # 根据象限和角度范围确定绘制条件
        while x <= y:
            # 8个对称点
            points = [
                (cx + x, cy - y),  # 1
                (cx + y, cy - x),  # 2
                (cx + y, cy + x),  # 3
                (cx + x, cy + y),  # 4
                (cx - x, cy + y),  # 5
                (cx - y, cy + x),  # 6
                (cx - y, cy - x),  # 7
                (cx - x, cy - y)   # 8
            ]
            for i, (px, py) in enumerate(points):
                # 根据象限判断角度范围（粗略，实际需要精确计算）
                angle = (i * 45) % 360
                # 简化：仅当角度在[start_angle, end_angle)内时绘制
                if start_angle <= angle < end_angle:
                    self.pixel(px, py, color)
            x += 1
            if d < 0:
                d += 2 * x + 1
            else:
                y -= 1
                d += 2 * (x - y) + 1


    def stroke_circle(self, cx, cy, radius, color, line_width=1):
        """
        绘制圆形边框
        :param cx, cy: 圆心坐标（屏幕绝对坐标）
        :param radius: 半径
        :param color: 边框颜色
        :param line_width: 边框宽度（像素），目前仅支持1（可通过绘制同心圆扩展）
        """
        if line_width != 1:
            # 对于更宽边框，可绘制多个同心圆，但为避免性能问题，暂只实现单像素
            # 此处仅绘制最外圈，然后内部填充（需背景色），为简化，先忽略宽度>1的情况
            # 简单处理：仍然绘制单像素边框
            pass

        # 使用中点圆算法绘制圆形轮廓
        x = 0
        y = radius
        d = 1 - radius
        while x <= y:
            # 绘制8个对称点
            self.pixel(cx + x, cy + y, color)
            self.pixel(cx - x, cy + y, color)
            self.pixel(cx + x, cy - y, color)
            self.pixel(cx - x, cy - y, color)
            self.pixel(cx + y, cy + x, color)
            self.pixel(cx - y, cy + x, color)
            self.pixel(cx + y, cy - x, color)
            self.pixel(cx - y, cy - x, color)

            x += 1
            if d < 0:
                d += 2 * x + 1
            else:
                y -= 1
                d += 2 * (x - y) + 1
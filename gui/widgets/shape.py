from gui.core.gui import Widget

class Line(Widget):
    def __init__(self, x1, y1, x2, y2, color, width=1):
        super().__init__(x1, y1, x2 - x1, y2 - y1)
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2

        self.color = color
        self.width = width

    def on_draw(self, draw_ctx):
        gr = self.global_rect()
        draw_ctx.line(gr.x, gr.y, gr.x + gr.w, gr.y + gr.h, self.color)

class Rectangle(Widget):
    """矩形控件，支持圆角、边框和背景色"""
    def __init__(self, x=0, y=0, w=0, h=0, bgcolor=None,
                 border_color=None, border_width=1, radius=0):
        """
        :param radius: 圆角半径，为0表示直角矩形
        """
        super().__init__(x, y, w, h)
        self.color = bgcolor
        self.border_color = border_color
        self.border_width = border_width
        self.radius = radius

    def on_draw(self, draw_ctx):
        # 获取全局坐标矩形
        gr = self.global_rect()

        # 绘制填充（背景）
        if self.color:
            if self.radius > 0:
                draw_ctx.fill_rounded_rect(gr, self.radius, self.color)
            else:
                draw_ctx.fill_rect(gr.x, gr.y, gr.w, gr.h, self.color)

        # 绘制边框
        if self.border_color:
            if self.radius > 0:
                draw_ctx.stroke_rounded_rect(gr, self.radius, self.border_color, self.border_width)
            else:
                draw_ctx.stroke_rect(gr, self.border_color, self.border_width)


class Circle(Widget):
    """圆形控件，支持边框和背景色"""
    def __init__(self, x=0, y=0, radius=0, bgcolor=None,
                 border_color=None, border_width=1):
        # 基类需要宽高，这里用半径*2填充
        w = 2 * radius
        h = 2 * radius
        super().__init__(x, y, w, h, bgcolor)
        self.radius = radius
        self.border_color = border_color
        self.border_width = border_width

    def on_draw(self, draw_ctx):
        # 获取全局矩形并计算圆心
        gr = self.global_rect()
        cx = gr.x + gr.w // 2
        cy = gr.y + gr.h // 2
        r = self.radius

        # 绘制填充
        if self.bgcolor:
            draw_ctx.fill_circle(cx, cy, r, self.bgcolor)

        # 绘制边框
        if self.border_color:
            draw_ctx.stroke_circle(cx, cy, r, self.border_color, self.border_width)
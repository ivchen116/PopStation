from gui.core.gui import Widget

class RectWidget(Widget):

    def __init__(self, x, y, w, h,
                 bgcolor=None,
                 border_color=None,
                 border_width=1):
        super().__init__(x, y, w, h)

        self.bgcolor = bgcolor
        self.border_color = border_color
        self.border_width = border_width

    def set_bgcolor(self, color):
        self.bgcolor = color
        self.invalidate()

    def draw(self, dc):
        # 绝对坐标
        gr = self.global_rect()
        x, y, w, h = gr.x, gr.y, gr.w, gr.h

        # ---- 填充 ----
        if self.bgcolor is not None:
            dc.fill_rect(x, y, w, h, self.bgcolor)

        # ---- 边框 ----
        if self.border_color is not None and self.border_width > 0:
            bw = self.border_width

            # 上
            dc.fill_rect(x, y, w, bw, self.border_color)
            # 下
            dc.fill_rect(x, y + h - bw, w, bw, self.border_color)
            # 左
            dc.fill_rect(x, y, bw, h, self.border_color)
            # 右
            dc.fill_rect(x + w - bw, y, bw, h, self.border_color)
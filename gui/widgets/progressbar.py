from gui.core.gui import Widget

class ProgressBar(Widget):
    def __init__(self, x, y, width, height, border_color=None, fill_color=0x07E0, empty_color=0x8410, value=0):
        """
        进度条控件
        :param x, y: 位置（局部坐标）
        :param width, height: 尺寸
        :param border_color: 边框颜色（RGB565），None 表示无边框
        :param fill_color: 进度填充颜色（默认绿色 0x07E0）
        :param empty_color: 未填充部分颜色（默认灰色 0x8410）
        :param value: 初始进度值（0-100）
        """
        super().__init__(x, y, width, height)
        self.border_color = border_color
        self.fill_color = fill_color
        self.empty_color = empty_color
        self._value = max(0, min(100, value))

    def set_value(self, value):
        """设置进度值（0-100）"""
        new_val = max(0, min(100, value))
        if new_val != self._value:
            self._value = new_val
            self.invalidate()  # 触发重绘

    def value(self):
        """获取当前进度值"""
        return self._value

    def on_draw(self, draw_ctx):
        # 获取屏幕绝对坐标
        gr = self.global_rect()
        x, y, w, h = gr.x, gr.y, gr.w, gr.h

        # 绘制边框
        if self.border_color is not None:
            draw_ctx.rect(x, y, w, h, self.border_color)

        # 绘制进度填充
        fill_width = int(w * self._value / 100)
        if fill_width > 0:
            draw_ctx.fill_rect(x, y, fill_width, h, self.fill_color)

        # 绘制背景（未完成部分）
        draw_ctx.fill_rect(x + fill_width, y, w - fill_width, h, self.empty_color)
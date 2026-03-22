from gui.core.gui import Widget

class Button(Widget):
    def __init__(self, x, y, w, h, text, font, text_color, bgcolor=None, border=None):
        super().__init__(x, y, w, h, bgcolor)
        self.text = text
        self.font = font
        self.text_color = text_color
        self.bgcolor = bgcolor
        self.border = border

    def on_draw(self, draw_ctx):
        # 获取全局坐标
        global_rect = self.global_rect()
        gx, gy, gw, gh = global_rect.x, global_rect.y, global_rect.w, global_rect.h

        # 绘制背景
        if self.bgcolor:
            print('draw btn background color')
            draw_ctx.fill_rect(gx, gy, gw, gh, self.bgcolor)

        # 绘制边框
        if self.border:
            print('draw btn border')
            draw_ctx.rect(gx, gy, gw, gh, self.border)

        # 绘制文本（居中）
        if self.text:
            print('draw btn text')
            # 计算文本总宽度
            text_width = 0
            for ch in self.text:
                _, _, char_width = self.font.get_ch(ch)   # 假设 get_ch 返回 (位图, 高度, 宽度)
                text_width += char_width

            # 计算居中位置
            text_x = gx + (gw - text_width) // 2
            text_y = gy + (gh - self.font.height()) // 2

            draw_ctx.text(self.font, self.text, text_x, text_y, self.text_color)
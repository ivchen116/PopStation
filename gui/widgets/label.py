from gui.core.gui import Widget

class Label(Widget):
    def __init__(self, x, y, text, font, color, align='left', valign='top'):
        self.text = text
        self.color = color
        self.font = font
        self.pos_x = x
        self.pos_y = y
        self.align = align
        self.valign = valign

        # 初始化尺寸
        self.h = font.height()           # 固定高度
        self._update_size()               # 计算初始宽度
        self._update_locate()

        super().__init__(self.x, self.y, self.w, self.h)

    def move_to(self, x, y):
        dx = x - self.pos_x
        dy = y - self.pos_y
        self.pos_x = x
        self.pos_y = y
        self._update_locate()
        return super().move(dx, dy)

    def move(self, dx, dy):
        return self.move_to(self.pos_x + dx, self.pos_y + dy)

    def _update_locate(self):
        # 水平坐标
        if self.align == 'left':
            self.x = self.pos_x
        elif self.align == 'center':
            self.x = self.pos_x - (self.w // 2)
        else:  # right
            self.x = self.pos_x - self.w
        # 垂直坐标
        if self.valign == 'top':
            self.y = self.pos_y
        elif self.valign == 'middle':
            self.y = self.pos_y - (self.h // 2)
        else:  # bottom
            self.y = self.pos_y - self.h

    def _update_size(self):
        """根据当前文本重新计算宽度"""
        self.w = 0
        for ch in self.text:
            _, _, char_width = self.font.get_ch(ch)
            self.w += char_width

    def set_text(self, new_text):
        """
        更新文本内容，并自动刷新显示
        """
        print(f"set_text:{new_text}")
        if self.text == new_text:
            return

        print(f"self.screen:{self.screen}")
        # 1. 标记旧区域为脏
        if self.screen:
            self.screen.invalid_rect(self.global_rect())

        # 2. 更新文本并重新计算宽度
        self.text = new_text
        old_w = self.w
        self._update_size()
        self._update_locate()

        # 3. 如果宽度变化，标记新区域为脏
        if self.screen and self.w != old_w:
            self.screen.invalid_rect(self.global_rect())
        # 注意：如果宽度未变，仅文本内容变化，旧区域的重绘已足够

    def on_draw(self, draw_ctx):
        # 使用全局坐标绘制文本
        global_rect = self.global_rect()
        draw_ctx.text(self.font, self.text, global_rect.x, global_rect.y, self.color)
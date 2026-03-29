from gui.core.gui import Widget
from gui.core.geom import Rect

class Label(Widget):
    def __init__(self, x, y, text, font, color, bgcolor = None, w = 0, h = 0, align='left', valign='top'):
        self.text = text
        self.color = color
        self.font = font
        self.align = align
        self.valign = valign
        self._text_pos_dirty = True
        self.text_h = font.height()
        self._update_size()
        if w == 0:
            w = self.text_w
        if h == 0:
            h = self.text_h

        super().__init__(x, y, w, h, bgcolor=bgcolor)
        self._update_offset()

    def _update_size(self):
        """根据当前文本重新计算宽度"""
        self.text_w = 0
        for ch in self.text:
            _, _, char_width = self.font.get_ch(ch)
            self.text_w += char_width

    def _update_offset(self):
        # ===== 水平 =====
        if self.align == 'left':
            self.offset_x = 0
        elif self.align == 'center':
            self.offset_x = (self.w - self.text_w) // 2
        else:  # right
            self.offset_x = self.w - self.text_w

        # ===== 垂直 =====
        if self.valign == 'top':
            self.offset_y = 0
        elif self.valign == 'middle':
            self.offset_y = (self.h - self.text_h) // 2
        else:  # bottom
            self.offset_y = self.h - self.text_h

    def _text_rect(self):
        label_rect = self.global_rect()

        return Rect(label_rect.x + self.offset_x, label_rect.y + self.offset_y, self.text_w, self.text_h)

    def set_text(self, new_text):
        """
        更新文本内容，并自动刷新显示
        """
        if self.text == new_text:
            return

        # 标记旧区域为脏
        old_rect = self._text_rect()

        # 更新文本内容
        old_len = self.text_w
        self.text = new_text
        self._update_size()
        self._update_offset()

        # 标记新区域为脏
        print(f"set_text:{new_text}")
        print(f"self.screen:{self.screen}")
        if self.screen:
            if old_len < self.text_w:
                self.screen.invalid_rect(self._text_rect())
                print(f"invalid new rect:{self._text_rect()}")
            else:
                self.screen.invalid_rect(old_rect)
                print(f"invalid old rect:{old_rect}")

    def set_align(self, align, valign):
        self.align = align
        self.valign = valign
        self._update_offset()

    def on_draw(self, draw_ctx):
        # 使用全局坐标绘制文本
        global_rect = self.global_rect()

        tx = global_rect.x + self.offset_x
        ty = global_rect.y + self.offset_y

        draw_ctx.text(self.font, self.text, tx, ty, self.color)
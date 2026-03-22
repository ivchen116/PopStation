from gui.core.gui import Widget

class ImageWidget(Widget):

    def __init__(self, x, y, filepath):
        self.x = x
        self.y = y
        self.filepath = filepath

        self.w = 0
        self.h = 0

        self._load_header()
        super().__init__(self.x, self.y, self.w, self.h)

    def _load_header(self):
        with open(self.filepath, "rb") as f:
            header = f.read(4)
            self.w = (header[1] << 8) | header[0]
            self.h = (header[3] << 8) | header[2]

    def draw(self, ctx):
        with open(self.filepath, "rb") as f:
            # skip header
            f.seek(4, 0)
            data = f.read()
            ctx.draw_buffer(data, self.x, self.y, self.w, self.h)
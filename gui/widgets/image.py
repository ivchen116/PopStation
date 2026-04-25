from gui.core.gui import Widget


IMAGE_TYPE_RAW = 0
IMAGE_TYPE_PNG = 1
IMAGE_TYPE_UNKNOWN = 0xFF


class ImageWidget(Widget):
    def __init__(self, x, y, filepath, cache=True, bgcolor = None):
        self.x = x
        self.y = y
        self.filepath = filepath
        self.cache = cache

        self.w = 0
        self.h = 0
        self.type = IMAGE_TYPE_UNKNOWN
        self.data_offset = 0
        self.png_alpha_color = 0
        self._data = None

        self._load_header()
        super().__init__(self.x, self.y, self.w, self.h)

        if self.cache and self.type != IMAGE_TYPE_UNKNOWN:
            self._ensure_data_loaded()

        if self.type == IMAGE_TYPE_PNG and bgcolor is not None:
            self.bgcolor = bgcolor

    def _load_header(self):
        try:
            with open(self.filepath, "rb") as f:
                header = f.read(8)
                if len(header) < 6:
                    raise ValueError("Invalid image header")

                type_magic = (header[1] << 8) | header[0]
                if type_magic == 0x8802:
                    if len(header) < 8:
                        raise ValueError("Invalid PNG image header")
                    self.type = IMAGE_TYPE_PNG
                    self.data_offset = 8
                    self.png_alpha_color = (header[6] << 8) | header[7]
                elif type_magic == 0x8801:
                    self.type = IMAGE_TYPE_RAW
                    self.data_offset = 6
                else:
                    raise ValueError("Unsupported image type")

                self.w = (header[3] << 8) | header[2]
                self.h = (header[5] << 8) | header[4]
        except Exception as e:
            print(f"Error loading image header: {e}")
            self.type = IMAGE_TYPE_UNKNOWN
            self.w = 0
            self.h = 0

    def _read_data(self):
        with open(self.filepath, "rb") as f:
            f.seek(self.data_offset, 0)
            return f.read()

    def _ensure_data_loaded(self):
        if self._data is None and self.type != IMAGE_TYPE_UNKNOWN:
            try:
                self._data = self._read_data()
            except Exception as e:
                print(f"Error loading image data: {e}")
                self.type = IMAGE_TYPE_UNKNOWN

    def release(self):
        self._data = None

    def draw(self, ctx):
        if self.type == IMAGE_TYPE_UNKNOWN:
            return

        data = self._data
        if data is None:
            try:
                data = self._read_data()
            except Exception as e:
                print(f"Error drawing image: {e}")
                return

        gr = self.global_rect()
        if self.type == IMAGE_TYPE_PNG:
            ctx.draw_buffer_skip_color(data, gr.x, gr.y, self.w, self.h, self.png_alpha_color)
        elif self.type == IMAGE_TYPE_RAW:
            ctx.draw_buffer(data, gr.x, gr.y, self.w, self.h)

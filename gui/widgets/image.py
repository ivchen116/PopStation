from gui.core.gui import Widget

IMAGE_TYPE_RAW = 0
IMAGE_TYPE_PNG = 1
IMAGE_TYPE_UNKNOWN = 0xFF

class ImageWidget(Widget):

    def __init__(self, x, y, filepath):
        self.x = x
        self.y = y
        self.filepath = filepath

        self.w = 0
        self.h = 0
        self.type = IMAGE_TYPE_UNKNOWN
        self.data_offset = 0

        self._load_header()
        super().__init__(self.x, self.y, self.w, self.h)

    def _load_header(self):
        try:
            with open(self.filepath, "rb") as f:
                header = f.read(8)

                type_magic = (header[1] << 8) | header[0]
                if type_magic == 0x8802:
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

                #print(f"w: {self.w}, h: {self.h}, type: {self.type}")
        except Exception as e:
            print(f"Error loading image: {e}")

    def draw(self, ctx):
        if self.type == IMAGE_TYPE_UNKNOWN:
            return
        
        with open(self.filepath, "rb") as f:
            # skip header
            f.seek(self.data_offset, 0)
            data = f.read()
            if self.type == IMAGE_TYPE_PNG:
                ctx.draw_buffer_skip_color(data, self.x, self.y, self.w, self.h, self.png_alpha_color)
            elif self.type == IMAGE_TYPE_RAW:
                ctx.draw_buffer(data, self.x, self.y, self.w, self.h)


# class PngImageWidget(Widget):

#     def __init__(self, x, y, filepath):
#         self.x = x
#         self.y = y
#         self.filepath = filepath

#         self.w = 0
#         self.h = 0
#         self.alpha_color = None

#         self._load_header()
#         super().__init__(self.x, self.y, self.w, self.h)

#     def _load_header(self):
#         with open(self.filepath, "rb") as f:
#             header = f.read(6)
#             self.w = (header[1] << 8) | header[0]
#             self.h = (header[3] << 8) | header[2]
#             self.alpha_color = (header[4] << 8) | header[5]
#             print(f"w: {self.w}, h: {self.h}, alpha_color: {self.alpha_color}")

#     def draw(self, ctx):
#         with open(self.filepath, "rb") as f:
#             # skip header
#             f.seek(6, 0)
#             data = f.read()
#             ctx.draw_buffer_skip_color(data, self.x, self.y, self.w, self.h, self.alpha_color)

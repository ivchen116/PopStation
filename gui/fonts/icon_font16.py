# Auto generated icon font (PNG input)
version = 'icon-0.1'

def height(): return 16
def max_width(): return 16
def hmap(): return True
def reverse(): return False
def monospaced(): return False
def min_ch(): return 127
def max_ch(): return 131

_font = \
b'\x10\x00\x00\x00\x00\x00\x1f\xfc\x1f\xfc\x10\x84\x00\x84\x10\x84'\
b'\x7c\x84\x7c\x84\x10\x84\x00\x84\x10\x84\x1f\xfc\x1f\xfc\x00\x00'\
b'\x00\x00\x10\x00\x00\x00\x00\x00\x3f\xf8\x3f\xf8\x21\x08\x21\x00'\
b'\x21\x08\x21\x3e\x21\x3e\x21\x08\x21\x00\x21\x08\x3f\xf8\x3f\xf8'\
b'\x00\x00\x00\x00\x10\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10'\
b'\x00\x38\x00\x70\x08\xe0\x1d\xc0\x0f\x80\x07\x00\x02\x00\x00\x00'\
b'\x00\x00\x00\x00\x00\x00\x10\x00\x00\x00\x00\x00\x00\x00\x00\x00'\
b'\x3f\xfc\x3f\xfc\x00\x00\x3f\xfc\x3f\xfc\x00\x00\x3f\xfc\x3f\xfc'\
b'\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x00\x00\x00\x00\x00'\
b'\x03\xd8\x0f\xf8\x0c\x38\x18\x78\x18\x00\x18\x18\x18\x18\x0c\x30'\
b'\x0f\xf0\x03\xc0\x00\x00\x00\x00\x00\x00'\


_index = \
b'\x00\x00\x22\x00\x44\x00\x66\x00\x88\x00'\



_mvfont = memoryview(_font)

def _chr_addr(ordch):
    offset = 2 * (ordch - min_ch())
    return int.from_bytes(_index[offset:offset + 2], 'little')

def get_ch(ch):
    ordch = ord(ch)
    if ordch < min_ch() or ordch > max_ch():
        print("Invalid character: {}".format(ch))
        return b'', 0, 0
    print("display icon char: {}".format(ch))
    offset = _chr_addr(ordch)
    width = int.from_bytes(_font[offset:offset + 2], 'little')
    next_offs = len(_font) if ordch == max_ch() else _chr_addr(ordch + 1)
    print(f"data: {_mvfont[offset + 2:next_offs]}, height: {height()}, width: {width}")
    return _mvfont[offset + 2:next_offs], height(), width
# Icon constants
ADD_COLUMN_LEFT = chr(127)
ADD_COLUMN_RIGHT = chr(128)
CHECK = chr(129)
MENU = chr(130)
REFRESH = chr(131)

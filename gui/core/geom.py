# geom.py

class Rect:
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def intersects(self, other):
        # 检查两个矩形是否相交
        return not (self.x + self.w <= other.x or
                   other.x + other.w <= self.x or
                   self.y + self.h <= other.y or
                   other.y + other.h <= self.y)

    def intersect(self, r):
        x1 = max(self.x, r.x)
        y1 = max(self.y, r.y)
        x2 = min(self.x + self.w, r.x + r.w)
        y2 = min(self.y + self.h, r.y + r.h)

        if x2 <= x1 or y2 <= y1:
            return None

        return Rect(x1, y1, x2 - x1, y2 - y1)
    
    def contains(self, other):
        return (self.x <= other.x and
                self.y <= other.y and
                self.x + self.w >= other.x + other.w and
                self.y + self.h >= other.y + other.h)
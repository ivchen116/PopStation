import uasyncio as asyncio

# ------------------ 基于 asyncio.Event 的异步队列 ------------------
class EventQueue:
    def __init__(self):
        self.items = []
        self.event = asyncio.Event()

    def put(self, item):
        self.items.append(item)
        self.event.set()

    def put_head(self, item):
        self.items.insert(0, item)
        self.event.set()

    async def get(self):
        while not self.items:
            self.event.clear()
            await self.event.wait()
        item = self.items.pop(0)
        return item

    async def wait_for_ms(self, ms = None):
        if ms is None or self.items:
            return await self.get()
        else:
            try:
                self.event.clear()
                await asyncio.wait_for_ms(self.event.wait(), ms)
                item = self.items.pop(0)
                return item
            except asyncio.TimeoutError:
                return None

    def empty(self):
        return len(self.items) == 0
    
    def get_nowait(self):
        if self.items:
            item = self.items.pop(0)
            if not self.items:
                self.event.clear()
            return item
        return None
    
    def clear(self):
        self.items.clear()
        self.event.clear()

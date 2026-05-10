class FileWavSource:
    def __init__(self, filepath, offset_bytes=0):
        self.filepath = filepath
        self.offset_bytes = offset_bytes if offset_bytes and offset_bytes > 0 else 0
        self.f = None

    async def open(self):
        print("[DEBUG] Open file: {}".format(self.filepath))
        self.f = open(self.filepath, "rb")

    async def seek_data_offset(self, data_start, offset_bytes):
        if self.f is None:
            return
        if offset_bytes and offset_bytes > 0:
            self.f.seek(data_start + offset_bytes, 0)

    async def readinto(self, mv):
        return self.f.readinto(mv)

    async def close(self):
        if self.f is not None:
            self.f.close()
            self.f = None

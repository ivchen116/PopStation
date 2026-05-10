import uasyncio as asyncio


class HttpWavSource:
    def __init__(self, url, timeout_connect_ms=3000, timeout_send_ms=2000):
        self.url = url
        self.timeout_connect_ms = timeout_connect_ms
        self.timeout_send_ms = timeout_send_ms
        self.reader = None
        self.writer = None
        self._leftover = b""

    def _parse_http_url(self):
        if not self.url.startswith("http://"):
            raise ValueError("only http:// is supported")
        rest = self.url[7:]
        slash = rest.find("/")
        hostport = rest if slash < 0 else rest[:slash]
        path = "/" if slash < 0 else rest[slash:]
        if ":" in hostport:
            host, port_s = hostport.split(":", 1)
            port = int(port_s)
        else:
            host, port = hostport, 80
        return host, port, path

    async def open(self):
        host, port, path = self._parse_http_url()
        try:
            self.reader, self.writer = await asyncio.wait_for_ms(asyncio.open_connection(host, port), self.timeout_connect_ms)
        except asyncio.TimeoutError:
            raise OSError("connect timeout")

        host_hdr = host if port == 80 else "{}:{}".format(host, port)
        req = "GET {} HTTP/1.0\r\nHost: {}\r\nConnection: close\r\n\r\n".format(path, host_hdr)
        self.writer.write(req.encode())
        try:
            await asyncio.wait_for_ms(self.writer.drain(), self.timeout_send_ms)
        except asyncio.TimeoutError:
            raise OSError("send timeout")

        headers, rest = await self._read_http_headers(self.reader)
        status = headers.split(b"\r\n", 1)[0]
        if b"200" not in status:
            raise ValueError("http status not 200")
        self._leftover = rest

    async def _read_http_headers(self, reader):
        buf = b""
        while True:
            chunk = await reader.read(256)
            if not chunk:
                break
            buf += chunk
            p = buf.find(b"\r\n\r\n")
            if p >= 0:
                return buf[: p + 4], buf[p + 4 :]
            if len(buf) > 4096:
                raise ValueError("http header too large")
        raise ValueError("http header incomplete")

    async def readinto(self, mv):
        if self._leftover:
            n = min(len(self._leftover), len(mv))
            mv[:n] = self._leftover[:n]
            self._leftover = self._leftover[n:]
            return n
        return await self.reader.readinto(mv)

    async def close(self):
        if self.writer is not None:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
        self.reader = None
        self.writer = None
        self._leftover = b""


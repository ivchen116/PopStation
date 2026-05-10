from config import config
import uasyncio as asyncio

class WifiService:
    def __init__(self):
        self._clients = set()
        self._subs = set()
        self._connected = False
        self._connecting = False
        self._idle_task = None

    # ---------- subscribe ----------
    def subscribe(self, cb):
        if cb:
            self._subs.add(cb)
            cb(self._state_evt())

    def unsubscribe(self, cb):
        self._subs.discard(cb)

    def _notify(self, evt):
        for cb in list(self._subs):
            try:
                cb(evt)
            except:
                pass

    def _state_evt(self):
        return {
            "event": "connected" if self._connected else "disconnected",
            "ok": self._connected,
            "msg": "WiFi OK" if self._connected else "WiFi OFF"
        }

    # ---------- API ----------
    async def acquire(self, client):
        self._clients.add(client)

        if self._idle_task:
            self._idle_task.cancel()
            self._idle_task = None

        if self._connected:
            return True, "WiFi OK"

        return await self._connect()

    def release(self, client):
        self._clients.discard(client)
        if not self._clients:
            self._start_idle()

    async def force_off(self):
        await self._disconnect()

    # ---------- internal ----------
    async def _connect(self):
        if self._connecting:
            while self._connecting:
                await asyncio.sleep_ms(100)
            return self._connected, "WiFi OK" if self._connected else "fail"

        self._connecting = True
        self._notify({"event": "connecting", "ok": True, "msg": "WiFi connecting"})

        try:
            import network
            wlan = network.WLAN(network.STA_IF)
            wlan.active(True)

            if wlan.isconnected():
                self._connected = True
                self._notify(self._state_evt())
                return True, "WiFi OK"

            ssid = config.get("wifi_ssid")
            pwd = config.get("wifi_password")

            wlan.connect(ssid, pwd)

            for _ in range(80):
                if wlan.isconnected():
                    self._connected = True
                    self._notify(self._state_evt())
                    return True, "WiFi OK"
                await asyncio.sleep_ms(100)

            self._notify({"event": "connected", "ok": False, "msg": "timeout"})
            return False, "timeout"

        finally:
            self._connecting = False

    def _start_idle(self):
        timeout = config.get("wifi_idle_timeout") or 30

        async def _idle():
            await asyncio.sleep(timeout)
            if not self._clients:
                await self._disconnect()

        self._idle_task = asyncio.create_task(_idle())

    async def _disconnect(self):
        try:
            import network
            wlan = network.WLAN(network.STA_IF)
            wlan.disconnect()
            wlan.active(False)
        except:
            pass

        self._connected = False
        self._notify(self._state_evt())


wifi_service = WifiService()
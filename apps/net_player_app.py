from config import config
from app_context import get_audio
from gui.core.colors import GRAY, WHITE, YELLOW
from gui.core.gui import Screen
from gui.fonts import freesans20
from gui.widgets.label import Label
from input_keys import (
    BLE_KEY_ENTER,
    BLE_KEY_LEFT,
    BLE_KEY_MENU,
    BLE_KEY_RIGHT,
    GPIO_KEY_ENTER,
    GPIO_KEY_MENU,
    GPIO_KEY_NEXT,
    GPIO_KEY_PREV,
    KEY_S_PRESSED,
)
from manager import PopApp, exit_app, send_user_event
from utils.trace import DEBUG_DBG, DEBUG_INFO, dprint
from wifi_services import wifi_service


NET_PLAYER_DEF = {
    "name": "NetRadio",
    # Reuse icon for now. If you provide a netradio.png565 we can swap.
    "menu_icon_image": "res/images/radar.png565",
}


# -------- Background Worker (async, event-driven) --------
class _NetWorker:
    EVT_WIFI = "wifi"
    EVT_PLAYLIST = "playlist"

    def __init__(self):
        self._busy = False

    def request(self, receiver, playlist_url):
        # Never block PopApp handlers; do work in background and post results
        dprint(DEBUG_INFO, "NetWorker request", playlist_url)
        if self._busy:
            send_user_event(receiver, {"type": self.EVT_WIFI, "ok": False, "msg": "busy"})
            return

        self._busy = True

        import uasyncio as asyncio

        async def _run():
            try:
                dprint(DEBUG_INFO, "NetWorker start")
                ok, msg = await wifi_service.acquire("net_player")
                dprint(DEBUG_INFO, "NetWorker wifi", ok, msg)
                send_user_event(receiver, {"type": self.EVT_WIFI, "action": "on", "ok": ok, "msg": msg})
                if not ok:
                    return

                if not playlist_url:
                    send_user_event(receiver, {"type": self.EVT_PLAYLIST, "ok": True, "urls": [], "names": []})
                    return

                text = await self._http_get_text(playlist_url)
                dprint(DEBUG_INFO, "NetWorker playlist bytes", len(text) if text else 0)
                if playlist_url.endswith(".m3u") or playlist_url.endswith(".m3u8"):
                    urls = self.normalize_urls(self._parse_m3u(text), playlist_url)
                    names = [""] * len(urls)
                else:
                    urls, names = self._parse_playlist_json(text)
                    urls = self.normalize_urls(urls, playlist_url)
                dprint(DEBUG_INFO, "NetWorker playlist parsed", len(urls))

                send_user_event(receiver, {"type": self.EVT_PLAYLIST, "ok": True, "urls": urls, "names": names})
            except Exception as e:
                send_user_event(receiver, {"type": self.EVT_PLAYLIST, "ok": False, "msg": str(e)})
            finally:
                self._busy = False

        asyncio.create_task(_run())

    def _parse_m3u(self, text):
        urls = []
        for raw in (text or "").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("http://") or line.startswith("https://"):
                urls.append(line)
        return urls

    def _parse_playlist_json(self, text):
        try:
            import ujson as json  # type: ignore
        except Exception:
            import json  # type: ignore

        data = json.loads(text or "[]")
        urls = []
        names = []
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                u = item.get("wav_url") or item.get("url")
                if isinstance(u, str) and u.startswith("http"):
                    urls.append(u)
                    names.append(item.get("name") or "")
        return urls, names

    async def _http_get_text(self, url):
        import uasyncio as asyncio

        if not url.startswith("http://"):
            raise ValueError("only http:// is supported")
        rest = url[7:]
        slash = rest.find("/")
        hostport = rest if slash < 0 else rest[:slash]
        path = "/" if slash < 0 else rest[slash:]
        if ":" in hostport:
            host, port_s = hostport.split(":", 1)
            port = int(port_s)
        else:
            host, port = hostport, 80

        dprint(DEBUG_INFO, "HTTP GET", host, port, path)

        # Some ports may block during connect; enforce a hard timeout.
        try:
            reader, writer = await asyncio.wait_for_ms(asyncio.open_connection(host, port), 3000)
        except asyncio.TimeoutError:
            raise ValueError("connect timeout")

        host_hdr = host if port == 80 else "{}:{}".format(host, port)
        req = "GET {} HTTP/1.0\r\nHost: {}\r\nConnection: close\r\n\r\n".format(path, host_hdr)
        writer.write(req.encode())
        try:
            await asyncio.wait_for_ms(writer.drain(), 2000)
        except asyncio.TimeoutError:
            raise ValueError("send timeout")

        # Read headers (with timeout) and parse content-length if present.
        buf = b""
        head = None
        data = b""
        for _ in range(200):  # ~10s worst case (50ms step)
            try:
                b = await asyncio.wait_for_ms(reader.read(256), 50)
            except asyncio.TimeoutError:
                continue
            if not b:
                break
            buf += b
            p = buf.find(b"\r\n\r\n")
            if p >= 0:
                head = buf[: p + 4]
                data = buf[p + 4 :]
                break
            if len(buf) > 4096:
                raise ValueError("http header too large")

        if head is None:
            raise ValueError("http header timeout")

        dprint(DEBUG_INFO, "HTTP header ok", len(head), "body_pre", len(data))

        status = head.split(b"\r\n", 1)[0]
        if b"200" not in status:
            raise ValueError("http status not 200")

        content_length = None
        try:
            for line in head.split(b"\r\n"):
                if line.lower().startswith(b"content-length:"):
                    content_length = int(line.split(b":", 1)[1].strip())
                    break
        except Exception:
            content_length = None

        # Read body: prefer content-length if available, otherwise read until close
        if content_length is not None:
            remaining = content_length - len(data)
            while remaining > 0:
                b = await reader.read(min(1024, remaining))
                if not b:
                    break
                data += b
                remaining -= len(b)
        else:
            # Some servers keep-alive even with HTTP/1.0; enforce an idle timeout.
            idle = 0
            while True:
                try:
                    b = await asyncio.wait_for_ms(reader.read(1024), 200)
                except asyncio.TimeoutError:
                    idle += 1
                    if idle >= 10:  # 2s idle -> stop
                        break
                    continue
                idle = 0
                if not b:
                    break
                data += b

        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

        try:
            return data.decode()
        except Exception:
            return str(data, "utf-8", "ignore")

    def normalize_urls(self, urls, playlist_url):
        # Fix common server-side base_url issue: absolute URLs may miss :port
        out = []
        for u in urls or []:
            out.append(self._inject_port_if_missing(u, playlist_url))
        return out

    def _inject_port_if_missing(self, url, playlist_url):
        try:
            if not url or not playlist_url:
                return url
            if not (url.startswith("http://") or url.startswith("https://")):
                return url
            if not playlist_url.startswith("http://"):
                return url

            pr = playlist_url[7:]
            pslash = pr.find("/")
            phostport = pr if pslash < 0 else pr[:pslash]
            if ":" not in phostport:
                return url
            phost, pport = phostport.split(":", 1)
            if not pport:
                return url

            scheme, ur = url.split("://", 1)
            uslash = ur.find("/")
            uhostport = ur if uslash < 0 else ur[:uslash]
            upath = "/" if uslash < 0 else ur[uslash:]

            # already has port
            if ":" in uhostport:
                return url
            # only patch when host matches
            if uhostport != phost:
                return url

            return "{}://{}:{}{}".format(scheme, phost, pport, upath)
        except Exception:
            return url


_worker = _NetWorker()


# -------- UI App --------
class NetPlayerApp(PopApp):
    def __init__(self):
        super().__init__()
        if getattr(self, "_net_player_inited", False):
            return
        self.screen = Screen(bgcolor=GRAY)
        screen_width = self.screen.w

        self.playlist_url = ""
        self.urls = []
        self.names = []
        self.selected_index = 0
        self.playing = False
        self._handle = None

        self.title_label = Label(0, 16, "Net Radio (Server Playlist)", freesans20, WHITE, w=screen_width, align="center")
        self.status_label = Label(
            0, 44, "", freesans20, YELLOW, w=screen_width, h=28, align="center", valign="middle"
        )

        self.item_labels = []
        y0 = 86
        for i in range(5):
            lbl = Label(10, y0 + i * 28, "", freesans20, WHITE, w=screen_width - 20)
            self.item_labels.append(lbl)

        self.screen.add_list([self.title_label, self.status_label] + self.item_labels)
        self._net_player_inited = True

    def _name_for(self, idx):
        def _basename_from_url(u):
            try:
                seg = u.rsplit("/", 1)[-1]
                seg = seg.split("?", 1)[0]
                return seg
            except Exception:
                return ""

        try:
            if self.names and 0 <= idx < len(self.names) and self.names[idx]:
                n = self.names[idx]
                # Keep display consistent: show xxx.wav instead of paths/naked stems.
                if isinstance(n, str):
                    # If server returns a stem without extension, show as wav.
                    if "/" in n or "\\" in n:
                        n = n.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
                    if "." not in n:
                        n = n + ".wav"
                    return n
        except Exception:
            pass
        try:
            u = self.urls[idx]
            return _basename_from_url(u)
        except Exception:
            return ""

    def _refresh(self):
        if not self.urls:
            if not self.status_label.text:
                self.status_label.set_text("No playlist / urls")
        else:
            cur_name = self._name_for(self.selected_index)
            self.status_label.set_text(("Playing: " if self.playing else "Selected: ") + cur_name)

        start = max(0, self.selected_index - 2)
        end = min(len(self.urls), start + 5)
        window_len = max(0, end - start)

        for i in range(5):
            if i < window_len:
                idx = start + i
                prefix = ">" if idx == self.selected_index else " "
                self.item_labels[i].set_text("{} {}".format(prefix, self._name_for(idx)))
            else:
                self.item_labels[i].set_text("")

        # Rely on widget-level invalidation from Label.set_text() to avoid forcing
        # full-screen blits (which can stall on some boards).

    def _select(self, delta):
        if not self.urls:
            return
        self.selected_index = (self.selected_index + delta) % len(self.urls)
        self._refresh()

    def _stop(self):
        try:
            if self._handle is not None:
                self._handle.stop()
        except Exception:
            pass

        # audio = get_audio()
        # if audio:
        #     try:
        #         audio.stop_fg()
        #     except Exception:
        #         pass

        self._handle = None
        self.playing = False

    def _play_selected(self):
        if not self.urls:
            return

        audio = get_audio()
        if not audio:
            self.status_label.set_text("Audio not ready")
            return

        self._stop()
        url = self.urls[self.selected_index]
        dprint(DEBUG_INFO, "NetPlayerApp play url", url)
        self._handle = audio.play_http_wav(url)
        self.playing = True
        self._refresh()

    def on_enter(self):
        dprint(DEBUG_INFO, "NetPlayerApp on_resume")
        self.playlist_url = config.get("net_playlist_url") or ""
        dprint(DEBUG_INFO, "NetPlayerApp playlist_url", self.playlist_url)
        self.urls = config.get("net_wav_urls") or []
        self.names = [""] * len(self.urls)
        self.selected_index = 0
        self.playing = False
        self._handle = None

        if self.playlist_url:
            self.status_label.set_text("WiFi + loading playlist...")
            self.urls = []
            self.names = []
            _worker.request(self, self.playlist_url)
        else:
            self.status_label.set_text("Using net_wav_urls (no playlist)")

        self._refresh()
        self.screen.invalidate()

    def on_exit(self):
        self._stop()
        # Release WiFi usage ownership for idle/off policy.
        wifi_service.release("net_player")

    def on_event(self, evt):
        # Worker posts async results here.
        dprint(DEBUG_DBG, "NetPlayerApp on_event", evt)
        try:
            if not isinstance(evt, dict):
                return
            t = evt.get("type")
            if t == _NetWorker.EVT_WIFI:
                self.status_label.set_text(evt.get("msg") or "")
                # Avoid full-screen refresh: only text widgets invalidate their own rects.
                self._refresh()
            elif t == _NetWorker.EVT_PLAYLIST:
                if not evt.get("ok"):
                    self.status_label.set_text("Playlist error: {}".format(evt.get("msg") or ""))
                else:
                    self.urls = evt.get("urls") or []
                    self.names = evt.get("names") or [""] * len(self.urls)
                    self.selected_index = 0
                    if not self.urls:
                        self.status_label.set_text("Playlist empty")
                    else:
                        self.status_label.set_text("Playlist loaded ({})".format(len(self.urls)))
                self._refresh()
        except Exception:
            pass

    def on_input(self, key, status):
        dprint(DEBUG_DBG, "NetPlayerApp on_input", key, status)
        # Some key sources may only emit RELEASED; treat it as a click.
        if status not in (KEY_S_PRESSED,):
            # Allow MENU on release to still exit quickly.
            if key not in (GPIO_KEY_MENU, BLE_KEY_MENU):
                return

        if key in (GPIO_KEY_PREV, BLE_KEY_LEFT):
            self._select(-1)
        elif key in (GPIO_KEY_NEXT, BLE_KEY_RIGHT):
            self._select(1)
        elif key in (GPIO_KEY_ENTER, BLE_KEY_ENTER):
            if self.playing:
                self._stop()
                self._refresh()
            else:
                self._play_selected()
        elif key in (GPIO_KEY_MENU, BLE_KEY_MENU):
            self._stop()
            wifi_service.release("net_player")
            exit_app()

    def render(self):
        self.screen.show()

    def on_pause(self):
        dprint(DEBUG_INFO, "NetPlayerApp on_pause")

    def on_resume(self):
        dprint(DEBUG_INFO, "NetPlayerApp on_resume")
        self.screen.invalidate()
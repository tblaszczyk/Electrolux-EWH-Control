"""
core/notifier.py
Powiadomienia ntfy o awariach (z wyciszaniem powtórzeń i komunikatem o powrocie do normy).

Adres tematu: zmienna NTFY_URL albo plik data/ntfy.url (obok config.json), np. https://ntfy.sh/moj-temat.
Brak adresu = powiadomienia wyłączone (tylko wpis w logu). Błędy sieci są ignorowane.
"""

import base64
import logging
import os
import threading
import time
import urllib.request

log = logging.getLogger("boiler.notify")

REPEAT_S = 6 * 3600   # przypomnienie, gdy awaria trwa


def _url() -> str:
    u = os.environ.get("NTFY_URL", "").strip()
    if u:
        return u
    cfg = os.environ.get("CFG_FILE", "/var/lib/boiler/config.json")
    try:
        with open(os.path.join(os.path.dirname(cfg), "ntfy.url")) as f:
            return f.read().strip()
    except OSError:
        return ""


def send(title: str, msg: str, prio: str = "default", tags: str = "") -> bool:
    url = _url()
    if not url:
        log.info(f"ntfy wyłączone (brak adresu): {title} — {msg}")
        return False
    try:
        t = title if title.isascii() else "=?UTF-8?B?" + base64.b64encode(title.encode("utf-8")).decode() + "?="
        req = urllib.request.Request(url, data=msg.encode("utf-8"), method="POST",
                                     headers={"Title": t, "Priority": prio, "Tags": tags})
        urllib.request.urlopen(req, timeout=10).read()
        return True
    except Exception as e:
        log.warning(f"ntfy: błąd wysyłki: {e}")
        return False


class _Tracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._st = {}   # klucz -> {"since", "alerted_at"}

    def track(self, key: str, bad: bool, after_s: float, title: str, msg: str,
              ok_title: str = "", ok_msg: str = "", prio: str = "high") -> None:
        """Wołaj przy każdym sprawdzeniu. Gdy `bad` trwa >= after_s → powiadomienie (i przypomnienie co 6 h);
        gdy wróci do normy po powiadomieniu → komunikat o powrocie."""
        now = time.time()
        send_args = None
        with self._lock:
            st = self._st.setdefault(key, {"since": None, "alerted_at": None})
            if bad:
                if st["since"] is None:
                    st["since"] = now
                due = st["alerted_at"] is None or now - st["alerted_at"] >= REPEAT_S
                if now - st["since"] >= after_s and due:
                    st["alerted_at"] = now
                    send_args = (title, msg, prio, "rotating_light")
            else:
                if st["alerted_at"] is not None and ok_title:
                    send_args = (ok_title, ok_msg, "default", "white_check_mark")
                st["since"] = None
                st["alerted_at"] = None
        if send_args:
            log.warning(f"ALERT: {send_args[0]} — {send_args[1]}") if send_args[3] == "rotating_light" \
                else log.info(f"Powrót do normy: {send_args[0]}")
            threading.Thread(target=send, args=send_args, daemon=True).start()


notifier = _Tracker()

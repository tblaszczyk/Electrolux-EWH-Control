"""
Klient Tuya przez „Device Sharing” (to samo API co integracja Home Assistant / Smart Life).

Dlaczego: stary core/tuya_client.py używa Tuya IoT Core (konto deweloperskie), które po
wygaśnięciu triala odrzuca wszystko błędem „IoT Core trial quota is exhausted”.
Device Sharing loguje się kontem aplikacji Smart Life (kod QR), nie wymaga IoT Core
i nie ma kwoty. Interfejs publiczny jest identyczny z TuyaClient:
get_raw_status(), get_status(), set_switch().

Sesja (access/refresh token) leży w pliku JSON (0600), tworzonym przez tools/tuya_login.py.
Tokeny odświeżają się same, a nowe wartości zapisujemy z powrotem do pliku.
Jedna sesja = jeden proces (każdy konsument powinien mieć własne logowanie QR,
bo odświeżenie tokenu przez jednego może unieważnić drugiego).
"""

import json
import logging
import os
import sys
import threading
import time
from typing import Optional

# SDK może być zainstalowane lokalnie (pip install --target app/vendor), gdy venv usługi jest tylko do odczytu
_VENDOR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vendor")
if os.path.isdir(_VENDOR) and _VENDOR not in sys.path:
    sys.path.append(_VENDOR)

log = logging.getLogger("boiler.tuya")

CLIENT_ID = "HA_3y9q4ak7g4ephrvke"   # publiczny identyfikator integracji HA (schema haauthorize)
_TOKEN_KEYS = ("t", "uid", "expire_time", "access_token", "refresh_token")
KEEPALIVE_S = 60            # co tyle sekund sprawdzamy ważność tokenu
REFRESH_BEFORE_S = 30 * 60  # odświeżamy token, gdy zostało mniej niż 30 min (ważność = 2 h)


class TuyaSharingClient:

    def __init__(self, session_file: str, device_id: str):
        self._session_file = session_file
        self._device_id = device_id
        self._lock = threading.Lock()
        self._mgr = None
        self._session: dict = {}
        self._keepalive_started = False
        self.auth_error: Optional[str] = None   # niepusty = sesja martwa, trzeba ponownie zalogować QR

    # ── sesja / Manager ────────────────────────────────────────

    def _save_session(self) -> None:
        tmp = self._session_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self._session, f)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self._session_file)

    def _manager(self):
        """Tworzy Managera leniwie (import SDK dopiero tutaj — brak SDK nie psuje startu aplikacji)."""
        if self._mgr is not None:
            return self._mgr
        from tuya_sharing import Manager, SharingTokenListener

        with open(self._session_file) as f:
            self._session = json.load(f)
        client = self

        class _Listener(SharingTokenListener):
            def update_token(self, token_info):
                client._session.update(token_info)
                try:
                    client._save_session()
                except OSError as e:
                    log.error(f"Tuya: nie można zapisać odświeżonego tokenu: {e}")

        s = self._session
        self._mgr = Manager(
            CLIENT_ID, s["user_code"], s["terminal_id"], s["endpoint"],
            {k: s[k] for k in _TOKEN_KEYS}, _Listener(),
        )
        self._start_keepalive()
        return self._mgr

    # ── podtrzymanie tokenu ────────────────────────────────────
    # SDK odświeża token dopiero w ostatniej minucie ważności (albo po wygaśnięciu), a wtedy
    # żądanie odświeżenia jest odrzucane ("token is expired"). Pompa odzywa się rzadko
    # (tylko przy zmianie stanu), więc bez podtrzymania sesja umierała po 2 h bezczynności.

    def _expires_in_s(self) -> float:
        return (self._mgr.customer_api.token_info.expire_time - time.time() * 1000) / 1000.0

    def _refresh_token(self) -> bool:
        """Odświeża token (ta sama procedura co w SDK, ale z wyprzedzeniem). True = sukces."""
        from tuya_sharing.customerapi import CustomerTokenInfo
        api = self._mgr.customer_api
        resp = api.get("/v1.0/m/token/" + api.token_info.refresh_token)
        if not resp.get("success"):
            raise RuntimeError(str(resp)[:200])
        r = resp.get("result", {})
        info = {"t": resp["t"], "expire_time": r["expireTime"], "uid": r["uid"],
                "access_token": r["accessToken"], "refresh_token": r["refreshToken"]}
        api.token_info = CustomerTokenInfo(info)
        self._session.update(info)
        self._save_session()
        return True

    def _keepalive_tick(self) -> None:
        with self._lock:
            if self._expires_in_s() > REFRESH_BEFORE_S:
                return
            try:
                self._refresh_token()
                if self.auth_error:
                    log.info("Tuya(sharing): sesja odnowiona")
                self.auth_error = None
                log.info("Tuya(sharing): token odświeżony z wyprzedzeniem")
            except Exception as e:
                msg = f"nie można odświeżyć tokenu ({e}) — wymagane ponowne logowanie QR (tools/tuya_login.py)"
                if msg != self.auth_error:
                    log.error(f"Tuya(sharing): {msg}")
                self.auth_error = msg

    def _start_keepalive(self) -> None:
        if self._keepalive_started:
            return
        self._keepalive_started = True

        def loop():
            while True:
                try:
                    self._keepalive_tick()
                except Exception as e:
                    log.error(f"Tuya(sharing): keepalive: {e}")
                time.sleep(KEEPALIVE_S)

        threading.Thread(target=loop, name="tuya_keepalive", daemon=True).start()

    def _device(self):
        """Świeży stan jednego urządzenia (REST, bez MQTT i bez pobierania całej listy)."""
        m = self._manager()
        devs = m.device_repository.query_devices_by_ids([self._device_id])
        return devs[0] if devs else None

    # ══════════════════════════════════════════════════════════
    # PUBLICZNE API (zgodne z TuyaClient)
    # ══════════════════════════════════════════════════════════

    def get_raw_status(self) -> Optional[list]:
        """Lista [{'code':..., 'value':...}] jak w IoT Core — do diagnostyki i get_status()."""
        try:
            with self._lock:
                dev = self._device()
        except Exception as e:
            log.error(f"Tuya(sharing): błąd odczytu statusu: {e}")
            return None
        if dev is None:
            log.error(f"Tuya(sharing): urządzenie {self._device_id} nie jest na koncie")
            return None
        return [{"code": k, "value": v} for k, v in (dev.status or {}).items()]

    def get_status(self) -> Optional[dict]:
        """{'power_w','voltage_v','current_ma','switch','raw'} albo None (skale jak w TuyaClient)."""
        dps_list = self.get_raw_status()
        if dps_list is None:
            return None
        dps = {d["code"]: d["value"] for d in dps_list}
        return {
            "power_w":    dps.get("cur_power", 0) / 10.0 if "cur_power" in dps else None,
            "voltage_v":  dps.get("cur_voltage", 0) / 10.0 if "cur_voltage" in dps else None,
            "current_ma": dps.get("cur_current"),
            "switch":     dps.get("switch_1", dps.get("switch")),
            "raw":        dps,
        }

    def set_switch(self, on: bool, dp_code: str = "switch_1") -> bool:
        """Włącz/wyłącz przełącznik. Zwraca True po przyjęciu komendy przez chmurę."""
        try:
            with self._lock:
                self._manager().send_commands(
                    self._device_id, [{"code": dp_code, "value": bool(on)}])
            return True
        except Exception as e:
            log.error(f"Tuya(sharing): błąd komendy set_switch({on}): {e}")
            return False

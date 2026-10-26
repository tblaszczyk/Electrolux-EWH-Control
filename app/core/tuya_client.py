"""
core/tuya_client.py
Klient Tuya OpenAPI (Cloud) — odczyt realnej mocy/energii z wtyczki pomiarowej
podłączonej do bojlera. Tylko odczyt (GET) — nigdy nie wysyła komend sterujących
do żadnego urządzenia Tuya.

Używane do zweryfikowania/skalibrowania szacunków energii opartych na power_w
(zadana moc) i ΔT (fizyczny model zbiornika) realnym pomiarem z licznika.
"""

import hashlib
import hmac
import json
import logging
import time
import urllib.request
import urllib.error
from typing import Optional

log = logging.getLogger("boiler.tuya")

REGION_ENDPOINTS = {
    "eu":  "https://openapi.tuyaeu.com",
    "weu": "https://openapi-weaz.tuyaeu.com",
    "us":  "https://openapi.tuyaus.com",
    "cn":  "https://openapi.tuyacn.com",
    "in":  "https://openapi.tuyain.com",
}


class TuyaClient:

    def __init__(self, client_id: str, client_secret: str, device_id: str, region: str = "eu"):
        self._client_id     = client_id
        self._client_secret = client_secret
        self._device_id     = device_id
        self._base = REGION_ENDPOINTS.get(region, REGION_ENDPOINTS["eu"])
        self._access_token: Optional[str] = None
        self._token_expires_at = 0.0

    # ── Podpisywanie żądań (Tuya Cloud API sign spec) ──────────

    def _sign(self, method: str, path: str, body: str = "", access_token: str = "") -> tuple:
        t = str(int(time.time() * 1000))
        content_sha256 = hashlib.sha256(body.encode()).hexdigest()
        string_to_sign = f"{method}\n{content_sha256}\n\n{path}"
        sign_str = self._client_id + access_token + t + string_to_sign
        sign = hmac.new(
            self._client_secret.encode(), sign_str.encode(), hashlib.sha256
        ).hexdigest().upper()
        return t, sign

    def _request(self, method: str, path: str, body: str = "", access_token: str = "") -> Optional[dict]:
        t, sign = self._sign(method, path, body=body, access_token=access_token)
        headers = {
            "client_id":   self._client_id,
            "sign":        sign,
            "t":           t,
            "sign_method": "HMAC-SHA256",
        }
        if access_token:
            headers["access_token"] = access_token
        if body:
            headers["Content-Type"] = "application/json"

        data = body.encode() if body else None
        req = urllib.request.Request(self._base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.URLError as e:
            log.error(f"Tuya: żądanie {path} nieudane: {e}")
            return None
        except Exception as e:
            log.error(f"Tuya: nieoczekiwany błąd {path}: {e}")
            return None

    # ── Token ────────────────────────────────────────────────

    def _get_token(self) -> Optional[str]:
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        data = self._request("GET", "/v1.0/token?grant_type=1")
        if not data or not data.get("success"):
            log.error(f"Tuya: błąd pobierania tokenu: {data.get('msg') if data else 'brak odpowiedzi'}")
            return None

        result = data["result"]
        self._access_token = result["access_token"]
        self._token_expires_at = time.time() + result.get("expire_time", 7200)
        return self._access_token

    # ══════════════════════════════════════════════════════════
    # PUBLICZNE API
    # ══════════════════════════════════════════════════════════

    def get_raw_status(self) -> Optional[list]:
        """Surowa lista DP-ów urządzenia — do diagnostyki (jakie kody raportuje)."""
        token = self._get_token()
        if not token:
            return None
        path = f"/v1.0/devices/{self._device_id}/status"
        data = self._request("GET", path, access_token=token)
        if not data or not data.get("success"):
            log.error(f"Tuya: błąd odczytu statusu: {data.get('msg') if data else 'brak odpowiedzi'}")
            return None
        return data.get("result", [])

    def get_status(self) -> Optional[dict]:
        """
        Zwraca {'power_w', 'voltage_v', 'current_ma', 'switch', 'raw'} albo None.
        Skalowanie (dzielenie przez 10) dotyczy typowych wtyczek Tuya z pomiarem
        mocy — jeśli po diagnostyce (get_raw_status) okaże się inne, poprawić tu.
        """
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
        """
        Wysyła komendę włącz/wyłącz do przełącznika Tuya (POST /commands).
        Jedyne miejsce w systemie wysyłające sterowanie do urządzenia Tuya —
        używane wyłącznie przez core/pump_logic.py + wątek sterujący pompą,
        nigdy przez odczyt/monitoring wtyczki bojlera.
        """
        token = self._get_token()
        if not token:
            return False
        path = f"/v1.0/devices/{self._device_id}/commands"
        body = json.dumps({"commands": [{"code": dp_code, "value": bool(on)}]})
        data = self._request("POST", path, body=body, access_token=token)
        if not data or not data.get("success"):
            log.error(f"Tuya: błąd komendy set_switch({on}): {data.get('msg') if data else 'brak odpowiedzi'}")
            return False
        return True

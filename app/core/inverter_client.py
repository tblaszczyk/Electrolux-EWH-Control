"""
core/inverter_client.py
Klient Hypontech Cloud API v2 — odczyt produkcji PV.
Zawsze zwraca dict (nigdy nie rzuca wyjątku do góry).

Publiczne API:
  get_data() → dict  (online=True/False, pv_power, today_kwh, ...)
"""

import json
import time
import logging
import threading
import urllib.request
from datetime import datetime
from typing import Optional

log = logging.getLogger("boiler.inverter")

BASE_URL = "https://api.hypon.cloud/v2"
HEADERS  = {
    "accept":       "application/json",
    "content-type": "application/json;charset=UTF-8",
    "User-Agent":   "Mozilla/5.0",
}

# Zwróć ten dict gdy brak komunikacji
_OFFLINE = {
    "online":     False,
    "pv_power":   0.0,
    "ac_power":   0.0,
    "today_kwh":  0.0,
    "total_kwh":  0.0,
    "ts":         None,
}


class InverterClient:

    def __init__(
        self,
        username: str,
        password: str,
        station_id: str,
        timeout: int = 15,
        token_ttl: int = 3000,     # sekundy ważności tokenu
    ):
        self._user      = username
        self._pass      = password
        self._station   = station_id
        self._timeout   = min(timeout, 5)
        self._token_ttl = token_ttl

        self._lock      = threading.Lock()
        self._token: Optional[str] = None
        self._token_ts: float = 0
        self._backoff_until: float = 0     # blokada po błędzie konta
        self._net_backoff = 300            # pauza (s) gdy chmura nieosiagalna

    # ── Logowanie ─────────────────────────────────────────────

    def _login(self) -> bool:
        if not self._user or not self._pass:
            log.warning("Inverter: brak credentiali — pomijam")
            return False
        try:
            payload = json.dumps({
                "username":   self._user,
                "password":   self._pass,
                "rememberMe": True
            }).encode()
            req = urllib.request.Request(
                f"{BASE_URL}/login",
                data=payload, headers=HEADERS, method="POST"
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as r:
                resp = json.loads(r.read())

            if resp.get("code") == 20000:
                self._token    = resp["data"]["token"]
                self._token_ts = time.time()
                log.info(f"Inverter: zalogowano (token={self._token[:8]}...)")
                return True

            msg = resp.get("message", "")
            log.error(f"Inverter login failed: {msg}")
            if "incorrectly" in msg or "cannot log in" in msg:
                self._backoff_until = time.time() + 900   # 15 min blokada
                log.warning("Inverter: konto zablokowane — pauza 15 min")
        except Exception as e:
            # Chmura nieosiagalna (timeout / siec) - pauza, aby nie
            # blokowac petli sterujacej co cykl. PV zostaje zignorowane.
            self._backoff_until = time.time() + self._net_backoff
            log.warning(
                f"Inverter: chmura nieosiagalna ({e}) - pauza "
                f"{self._net_backoff // 60} min, PV ignorowane"
            )
        return False

    # ── GET helper ────────────────────────────────────────────

    def _get(self, path: str) -> Optional[dict]:
        if time.time() < self._backoff_until:
            return None

        if not self._token or (time.time() - self._token_ts) > self._token_ttl:
            if not self._login():
                return None

        def _request() -> Optional[dict]:
            hdrs = {**HEADERS, "authorization": f"Bearer {self._token}"}
            req  = urllib.request.Request(f"{BASE_URL}{path}", headers=hdrs)
            with urllib.request.urlopen(req, timeout=self._timeout) as r:
                return json.loads(r.read())

        try:
            resp = _request()
            if resp and resp.get("code") == 20000:
                return resp.get("data")
            # Token wygasł — odśwież raz
            if resp and resp.get("code") in (40001, 40002, 401):
                self._token = None
                if self._login():
                    resp = _request()
                    if resp and resp.get("code") == 20000:
                        return resp.get("data")
            log.warning(f"Inverter GET {path}: {resp.get('code') if resp else 'no resp'}")
        except Exception as e:
            log.error(f"Inverter GET {path}: {e}")
        return None

    # ══════════════════════════════════════════════════════════
    # PUBLICZNE API
    # ══════════════════════════════════════════════════════════

    def get_data(self) -> dict:
        """
        Pobierz aktualną produkcję PV i energię dzienną.
        Zawsze zwraca dict — online=False gdy brak komunikacji.
        """
        with self._lock:
            try:
                station  = self._station
                monitor  = self._get(f"/plant/{station}/monitor?refresh=true")
                if not monitor:
                    return {**_OFFLINE, "ts": datetime.now().isoformat()}

                today = datetime.now()
                energy = self._get(
                    f"/plant/{station}/energy2"
                    f"?day={today.day:02d}&month={today.month:02d}"
                    f"&type=day&year={today.year}"
                )

                result = {
                    "online":     True,
                    "pv_power":   float(monitor.get("power_pv",   0)),
                    "ac_power":   float(monitor.get("meter_power", 0)),
                    "power_load": float(monitor.get("power_load",  0)),
                    "today_kwh":  float(monitor.get("e_today",     0)),
                    "total_kwh":  float(monitor.get("e_total",     0)),
                    "soc":        float(monitor.get("soc",         0)),
                    "ts":         datetime.now().isoformat(),
                }
                if energy:
                    result["today_kwh"] = float(energy.get("pvkwh", result["today_kwh"]))

                return result

            except Exception as e:
                log.error(f"Inverter get_data: {e}")
                return {**_OFFLINE, "ts": datetime.now().isoformat()}

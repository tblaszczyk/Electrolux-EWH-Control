"""
core/tauron_client.py
Klient nieoficjalnego API eLicznika Tauron — pobór/oddanie energii z sieci.
Logowanie przez Keycloak (TAURON migrował z CAS na OIDC w 05/2026).
Bez zewnętrznych zależności — stdlib urllib + http.cookiejar (ten sam
zestaw co core/inverter_client.py).

Uwaga: eLicznik raportuje TYLKO przepływ z/do sieci (pobór/oddanie), nie
całkowitą produkcję PV ani całkowite zużycie domu — to ograniczenie
samego licznika dwukierunkowego (patrz core/inverter_client.py dla
prawdziwej produkcji PV).

Publiczne API:
  login() → bool
  get_daily_sums(date_from, date_to, kind) → [{date, kwh}]   (rozdzielczość dzienna)
  get_hourly(date_from, date_to, kind) → [{date, hour, kwh}]  (surowe odczyty godzinowe)
"""

import json
import re
import logging
import urllib.request
import urllib.parse
import http.cookiejar
from datetime import datetime
from typing import Optional

log = logging.getLogger("boiler.tauron")

LOGIN_URL            = "https://logowanie.tauron-dystrybucja.pl/login"
SERVICE_URL          = "https://elicznik.tauron-dystrybucja.pl"
SELECT_METER_URL     = f"{SERVICE_URL}/ustaw_punkt"
ENERGY_URL           = f"{SERVICE_URL}/energia/api"
ENERGY_URL_BUSINESS  = f"{SERVICE_URL}/energia/wo/api"
TOO_MANY_LOGINS      = "Przekroczono maksymalną liczbę logowań"


class TauronClient:

    def __init__(self, username: str, password: str, meter_id: Optional[str] = None, timeout: int = 20):
        self._user    = username
        self._pass    = password
        self._meter_id = meter_id or None
        self._timeout = timeout

        cj = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

        self._logged_in  = False
        self._is_business = False
        self.tariff: Optional[str] = None
        self.meters: list = []

    @property
    def meter_id(self) -> Optional[str]:
        return self._meter_id

    @property
    def logged_in(self) -> bool:
        return self._logged_in

    # ── HTTP helper ───────────────────────────────────────────

    def _request(self, url: str, data: Optional[bytes] = None, headers: Optional[dict] = None) -> str:
        hdrs = {"cache-control": "no-cache"}
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, data=data, headers=hdrs)
        with self._opener.open(req, timeout=self._timeout) as r:
            return r.read().decode("utf-8", errors="replace")

    # ── Logowanie ─────────────────────────────────────────────

    def login(self) -> bool:
        if not self._user or not self._pass:
            log.warning("Tauron: brak danych logowania (username/password)")
            return False
        try:
            url = f"{LOGIN_URL}?service={urllib.parse.quote(SERVICE_URL, safe='')}"
            html = self._request(url)

            m = re.search(r'<form[^>]+id="kc-form-login"[^>]+action="([^"]+)"', html)
            if not m:
                log.error("Tauron: nie znaleziono formularza logowania Keycloak (strona mogła się zmienić)")
                return False
            action = m.group(1).replace("&amp;", "&")

            body = urllib.parse.urlencode({
                "username": self._user, "password": self._pass, "credentialId": "",
            }).encode()
            login_text = self._request(action, data=body,
                headers={"content-type": "application/x-www-form-urlencoded"})

            if TOO_MANY_LOGINS in login_text:
                log.error("Tauron: przekroczono limit prób logowania")
                return False
            if 'id="kc-form-login"' in login_text:
                log.error("Tauron: błędny login lub hasło")
                return False
            if self._user.lower() not in login_text.lower():
                log.error("Tauron: logowanie nieudane (nieoczekiwana odpowiedź)")
                return False

            self.meters = self._parse_meters(login_text)
            meter_id = self._meter_id or (self.meters[0]["meter_id"] if self.meters else None)
            if not meter_id:
                log.error("Tauron: nie znaleziono żadnego licznika na koncie")
                return False
            self._meter_id = meter_id

            selected = next((mm for mm in self.meters if mm["meter_id"] == meter_id), None)
            self._is_business = bool(selected and selected["meter_type"] == "WO")

            sel_body = urllib.parse.urlencode({"site[client]": meter_id}).encode()
            sel_text = self._request(SELECT_METER_URL, data=sel_body,
                headers={"content-type": "application/x-www-form-urlencoded"})
            tm = re.search(r"[^_]Tariff: '(.*)',", sel_text)
            self.tariff = tm.group(1) if tm else "unknown"

            self._logged_in = True
            log.info(f"Tauron: zalogowano, licznik={meter_id}, taryfa={self.tariff}")
            return True

        except Exception as e:
            log.error(f"Tauron: błąd logowania: {e}")
            return False

    @staticmethod
    def _parse_meters(html: str) -> list:
        pattern = re.compile(r'.*data-data=\'\{"type": ".*"\}\'>.*')
        meters = []
        for line in pattern.findall(html):
            m1 = re.search(r'value="([\d_]+)"', line)
            m2 = re.search(r"\"\}'>(.*)</option>", line)
            m3 = re.search(r'data-data=\'\{"type": "(.*)"\}\'>', line)
            if m1 and m2 and m3:
                meters.append({
                    "meter_id":   m1.group(1),
                    "meter_name": m2.group(1),
                    "meter_type": m3.group(1),
                })
        return meters

    # ── Dane ──────────────────────────────────────────────────

    def _chart(self, payload: dict) -> Optional[dict]:
        url = ENERGY_URL_BUSINESS if self._is_business else ENERGY_URL
        body = urllib.parse.urlencode(payload).encode()
        try:
            text = self._request(url, data=body,
                headers={"content-type": "application/x-www-form-urlencoded"})
        except Exception as e:
            log.error(f"Tauron: błąd zapytania o dane: {e}")
            return None
        if TOO_MANY_LOGINS in text:
            log.error("Tauron: przekroczono limit zapytań")
            return None
        if not text.startswith('{"success":true'):
            return None
        try:
            return json.loads(text)
        except Exception:
            return None

    @staticmethod
    def _fmt_date(d: datetime) -> str:
        return d.strftime("%d.%m.%Y")

    def get_daily_sums(self, date_from: datetime, date_to: datetime, kind: str) -> list:
        """kind: 'import' (pobór z sieci) lub 'export' (oddanie do sieci).
        Zwraca [{'date': 'YYYY-MM-DD', 'kwh': float}] — jeden wpis na dzień."""
        generation = kind == "export"
        payload = {
            "from": self._fmt_date(date_from), "to": self._fmt_date(date_to),
            "profile": "month",
            "type": "oze" if generation else "consum",
            "energy": 2 if generation else 1,
        }
        data = self._chart(payload)
        rows = ((data or {}).get("data") or {}).get("allData") or []
        out = []
        for r in rows:
            if r.get("Period") is None or r.get("Sum") is None:
                continue
            try:
                out.append({"date": r["Period"], "kwh": float(r["Sum"])})
            except (TypeError, ValueError):
                continue
        return out

    def get_hourly(self, date_from: datetime, date_to: datetime, kind: str) -> list:
        """Surowe odczyty godzinowe. Zwraca [{'date': 'YYYY-MM-DD', 'hour': 1..24, 'kwh': float}]."""
        generation = kind == "export"
        data = self._chart({
            "from": self._fmt_date(date_from), "to": self._fmt_date(date_to),
            "profile": "full time",
            "type": "oze" if generation else "consum",
            "energy": 2 if generation else 1,
        })
        rows = ((data or {}).get("data") or {}).get("allData") or []
        out = []
        for r in rows:
            try:
                out.append({"date": r["Date"][:10], "hour": int(r["Hour"]), "kwh": float(r["EC"])})
            except (KeyError, TypeError, ValueError):
                continue
        return out

"""Jednorazowe logowanie Bojler2 do Tuya przez kod QR (Smart Life, bez IoT Core).

Użycie (na serwerze Bojler2, w jego venv):
    /opt/boiler/venv/bin/python /opt/boiler2/tools/tuya_login.py <KOD_UŻYTKOWNIKA> [plik_sesji]

Kod użytkownika: aplikacja Smart Life → Ja → ikona ustawień → Konto i bezpieczeństwo → Kod użytkownika.
Skrypt wypisuje adres/QR (ASCII), czeka do 5 min na zeskanowanie QR w aplikacji
(Smart Life → Ja → ikona skanera) i zapisuje sesję (0600). Potem w config.json:
    "tuya_backend": "sharing"   (+ restart usługi boiler2).
"""
import json
import os
import sys
import time

_V = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vendor")
if os.path.isdir(_V):
    sys.path.append(_V)

from tuya_sharing import LoginControl

CLIENT_ID, SCHEMA = "HA_3y9q4ak7g4ephrvke", "haauthorize"   # publiczne wartości integracji Home Assistant


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    user_code = sys.argv[1].strip()
    out = sys.argv[2] if len(sys.argv) > 2 else "/opt/boiler2/data/tuya_session.json"
    lc = LoginControl()
    r = lc.qr_code(CLIENT_ID, SCHEMA, user_code)
    if not r.get("success"):
        sys.exit("BŁĄD qr_code: " + json.dumps(r, ensure_ascii=False)[:300])
    token = r["result"]["qrcode"]
    data = "tuyaSmart--qrLogin?token=" + token
    try:
        import qrcode
        q = qrcode.QRCode(border=2)
        q.add_data(data)
        q.make()
        q.print_ascii(invert=True)
    except ImportError:
        print("Brak biblioteki qrcode — wygeneruj kod QR z tekstu poniżej (dowolny generator):")
    print("Dane do kodu QR:", data, flush=True)
    print("Czekam do 5 min na zeskanowanie QR w aplikacji Smart Life...", flush=True)
    for _ in range(100):
        ok, info = lc.login_result(token, CLIENT_ID, user_code)
        if ok:
            info["user_code"] = user_code
            tmp = out + ".tmp"
            with open(tmp, "w") as f:
                json.dump(info, f)
            os.chmod(tmp, 0o660)   # usługa boiler2 działa jako www-data (wspólna grupa z kontem uruchamiającym)
            try:
                os.chown(tmp, -1, os.stat(os.path.dirname(os.path.abspath(out))).st_gid)
            except OSError:
                pass
            os.replace(tmp, out)
            print("ZALOGOWANO; zapisano", out)
            return
        time.sleep(3)
    sys.exit("Minął czas — nie zeskanowano QR")


if __name__ == "__main__":
    main()

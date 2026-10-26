"""
core/boiler_client.py
Komunikacja z bojlerem Electrolux EWH — protokół UDP z szyfrowaniem X25519/AES.
Protokół przepisany 1:1 z działającego kodu + mDNS auto-refresh klucza + dry_run.

Publiczne API:
  get_status()                → dict | None
  set_target(temp_c, power_w) → bool
  refresh_pub_key()           → str
"""

import re
import socket
import struct
import hashlib
import logging
import threading
import time
from datetime import datetime
from typing import Optional

log = logging.getLogger("boiler.client")

FRAME_ACK     = 0
FRAME_CMD     = 1
FRAME_NAK     = 3
CMD_HANDSHAKE = 0x00

MODE_NAMES = {0: "normal", 1: "eco", 2: "turbo", 3: "no_heat"}

POWER_W_TO_LEVEL = {0: 0, 700: 1, 1300: 2, 2000: 3}
POWER_LEVEL_TO_W = {1: 700, 2: 1300, 3: 2000}

MDNS_GROUP = "224.0.0.251"
MDNS_PORT  = 5353
MDNS_QUERY = (
    b'\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00'
    b'\x08_syncleo\x04_udp\x05local\x00\x00\xff\x00\x01'
)


class BoilerClient:

    def __init__(
        self,
        ip: str,
        port: int,
        token: str,
        pub_key: str,
        retry_count: int = 3,
        dry_run: bool = False,
        mdns_refresh_interval_s: int = 3600,
    ):
        self._ip          = ip
        self._port        = port
        self._token       = bytes.fromhex(token) if token else b"\x00" * 16
        self._pub_key     = pub_key
        self._retry       = retry_count
        self._dry_run     = dry_run
        self._mdns_interval = mdns_refresh_interval_s

        self._lock        = threading.Lock()
        self._seq_out     = 0xFF
        self._seq_in      = 0x00
        self._enc_in:  Optional[bytes] = None
        self._enc_out: Optional[bytes] = None
        self._last_pwr_byte: Optional[int] = None

        if dry_run:
            log.warning("BoilerClient: DRY RUN — komendy nie są wysyłane")

        self._import_crypto()

        t = threading.Thread(target=self._mdns_refresh_loop,
                             name="mdns-refresh", daemon=True)
        t.start()

    def _import_crypto(self):
        from cryptography.hazmat.primitives.asymmetric.x25519 import (
            X25519PrivateKey, X25519PublicKey)
        from cryptography.hazmat.primitives import serialization, padding
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
        self._X25519Priv = X25519PrivateKey
        self._X25519Pub  = X25519PublicKey
        self._serial     = serialization
        self._padding    = padding
        self._Cipher     = Cipher
        self._alg        = algorithms
        self._modes      = modes
        self._backend    = default_backend

    # ── Narzędzia ─────────────────────────────────────────────

    def _seq_next(self) -> int:
        self._seq_out = (self._seq_out + 1) & 0xFF
        return self._seq_out

    def _rotate(self, key: bytes, n: int) -> bytes:
        n = n % len(key)
        return key[n:] + key[:n]

    def _make_frame(self, seq: int, ftype: int, payload: bytes) -> bytes:
        return struct.pack("<BBBB", seq, ftype,
                          len(payload) & 0xFF, (len(payload) >> 8) & 0xFF) + payload

    def _parse_frame(self, data: bytes):
        if len(data) < 4:
            return None, None, b""
        seq, ftype, ll, lh = struct.unpack("<BBBB", data[:4])
        return seq, ftype, data[4:4 + (ll | (lh << 8))]

    def _aes_nopad(self, key: bytes, iv: bytes, pt: bytes) -> bytes:
        c = self._Cipher(self._alg.AES(key), self._modes.CBC(iv),
                         backend=self._backend())
        e = c.encryptor()
        return e.update(pt) + e.finalize()

    def _aes_dec_pkcs7(self, key: bytes, iv: bytes, ct: bytes) -> bytes:
        c = self._Cipher(self._alg.AES(key), self._modes.CBC(iv),
                         backend=self._backend())
        d = c.decryptor()
        padded = d.update(ct) + d.finalize()
        try:
            up = self._padding.PKCS7(128).unpadder()
            return up.update(padded) + up.finalize()
        except Exception:
            return padded

    def _aes_enc_pkcs7(self, key: bytes, iv: bytes, pt: bytes) -> bytes:
        pad = self._padding.PKCS7(128).padder()
        padded = pad.update(pt) + pad.finalize()
        c = self._Cipher(self._alg.AES(key), self._modes.CBC(iv),
                         backend=self._backend())
        e = c.encryptor()
        return e.update(padded) + e.finalize()

    # ── mDNS ──────────────────────────────────────────────────

    def refresh_pub_key(self) -> str:
        """Odczytaj klucz publiczny bojlera przez mDNS."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5.0)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", 5353))
            import struct
            mreq = struct.pack("4sL", socket.inet_aton(MDNS_GROUP), socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
            sock.sendto(MDNS_QUERY, (MDNS_GROUP, MDNS_PORT))

            for _ in range(15):
                try:
                    data, addr = sock.recvfrom(4096)
                    if "public=" not in data.decode("utf-8", errors="replace"):
                        continue
                    m = re.search(r"public=([0-9a-f]{64})",
                                  data.decode("utf-8", errors="replace"))
                    if m:
                        new_key = m.group(1)
                        sock.close()
                        if True:  # no lock
                            if new_key != self._pub_key:
                                log.warning(
                                    f"mDNS: klucz ZMIENIONY "
                                    f"{self._pub_key[:16]}... → {new_key[:16]}..."
                                )
                                self._pub_key = new_key
                            else:
                                log.debug(f"mDNS: klucz bez zmian ({new_key[:16]}...)")
                        return new_key
                except socket.timeout:
                    break
            sock.close()
            log.warning("mDNS: brak odpowiedzi od bojlera")
        except Exception as e:
            log.warning(f"mDNS refresh error: {e}")

        
            return self._pub_key

    def _mdns_refresh_loop(self) -> None:
        time.sleep(5)
        log.info("mDNS: pierwsze odświeżenie klucza...")
        self.refresh_pub_key()
        while True:
            time.sleep(self._mdns_interval)
            log.info("mDNS: cykliczne odświeżenie klucza...")
            self.refresh_pub_key()

    # ── Handshake (oryginalny protokół) ───────────────────────

    def _compute_keys(self, priv_key, dev_pub_reversed: bytes):
        dev_pub_raw = bytes(reversed(dev_pub_reversed))
        dev_pub     = self._X25519Pub.from_public_bytes(dev_pub_raw)
        shared      = bytes(reversed(priv_key.exchange(dev_pub)))
        digest      = hashlib.sha256(shared).digest()
        return digest[:16], digest[16:32]   # enc_in, enc_out

    def _make_enc_ack(self, seq: int) -> bytes:
        key = self._rotate(self._enc_out, seq & 0xF)
        iv  = self._rotate(self._enc_in,  (seq >> 4) & 0xF)
        return self._make_frame(seq, FRAME_ACK,
                                self._aes_enc_pkcs7(key, iv, bytes([seq])))

    def _handshake(self, sock: socket.socket) -> bool:
        try:
            if True:  # no lock
                pub_hex = self._pub_key
            if not pub_hex or len(pub_hex) != 64:
                log.error(f"Bojler: nieprawidłowy klucz pub ({pub_hex!r})")
                return False

            dev_pub       = bytes.fromhex(pub_hex)
            token         = self._token[:16]
            priv          = self._X25519Priv.generate()
            pub_raw       = priv.public_key().public_bytes(
                self._serial.Encoding.Raw, self._serial.PublicFormat.Raw)
            phone_pub_rev = bytes(reversed(pub_raw))
            enc_in, enc_out = self._compute_keys(priv, dev_pub)
            enc_token     = self._aes_nopad(enc_out, enc_in, token)

            payload = bytes([CMD_HANDSHAKE]) + phone_pub_rev + enc_token
            self._seq_out = 0xFF
            self._seq_in  = 0x00
            seq   = self._seq_next()   # = 0x00
            sock.sendto(self._make_frame(seq, FRAME_CMD, payload),
                        (self._ip, self._port))

            sock.settimeout(6.0)
            for _ in range(5):
                try:
                    resp = sock.recvfrom(4096)[0]
                except socket.timeout:
                    log.warning("Bojler: timeout na handshake")
                    return False

                r_seq, r_type, r_pl = self._parse_frame(resp)

                # Wyślij ACK
                ack_key = self._rotate(enc_out, r_seq & 0xF)
                ack_iv  = self._rotate(enc_in,  (r_seq >> 4) & 0xF)
                ack_pl  = self._aes_enc_pkcs7(ack_key, ack_iv, bytes([r_seq]))
                sock.sendto(self._make_frame(r_seq, FRAME_ACK, ack_pl),
                            (self._ip, self._port))

                if r_type != FRAME_CMD or len(r_pl) < 16:
                    continue

                key_d = self._rotate(enc_in,  r_seq & 0xF)
                iv_d  = self._rotate(enc_out, (r_seq >> 4) & 0xF)
                try:
                    dec = self._aes_dec_pkcs7(key_d, iv_d, r_pl)
                except Exception:
                    continue

                if not dec or dec[0] != r_seq:
                    continue
                content = dec[1:]
                if not content or content[0] != CMD_HANDSHAKE or len(content) < 22:
                    continue

                recv_token = content[6:22]
                if recv_token == bytes(16):
                    log.warning("Bojler: AUTH failed — pusty token (zły klucz?)")
                    # Spróbuj natychmiast odświeżyć klucz
                    threading.Thread(target=self.refresh_pub_key,
                                     daemon=True).start()
                    return False

                self._enc_in  = enc_in
                self._enc_out = enc_out
                log.info(f"Bojler: połączono fw={content[3]}.{content[4]}")

                # Przywróć moc (handshake resetuje do LOW)
                if self._last_pwr_byte is not None:
                    seq2  = self._seq_next()
                    key2  = self._rotate(enc_out, seq2 & 0xF)
                    iv2   = self._rotate(enc_in,  (seq2 >> 4) & 0xF)
                    enc2  = self._aes_enc_pkcs7(
                        key2, iv2, bytes([seq2, 0x01, self._last_pwr_byte]))
                    sock.sendto(self._make_frame(seq2, FRAME_CMD, enc2),
                                (self._ip, self._port))
                    sock.settimeout(0.3)
                    for _ in range(3):
                        try:
                            sock.recvfrom(4096)
                        except socket.timeout:
                            break

                return True

        except Exception as e:
            log.error(f"Bojler handshake error: {e}")
        return False

    # ── Sesje ────────────────────────────────────────────────

    def _session_read(self) -> Optional[list]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(6.0)
        try:
            if not self._handshake(sock):
                return None
            frames   = []
            sock.settimeout(0.5)
            deadline = time.time() + 2.0
            while time.time() < deadline:
                try:
                    resp = sock.recvfrom(4096)[0]
                    r_seq, r_type, r_pl = self._parse_frame(resp)
                    if r_type == FRAME_ACK:
                        continue
                    if r_type == FRAME_CMD and r_pl:
                        sock.sendto(self._make_enc_ack(r_seq), (self._ip, self._port))
                        key_d = self._rotate(self._enc_in,  r_seq & 0xF)
                        iv_d  = self._rotate(self._enc_out, (r_seq >> 4) & 0xF)
                        dec   = self._aes_dec_pkcs7(key_d, iv_d, r_pl)
                        if dec and dec[0] == r_seq:
                            content = dec[1:]
                            if content and content[0] != 0x00:
                                frames.append((content[0], content[1:]))
                except socket.timeout:
                    break
            return frames if frames else None
        except Exception as e:
            log.error(f"Bojler session_read: {e}")
        finally:
            sock.close()
        return None

    def _session_send(self, cmds: list) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(6.0)
        try:
            if not self._handshake(sock):
                return False
            sock.settimeout(1.0)
            for cmd_bytes in cmds:
                seq   = self._seq_next()
                key_e = self._rotate(self._enc_out, seq & 0xF)
                iv_e  = self._rotate(self._enc_in,  (seq >> 4) & 0xF)
                enc   = self._aes_enc_pkcs7(key_e, iv_e, bytes([seq]) + cmd_bytes)
                sock.sendto(self._make_frame(seq, FRAME_CMD, enc),
                            (self._ip, self._port))
                for _ in range(10):
                    try:
                        resp = sock.recvfrom(4096)[0]
                        r_seq, r_type, r_pl = self._parse_frame(resp)
                        if r_type == FRAME_ACK:
                            break
                        if r_type == FRAME_CMD and r_pl:
                            sock.sendto(self._make_enc_ack(r_seq),
                                        (self._ip, self._port))
                            break
                    except socket.timeout:
                        break
            return True
        except Exception as e:
            log.error(f"Bojler session_send: {e}")
        finally:
            sock.close()
        return False

    # ── Parsowanie ────────────────────────────────────────────

    def _parse_all(self, frames: list) -> dict:
        s = {"online": True, "ts": datetime.now().isoformat(),
             "power": False, "heating": False, "mode": 0,
             "temp_current": 0, "temp_target": 0, "power_level": 0}
        for cmd, payload in frames:
            if cmd == 0x91 and len(payload) >= 2:
                flags      = payload[1]
                s["power"] = bool(flags & 0x01)
                s["mode"]  = (flags >> 2) & 0x07
            elif cmd == 0x14 and len(payload) >= 1:
                s["temp_current"] = payload[0]
            elif cmd == 0x02 and len(payload) >= 1:
                s["temp_target"]  = payload[0]
            elif cmd == 0x01 and len(payload) >= 1:
                val = payload[0]
                if val >= 1:
                    s["power"]       = True
                    s["power_level"] = val
        s["mode_name"] = MODE_NAMES.get(s["mode"], "normal")
        s["power_w"]   = POWER_LEVEL_TO_W.get(s["power_level"], 0)
        s["heating"]   = (s["power"] and s["temp_current"] > 0
                          and s["temp_current"] < s["temp_target"])
        return s

    # ══════════════════════════════════════════════════════════
    # PUBLICZNE API
    # ══════════════════════════════════════════════════════════

    def get_status(self) -> Optional[dict]:
        for attempt in range(1, self._retry + 1):
            frames = self._session_read()
            if frames is not None:
                return self._parse_all(frames)
            log.warning(f"Bojler get_status: próba {attempt}/{self._retry} nieudana")
            if attempt < self._retry:
                time.sleep(1)
        log.error("Bojler: wszystkie próby nieudane — odświeżam klucz mDNS")
        self.refresh_pub_key()
        return None

    def set_target(self, temp_c: int, power_w: int) -> bool:
        if not (20 <= temp_c <= 75):
            log.error(f"set_target: temp {temp_c}°C poza zakresem")
            return False
        power_level = POWER_W_TO_LEVEL.get(power_w)
        if power_level is None:
            log.error(f"set_target: nieprawidłowa moc {power_w}W")
            return False
        if self._dry_run:
            log.info(f"[DRY RUN] set_target: {temp_c}°C {power_w}W")
            return True

        pwr_byte = power_level if power_w > 0 else 0
        self._last_pwr_byte = pwr_byte
        cmds = ([bytes([0x01, 0x00])] if power_w == 0
                else [bytes([0x02, temp_c & 0xFF, 0x00]), bytes([0x01, pwr_byte])])

        for attempt in range(1, self._retry + 1):
            if self._session_send(cmds):
                log.info(f"Bojler set_target: {temp_c}°C {power_w}W OK")
                return True
            log.warning(f"Bojler set_target: próba {attempt}/{self._retry}")
            if attempt < self._retry:
                time.sleep(1)
        log.error("Bojler set_target: wszystkie próby nieudane")
        return False

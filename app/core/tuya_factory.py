"""Wybór backendu Tuya: „cloud” (stary IoT Core, wymaga projektu deweloperskiego)
albo „sharing” (Device Sharing przez konto Smart Life — bez IoT Core i bez kwoty)."""

import os

from core.tuya_client import TuyaClient


def backend(cfg: dict) -> str:
    """tuya_backend: "sharing" | "cloud" | "auto" (domyślnie: sharing, jeśli istnieje plik sesji QR)."""
    b = cfg.get("tuya_backend", "auto")
    if b == "auto":
        return "sharing" if os.path.isfile(cfg.get("tuya_session_file") or "") else "cloud"
    return "sharing" if b == "sharing" else "cloud"


def configured(cfg: dict, device_id: str) -> bool:
    """Czy mamy komplet danych, żeby w ogóle tworzyć klienta."""
    if not device_id:
        return False
    if backend(cfg) == "sharing":
        return bool(cfg.get("tuya_session_file"))
    return bool(cfg.get("tuya_client_id"))


def make_client(cfg: dict, device_id: str):
    if backend(cfg) == "sharing":
        from core.tuya_sharing_client import TuyaSharingClient
        return TuyaSharingClient(cfg["tuya_session_file"], device_id)
    return TuyaClient(
        client_id=cfg.get("tuya_client_id", ""),
        client_secret=cfg.get("tuya_client_secret", ""),
        device_id=device_id,
        region=cfg.get("tuya_api_region", "eu"),
    )

"""
config_reader.py — Modul pembaca konfigurasi bot KRS.
Membaca config.txt (format Indonesia) dengan fallback ke .env.
"""
import os
import base64

# Mapping dari key Indonesia (config.txt) ke key internal
_KEY_MAP = {
    "EMAIL_PENGIRIM": "SENDER_EMAIL",
    "PASSWORD_PENGIRIM": "SENDER_PASSWORD",
    "EMAIL_PENERIMA": "RECEIVER_EMAIL",
    "TARGET_MATKUL": "TARGET_COURSES",
    "JEDA_CEK": "CHECK_INTERVAL_SECONDS",
    # Key .env / internal langsung di-pass through
    "SMTP_SERVER": "SMTP_SERVER",
    "SMTP_PORT": "SMTP_PORT",
    "SENDER_EMAIL": "SENDER_EMAIL",
    "SENDER_PASSWORD": "SENDER_PASSWORD",
    "RECEIVER_EMAIL": "RECEIVER_EMAIL",
    "TARGET_COURSES": "TARGET_COURSES",
    "TARGET_COURSE_CODES": "TARGET_COURSES",
    "CHECK_INTERVAL_SECONDS": "CHECK_INTERVAL_SECONDS",
}

_config = {}

def _load_file(filepath):
    """Parse file KEY=VALUE, abaikan komentar dan baris kosong."""
    if not os.path.exists(filepath):
        return {}
    result = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Map ke internal key jika ada di mapping
            internal_key = _KEY_MAP.get(key, key)
            if value:  # Hanya simpan jika ada nilainya
                result[internal_key] = value
    return result

def load_config():
    """
    Muat konfigurasi. Prioritas:
    1. config.txt (format Indonesia, untuk distribusi)
    2. .env (format developer, untuk Gilang)
    """
    global _config
    _config = {}

    # Defaults
    _config["SMTP_SERVER"] = "smtp.gmail.com"
    _config["SMTP_PORT"] = "587"
    _config["CHECK_INTERVAL_SECONDS"] = "30"

    # Coba baca .env dulu sebagai base
    env_path = os.path.join(os.getcwd(), ".env")
    _config.update(_load_file(env_path))

    # config.txt menimpa .env jika ada (cek di root maupun di folder windows/)
    for cfg_name in ["config.txt", os.path.join("windows", "config.txt")]:
        config_path = os.path.join(os.getcwd(), cfg_name)
        if os.path.exists(config_path):
            _config.update(_load_file(config_path))

    return _config

def get(key, default=None):
    """Ambil nilai konfigurasi."""
    if not _config:
        load_config()
    return _config.get(key, default)

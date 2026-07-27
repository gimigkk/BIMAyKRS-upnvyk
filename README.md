# BIMAyKRS for UPNVY

Bot otomatis pemantau dan eksekutor (Auto-Enroll) KRS portal BIMA UPN "Veteran" Yogyakarta.

## 🚀 Fitur Utama

- **Smart Scraper & Auto-Enroll**: Memantau ketersediaan slot KRS dan otomatis mengambil kelas target berdasarkan urutan prioritas.
- **Persistent Session**: Menggunakan browser context lokal untuk menjaga sesi login tanpa perlu re-login.
- **Smart DOM & SPA Support**: Mendukung rendering SPA (React/Vue) dengan penanganan `networkidle` dan elemen UI modern (Radix UI / Shadcn).
- **Anti Server-Down & Session Logout**: Deteksi otomatis saat sesi ter-logout atau server kampus mengalami *Internal Server Error (500)*.
- **Notifikasi Email & Desktop**: Peringatan otomatis jika slot dibuka atau jika terjadi error sistem.

## 📂 Struktur Proyek

```
BotKrs/
├── main.py              # Logic utama bot KRS (scraping & clicker)
├── config_reader.py     # Parser konfigurasi (.env dan config.txt)
├── notifier.py          # Modul notifikasi email & desktop
├── utils.py             # Utilitas bersama (Colors, helper)
├── requirements.txt     # Dependensi Python
├── windows/             # Paket & skrip otomatisasi untuk Windows
│   ├── INSTALL.bat
│   ├── MULAI.bat
│   ├── config.txt
│   ├── Cara Isi Config.txt
│   └── README.txt
└── tests/               # Unit test suite (Pytest & Playwright)
```

## 🛠️ Penggunaan (Developer / Linux / macOS)

1. **Instalasi Dependensi**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Konfigurasi Environment**:
   Salin `.env.example` ke `.env` dan atur variabel target:
   ```env
   TARGET_COURSES=142240283:EA-C, 142240283:EA-B, 142240373:EA-A
   CHECK_INTERVAL_SECONDS=10
   ```

3. **Jalankan Bot**:
   ```bash
   python main.py
   ```

## 🪟 Penggunaan (Pengguna Windows / Non-Teknis)

Lihat dokumentasi panduan lengkap di folder [`windows/README.txt`](windows/README.txt) atau jalankan `windows/INSTALL.bat` kemudian `windows/MULAI.bat`.

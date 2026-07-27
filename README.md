# 🤖 BIMAyKRS for UPNVY

Bot otomatis pemantau dan eksekutor (*Auto-Enroll*) KRS portal BIMA UPN "Veteran" Yogyakarta.

---

## 🚀 Fitur Utama

- **Smart Scraper & Priority Auto-Enroll**: Memantau ketersediaan slot KRS dan otomatis mengeksekusi kelas target berdasarkan hirarki prioritas yang Anda atur.
- **Support UI Modern (Radix UI / Shadcn)**: Menggunakan JavaScript DOM evaluation untuk mengeklik elemen `<button role="checkbox">` secara presisi tanpa terhalang CSS overlay.
- **Persistent Session**: Menggunakan *browser context* lokal (`browser_data/`) untuk mempertahankan sesi login tanpa harus berulang kali menyelesaikan Captcha.
- **Resilient & Anti Spam Error**: Memiliki sistem pendeteksi otomatis saat sesi ter-logout atau server kampus mengalami *Internal Server Error (500/502/503)*. Notifikasi email error hanya terkirim sekali hingga sistem pulih kembali.
- **Notifikasi Multi-Channel**: Peringatan instan via Email (SMTP) dan Notifikasi Desktop lokal jika slot dibuka atau jika terjadi error sistem.

---

## 📂 Struktur Proyek

```
BotKrs/
├── main.py              # Logika utama bot KRS (scraping, priority check & clicker)
├── config_reader.py     # Parser konfigurasi (.env dan config.txt)
├── notifier.py          # Modul notifikasi Email & Desktop
├── utils.py             # Utilitas bersama (Colors, terminal helper)
├── requirements.txt     # Dependensi Python & Playwright
├── .env.example         # Template variabel lingkungan
├── .gitignore           # Menjaga file rahasia & build lokal agar tidak ter-push
├── windows/             # Skrip khusus Windows (Di-ignore dari git, dibundel di Zip)
│   ├── INSTALL.bat
│   ├── MULAI.bat
│   ├── config.txt
│   ├── Cara Isi Config.txt
│   └── README.txt
└── tests/               # Unit test suite (Pytest & Playwright)
    └── test_check_slots.py
```

---

## 🛠️ Penggunaan (Developer / Linux / macOS)

### 1. Instalasi Dependensi
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Konfigurasi Environment
Salin `.env.example` menjadi `.env`:
```bash
cp .env.example .env
```
Edit `.env` sesuai kebutuhan target Anda:
```env
# Email Notifikasi (Opsional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=email_kamu@gmail.com
SENDER_PASSWORD=app_password_gmail
RECEIVER_EMAIL=email_tujuan@gmail.com

# Target Matkul (Format: KODE_MATKUL:KELAS_PRIORITAS_1, KODE_MATKUL:KELAS_PRIORITAS_2)
TARGET_COURSES=142240283:EA-C, 142240283:EA-B, 142240373:EA-A
CHECK_INTERVAL_SECONDS=10
```

### 3. Jalankan Bot
```bash
python main.py
```

---

## 🧪 Menguji Skenario (Unit Testing)

Proyek ini dilengkapi dengan 19 skenario pengujian otomatis menggunakan Pytest & Playwright:

```bash
source venv/bin/activate
pytest tests/test_check_slots.py -v
```

---

## 📦 Membangun Paket Distribusi Windows (Zip)

Untuk membundel aplikasi bagi pengguna Windows non-teknis tanpa menyertakan kredensial di repository Git:

```bash
zip -j BotKRS_Untuk_Teman.zip main.py notifier.py config_reader.py utils.py requirements.txt windows/*
```

Hasil zip (`BotKRS_Untuk_Teman.zip`) berisi file installer otomatis dan konfigurasi default yang siap langsung dipakai.

---

## 🪟 Penggunaan (Pengguna Windows / Non-Teknis)

Untuk pengguna Windows yang menerima paket distribusi zip:
1. Ekstrak `BotKRS_Untuk_Teman.zip`.
2. Klik ganda **`INSTALL.bat`** (hanya sekali saat pertama kali).
3. Isi data target mata kuliah pada file **`config.txt`**.
4. Klik ganda **`MULAI.bat`** untuk menjalankan bot.

# BIMAyKRS for UPNVY

Automated KRS monitoring and auto-enrollment bot for BIMA portal at UPN "Veteran" Yogyakarta.

## Features

- **Priority Auto-Enroll**: Monitors course slot availability and automatically enrolls based on defined priority rankings.
- **Radix UI Checkbox Support**: Injects JavaScript click events to interact with `<button role="checkbox">` elements cleanly.
- **Persistent Sessions**: Reuses browser context (`browser_data/`) to maintain login state and minimize CAPTCHAs.
- **Resilient Error Handling**: Detects session expiration and HTTP 500/502/503 server errors with anti-spam alert mechanisms.
- **Multi-channel Notifications**: Sends instant alerts via SMTP email and desktop notification upon slot detection or system errors.

## Repository Structure

```
BotKrs/
├── main.py              # Main monitoring and enrollment loop
├── config_reader.py     # Configuration loader (.env & config.txt)
├── notifier.py          # SMTP & desktop notification handler
├── utils.py             # Shared utilities and color formatting
├── requirements.txt     # Python dependencies
├── .env.example         # Template environment variables
├── .gitignore           # Git ignore rules
└── tests/               # Unit test suite
    └── test_check_slots.py
```

## Quick Start

### 1. Installation
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Configuration
Copy `.env.example` to `.env` and set your target courses:
```bash
cp .env.example .env
```
Example `.env`:
```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password
RECEIVER_EMAIL=your_email@gmail.com

CHECK_INTERVAL_SECONDS=10
TARGET_COURSES=142240283:EA-C, 142240283:EA-B
```

### 3. Usage
```bash
python main.py
```

## Testing

Run unit tests:
```bash
source venv/bin/activate
pytest tests/test_check_slots.py -v
```

## Windows Distribution

For non-technical Windows users, download `BotKRS_Untuk_Teman.zip`:
1. Extract `BotKRS_Untuk_Teman.zip`.
2. Double-click `INSTALL.bat` (first-time setup).
3. Fill in target courses in `config.txt`.
4. Double-click `MULAI.bat` to run.

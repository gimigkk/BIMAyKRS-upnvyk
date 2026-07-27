import smtplib
import time
import subprocess
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config_reader import get as cfg
from utils import Colors

SMTP_SERVER = cfg("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(cfg("SMTP_PORT", "587"))
SENDER_EMAIL = cfg("SENDER_EMAIL")
SENDER_PASSWORD = cfg("SENDER_PASSWORD")
RECEIVER_EMAIL = cfg("RECEIVER_EMAIL")

def send_notification(course_code: str, total_slots: int, enrolled_class: Optional[str] = None) -> bool:
    """Mengirim email notifikasi jika slot tersedia atau berhasil diambil."""
    if not all([SENDER_EMAIL, SENDER_PASSWORD, RECEIVER_EMAIL]):
        print(f"{Colors.RED}[ERROR]{Colors.RESET} Kredensial email belum lengkap di .env. Notifikasi tidak dikirim.")
        return False

    receivers = [email.strip() for email in RECEIVER_EMAIL.split(",") if email.strip()]
    if not receivers:
        print(f"  > {Colors.YELLOW}[INFO]{Colors.RESET} Notifikasi email dinonaktifkan.")
        return False

    title = "SLOT KOSONG TERSEDIA!"
    color = "#ff0000" # Merah
    slot_text = "Sisa Slot Saat Ini:"
    slot_value = str(total_slots)
    subject_msg = f"SLOT KOSONG TERSEDIA: {course_code}"

    if enrolled_class:
        subtext = "Segera login ke BIMA KRP untuk mengambil kelas!"
        notif_msg = "🚨 SLOT KOSONG + AUTO-ENROLL SUKSES"
    else:
        subtext = "Segera login ke BIMA KRP untuk mengambil kelas!"
        notif_msg = "🚨 SLOT KOSONG KRS"

    # Kirim notifikasi desktop (Linux)
    try:
        subprocess.run(["notify-send", "-u", "critical", notif_msg, f"{course_code}: {slot_value}"], check=False)
    except Exception as e:
        pass

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = ", ".join(receivers)
    msg['Subject'] = subject_msg

    html_body = f"""\
    <html>
      <body style="font-family: Arial, sans-serif; text-align: center; padding: 20px;">
        <h2 style="color: {color};">{title}</h2>
        <p>Mata Kuliah: <strong>{course_code}</strong></p>
        <hr style="border: 1px solid #ddd; margin: 20px 0;">
        <p style="font-size: 18px; color: #555;">{slot_text}</p>
        <h1 style="font-size: 72px; color: {color}; margin: 10px 0;">{slot_value}</h1>
        <p style="margin-top: 30px; font-size: 16px;">{subtext}</p>
      </body>
    </html>
    """
    msg.attach(MIMEText(html_body, 'html'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        
        text = msg.as_string()
        server.sendmail(SENDER_EMAIL, receivers, text)
        print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} Email notifikasi berhasil dikirim ke: {', '.join(receivers)}")
            
        server.quit()
        return True
    except Exception as e:
        print(f"{Colors.RED}[ERROR]{Colors.RESET} Gagal mengirim email: {e}")
        return False

def send_error_warning(error_msg):
    """Mengirim email peringatan jika bot mengalami kegagalan."""
    if not all([SENDER_EMAIL, SENDER_PASSWORD, RECEIVER_EMAIL]):
        return False

    receivers = [email.strip() for email in RECEIVER_EMAIL.split(",") if email.strip()]
    if not receivers:
        return False

    # Kirim notifikasi desktop (Linux)
    try:
        subprocess.run(["notify-send", "-u", "critical", "❌ BOT KRS ERROR", str(error_msg)], check=False)
    except Exception as e:
        pass

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = ", ".join(receivers)
    msg['Subject'] = "[URGENT] Bot KRS Terhenti/Error!"

    body = f"Peringatan! Bot KRS mengalami kegagalan dan kemungkinan terhenti atau tersangkut.\n\nSegera cek laptop Anda.\n\nDetail Error:\n{error_msg}"
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        
        text = msg.as_string()
        server.sendmail(SENDER_EMAIL, receivers, text)
        print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} Email peringatan error dikirim ke: {', '.join(receivers)}")
            
        server.quit()
        return True
    except Exception as e:
        print(f"{Colors.RED}[ERROR]{Colors.RESET} Gagal mengirim email peringatan: {e}")
        return False

if __name__ == "__main__":
    print(f"{Colors.YELLOW}[INFO]{Colors.RESET} Mengetes pengiriman email...")
    send_notification("TEST-COURSE", "Ini adalah pesan percobaan.")

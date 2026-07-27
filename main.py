import os
import random
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from playwright.sync_api import Page, sync_playwright

from config_reader import get as cfg, load_config
from notifier import send_error_warning, send_notification
from utils import Colors

load_config()

TARGET_COURSES_RAW = cfg("TARGET_COURSES", "")
CHECK_INTERVAL = int(cfg("CHECK_INTERVAL_SECONDS", "60"))

def parse_targets(raw_targets: str) -> Dict[str, List[Optional[str]]]:
    """Mengubah string konfigurasi target menjadi dictionary prioritas per matkul."""
    targets: Dict[str, List[Optional[str]]] = {}
    for item in raw_targets.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            code, kelas = item.split(":", 1)
            code, kelas = code.strip(), kelas.strip()
            if code not in targets:
                targets[code] = []
            targets[code].append(kelas)
        else:
            code = item.strip()
            if code not in targets:
                targets[code] = []
            targets[code].append(None)
    return targets

def check_slots(page: Page, course_code: str, target_kelas_list: List[Optional[str]]) -> Tuple[int, str, bool, Optional[str]]:
    """
    Mengecek slot untuk mata kuliah tertentu dan melakukan klik otomatis jika sesuai target.
    
    Returns:
        Tuple berisi (total_slots, course_name, enrolled_successfully, enrolled_class)
    """
    course_name = course_code
    enrolled_successfully = False
    enrolled_class = None
    try:
        course_btn = page.get_by_text(course_code, exact=True).first
        
        try:
            course_btn.wait_for(state="visible", timeout=5000)
        except Exception:
            if "login" in page.url.lower():
                raise Exception("Sesi berakhir! Anda telah ter-logout dari portal.")
            print(f"{Colors.YELLOW}[WARN]{Colors.RESET} Kode mata kuliah '{course_code}' tidak ditemukan di halaman.")
            return 0, course_name, False, None

        btn_parent = course_btn.locator("xpath=ancestor::button").first
        if btn_parent.count() > 0:
            full_text = btn_parent.inner_text().strip()
            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
            
            if len(lines) >= 2:
                # Jika baris pertama persis sama dengan kode matkul, baris kedua biasanya namanya
                if lines[0] == course_code:
                    course_name = lines[1]
                elif " - " in lines[0]:
                    course_name = lines[0].split(" - ", 1)[1].strip()
                else:
                    course_name = lines[0]
            elif len(lines) == 1:
                if " - " in lines[0]:
                    course_name = lines[0].split(" - ", 1)[1].strip()
                else:
                    course_name = lines[0]
            
            print(f"  > Matkul: {Colors.CYAN}{course_name}{Colors.RESET}")

            if btn_parent.get_attribute("aria-expanded") == "false":
                course_btn.click()

        # Dapatkan elemen pembungkus terdekat yang mengandung tabel (beradaptasi dengan berbagai struktur HTML)
        course_container = btn_parent.locator("xpath=ancestor::*[.//tbody][1]")
        
        # SELALU tunggu sampai data tabel benar-benar terlihat dan tidak kosong (menghindari scraping saat skeleton loader)
        try:
            course_container.locator("tbody tr td").first.wait_for(state="visible", timeout=10000)
            page.wait_for_timeout(800)  # Extra buffer untuk memastikan text di dalam <td> sudah ter-render oleh React/Vue
        except Exception:
            page.wait_for_timeout(3000)

        rows = course_container.locator("tbody tr").all()
        if not rows:
            print(f"{Colors.YELLOW}[WARN]{Colors.RESET} Tabel kelas tidak muncul. Pastikan matkul {course_code} memiliki kelas.")
            return 0, course_name, False, None

        total_slots = 0
        is_monitoring_only = (not target_kelas_list) or (target_kelas_list == [None])
        available_classes = {}

        for row in rows:
            tds = row.locator("td").all()
            if len(tds) >= 6:
                kelas = tds[1].inner_text().strip()
                sisa_text = tds[5].inner_text().strip()
                
                # Skip baris yang masih loading (kosong)
                if not kelas:
                    continue
                
                is_target_match = (not is_monitoring_only) and (kelas in target_kelas_list)
                match_marker = "*" if is_target_match else " "
                
                print(f"  {match_marker}> Kelas: {kelas} | Sisa slot: {Colors.BOLD}{sisa_text}{Colors.RESET}")
                
                if sisa_text.isdigit() and int(sisa_text) > 0:
                    if is_monitoring_only or is_target_match:
                        total_slots += int(sisa_text)
                    if is_target_match:
                        available_classes[kelas] = row

        # Eksekusi Prioritas
        if not is_monitoring_only and not enrolled_successfully:
            for priority_kelas in target_kelas_list:
                if priority_kelas in available_classes:
                    try:
                        print(f"    {Colors.YELLOW}[ACTION]{Colors.RESET} Prioritas ditemukan! Mencoba auto-enroll kelas {priority_kelas}...")
                        checkbox = available_classes[priority_kelas].locator("button[role='checkbox']").first
                        if checkbox.count() > 0:
                            # Eksekusi JS click agar terhindar dari error 'Element is intercepted' oleh CSS overlay
                            checkbox.evaluate("el => el.click()")
                            page.wait_for_timeout(2000)
                            enrolled_successfully = True
                            enrolled_class = priority_kelas
                            print(f"    {Colors.GREEN}[SUCCESS]{Colors.RESET} Berhasil mencentang checkbox untuk kelas {priority_kelas}!")
                            break # Hentikan eksekusi, cukup ambil 1 kelas saja
                        else:
                            print(f"    {Colors.RED}[FAILED]{Colors.RESET} Tidak menemukan checkbox di baris ini.")
                    except Exception as e:
                        print(f"    {Colors.RED}[FAILED]{Colors.RESET} Error saat auto-enroll: {e}")
                            
        return total_slots, course_name, enrolled_successfully, enrolled_class
        
    except Exception as e:
        print(f"{Colors.RED}[ERROR]{Colors.RESET} Terjadi kesalahan saat mengecek DOM: {e}")
        raise e

def main():
    targets_by_code = parse_targets(TARGET_COURSES_RAW)
    if not targets_by_code:
        print(f"{Colors.RED}[ERROR]{Colors.RESET} Tidak ada kode mata kuliah yang diatur di TARGET_COURSES.")
        return

    print(f"{Colors.CYAN}[START]{Colors.RESET} Memulai BIMAyKRS for UPNVY (Headed Browser) - Total Target: {len(targets_by_code)} Matkul")
    
    USER_DATA_DIR = os.path.join(os.getcwd(), "browser_data")
    
    with sync_playwright() as p:
        # Menggunakan persistent context agar cookies & history tersimpan (seperti browser biasa)
        # Ini akan sangat membantu mengurangi/menghilangkan Captcha yang berulang.
        # Di Windows, gunakan Microsoft Edge bawaan (channel="msedge") agar teman tidak perlu download Chromium.
        # Fallback ke Chromium standar jika msedge tidak ditemukan.
        launch_kwargs = {
            "user_data_dir": USER_DATA_DIR,
            "headless": False,
            "no_viewport": True
        }
        try:
            context = p.chromium.launch_persistent_context(**launch_kwargs, channel="msedge")
        except Exception:
            context = p.chromium.launch_persistent_context(**launch_kwargs)
            
        page = context.pages[0] if context.pages else context.new_page()
        
        # Auto-accept all dialogs/alerts automatically (menghindari stuck di pop-up konfirmasi)
        page.on("dialog", lambda dialog: dialog.accept())
        
        page.goto("https://bima.upnyk.ac.id")
        
        print("\n========================================================")
        print("1. Jendela browser telah terbuka.")
        print("2. Silakan LOGIN secara manual (selesaikan Captcha jika ada).")
        print("3. Navigasikan ke halaman 'Pengajuan KRP'.")
        print("========================================================\n")
        input(f"{Colors.BOLD}TEKAN ENTER DI SINI (TERMINAL) JIKA ANDA SUDAH SIAP DI HALAMAN PENGAJUAN KRP... {Colors.RESET}")
        
        last_slot_count = {}
        enrolled_status = {}
        error_notified = False

        while True:
            print(f"\n{Colors.BLUE}[{datetime.now().strftime('%H:%M:%S')}]{Colors.RESET} Merefresh halaman dan mengecek ketersediaan...")
            
            try:
                page.reload(wait_until="domcontentloaded")
                try:
                    # Smart wait: Tunggu aktivitas jaringan selesai (SPA render)
                    page.wait_for_load_state("networkidle", timeout=5000)
                except:
                    pass
                
                # Deteksi jika server kampus sedang down/error
                if page.get_by_text("Internal Server Error", exact=False).count() > 0 or \
                   page.get_by_text("Bad Gateway", exact=False).count() > 0 or \
                   page.get_by_text("Service Unavailable", exact=False).count() > 0:
                    raise Exception("Server kampus sedang down (Internal Server Error / Bad Gateway).")
                
                
                for target_code, target_kelas_list in targets_by_code.items():
                    current_enrolled = enrolled_status.get(target_code, None)
                    
                    # Filter target yang masih diburu (harus lebih tinggi prioritasnya dari yang sekarang)
                    active_targets = target_kelas_list
                    if current_enrolled and current_enrolled in target_kelas_list:
                        idx = target_kelas_list.index(current_enrolled)
                        active_targets = target_kelas_list[:idx]
                        
                    log_text = f"Mengecek: {target_code}"
                    if active_targets and active_targets != [None]:
                        log_text += f" (Memburu: {' > '.join(active_targets)})"
                    elif current_enrolled:
                        log_text += f" (Sudah aman di kelas {current_enrolled})"
                    print(f"\n{Colors.CYAN}[CHECK]{Colors.RESET} {log_text}")
                    
                    total_slots, course_name, enrolled, enrolled_class = check_slots(page, target_code, active_targets)
                    
                    display_name = f"{target_code} - {course_name}" if course_name != target_code else target_code
                    
                    if enrolled:
                        # Pesan khusus jika ini adalah aksi "Pindah Kelas" ke prioritas lebih tinggi
                        if current_enrolled:
                            send_notification(display_name, total_slots, enrolled_class=f"{enrolled_class} (PINDAH dari {current_enrolled})")
                        else:
                            send_notification(display_name, total_slots, enrolled_class=enrolled_class)
                            
                        # Update status memori bot ke kelas yang baru
                        enrolled_status[target_code] = enrolled_class
                        
                        # Sync snapshot slot agar tidak mengirim email ganda di iterasi berikutnya
                        last_slot_count[target_code] = total_slots
                        
                    elif total_slots > 0:
                        print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} TOTAL {total_slots} SLOT KOSONG DITEMUKAN UNTUK {display_name}!")
                        
                        previous_slots = last_slot_count.get(target_code, 0)
                        if total_slots != previous_slots:
                            send_notification(display_name, total_slots)
                            last_slot_count[target_code] = total_slots
                        else:
                            print(f"{Colors.YELLOW}[INFO]{Colors.RESET} (Slot tidak berubah dari sebelumnya ({total_slots}). Skip spam email.)")
                    else:
                        if last_slot_count.get(target_code, 0) > 0:
                            last_slot_count[target_code] = 0
                            print(f"{Colors.YELLOW}[INFO]{Colors.RESET} (Slot untuk {display_name} telah habis kembali.)")
                            
                # Jika seluruh loop pengecekan matkul berhasil tanpa crash, reset status error
                if error_notified:
                    error_notified = False
                
            except Exception as e:
                print(f"{Colors.RED}[ERROR]{Colors.RESET} Terjadi kesalahan: {e}")
                if not error_notified:
                    send_error_warning(str(e))
                    error_notified = True
                
            jitter = random.uniform(-5, 5)
            sleep_time = int(max(5, CHECK_INTERVAL + jitter))
            
            # Countdown loop with carriage return replacement
            print() # Print empty line before countdown
            for remaining in range(sleep_time, 0, -1):
                sys.stdout.write(f"\r{Colors.YELLOW}[WAIT]{Colors.RESET} Menunggu {remaining:02d} detik sebelum pengecekan berikutnya... ")
                sys.stdout.flush()
                time.sleep(1)
            sys.stdout.write(f"\r{' ' * 80}\r") # Clear line completely
            sys.stdout.flush()

if __name__ == "__main__":
    main()

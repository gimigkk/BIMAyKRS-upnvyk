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

def safe_reload_page(page: Page, target_codes: Optional[List[str]] = None, max_retries: int = 3) -> Tuple[bool, bool]:
    """
    Me-refresh halaman BIMA dan menangani:
    1. Error transient API / JS crash toast ('Cannot read properties of undefined (reading data)') -> Quick retries (max 3x).
    2. Server 5xx / Network error -> Langsung bypass quick retries dan beralih ke mode Server Down (10s).
    
    Returns:
        Tuple[bool, bool]: (is_loaded, is_server_down)
    """
    for attempt in range(1, max_retries + 1):
        try:
            page.reload(wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=4000)
            except Exception:
                pass

            # Deteksi jika ter-logout / terlempar ke halaman login
            if "login" in page.url.lower():
                raise Exception("Sesi berakhir! Anda telah ter-logout dari portal. Silakan login kembali di browser.")

            # Deteksi jika server kampus sedang down / error 500/502/503/504
            if page.get_by_text("Internal Server Error", exact=False).count() > 0 or \
               page.get_by_text("Bad Gateway", exact=False).count() > 0 or \
               page.get_by_text("Service Unavailable", exact=False).count() > 0 or \
               page.get_by_text("Gateway Time-out", exact=False).count() > 0 or \
               page.get_by_text("Gateway Timeout", exact=False).count() > 0:
                return False, True

            # 1. Deteksi error JS toast khas BIMA: 'Cannot read properties of undefined (reading 'data')'
            has_js_error = (
                page.get_by_text("reading 'data'", exact=False).count() > 0 or
                page.get_by_text("Cannot read properties of undefined", exact=False).count() > 0
            )

            # 2. Deteksi silent API load failure (daftar matkul tidak kunjung ter-render di DOM)
            has_rendered_courses = False
            if target_codes:
                # Berikan buffer waktu hingga 3-4 detik untuk memastikan React/Vue selesai merender elemen
                for _ in range(4):
                    for code in target_codes:
                        if page.get_by_text(code, exact=True).count() > 0:
                            has_rendered_courses = True
                            break
                    if has_rendered_courses:
                        break
                    page.wait_for_timeout(800)
            else:
                has_rendered_courses = True

            if has_js_error or not has_rendered_courses:
                reason = "error API ('reading data')" if has_js_error else "daftar matkul kosong / gantung (silent API load failure)"
                if attempt < max_retries:
                    print(f"{Colors.YELLOW}[RETRY]{Colors.RESET} Terdeteksi {reason}. Refresh ulang otomatis ({attempt}/{max_retries})...")
                    page.wait_for_timeout(2000)
                    continue
                else:
                    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {reason.capitalize()} masih terjadi setelah {max_retries}x percobaan reload.")
                    return False, False

            # Jika data terload sempurna
            return True, False
        except Exception as e:
            err_msg = str(e)
            if "sesi berakhir" in err_msg.lower() or "logout" in err_msg.lower():
                raise e

            is_net_error = any(k in err_msg for k in ["ERR_ABORTED", "ERR_CONNECTION", "Timeout", "502", "500", "503", "504", "down"])
            
            if is_net_error:
                return False, True
            else:
                if attempt == max_retries:
                    raise e
                print(f"{Colors.YELLOW}[RETRY]{Colors.RESET} Reload gagal ({err_msg}). Mencoba lagi ({attempt}/{max_retries})...")
                page.wait_for_timeout(2000)
            
    return False, False

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
        
        # Buka BIMA dengan retry otomatis jika server kampus sedang down/timeout saat pertama kali dinyalakan
        while True:
            try:
                page.goto("https://bima.upnyk.ac.id", wait_until="domcontentloaded", timeout=15000)
                break
            except Exception as e:
                print(f"{Colors.YELLOW}[WARN]{Colors.RESET} Gagal membuka bima.upnyk.ac.id ({e}). Server kampus mungkin sedang down/timeout. Mencoba lagi dalam 5 detik...")
                time.sleep(5)
        
        print("\n========================================================")
        print("1. Jendela browser telah terbuka.")
        print("2. Silakan LOGIN secara manual (selesaikan Captcha jika ada).")
        print("3. Navigasikan ke halaman 'Pengajuan KRP'.")
        print("========================================================\n")
        input(f"{Colors.BOLD}TEKAN ENTER DI SINI (TERMINAL) JIKA ANDA SUDAH SIAP DI HALAMAN PENGAJUAN KRP... {Colors.RESET}")
        
        last_slot_count = {}
        enrolled_status = {}
        error_notified = False
        downtime_start_time = None

        while True:
            is_server_down_mode = False
            
            try:
                is_loaded, is_server_down = safe_reload_page(page, target_codes=list(targets_by_code.keys()), max_retries=3)
                is_server_down_mode = is_server_down
                
                if is_server_down:
                    if downtime_start_time is None:
                        downtime_start_time = datetime.now().strftime('%H:%M:%S')
                elif not is_loaded:
                    print(f"\n{Colors.BLUE}[{datetime.now().strftime('%H:%M:%S')}]{Colors.RESET} Merefresh halaman dan mengecek ketersediaan...")
                    print(f"{Colors.YELLOW}[SKIP]{Colors.RESET} Melewati pengecekan matkul pada iterasi ini karena data halaman gagal dimuat.")
                else:
                    if downtime_start_time is not None:
                        rec_time = datetime.now().strftime('%H:%M:%S')
                        sys.stdout.write(f"\r{' ' * 100}\r")
                        print(f"{Colors.GREEN}[RECOVERED {rec_time}]{Colors.RESET} Server BIMA kembali online! Downtime: {downtime_start_time} s/d {rec_time}.\n")
                        downtime_start_time = None

                    print(f"\n{Colors.BLUE}[{datetime.now().strftime('%H:%M:%S')}]{Colors.RESET} Merefresh halaman dan mengecek ketersediaan...")
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
                err_str = str(e)
                print(f"{Colors.RED}[ERROR]{Colors.RESET} Terjadi kesalahan: {err_str}")
                
                # Kirim email peringatan HANYA jika membutuhkan tindakan manusia (misal: ter-logout / butuh re-login)
                is_human_action_required = any(k in err_str.lower() for k in ["logout", "login", "sesi", "captcha", "auth"])
                
                if is_human_action_required:
                    if not error_notified:
                        send_error_warning(err_str)
                        error_notified = True
                else:
                    print(f"{Colors.YELLOW}[INFO]{Colors.RESET} Error server/jaringan transient. Email diabaikan (bot akan auto-retry).")
                
                if any(k in err_str for k in ["502", "500", "503", "504", "ERR_ABORTED", "ERR_CONNECTION", "Timeout", "down"]):
                    is_server_down_mode = True
                    if downtime_start_time is None:
                        downtime_start_time = datetime.now().strftime('%H:%M:%S')
                
            if is_server_down_mode:
                down_jitter = random.uniform(-2, 3)
                sleep_time = int(max(5, 10 + down_jitter))
            else:
                jitter = random.uniform(-1, 2)
                sleep_time = int(max(3, CHECK_INTERVAL + jitter))
            
            # Countdown loop with carriage return in-place replacement
            if not is_server_down_mode:
                print() # Print empty line before countdown in normal mode
                
            for remaining in range(sleep_time, 0, -1):
                if is_server_down_mode:
                    sys.stdout.write(f"\r\033[K{Colors.YELLOW}[STANDBY {downtime_start_time}]{Colors.RESET} Server 502 down. Retry in {remaining:02d}s... ")
                else:
                    sys.stdout.write(f"\r\033[K{Colors.YELLOW}[WAIT]{Colors.RESET} Cek ulang dalam {remaining:02d}s... ")
                sys.stdout.flush()
                time.sleep(1)
                
            sys.stdout.write("\r\033[K") # Clear line completely
            sys.stdout.flush()

if __name__ == "__main__":
    main()

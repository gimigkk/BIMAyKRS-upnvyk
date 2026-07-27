import os
import sys
import pytest
from playwright.sync_api import sync_playwright

# Masukkan folder root ke dalam sys.path agar bisa import main.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import check_slots

MOCK_HTML_PATH = f"file://{os.path.abspath(os.path.join(os.path.dirname(__file__), 'mock_krp.html'))}"

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def browser_context():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        yield context
        browser.close()

@pytest.fixture
def page(browser_context):
    page = browser_context.new_page()
    page.goto(MOCK_HTML_PATH)
    page.on("dialog", lambda dialog: dialog.accept())
    yield page
    page.close()

# ============================================================================
# HELPERS
# ============================================================================

def set_slots(page, row_id, slots):
    """Helper untuk memanipulasi DOM sisa slot di mock HTML."""
    page.evaluate(f"document.querySelector('#{row_id} .sisa').innerText = '{slots}';")

def reset_accordion(page):
    """Reset accordion ke state tertutup."""
    page.evaluate("document.getElementById('course_btn').setAttribute('aria-expanded', 'false');")
    page.evaluate("document.getElementById('course_content').style.display = 'none';")

def set_all_slots(page, a=0, b=0, c=0):
    """Set sisa slot semua kelas sekaligus + reset accordion."""
    set_slots(page, 'row-A', str(a))
    set_slots(page, 'row-B', str(b))
    set_slots(page, 'row-C', str(c))
    reset_accordion(page)

# ============================================================================
# 1. PRIORITY RANKING TESTS
# ============================================================================

class TestPriorityRanking:
    """Menguji apakah bot selalu memilih kelas sesuai urutan prioritas."""

    def test_priority_1_chosen_when_both_available(self, page):
        """EA-B (P1) dan EA-C (P2) sama-sama kosong → Bot HARUS memilih EA-B."""
        set_all_slots(page, a=0, b=3, c=1)
        total, name, enrolled, kelas = check_slots(page, "142240283", ["EA-B", "EA-C"])
        
        assert enrolled is True
        assert kelas == "EA-B"
        assert total == 4  # 3 + 1 (kedua target dijumlahkan)

    def test_priority_2_chosen_when_p1_full(self, page):
        """EA-B (P1) penuh, EA-C (P2) kosong → Bot ambil EA-C."""
        set_all_slots(page, a=0, b=0, c=5)
        total, name, enrolled, kelas = check_slots(page, "142240283", ["EA-B", "EA-C"])
        
        assert enrolled is True
        assert kelas == "EA-C"
        assert total == 5

    def test_all_three_available_picks_first(self, page):
        """EA-A, EA-B, EA-C semua kosong, prioritas [EA-B, EA-C] → pilih EA-B, ABAIKAN EA-A."""
        set_all_slots(page, a=10, b=2, c=3)
        total, name, enrolled, kelas = check_slots(page, "142240283", ["EA-B", "EA-C"])
        
        assert enrolled is True
        assert kelas == "EA-B"
        # EA-A punya slot tapi bukan target, jadi tidak dihitung
        assert total == 5  # hanya EA-B (2) + EA-C (3)

# ============================================================================
# 2. PRIORITY UPGRADE (PINDAH KELAS) TESTS
# ============================================================================

class TestPriorityUpgrade:
    """Menguji skenario bot sudah punya kelas, lalu ada kelas lebih baik."""

    def test_upgrade_from_p2_to_p1(self, page):
        """Bot sudah di EA-C, tiba-tiba EA-B kosong → Bot HARUS pindah ke EA-B."""
        set_all_slots(page, a=0, b=2, c=1)
        # Simulasi: main loop memfilter active_targets = target_kelas_list[:idx_of_EA-C]
        # target_kelas_list = ["EA-B", "EA-C"], idx EA-C = 1, active = ["EA-B"]
        active_targets = ["EA-B"]
        
        total, name, enrolled, kelas = check_slots(page, "142240283", active_targets)
        
        assert enrolled is True
        assert kelas == "EA-B"

    def test_no_upgrade_if_p1_still_full(self, page):
        """Bot sudah di EA-C, EA-B masih penuh → Bot TIDAK boleh klik apapun."""
        set_all_slots(page, a=5, b=0, c=3)
        active_targets = ["EA-B"]  # Hanya memburu EA-B
        
        total, name, enrolled, kelas = check_slots(page, "142240283", active_targets)
        
        assert enrolled is False
        assert kelas is None
        assert total == 0  # EA-B kosong, dan EA-A/EA-C bukan target aktif

    def test_already_at_top_priority(self, page):
        """Bot sudah di EA-B (P1, tertinggi) → active_targets jadi list kosong []."""
        set_all_slots(page, a=0, b=3, c=5)
        active_targets = []  # Tidak ada yang lebih tinggi dari EA-B
        
        total, name, enrolled, kelas = check_slots(page, "142240283", active_targets)
        
        # List kosong → is_monitoring_only → hanya monitor, TIDAK klik
        assert enrolled is False
        assert kelas is None

# ============================================================================
# 3. MONITORING ONLY TESTS (tanpa target kelas)
# ============================================================================

class TestMonitoringOnly:
    """Menguji mode pemantauan murni (tanpa auto-enroll)."""

    def test_monitoring_counts_all_slots(self, page):
        """Mode monitoring harus menjumlahkan SEMUA kelas yang ada slotnya."""
        set_all_slots(page, a=5, b=3, c=2)
        
        total, name, enrolled, kelas = check_slots(page, "142240283", [None])
        
        assert total == 10  # 5 + 3 + 2
        assert enrolled is False
        assert kelas is None

    def test_monitoring_with_empty_list(self, page):
        """target_kelas_list = [] juga harus jadi monitoring only."""
        set_all_slots(page, a=1, b=2, c=0)
        
        total, name, enrolled, kelas = check_slots(page, "142240283", [])
        
        assert total == 3  # 1 + 2
        assert enrolled is False

    def test_monitoring_no_slots(self, page):
        """Semua kelas penuh → total harus 0, tidak ada klik."""
        set_all_slots(page, a=0, b=0, c=0)
        
        total, name, enrolled, kelas = check_slots(page, "142240283", [None])
        
        assert total == 0
        assert enrolled is False

# ============================================================================
# 4. EDGE CASE: NON-TARGET SLOTS
# ============================================================================

class TestNonTargetSlots:
    """Menguji bahwa bot TIDAK menghitung/mengklik kelas yang bukan target."""

    def test_non_target_class_has_slots(self, page):
        """EA-A punya banyak slot, tapi kita cuma target EA-B → JANGAN ambil EA-A."""
        set_all_slots(page, a=20, b=0, c=0)
        
        total, name, enrolled, kelas = check_slots(page, "142240283", ["EA-B"])
        
        assert total == 0  # EA-A bukan target, slotnya tidak dihitung
        assert enrolled is False
        assert kelas is None

    def test_only_non_target_classes_have_slots(self, page):
        """EA-A dan EA-C kosong, tapi target hanya EA-B → Bot tidak boleh klik apapun."""
        set_all_slots(page, a=5, b=0, c=10)
        
        total, name, enrolled, kelas = check_slots(page, "142240283", ["EA-B"])
        
        assert total == 0
        assert enrolled is False

# ============================================================================
# 5. EDGE CASE: INVALID / WEIRD DATA
# ============================================================================

class TestEdgeCaseData:
    """Menguji ketahanan bot terhadap data aneh di DOM."""

    def test_non_numeric_slot_text(self, page):
        """Sisa slot berisi teks 'PENUH' bukan angka → Bot tidak boleh crash."""
        set_all_slots(page, a=0, b=0, c=0)
        set_slots(page, 'row-B', 'PENUH')
        reset_accordion(page)
        
        total, name, enrolled, kelas = check_slots(page, "142240283", ["EA-B"])
        
        assert total == 0
        assert enrolled is False

    def test_negative_slot_value(self, page):
        """Sisa slot berisi angka negatif → Bot harus abaikan."""
        set_all_slots(page, a=0, b=0, c=0)
        set_slots(page, 'row-B', '-3')
        reset_accordion(page)
        
        total, name, enrolled, kelas = check_slots(page, "142240283", ["EA-B"])
        
        assert total == 0
        assert enrolled is False

    def test_course_not_found(self, page):
        """Kode matkul tidak ada di halaman → Bot harus return gracefully, BUKAN crash."""
        total, name, enrolled, kelas = check_slots(page, "999999999", ["EA-B"])
        
        assert total == 0
        assert enrolled is False
        assert kelas is None

    def test_zero_slot_not_enrolled(self, page):
        """Slot = '0' secara eksplisit → Bot TIDAK boleh klik."""
        set_all_slots(page, a=0, b=0, c=0)
        
        total, name, enrolled, kelas = check_slots(page, "142240283", ["EA-B", "EA-C"])
        
        assert total == 0
        assert enrolled is False

# ============================================================================
# 6. COURSE NAME DETECTION TESTS
# ============================================================================

class TestCourseNameDetection:
    """Menguji apakah bot berhasil mendeteksi nama mata kuliah dari DOM."""

    def test_course_name_extracted(self, page):
        """Bot harus mendeteksi 'Advanced Excel' dari teks button accordion."""
        set_all_slots(page, a=1, b=0, c=0)
        
        total, name, enrolled, kelas = check_slots(page, "142240283", [None])
        
        assert name == "Advanced Excel"

# ============================================================================
# 7. DIALOG AUTO-ACCEPT TEST
# ============================================================================

class TestDialogHandling:
    """Menguji apakah pop-up konfirmasi di-bypass otomatis."""

    def test_dialog_does_not_block_enroll(self, page):
        """Tombol 'Ambil' memunculkan confirm() dialog → Bot harus tetap sukses."""
        set_all_slots(page, a=0, b=1, c=0)
        
        total, name, enrolled, kelas = check_slots(page, "142240283", ["EA-B"])
        
        # Jika dialog TIDAK di-handle, Playwright akan stuck/timeout
        # Test ini PASSING = dialog berhasil di-bypass
        assert enrolled is True
        assert kelas == "EA-B"

# ============================================================================
# 8. SINGLE TARGET (TANPA FALLBACK) TEST
# ============================================================================

class TestSingleTarget:
    """Menguji skenario hanya 1 target kelas tanpa cadangan."""

    def test_single_target_available(self, page):
        """Hanya mengincar EA-C, dan EA-C kosong → Ambil."""
        set_all_slots(page, a=5, b=3, c=2)
        
        total, name, enrolled, kelas = check_slots(page, "142240283", ["EA-C"])
        
        assert enrolled is True
        assert kelas == "EA-C"
        assert total == 2  # Hanya menghitung EA-C

    def test_single_target_full(self, page):
        """Hanya mengincar EA-C, tapi EA-C penuh → Jangan ambil apapun."""
        set_all_slots(page, a=5, b=3, c=0)
        
        total, name, enrolled, kelas = check_slots(page, "142240283", ["EA-C"])
        
        assert enrolled is False
        assert total == 0

import requests
import sys
import os
from urllib.parse import urlparse
from datetime import datetime # Untuk timestamp di log file

# --- Kode Warna ANSI ---
COLOR_GREEN = "\033[92m" # Hijau
COLOR_RED = "\033[91m"   # Merah
COLOR_RESET = "\033[0m"  # Reset warna

def check_wordpress_login(target_base_url, username, password):
    """
    Melakukan percobaan login ke WordPress dan memeriksa hasilnya.
    Menggunakan requests.Session() untuk mempertahankan cookies.
    """
    login_url = f"{target_base_url.rstrip('/')}/wp-login.php"

    payload = {
        'log': username,
        'pwd': password,
        'wp-submit': 'Log In',
        'redirect_to': f"{target_base_url.rstrip('/')}/wp-admin/",
        'testcookie': '1'
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.88 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': target_base_url.rstrip('/'),
        'Referer': login_url
    }

    with requests.Session() as session:
        try:
            # Langkah 1: Kunjungi halaman login terlebih dahulu untuk mendapatkan session cookie (jika ada)
            initial_response = session.get(login_url, headers=headers, timeout=10)

            # Langkah 2: Kirim POST request login
            response = session.post(login_url, data=payload, allow_redirects=False, timeout=10, headers=headers)

            if response.status_code == 302:
                location = response.headers.get('Location', '')
                if 'wp-admin' in location or 'dashboard' in location:
                    return True, "Login BERHASIL (redirect ke admin)!"
                elif 'wp-login.php?loggedout=true' in location:
                    return False, "Login GAGAL (diredirect ke logout, kemungkinan sudah login sebelumnya atau sesi kadaluarsa)"
                else:
                    return False, f"Login GAGAL (redirect tidak terduga ke: {location})"

            elif response.status_code == 200:
                if "Incorrect username or password" in response.text or \
                   "Password is incorrect" in response.text or \
                   "Username is incorrect" in response.text:
                    return False, "Login GAGAL (username/password salah)."
                elif "Too many failed login attempts" in response.text:
                    return False, "Login GAGAL (terlalu banyak percobaan, diblokir/rate-limit)."
                elif "Invalid email address" in response.text:
                    return False, "Login GAGAL (email tidak valid)."
                else:
                    return False, "Login GAGAL (status 200, tidak ada pesan error spesifik, cek manual)."
            else:
                return False, f"Login GAGAL (Status Code: {response.status_code})"

        except requests.exceptions.ConnectionError:
            return False, "KONEKSI GAGAL: Tidak dapat terhubung ke target URL."
        except requests.exceptions.Timeout:
            return False, "WAKTU HABIS: Permintaan melebihi batas waktu."
        except requests.exceptions.RequestException as e:
            return False, f"ERROR UMUM: {e}"

def parse_input_string(input_str):
    """
    Mem-parsing string input 'URL:user:pass'.
    Secara otomatis membersihkan URL dari path yang tidak relevan seperti /wp-admin
    dan mengembalikan base URL, username, dan password.
    """
    parts = input_str.split(':')

    if len(parts) < 3:
        raise ValueError("Format input tidak valid. Seharusnya 'URL:username:password'.")

    url_candidate = ":".join(parts[:-2])
    username = parts[-2]
    password = parts[-1]

    parsed_url = urlparse(url_candidate)

    if not parsed_url.scheme:
        url_candidate = "https://" + url_candidate
        parsed_url = urlparse(url_candidate)

    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

    if parsed_url.path:
        path = parsed_url.path.lower()

        if "/wp-admin" in path:
            path = path.replace("/wp-admin", "")
        elif "/wp-login.php" in path:
            path = path.replace("/wp-login.php", "")

        if path.strip('/') != '':
            base_url = f"{base_url}{path.rstrip('/')}"

    return base_url.rstrip('/'), username, password

def load_targets_from_file(filepath):
    """
    Membaca daftar target (URL:username:password) dari file.
    """
    targets = []
    if not os.path.exists(filepath):
        print(f"[-] ERROR: File target '{filepath}' tidak ditemukan.")
        return []

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            try:
                base_url, username, password = parse_input_string(line)
                targets.append((base_url, username, password))
            except ValueError as e:
                print(f"[-] PERINGATAN: Melewatkan baris tidak valid '{line}': {e}")
            except Exception as e:
                print(f"[-] PERINGATAN: Terjadi kesalahan saat mem-parsing baris '{line}': {e}")

    return targets

# --- MAIN EXECUTION BLOCK ---
if __name__ == "__main__":
    # Menampilkan Credit/Watermark
    print(f"\n{COLOR_GREEN}======================================")
    print("      WordPress Login Checker")
    print("      by GeminiAI X gRoot")
    print("======================================\n" + COLOR_RESET)

    if len(sys.argv) < 2:
        print("Penggunaan:")
        print(f"python {sys.argv[0]} <nama_file_target>")
        print("\nContoh File Target (misal: targets.txt):")
        print("https://example.com:admin:password123")
        print("http://localhost/wordpress/wp-admin:user:mysecretpass")
        sys.exit(1)

    TARGETS_FILE = sys.argv[1]
    SUCCESS_LOG_FILE = "successful_logins.txt" # Nama file untuk menyimpan hasil berhasil

    print(f"--- Memulai Pengujian Login WordPress dari File ---")
    print(f"Memuat target dari file: {TARGETS_FILE}")
    print(f"Hasil login BERHASIL akan disimpan di: {SUCCESS_LOG_FILE}\n")

    targets_to_test = load_targets_from_file(TARGETS_FILE)

    if not targets_to_test:
        print(f"{COLOR_RED}[-] Tidak ada target yang dimuat. Hentikan pengujian.{COLOR_RESET}")
    else:
        with open(SUCCESS_LOG_FILE, 'a') as f_log: # Buka file log dalam mode append ('a')
            for target_url, username, password in targets_to_test:
                print(f"[*] Menguji: {target_url} (U:{username} P:{password})")
                success, message = check_wordpress_login(target_url, username, password)

                if success:
                    print(f"{COLOR_GREEN}[+] BERHASIL: {message} -> U:{username} P:{password}{COLOR_RESET}\n")
                    # Tulis ke file log
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f_log.write(f"[{timestamp}] BERHASIL: {target_url}:{username}:{password}\n")
                else:
                    print(f"{COLOR_RED}[-] GAGAL: {message} -> U:{username} P:{password}{COLOR_RESET}\n")

        print("--- Pengujian Selesai ---")

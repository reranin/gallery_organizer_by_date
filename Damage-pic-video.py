import os
import subprocess
from PIL import Image
from datetime import datetime
import shutil
import uuid
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import psutil
import hashlib

# ===================== تنظیمات =====================
# مسیر پوشه برای بررسی
folder = r"/Users/yourname/RecoveredFiles"  # Windows: r"D:\RecoveredFiles"

# فرمت‌های عکس و ویدیو
image_exts = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.heic', '.dng')
video_exts = ('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.mpeg', '.mpg', '.ts')

# پوشه مقصد برای فایل‌های خراب
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
corrupt_folder = os.path.join(folder, f"Corrupt_Files_{timestamp}")
backup_folder = os.path.join(folder, f"Backup_Corrupt_Files_{timestamp}")
os.makedirs(corrupt_folder, exist_ok=True)
os.makedirs(backup_folder, exist_ok=True)

# تعداد thread برای Multi-thread processing
MAX_THREADS = 4

# ===================== توابع امنیتی =====================
def check_disk_space(folder_path, required_size_mb=1000):
    """بررسی فضای دیسک قبل از شروع عملیات"""
    try:
        disk_usage = psutil.disk_usage(folder_path)
        free_space_mb = disk_usage.free / (1024 * 1024)
        if free_space_mb < required_size_mb:
            print(f"⚠️ هشدار: فضای دیسک کم است. فضای آزاد: {free_space_mb:.2f} MB")
            return False
        return True
    except:
        print("⚠️ خطا در بررسی فضای دیسک")
        return False

def calculate_file_hash(file_path):
    """محاسبه hash فایل برای اطمینان از یکسان بودن"""
    try:
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except:
        return None

def verify_file_integrity(original_path, backup_path):
    """بررسی یکسان بودن فایل اصلی و backup"""
    original_hash = calculate_file_hash(original_path)
    backup_hash = calculate_file_hash(backup_path)
    return original_hash and backup_hash and original_hash == backup_hash

def safe_copy_file(src, dest_folder):
    """کپی امن فایل بدون حذف فایل اصلی"""
    os.makedirs(dest_folder, exist_ok=True)
    file_name = os.path.basename(src)
    target_path = os.path.join(dest_folder, file_name)
    
    # مدیریت فایل‌های تکراری
    if os.path.exists(target_path):
        base, ext = os.path.splitext(file_name)
        unique_name = f"{base}_{uuid.uuid4().hex[:8]}{ext}"
        target_path = os.path.join(dest_folder, unique_name)
    
    try:
        # ابتدا کپی می‌کنیم
        shutil.copy2(src, target_path)
        
        # بررسی یکسان بودن
        if verify_file_integrity(src, target_path):
            return target_path
        else:
            # اگر کپی ناقص بود، فایل backup را حذف می‌کنیم
            if os.path.exists(target_path):
                os.remove(target_path)
            raise Exception("فایل کپی شده با فایل اصلی یکسان نیست")
    except Exception as e:
        print(f"❌ خطا در کپی فایل {src}: {e}")
        return None

def is_image_corrupt(path):
    """بررسی خرابی عکس با روش‌های مختلف"""
    try:
        # روش 1: بررسی با PIL
        img = Image.open(path)
        img.verify()
        
        # روش 2: بررسی اندازه فایل
        if os.path.getsize(path) < 100:  # فایل‌های خیلی کوچک مشکوک هستند
            return True
            
        # روش 3: تلاش برای باز کردن و بررسی
        img = Image.open(path)
        img.load()
        return False
    except Exception as e:
        return True

def is_video_corrupt(path):
    """بررسی خرابی ویدیو با روش‌های مختلف"""
    try:
        # روش 1: بررسی اندازه فایل
        if os.path.getsize(path) < 1024:  # کمتر از 1KB
            return True
            
        # روش 2: بررسی با ffmpeg
        cmd = ['ffmpeg', '-v', 'error', '-i', path, '-f', 'null', '-']
        result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, timeout=30)
        return bool(result.stderr)
    except subprocess.TimeoutExpired:
        print(f"⏰ timeout در بررسی ویدیو: {path}")
        return True
    except Exception as e:
        print(f"❌ خطا در بررسی ویدیو {path}: {e}")
        return True

def backup_file_safe(src):
    """Backup امن فایل با بررسی یکسان بودن"""
    ext = os.path.splitext(src)[1].lower().replace('.', '')
    target_folder = os.path.join(backup_folder, ext.upper())
    
    # ابتدا کپی می‌کنیم
    backup_path = safe_copy_file(src, target_folder)
    if not backup_path:
        return None
    
    # بررسی یکسان بودن
    if verify_file_integrity(src, backup_path):
        print(f"✅ Backup موفق: {os.path.basename(src)}")
        return backup_path
    else:
        print(f"❌ Backup ناموفق: {os.path.basename(src)}")
        if os.path.exists(backup_path):
            os.remove(backup_path)
        return None

# ===================== بررسی فضای دیسک =====================
print("🔍 بررسی فضای دیسک...")
if not check_disk_space(folder, 2000):  # حداقل 2GB فضای آزاد
    print("❌ فضای دیسک کافی نیست. لطفاً فضای بیشتری آزاد کنید.")
    exit()

# ===================== جمع‌آوری فایل‌ها =====================
print("📁 جمع‌آوری فایل‌ها...")
all_files = []
for root, dirs, files in os.walk(folder):
    for file in files:
        path = os.path.join(root, file)
        if file.lower().endswith(image_exts + video_exts):
            all_files.append(path)

print(f"📊 تعداد کل فایل‌ها: {len(all_files)}")

# ===================== شناسایی فایل‌های خراب =====================
corrupt_files = []

print("\n🔍 در حال شناسایی فایل‌های خراب...")
with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
    future_to_file = {}
    for path in all_files:
        if path.lower().endswith(image_exts):
            future = executor.submit(is_image_corrupt, path)
        else:
            future = executor.submit(is_video_corrupt, path)
        future_to_file[future] = path

    for future in tqdm(as_completed(future_to_file), total=len(future_to_file)):
        path = future_to_file[future]
        if future.result():
            corrupt_files.append(path)

if not corrupt_files:
    print("✅ هیچ فایل خرابی پیدا نشد.")
    exit()

print(f"\n📂 تعداد فایل‌های خراب: {len(corrupt_files)}")

# ===================== Backup امن =====================
print("\n📦 در حال Backup امن فایل‌های خراب...")
file_log = []
successful_backups = 0

for path in tqdm(corrupt_files):
    try:
        # Backup امن
        backup_path = backup_file_safe(path)
        if backup_path:
            successful_backups += 1
            # انتقال به فولدر اصلی
            ext = os.path.splitext(path)[1].lower().replace('.', '')
            target_folder = os.path.join(corrupt_folder, ext.upper())
            final_path = safe_copy_file(backup_path, target_folder)
            
            if final_path:
                file_log.append({
                    'original': path,
                    'backup': backup_path,
                    'final': final_path,
                    'ext': ext.upper(),
                    'status': 'success'
                })
            else:
                file_log.append({
                    'original': path,
                    'backup': backup_path,
                    'final': None,
                    'ext': ext.upper(),
                    'status': 'transfer_failed'
                })
        else:
            file_log.append({
                'original': path,
                'backup': None,
                'final': None,
                'ext': os.path.splitext(path)[1].lower().replace('.', ''),
                'status': 'backup_failed'
            })
    except Exception as e:
        print(f"⚠️ خطا در پردازش {path}: {e}")
        file_log.append({
            'original': path,
            'backup': None,
            'final': None,
            'ext': os.path.splitext(path)[1].lower().replace('.', ''),
            'status': 'error'
        })

print(f"\n📊 خلاصه عملیات:")
print(f"✅ Backup موفق: {successful_backups}/{len(corrupt_files)}")
print(f"❌ Backup ناموفق: {len(corrupt_files) - successful_backups}")

# ===================== انتخاب عملیات =====================
print(f"\n🔧 عملیات‌های ممکن:")
print("1. حذف فایل‌های خراب (فقط بعد از اطمینان از Backup)")
print("2. تعمیر ویدیوهای خراب")
print("3. فقط گزارش و بررسی")
print("4. خروج بدون انجام عملیات")

choice = input("\nانتخاب کنید (1-4): ").strip()

if choice == '1':
    if successful_backups == len(corrupt_files):
        confirm = input("⚠️ آیا مطمئن هستید که می‌خواهید فایل‌های خراب را حذف کنید؟ (y/N): ").strip().lower()
        if confirm == 'y':
            print("\n🗑️ در حال حذف فایل‌های خراب...")
            deleted_count = 0
            for f in tqdm(file_log):
                if f['status'] == 'success' and f['final']:
                    try:
                        os.remove(f['final'])
                        deleted_count += 1
                    except Exception as e:
                        print(f"⚠️ خطا در حذف: {f['final']} - {e}")
            print(f"✅ {deleted_count} فایل حذف شد.")
        else:
            print("❌ عملیات حذف لغو شد.")
    else:
        print("❌ نمی‌توان فایل‌ها را حذف کرد زیرا برخی Backup ناموفق بودند.")

elif choice == '2':
    print("\n🔧 در حال تعمیر ویدیوهای خراب...")
    repair_folder = os.path.join(corrupt_folder, "Repaired_Videos")
    repaired_count = 0
    
    for f in tqdm(file_log):
        if f['status'] == 'success' and f['ext'] in [v.replace('.', '').upper() for v in video_exts]:
            try:
                if f['final']:
                    # تعمیر ویدیو
                    cmd = ['ffmpeg', '-i', f['final'], '-c', 'copy', '-map', '0', 
                           os.path.join(repair_folder, f"repaired_{os.path.basename(f['final'])}"), '-y']
                    subprocess.run(cmd, timeout=300)  # 5 دقیقه timeout
                    repaired_count += 1
            except Exception as e:
                print(f"⚠️ خطا در تعمیر: {f['final']} - {e}")
    
    print(f"✅ {repaired_count} ویدیو تعمیر شد.")

elif choice == '3':
    print("\n📑 فقط گزارش ایجاد شد.")

else:
    print("\n❌ خروج بدون انجام عملیات.")

# ===================== ذخیره گزارش کامل =====================
log_file_path = os.path.join(corrupt_folder, f"corrupt_log_{timestamp}.txt")
with open(log_file_path, "w", encoding="utf-8") as f:
    f.write(f"گزارش بررسی فایل‌های خراب - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write("="*60 + "\n\n")
    
    for item in file_log:
        f.write(f"فایل اصلی: {item['original']}\n")
        f.write(f"Backup:    {item['backup'] or 'ناموفق'}\n")
        f.write(f"انتقال:    {item['final'] or 'ناموفق'}\n")
        f.write(f"فرمت:      {item['ext']}\n")
        f.write(f"وضعیت:     {item['status']}\n")
        f.write("-"*50 + "\n")

print(f"\n📑 گزارش کامل در: {log_file_path}")
print(f"📁 فایل‌های Backup در: {backup_folder}")
print(f"📁 فایل‌های خراب در: {corrupt_folder}")

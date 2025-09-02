import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import hashlib
import mimetypes
from dataclasses import dataclass, asdict, field
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
import threading
import time

# کتابخانه‌های تصویر
try:
    from PIL import Image, UnidentifiedImageError
    # برای جلوگیری از دیکود lenient و کشف فایل‌های ناقص
    try:
        from PIL import ImageFile
        ImageFile.LOAD_TRUNCATED_IMAGES = False
    except Exception:
        pass
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️ کتابخانه Pillow نصب نیست. بررسی تصاویر محدود خواهد بود.")

# کتابخانه‌های ویدیو
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("⚠️ کتابخانه OpenCV نصب نیست. بررسی ویدیوها محدود خواهد بود.")

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    print("⚠️ کتابخانه tqdm نصب نیست. نوار پیشرفت نمایش داده نمی‌شود.")

# بارگذاری تنظیمات از .env در صورت وجود
try:
    from dotenv import load_dotenv, find_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

if DOTENV_AVAILABLE:
    try:
        dotenv_path = find_dotenv(usecwd=True)
        if dotenv_path:
            load_dotenv(dotenv_path)
        else:
            load_dotenv()
    except Exception:
        # اگر بارگذاری .env با خطا مواجه شد، صرفاً ادامه می‌دهیم
        pass

def parse_extensions_env(var_name: str, default_extensions: set) -> set:
    """خواندن لیست پسوندها از متغیر محیطی و تبدیل به مجموعه پسوندهای استاندارد.
    قالب مورد انتظار: ".jpg,.png,.gif" یا بدون نقطه: "jpg,png,gif"
    فاصله‌ها نادیده گرفته می‌شود.
    """
    raw_value = os.getenv(var_name)
    if not raw_value:
        return set(default_extensions)
    try:
        items = [item.strip() for item in raw_value.split(',') if item.strip()]
        normed = []
        for item in items:
            ext = item.lower()
            if not ext.startswith('.'):
                ext = '.' + ext
            normed.append(ext)
        return set(normed) if normed else set(default_extensions)
    except Exception:
        return set(default_extensions)

# ===================== تنظیمات =====================
@dataclass
class Config:
    """تنظیمات برنامه"""
    # فرمت‌های فایل
    IMAGE_EXTENSIONS: set = field(default_factory=lambda: parse_extensions_env(
        "IMAGE_EXTENSIONS",
        {
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff',
            '.webp', '.heic', '.dng', '.raw', '.svg', '.ico'
        }
    ))
    
    VIDEO_EXTENSIONS: set = field(default_factory=lambda: parse_extensions_env(
        "VIDEO_EXTENSIONS",
        {
            '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv',
            '.webm', '.mpeg', '.mpg', '.ts', '.m4v', '.3gp'
        }
    ))
    
    # تنظیمات بررسی
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "10000"))  # حداکثر اندازه فایل برای بررسی
    MIN_FILE_SIZE_BYTES: int = int(os.getenv("MIN_FILE_SIZE_BYTES", "100"))  # حداقل اندازه فایل
    THREAD_COUNT: int = int(os.getenv("THREAD_COUNT", "8"))  # افزایش thread ها برای حجم زیاد فایل‌ها
    TIMEOUT_SECONDS: int = int(os.getenv("TIMEOUT_SECONDS", "30"))  # timeout برای بررسی هر فایل
    
    # تنظیمات بهینه‌سازی برای حجم زیاد فایل‌ها
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "1000"))  # پردازش batch فایل‌ها
    SAVE_PROGRESS_INTERVAL: int = int(os.getenv("SAVE_PROGRESS_INTERVAL", "100"))  # ذخیره پیشرفت هر چند فایل
    MAX_MEMORY_USAGE_MB: int = int(os.getenv("MAX_MEMORY_USAGE_MB", "2000"))  # حداکثر استفاده از حافظه
    ENABLE_INCREMENTAL_SAVE: bool = os.getenv("ENABLE_INCREMENTAL_SAVE", "true").lower() in {"1", "true", "yes"}  # ذخیره تدریجی نتایج
    
    # تنظیمات گزارش
    LOG_LEVEL: int = logging.INFO
    SAVE_DETAILED_REPORT: bool = os.getenv("SAVE_DETAILED_REPORT", "true").lower() in {"1", "true", "yes"}
    SAVE_JSON_REPORT: bool = os.getenv("SAVE_JSON_REPORT", "true").lower() in {"1", "true", "yes"}
    
    # تنظیمات انتقال فایل‌های خراب
    MOVE_CORRUPTED_FILES: bool = os.getenv("MOVE_CORRUPTED_FILES", "true").lower() in {"1", "true", "yes"}  # آیا فایل‌های خراب منتقل شوند؟
    CORRUPTED_FILES_FOLDER: str = os.getenv("CORRUPTED_FILES_FOLDER", "corrupted_files")  # نام پوشه فایل‌های خراب
    CREATE_SUBFOLDERS: bool = os.getenv("CREATE_SUBFOLDERS", "true").lower() in {"1", "true", "yes"}  # ایجاد پوشه‌های فرعی بر اساس نوع فایل
    
    # ===================== آدرس‌های پوشه‌ها =====================
    INPUT_DIRECTORY: Optional[str] = os.getenv("INPUT_DIRECTORY")  # پوشه ورودی برای اسکن (لازم از .env)
    OUTPUT_DIRECTORY: Optional[str] = os.getenv("OUTPUT_DIRECTORY")  # پوشه خروجی برای گزارش‌ها و فایل‌های خراب (لازم از .env)

# ===================== کلاس‌های اصلی =====================
@dataclass
class FileInfo:
    """اطلاعات فایل"""
    path: str
    name: str
    size: int
    extension: str
    mime_type: str
    is_image: bool
    is_video: bool
    corruption_status: str = "unknown"
    corruption_details: str = ""
    check_time: float = 0.0
    error_message: str = ""

class DamageDetector:
    """کلاس اصلی برای شناسایی فایل‌های خراب"""
    
    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.setup_logging()
        self.results: List[FileInfo] = []
        self.lock = threading.Lock()
        
    def setup_logging(self):
        """تنظیم سیستم لاگینگ"""
        logging.basicConfig(
            level=self.config.LOG_LEVEL,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'damage_detector_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def get_file_info(self, file_path: str) -> Optional[FileInfo]:
        """دریافت اطلاعات پایه فایل"""
        try:
            path = Path(file_path)
            if not path.exists():
                return None
                
            stat = path.stat()
            size = stat.st_size
            
            # بررسی اندازه فایل
            if size < self.config.MIN_FILE_SIZE_BYTES:
                return None
                
            if size > self.config.MAX_FILE_SIZE_MB * 1024 * 1024:
                return None
            
            extension = path.suffix.lower()
            mime_type, _ = mimetypes.guess_type(str(path))
            
            is_image = extension in self.config.IMAGE_EXTENSIONS
            is_video = extension in self.config.VIDEO_EXTENSIONS
            
            if not (is_image or is_video):
                return None
            
            return FileInfo(
                path=str(path),
                name=path.name,
                size=size,
                extension=extension,
                mime_type=mime_type or "unknown",
                is_image=is_image,
                is_video=is_video
            )
            
        except Exception as e:
            self.logger.error(f"خطا در دریافت اطلاعات فایل {file_path}: {e}")
            return None
    
    def check_image_corruption(self, file_info: FileInfo) -> Tuple[str, str]:
        """بررسی خرابی تصویر"""
        start_time = datetime.now().timestamp()
        
        try:
            if not PIL_AVAILABLE:
                return "skipped", "کتابخانه Pillow نصب نیست"
            
            # بررسی با PIL
            with Image.open(file_info.path) as img:
                # بررسی metadata
                img.verify()
                
                # تلاش برای بارگذاری کامل تصویر
                img = Image.open(file_info.path)
                # تبدیل و dump کامل بایت‌ها برای اجبار دیکود سراسری
                img_converted = img.convert("RGB")
                _ = img_converted.tobytes()
                
                # بررسی ابعاد
                if img.size[0] <= 0 or img.size[1] <= 0:
                    return "corrupt", "ابعاد تصویر نامعتبر"

                # بررسی تریلر/پایان فایل برای برخی فرمت‌ها
                trailer_ok, trailer_msg = self._check_image_trailer(file_info.path, file_info.extension)
                if not trailer_ok:
                    return "corrupt", trailer_msg

                return "healthy", "تصویر سالم است"
                
        except UnidentifiedImageError:
            return "corrupt", "فرمت تصویر شناسایی نشد"
        except OSError as e:
            # نمونه‌های رایج Pillow برای فایل ناقص
            msg = str(e).lower()
            if "truncated" in msg or "truncat" in msg or "image file is truncated" in msg:
                return "corrupt", "تصویر ناقص/بریده (truncated)"
            if "broken data stream" in msg or "cannot identify image file" in msg:
                return "corrupt", "داده تصویری ناقص یا خراب"
            return "corrupt", f"خطا در بررسی تصویر: {str(e)}"
        except Exception as e:
            return "corrupt", f"خطا در بررسی تصویر: {str(e)}"
        finally:
            file_info.check_time = datetime.now().timestamp() - start_time

    def _check_image_trailer(self, path: str, extension: str) -> Tuple[bool, str]:
        """بررسی وجود تریلر/پایان فایل برای فرمت‌های رایج تا کشف ناقص بودن فایل.
        در صورت مشکلی، False و پیام مناسب برمی‌گرداند.
        """
        ext = extension.lower()
        try:
            if ext in {".jpg", ".jpeg"}:
                # برخی ابزارها پس از EOI بایت‌های اضافه می‌نویسند؛ اگر EOI در انتهای نزدیک یافت شود، سالم تلقی می‌کنیم
                search_window = 64 * 1024
                with open(path, "rb") as f:
                    f.seek(0, os.SEEK_END)
                    file_size = f.tell()
                    if file_size < 2:
                        return False, "تصویر ناقص/بریده (اندازه بسیار کم)"
                    start = max(0, file_size - search_window)
                    f.seek(start, os.SEEK_SET)
                    tail = f.read(file_size - start)
                    if b"\xff\xd9" not in tail:
                        return False, "پایان فایل JPEG (FFD9) یافت نشد"
                return True, ""
            if ext == ".png":
                # وجود چانک IEND کافی است؛ داده اضافه بعد از آن را تحمل می‌کنیم
                search_window = 64 * 1024
                with open(path, "rb") as f:
                    f.seek(0, os.SEEK_END)
                    file_size = f.tell()
                    if file_size < 12:
                        return False, "تصویر ناقص/بریده (اندازه بسیار کم)"
                    start = max(0, file_size - search_window)
                    f.seek(start, os.SEEK_SET)
                    tail = f.read(file_size - start)
                    if b"IEND" not in tail:
                        return False, "پایان فایل PNG (IEND) ناقص/مفقود"
                return True, ""
            if ext == ".gif":
                # وجود ';' به عنوان terminator در انتهای نزدیک کافی است
                search_window = 16 * 1024
                with open(path, "rb") as f:
                    f.seek(0, os.SEEK_END)
                    file_size = f.tell()
                    if file_size < 1:
                        return False, "تصویر ناقص/بریده (اندازه بسیار کم)"
                    start = max(0, file_size - search_window)
                    f.seek(start, os.SEEK_SET)
                    tail = f.read(file_size - start)
                    if b"\x3B" not in tail:
                        return False, "پایان فایل GIF (';') یافت نشد"
                return True, ""
        except Exception:
            # در صورت هر خطایی، عدم تایید تریلر را به عنوان مشکوک گزارش کنیم
            return False, "بررسی پایان فایل با خطا مواجه شد"
        # برای سایر فرمت‌ها بررسی انجام نمی‌دهیم
        return True, ""
    
    def check_video_corruption(self, file_info: FileInfo) -> Tuple[str, str]:
        """بررسی خرابی ویدیو"""
        start_time = datetime.now().timestamp()
        
        try:
            if not CV2_AVAILABLE:
                return "skipped", "کتابخانه OpenCV نصب نیست"
            
            # بررسی با OpenCV
            cap = cv2.VideoCapture(file_info.path)
            if not cap.isOpened():
                return "corrupt", "فایل ویدیو باز نشد"

            # بررسی اطلاعات ویدیو
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            if width <= 0 or height <= 0:
                return "corrupt", "ابعاد ویدیو نامعتبر"

            # تلاش برای خواندن چند فریم
            frames_read = 0
            max_frames_to_check = 10 if frame_count <= 0 else min(10, frame_count)

            for _ in range(max_frames_to_check):
                ret, frame = cap.read()
                if ret and frame is not None:
                    frames_read += 1
                else:
                    break

            if frames_read == 0:
                return "corrupt", "هیچ فریمی خوانده نشد"

            if frame_count > 0 and frames_read < max_frames_to_check * 0.5:
                return "suspicious", "بسیاری از فریم‌ها قابل خواندن نیستند"

            # بررسی اندازه فایل نسبت به مدت زمان (تنها در صورت معتبر بودن fps)
            duration = frame_count / fps if (frame_count > 0 and fps and fps > 0) else 0
            if duration > 0:
                bytes_per_second = file_info.size / duration
                if bytes_per_second < 1000:  # کمتر از 1KB در ثانیه
                    return "suspicious", "نرخ بیت ویدیو کم است"

            return "healthy", "ویدیو سالم است"
            
        except Exception as e:
            return "corrupt", f"خطا در بررسی ویدیو: {str(e)}"
        finally:
            try:
                if 'cap' in locals():
                    cap.release()
            except Exception:
                pass
            file_info.check_time = datetime.now().timestamp() - start_time
    
    def check_file_corruption(self, file_info: FileInfo) -> None:
        """بررسی خرابی فایل"""
        try:
            if file_info.is_image:
                status, details = self.check_image_corruption(file_info)
            elif file_info.is_video:
                status, details = self.check_video_corruption(file_info)
            else:
                return
            
            file_info.corruption_status = status
            file_info.corruption_details = details
            
            # ثبت در نتایج
            with self.lock:
                self.results.append(file_info)
                
        except Exception as e:
            file_info.corruption_status = "error"
            file_info.error_message = str(e)
            with self.lock:
                self.results.append(file_info)
    
    def scan_directory(self, directory_path: str) -> List[FileInfo]:
        """اسکن پوشه و جمع‌آوری فایل‌ها"""
        self.logger.info(f"شروع اسکن پوشه: {directory_path}")
        
        if not os.path.exists(directory_path):
            self.logger.error(f"پوشه وجود ندارد: {directory_path}")
            return []
        
        files_to_check = []
        
        # جمع‌آوری فایل‌ها
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                file_path = os.path.join(root, file)
                file_info = self.get_file_info(file_path)
                if file_info:
                    files_to_check.append(file_info)
        
        self.logger.info(f"تعداد فایل‌های یافت شده: {len(files_to_check)}")
        return files_to_check
    
    def process_files(self, files: List[FileInfo], output_dir: Optional[str] = None) -> None:
        """پردازش فایل‌ها با multi-threading و ذخیره تدریجی نتایج"""
        self.logger.info(f"شروع پردازش {len(files)} فایل")

        if TQDM_AVAILABLE:
            progress_bar = tqdm(total=len(files), desc="بررسی فایل‌ها")
        else:
            progress_bar = None

        processed_since_save = 0

        with ThreadPoolExecutor(max_workers=self.config.THREAD_COUNT) as executor:
            future_to_file = {executor.submit(self.check_file_corruption, file): file for file in files}
            submit_times = {future: time.time() for future in future_to_file}
            warned = set()

            pending = set(future_to_file.keys())
            while pending:
                done, pending = wait(pending, timeout=1)
                for future in done:
                    if progress_bar:
                        progress_bar.update(1)
                    try:
                        future.result()
                    except Exception as e:
                        self.logger.error(f"خطا در پردازش فایل: {e}")

                    processed_since_save += 1
                    if (
                        output_dir
                        and self.config.ENABLE_INCREMENTAL_SAVE
                        and processed_since_save >= self.config.SAVE_PROGRESS_INTERVAL
                    ):
                        try:
                            # ذخیره تدریجی نتایج تا این لحظه
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            json_path = os.path.join(output_dir, f"damage_report_partial_{timestamp}.json")
                            report_data = {
                                "summary": {
                                    "total_files": len(self.results),
                                    "scan_time": datetime.now().isoformat()
                                },
                                "files": [asdict(f) for f in self.results]
                            }
                            with open(json_path, 'w', encoding='utf-8') as f:
                                json.dump(report_data, f, ensure_ascii=False, indent=2)
                            processed_since_save = 0
                            self.logger.info(f"ذخیره تدریجی نتایج: {json_path}")
                        except Exception as save_err:
                            self.logger.warning(f"خطا در ذخیره تدریجی نتایج: {save_err}")

                # پایش تایم‌اوت و هشدار برای کارهای طولانی
                for future in list(pending):
                    start_ts = submit_times.get(future, time.time())
                    if (time.time() - start_ts) > self.config.TIMEOUT_SECONDS and future not in warned:
                        file_info = future_to_file.get(future)
                        self.logger.warning(f"زمان بررسی طولانی برای فایل: {getattr(file_info, 'path', 'نامشخص')}")
                        warned.add(future)

        if progress_bar:
            progress_bar.close()

        self.logger.info("پردازش فایل‌ها تکمیل شد")
    
    def generate_report(self, output_dir: str = ".") -> str:
        """تولید گزارش کامل"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # آمار کلی
        total_files = len(self.results)
        healthy_files = len([f for f in self.results if f.corruption_status == "healthy"])
        Corrupt_Files = len([f for f in self.results if f.corruption_status == "corrupt"])
        suspicious_files = len([f for f in self.results if f.corruption_status == "suspicious"])
        skipped_files = len([f for f in self.results if f.corruption_status == "skipped"])
        error_files = len([f for f in self.results if f.corruption_status == "error"])
        
        # گزارش متنی
        if self.config.SAVE_DETAILED_REPORT:
            report_path = os.path.join(output_dir, f"damage_report_{timestamp}.txt")
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("گزارش بررسی فایل‌های خراب\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"تاریخ بررسی: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"تعداد کل فایل‌ها: {total_files}\n")
                f.write(f"فایل‌های سالم: {healthy_files}\n")
                f.write(f"فایل‌های خراب: {Corrupt_Files}\n")
                f.write(f"فایل‌های مشکوک: {suspicious_files}\n")
                f.write(f"فایل‌های رد شده: {skipped_files}\n")
                f.write(f"فایل‌های خطا: {error_files}\n\n")
                
                f.write("جزئیات فایل‌های خراب:\n")
                f.write("-" * 50 + "\n")
                for file_info in self.results:
                    if file_info.corruption_status in ["corrupt", "suspicious"]:
                        f.write(f"فایل: {file_info.name}\n")
                        f.write(f"مسیر: {file_info.path}\n")
                        f.write(f"اندازه: {file_info.size:,} بایت\n")
                        f.write(f"وضعیت: {file_info.corruption_status}\n")
                        f.write(f"جزئیات: {file_info.corruption_details}\n")
                        f.write("-" * 30 + "\n")
        
        # گزارش JSON
        if self.config.SAVE_JSON_REPORT:
            json_path = os.path.join(output_dir, f"damage_report_{timestamp}.json")
            report_data = {
                "summary": {
                    "total_files": total_files,
                    "healthy_files": healthy_files,
                    "Corrupt_Files": Corrupt_Files,
                    "suspicious_files": suspicious_files,
                    "skipped_files": skipped_files,
                    "error_files": error_files,
                    "scan_time": datetime.now().isoformat()
                },
                "files": [asdict(f) for f in self.results]
            }
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        return f"گزارش‌ها در پوشه {output_dir} ذخیره شد"
    
    def move_corrupted_files(self, output_dir: str = ".") -> Dict:
        """انتقال فایل‌های خراب به پوشه جداگانه"""
        if not self.config.MOVE_CORRUPTED_FILES:
            return {"message": "انتقال فایل‌های خراب غیرفعال است"}
        
        corrupted_files = [f for f in self.results if f.corruption_status in ["corrupt", "suspicious"]]
        if not corrupted_files:
            return {"message": "هیچ فایل خرابی برای انتقال یافت نشد"}
        
        # ایجاد پوشه اصلی فایل‌های خراب
        corrupted_folder = os.path.join(output_dir, self.config.CORRUPTED_FILES_FOLDER)
        os.makedirs(corrupted_folder, exist_ok=True)
        
        moved_files = []
        failed_moves = []
        
        for file_info in corrupted_files:
            try:
                # تعیین پوشه مقصد
                if self.config.CREATE_SUBFOLDERS:
                    if file_info.is_image:
                        subfolder = "images"
                    elif file_info.is_video:
                        subfolder = "videos"
                    else:
                        subfolder = "others"
                    
                    dest_folder = os.path.join(corrupted_folder, subfolder)
                    os.makedirs(dest_folder, exist_ok=True)
                else:
                    dest_folder = corrupted_folder
                
                # نام فایل مقصد (همان نام اصلی)
                source_path = Path(file_info.path)
                dest_filename = source_path.name
                dest_path = os.path.join(dest_folder, dest_filename)
                
                # اگر فایل مقصد وجود دارد، نام را تغییر دهید
                counter = 1
                while os.path.exists(dest_path):
                    name_without_ext = source_path.stem
                    dest_filename = f"{name_without_ext}_{counter}{source_path.suffix}"
                    dest_path = os.path.join(dest_folder, dest_filename)
                    counter += 1
                
                # انتقال فایل
                import shutil
                original_path = file_info.path
                shutil.move(file_info.path, dest_path)
                
                # به‌روزرسانی مسیر فایل
                file_info.path = dest_path
                file_info.name = dest_filename
                
                moved_files.append({
                    "original_path": original_path,
                    "new_path": dest_path,
                    "status": file_info.corruption_status,
                    "details": file_info.corruption_details
                })
                
                self.logger.info(f"فایل خراب منتقل شد: {file_info.name} -> {dest_path}")
                
            except Exception as e:
                error_msg = f"خطا در انتقال فایل {file_info.name}: {str(e)}"
                self.logger.error(error_msg)
                failed_moves.append({
                    "file": file_info.name,
                    "error": str(e)
                })
        
        # تولید گزارش انتقال
        move_report_path = os.path.join(output_dir, f"move_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(move_report_path, 'w', encoding='utf-8') as f:
            f.write("گزارش انتقال فایل‌های خراب\n")
            f.write("=" * 40 + "\n\n")
            f.write(f"تاریخ انتقال: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"تعداد فایل‌های منتقل شده: {len(moved_files)}\n")
            f.write(f"تعداد انتقال‌های ناموفق: {len(failed_moves)}\n\n")
            
            if moved_files:
                f.write("فایل‌های منتقل شده:\n")
                f.write("-" * 30 + "\n")
                for move_info in moved_files:
                    f.write(f"فایل: {os.path.basename(move_info['new_path'])}\n")
                    f.write(f"مسیر جدید: {move_info['new_path']}\n")
                    f.write(f"وضعیت: {move_info['status']}\n")
                    f.write(f"جزئیات: {move_info['details']}\n")
                    f.write("-" * 20 + "\n")
            
            if failed_moves:
                f.write("\nانتقال‌های ناموفق:\n")
                f.write("-" * 30 + "\n")
                for fail_info in failed_moves:
                    f.write(f"فایل: {fail_info['file']}\n")
                    f.write(f"خطا: {fail_info['error']}\n")
                    f.write("-" * 20 + "\n")
        
        return {
            "moved_files": len(moved_files),
            "failed_moves": len(failed_moves),
            "corrupted_folder": corrupted_folder,
            "move_report": move_report_path,
            "message": f"{len(moved_files)} فایل خراب به پوشه {corrupted_folder} منتقل شد"
        }
    
    def run_scan(self, directory_path: str, output_dir: str = ".") -> Dict:
        """اجرای کامل اسکن"""
        self.logger.info("شروع اسکن فایل‌های خراب")
        
        # اسکن پوشه
        files = self.scan_directory(directory_path)
        if not files:
            return {"error": "هیچ فایلی برای بررسی یافت نشد"}
        
        # پردازش فایل‌ها (به صورت دسته‌ای در صورت نیاز)
        if self.config.BATCH_SIZE and self.config.BATCH_SIZE > 0 and len(files) > self.config.BATCH_SIZE:
            self.logger.info(f"پردازش دسته‌ای با اندازه {self.config.BATCH_SIZE}")
            for i in range(0, len(files), self.config.BATCH_SIZE):
                batch = files[i:i + self.config.BATCH_SIZE]
                self.process_files(batch, output_dir)
        else:
            self.process_files(files, output_dir)
        
        # تولید گزارش
        report_message = self.generate_report(output_dir)
        
        # انتقال فایل‌های خراب
        move_results = self.move_corrupted_files(output_dir)
        
        # آمار نهایی
        stats = {
            "total_files": len(self.results),
            "healthy_files": len([f for f in self.results if f.corruption_status == "healthy"]),
            "Corrupt_Files": len([f for f in self.results if f.corruption_status == "corrupt"]),
            "suspicious_files": len([f for f in self.results if f.corruption_status == "suspicious"]),
            "report_message": report_message,
            "move_results": move_results
        }
        
        self.logger.info("اسکن تکمیل شد")
        return stats

# ===================== تابع اصلی =====================
def main():
    """تابع اصلی برنامه"""
    print("🔍 شناسایی کننده فایل‌های خراب")
    print("=" * 40)
    
    # تنظیمات
    config = Config()
    
    # استفاده از آدرس‌های ثابت
    directory_path = config.INPUT_DIRECTORY
    output_dir = config.OUTPUT_DIRECTORY
    
    # بررسی مقداردهی از .env
    if not directory_path:
        print("❌ مقدار INPUT_DIRECTORY در محیط/.env تنظیم نشده است")
        return
    if not output_dir:
        print("❌ مقدار OUTPUT_DIRECTORY در محیط/.env تنظیم نشده است")
        return

    # بررسی وجود پوشه ورودی
    if not os.path.exists(directory_path):
        print(f"❌ پوشه ورودی وجود ندارد: {directory_path}")
        print("لطفاً مقدار INPUT_DIRECTORY را در فایل .env تنظیم/تصحیح کنید")
        return
    
    # ایجاد پوشه خروجی اگر وجود ندارد
    os.makedirs(output_dir, exist_ok=True)
    print(f"📁 پوشه ورودی: {directory_path}")
    print(f"📁 پوشه خروجی: {output_dir}")
    
    # تنظیمات انتقال فایل‌های خراب (ثابت)
    print(f"\n⚙️ تنظیمات انتقال فایل‌های خراب:")
    print(f"انتقال فایل‌ها: {'فعال' if config.MOVE_CORRUPTED_FILES else 'غیرفعال'}")
    print(f"پوشه مقصد: {config.CORRUPTED_FILES_FOLDER}")
    print(f"پوشه‌های فرعی: {'فعال' if config.CREATE_SUBFOLDERS else 'غیرفعال'}")
    
    # ایجاد detector
    detector = DamageDetector(config)
    
    try:
        # اجرای اسکن
        results = detector.run_scan(directory_path, output_dir)
        
        if "error" in results:
            print(f"❌ خطا: {results['error']}")
            return
        
        # نمایش نتایج
        print("\n📊 نتایج اسکن:")
        print(f"✅ فایل‌های سالم: {results['healthy_files']}")
        print(f"❌ فایل‌های خراب: {results['Corrupt_Files']}")
        print(f"⚠️ فایل‌های مشکوک: {results['suspicious_files']}")
        print(f"📁 کل فایل‌ها: {results['total_files']}")
        print(f"\n📄 {results['report_message']}")
        
        # نمایش نتایج انتقال
        if 'move_results' in results and results['move_results']:
            move_info = results['move_results']
            print(f"\n📦 نتایج انتقال فایل‌های خراب:")
            print(f"📁 پوشه مقصد: {move_info.get('corrupted_folder', 'نامشخص')}")
            print(f"✅ فایل‌های منتقل شده: {move_info.get('moved_files', 0)}")
            print(f"❌ انتقال‌های ناموفق: {move_info.get('failed_moves', 0)}")
            print(f"📋 گزارش انتقال: {move_info.get('move_report', 'نامشخص')}")
            print(f"💬 {move_info.get('message', '')}")
        
    except KeyboardInterrupt:
        print("\n⏹️ اسکن توسط کاربر متوقف شد")
    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {e}")
        detector.logger.error(f"خطای غیرمنتظره: {e}")

if __name__ == "__main__":
    main()

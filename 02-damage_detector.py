#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
شناسایی فایل‌های خراب
تشخیص و شناسایی فایل‌های تصویری و ویدیویی خراب یا ناقص
"""

import os
import sys
import json
import logging
import argparse
import mimetypes
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# کتابخانه‌های اختیاری
try:
    from PIL import Image, UnidentifiedImageError
    try:
        from PIL import ImageFile
        ImageFile.LOAD_TRUNCATED_IMAGES = False
    except Exception:
        pass
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️ کتابخانه Pillow نصب نیست. بررسی تصاویر محدود خواهد بود.")

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
    """کلاس شناسایی فایل‌های خراب"""
    
    def __init__(self, config: Dict = None):
        self.config = config or self.get_default_config()
        self.setup_logging()
        self.results: List[FileInfo] = []
        self.original_directory = ""
        
    def get_default_config(self) -> Dict:
        """تنظیمات پیش‌فرض"""
        return {
            'IMAGE_EXTENSIONS': {
                '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff',
                '.webp', '.heic', '.dng', '.raw', '.svg', '.ico'
            },
            'VIDEO_EXTENSIONS': {
                '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv',
                '.webm', '.mpeg', '.mpg', '.ts', '.m4v', '.3gp'
            },
            'MAX_FILE_SIZE_MB': 10000,
            'MIN_FILE_SIZE_BYTES': 100,
            'THREAD_COUNT': 4,
            'TIMEOUT_SECONDS': 30
        }
    
    def setup_logging(self):
        """تنظیم سیستم لاگینگ"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f'damage_detector_{timestamp}.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def get_file_info(self, file_path: Path) -> Optional[FileInfo]:
        """دریافت اطلاعات پایه فایل"""
        try:
            if not file_path.exists() or not file_path.is_file():
                return None
                
            stat = file_path.stat()
            size = stat.st_size
            
            # بررسی اندازه فایل
            if size < self.config['MIN_FILE_SIZE_BYTES']:
                return None
                
            if size > self.config['MAX_FILE_SIZE_MB'] * 1024 * 1024:
                return None
            
            extension = file_path.suffix.lower()
            mime_type, _ = mimetypes.guess_type(str(file_path))
            
            is_image = extension in self.config['IMAGE_EXTENSIONS']
            is_video = extension in self.config['VIDEO_EXTENSIONS']
            
            if not (is_image or is_video):
                return None
            
            return FileInfo(
                path=str(file_path),
                name=file_path.name,
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
        import time
        start_time = time.time()
        
        try:
            if not PIL_AVAILABLE:
                return "skipped", "کتابخانه Pillow نصب نیست"
            
            # بررسی با PIL
            with Image.open(file_info.path) as img:
                # بررسی metadata
                img.verify()
                
                # تلاش برای بارگذاری کامل تصویر
                img = Image.open(file_info.path)
                img_converted = img.convert("RGB")
                _ = img_converted.tobytes()
                
                # بررسی ابعاد
                if img.size[0] <= 0 or img.size[1] <= 0:
                    return "corrupt", "ابعاد تصویر نامعتبر"

                # بررسی تریلر/پایان فایل
                trailer_ok, trailer_msg = self._check_image_trailer(file_info.path, file_info.extension)
                if not trailer_ok:
                    return "corrupt", trailer_msg

                return "healthy", "تصویر سالم است"
                
        except UnidentifiedImageError:
            return "corrupt", "فرمت تصویر شناسایی نشد"
        except OSError as e:
            msg = str(e).lower()
            if "truncated" in msg or "truncat" in msg:
                return "corrupt", "تصویر ناقص/بریده (truncated)"
            if "broken data stream" in msg or "cannot identify image file" in msg:
                return "corrupt", "داده تصویری ناقص یا خراب"
            return "corrupt", f"خطا در بررسی تصویر: {str(e)}"
        except Exception as e:
            return "corrupt", f"خطا در بررسی تصویر: {str(e)}"
        finally:
            file_info.check_time = time.time() - start_time

    def _check_image_trailer(self, path: str, extension: str) -> Tuple[bool, str]:
        """بررسی وجود تریلر/پایان فایل"""
        ext = extension.lower()
        try:
            if ext in {".jpg", ".jpeg"}:
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
            return False, "بررسی پایان فایل با خطا مواجه شد"
        return True, ""
    
    def check_video_corruption(self, file_info: FileInfo) -> Tuple[str, str]:
        """بررسی خرابی ویدیو"""
        import time
        start_time = time.time()
        
        try:
            if not CV2_AVAILABLE:
                # تلاش با ffmpeg
                return self._check_video_with_ffmpeg(file_info)
            
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

            return "healthy", "ویدیو سالم است"
            
        except Exception as e:
            return "corrupt", f"خطا در بررسی ویدیو: {str(e)}"
        finally:
            try:
                if 'cap' in locals():
                    cap.release()
            except Exception:
                pass
            file_info.check_time = time.time() - start_time
    
    def _check_video_with_ffmpeg(self, file_info: FileInfo) -> Tuple[str, str]:
        """بررسی ویدیو با ffmpeg"""
        try:
            cmd = ['ffmpeg', '-v', 'error', '-i', file_info.path, '-f', 'null', '-']
            result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, 
                                  timeout=self.config['TIMEOUT_SECONDS'])
            if result.stderr:
                return "corrupt", f"خطا در ffmpeg: {result.stderr.decode('utf-8', errors='ignore')}"
            return "healthy", "ویدیو سالم است (بررسی با ffmpeg)"
        except subprocess.TimeoutExpired:
            return "suspicious", "timeout در بررسی ویدیو"
        except FileNotFoundError:
            return "skipped", "ffmpeg نصب نیست"
        except Exception as e:
            return "corrupt", f"خطا در بررسی با ffmpeg: {str(e)}"
    
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
            self.results.append(file_info)
                
        except Exception as e:
            file_info.corruption_status = "error"
            file_info.error_message = str(e)
            self.results.append(file_info)
    
    def scan_directory(self, directory_path: str) -> List[FileInfo]:
        """اسکن پوشه و جمع‌آوری فایل‌ها"""
        self.logger.info(f"شروع اسکن پوشه: {directory_path}")
        
        if not os.path.exists(directory_path):
            self.logger.error(f"پوشه وجود ندارد: {directory_path}")
            return []
        
        # ذخیره پوشه اصلی برای جدا سازی
        self.original_directory = os.path.abspath(directory_path)
        
        files_to_check = []
        
        # جمع‌آوری فایل‌ها
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                file_path = Path(root) / file
                file_info = self.get_file_info(file_path)
                if file_info:
                    files_to_check.append(file_info)
        
        self.logger.info(f"تعداد فایل‌های یافت شده: {len(files_to_check)}")
        return files_to_check
    
    def process_files(self, files: List[FileInfo]) -> None:
        """پردازش فایل‌ها با multi-threading"""
        self.logger.info(f"شروع پردازش {len(files)} فایل")

        if TQDM_AVAILABLE:
            progress_bar = tqdm(total=len(files), desc="بررسی فایل‌ها")
        else:
            progress_bar = None

        with ThreadPoolExecutor(max_workers=self.config['THREAD_COUNT']) as executor:
            futures = [executor.submit(self.check_file_corruption, file) for file in files]
            
            for future in as_completed(futures):
                if progress_bar:
                    progress_bar.update(1)
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(f"خطا در پردازش فایل: {e}")

        if progress_bar:
            progress_bar.close()

        self.logger.info("پردازش فایل‌ها تکمیل شد")
    
    def separate_corrupt_files(self, output_dir: str, include_suspicious: bool = True) -> Dict:
        """جدا سازی فایل‌های خراب با حفظ ساختار پوشه"""
        if not self.original_directory:
            return {"error": "پوشه اصلی مشخص نیست"}
        
        corrupt_output_dir = os.path.join(output_dir, "Corrupt_Files")
        suspicious_output_dir = os.path.join(output_dir, "Suspicious_Files")
        
        stats = {
            "corrupt_moved": 0,
            "suspicious_moved": 0,
            "errors": 0,
            "error_details": []
        }
        
        try:
            original_path = Path(self.original_directory)
            
            for file_info in self.results:
                if file_info.corruption_status == "corrupt":
                    try:
                        self._move_file_with_structure(file_info.path, original_path, corrupt_output_dir)
                        stats["corrupt_moved"] += 1
                        self.logger.info(f"فایل خراب منتقل شد: {file_info.name}")
                    except Exception as e:
                        stats["errors"] += 1
                        error_msg = f"خطا در انتقال {file_info.path}: {str(e)}"
                        stats["error_details"].append(error_msg)
                        self.logger.error(error_msg)
                
                elif file_info.corruption_status == "suspicious" and include_suspicious:
                    try:
                        self._move_file_with_structure(file_info.path, original_path, suspicious_output_dir)
                        stats["suspicious_moved"] += 1
                        self.logger.info(f"فایل مشکوک منتقل شد: {file_info.name}")
                    except Exception as e:
                        stats["errors"] += 1
                        error_msg = f"خطا در انتقال {file_info.path}: {str(e)}"
                        stats["error_details"].append(error_msg)
                        self.logger.error(error_msg)
            
            return stats
            
        except Exception as e:
            return {"error": f"خطا در جدا سازی فایل‌ها: {str(e)}"}
    
    def _move_file_with_structure(self, source_path: str, original_base: Path, target_base: str):
        """انتقال فایل با حفظ ساختار پوشه"""
        source_file = Path(source_path)
        
        # محاسبه مسیر نسبی
        try:
            relative_path = source_file.relative_to(original_base)
        except ValueError:
            # اگر فایل خارج از پوشه اصلی است
            relative_path = source_file.name
        
        # ایجاد مسیر مقصد
        target_path = Path(target_base) / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # انتقال فایل
        if source_file.exists():
            shutil.move(str(source_file), str(target_path))
            self.logger.debug(f"فایل منتقل شد: {source_path} -> {target_path}")
        else:
            raise FileNotFoundError(f"فایل منبع وجود ندارد: {source_path}")
    
    def generate_report(self, output_dir: str = ".") -> str:
        """تولید گزارش کامل"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # آمار کلی
        total_files = len(self.results)
        healthy_files = len([f for f in self.results if f.corruption_status == "healthy"])
        corrupt_files = len([f for f in self.results if f.corruption_status == "corrupt"])
        suspicious_files = len([f for f in self.results if f.corruption_status == "suspicious"])
        skipped_files = len([f for f in self.results if f.corruption_status == "skipped"])
        error_files = len([f for f in self.results if f.corruption_status == "error"])
        
        # اطمینان از وجود پوشه خروجی
        os.makedirs(output_dir, exist_ok=True)
        
        # گزارش متنی
        report_path = os.path.join(output_dir, f"damage_report_{timestamp}.txt")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("گزارش بررسی فایل‌های خراب\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"تاریخ بررسی: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"تعداد کل فایل‌ها: {total_files}\n")
            f.write(f"فایل‌های سالم: {healthy_files}\n")
            f.write(f"فایل‌های خراب: {corrupt_files}\n")
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
        json_path = os.path.join(output_dir, f"damage_report_{timestamp}.json")
        report_data = {
            "summary": {
                "total_files": total_files,
                "healthy_files": healthy_files,
                "corrupt_files": corrupt_files,
                "suspicious_files": suspicious_files,
                "skipped_files": skipped_files,
                "error_files": error_files,
                "scan_time": datetime.now().isoformat()
            },
            "files": [asdict(f) for f in self.results]
        }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        return f"گزارش‌ها در {output_dir} ذخیره شد"
    
    def run_scan(self, directory_path: str, output_dir: str = ".", separate_files: bool = False, include_suspicious: bool = True) -> Dict:
        """اجرای کامل اسکن"""
        self.logger.info("شروع اسکن فایل‌های خراب")
        
        # اسکن پوشه
        files = self.scan_directory(directory_path)
        if not files:
            return {"error": "هیچ فایلی برای بررسی یافت نشد"}
        
        # پردازش فایل‌ها
        self.process_files(files)
        
        # تولید گزارش
        report_message = self.generate_report(output_dir)
        
        # آمار نهایی
        stats = {
            "total_files": len(self.results),
            "healthy_files": len([f for f in self.results if f.corruption_status == "healthy"]),
            "corrupt_files": len([f for f in self.results if f.corruption_status == "corrupt"]),
            "suspicious_files": len([f for f in self.results if f.corruption_status == "suspicious"]),
            "report_message": report_message
        }
        
        # جدا سازی فایل‌های خراب (اگر درخواست شده باشد)
        if separate_files:
            self.logger.info("شروع جدا سازی فایل‌های خراب")
            separation_stats = self.separate_corrupt_files(output_dir, include_suspicious)
            if "error" in separation_stats:
                stats["separation_error"] = separation_stats["error"]
            else:
                stats.update({
                    "corrupt_moved": separation_stats["corrupt_moved"],
                    "suspicious_moved": separation_stats["suspicious_moved"],
                    "separation_errors": separation_stats["errors"],
                    "separation_error_details": separation_stats["error_details"]
                })
                self.logger.info(f"جدا سازی تکمیل شد - خراب: {separation_stats['corrupt_moved']}, مشکوک: {separation_stats['suspicious_moved']}")
            stats["files_separated"] = True
        else:
            stats["files_separated"] = False
        
        self.logger.info("اسکن تکمیل شد")
        return stats


def main():
    """تابع اصلی"""
    parser = argparse.ArgumentParser(description="شناسایی فایل‌های خراب")
    parser.add_argument("directory", nargs='?', help="پوشه برای اسکن (اختیاری، از .env خوانده می‌شود)")
    parser.add_argument("-o", "--output", help="پوشه خروجی برای گزارش‌ها (اختیاری، از .env خوانده می‌شود)")
    parser.add_argument("-t", "--threads", type=int, help="تعداد thread ها")
    parser.add_argument("--max-size", type=int, help="حداکثر اندازه فایل (MB)")
    parser.add_argument("--min-size", type=int, help="حداقل اندازه فایل (bytes)")
    parser.add_argument("-s", "--separate", action="store_true", help="جدا سازی فایل‌های خراب با حفظ ساختار پوشه")
    parser.add_argument("--no-suspicious", action="store_true", help="عدم انتقال فایل‌های مشکوک (فقط فایل‌های خراب)")
    
    args = parser.parse_args()
    
    print("🔍 شناسایی کننده فایل‌های خراب")
    print("=" * 40)
    
    try:
        # تعیین مسیرهای ورودی و خروجی
        input_dir = args.directory or os.getenv("INPUT_DIRECTORY")
        output_dir = args.output or os.getenv("OUTPUT_DIRECTORY", ".")
        
        if not input_dir:
            print("❌ خطا: پوشه ورودی مشخص نشده")
            print("لطفاً مسیر را به عنوان آرگومان وارد کنید یا در فایل .env تنظیم کنید:")
            print("INPUT_DIRECTORY=/path/to/input")
            return 1
        
        # طبیعی‌سازی مسیرها
        input_dir = os.path.abspath(input_dir)
        output_dir = os.path.abspath(output_dir)
        
        print(f"📂 پوشه ورودی: {input_dir}")
        print(f"📂 پوشه خروجی: {output_dir}")
        
        # بررسی وجود پوشه ورودی
        if not os.path.exists(input_dir):
            print(f"❌ خطا: پوشه ورودی وجود ندارد: {input_dir}")
            return 1
        
        # تنظیمات از .env یا آرگومان‌ها
        config = {
            'IMAGE_EXTENSIONS': set(os.getenv("IMAGE_EXTENSIONS", "jpg,jpeg,png,gif,bmp,tiff,webp,heic,dng,raw,svg,ico").split(",")),
            'VIDEO_EXTENSIONS': set(os.getenv("VIDEO_EXTENSIONS", "mp4,avi,mkv,mov,wmv,flv,webm,mpeg,mpg,ts,m4v,3gp").split(",")),
            'MAX_FILE_SIZE_MB': args.max_size or int(os.getenv("MAX_FILE_SIZE_MB", "10000")),
            'MIN_FILE_SIZE_BYTES': args.min_size or int(os.getenv("MIN_FILE_SIZE_BYTES", "100")),
            'THREAD_COUNT': args.threads or int(os.getenv("THREAD_COUNT", "4")),
            'TIMEOUT_SECONDS': int(os.getenv("TIMEOUT_SECONDS", "30"))
        }
        
        # تبدیل پسوندها به فرمت صحیح
        config['IMAGE_EXTENSIONS'] = {f".{ext.strip().lstrip('.')}" for ext in config['IMAGE_EXTENSIONS'] if ext.strip()}
        config['VIDEO_EXTENSIONS'] = {f".{ext.strip().lstrip('.')}" for ext in config['VIDEO_EXTENSIONS'] if ext.strip()}
        
        print(f"⚙️ تعداد Thread ها: {config['THREAD_COUNT']}")
        print(f"⚙️ حداکثر اندازه فایل: {config['MAX_FILE_SIZE_MB']} MB")
        
        if args.separate:
            print("📂 حالت جدا سازی فایل‌های خراب فعال است")
            if args.no_suspicious:
                print("⚠️ فایل‌های مشکوک منتقل نخواهند شد")
            else:
                print("⚠️ فایل‌های مشکوک نیز منتقل خواهند شد")
        
        detector = DamageDetector(config)
        
        # اجرای اسکن
        include_suspicious = not args.no_suspicious
        results = detector.run_scan(input_dir, output_dir, args.separate, include_suspicious)
        
        if "error" in results:
            print(f"❌ خطا: {results['error']}")
            return 1
        
        # نمایش نتایج
        print("\n📊 نتایج اسکن:")
        print(f"✅ فایل‌های سالم: {results['healthy_files']}")
        print(f"❌ فایل‌های خراب: {results['corrupt_files']}")
        print(f"⚠️ فایل‌های مشکوک: {results['suspicious_files']}")
        print(f"📁 کل فایل‌ها: {results['total_files']}")
        print(f"\n📄 {results['report_message']}")
        
        # نمایش نتایج جدا سازی
        if results.get('files_separated', False):
            print("\n📂 نتایج جدا سازی:")
            if 'separation_error' in results:
                print(f"❌ خطا در جدا سازی: {results['separation_error']}")
            else:
                print(f"📦 فایل‌های خراب منتقل شده: {results.get('corrupt_moved', 0)}")
                if include_suspicious:
                    print(f"⚠️ فایل‌های مشکوک منتقل شده: {results.get('suspicious_moved', 0)}")
                if results.get('separation_errors', 0) > 0:
                    print(f"❌ خطاهای انتقال: {results['separation_errors']}")
                    for error in results.get('separation_error_details', []):
                        print(f"   - {error}")
                print("✅ جدا سازی با موفقیت تکمیل شد")
        
    except KeyboardInterrupt:
        print("\n⏹️ اسکن توسط کاربر متوقف شد")
        return 1
    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

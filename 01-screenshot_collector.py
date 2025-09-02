#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
جمع‌آوری اسکرین‌شات‌ها
جمع‌آوری و سازماندهی فایل‌های اسکرین‌شات از پوشه‌های مختلف
"""

import os
import re
import shutil
import argparse
import logging
from pathlib import Path
from typing import Iterable, List, Set, Tuple
from datetime import datetime

# کتابخانه‌های اختیاری
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    print("⚠️ کتابخانه python-dotenv نصب نیست. از تنظیمات پیش‌فرض استفاده می‌شود.")

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    print("⚠️ کتابخانه tqdm نصب نیست. نوار پیشرفت نمایش داده نمی‌شود.")

class ScreenshotCollector:
    """کلاس جمع‌آوری اسکرین‌شات‌ها"""
    
    def __init__(self):
        self.setup_logging()
        self.load_config()
        
    def setup_logging(self):
        """تنظیم سیستم لاگینگ"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f'screenshot_collector_{timestamp}.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_config(self):
        """بارگذاری تنظیمات"""
        if DOTENV_AVAILABLE:
            try:
                load_dotenv()
            except Exception:
                pass
        
        # الگوهای نام اسکرین‌شات
        patterns_str = os.getenv(
            "SCREENSHOT_NAME_PATTERNS",
            "Screenshot,Snip,Snipping,Screen Shot,ScreenShot,اسکرین"
        ).strip()
        self.name_patterns = [p.strip() for p in patterns_str.split(",") if p.strip()]
        
        # پسوندهای مجاز
        exts_str = os.getenv("IMAGE_EXTENSIONS", "png,jpg,jpeg,bmp,webp,gif,tiff").strip()
        self.allowed_extensions = {e.lower().strip().lstrip('.') for e in exts_str.split(",") if e.strip()}
        
        self.logger.info(f"الگوهای نام: {self.name_patterns}")
        self.logger.info(f"پسوندهای مجاز: {self.allowed_extensions}")
    
    def is_screenshot_file(self, path: Path) -> bool:
        """تشخیص اسکرین‌شات بودن فایل"""
        if not path.is_file():
            return False
            
        # بررسی پسوند
        ext = path.suffix.lower().lstrip('.')
        if ext not in self.allowed_extensions:
            return False
        
        # بررسی نام فایل
        lowercase_name = path.name.lower()
        
        # بررسی الگوهای تعریف شده
        for pattern in self.name_patterns:
            if pattern.lower() in lowercase_name:
                return True
        
        # بررسی الگوهای رایج با regex
        if re.search(r"screen\s*shot|screenshot|snip|snipping|اسکرین", lowercase_name):
            return True
            
        return False
    
    def ensure_directory(self, path: Path) -> None:
        """ایجاد پوشه در صورت عدم وجود"""
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"پوشه ایجاد شد: {path}")
    
    def move_file_safe(self, src: Path, dst_dir: Path) -> Path:
        """انتقال امن فایل با مدیریت نام‌های تکراری"""
        self.ensure_directory(dst_dir)
        destination = dst_dir / src.name
        counter = 1
        
        # مدیریت نام‌های تکراری
        while destination.exists():
            stem, suffix = src.stem, src.suffix
            destination = dst_dir / f"{stem} ({counter}){suffix}"
            counter += 1
        
        try:
            shutil.move(str(src), str(destination))
            self.logger.info(f"منتقل شد: {src.name} -> {destination}")
            return destination
        except Exception as e:
            self.logger.error(f"خطا در انتقال {src}: {e}")
            raise
    
    def collect_screenshots(self, source_dir: str, dest_dir: str, move_files: bool = True) -> int:
        """جمع‌آوری اسکرین‌شات‌ها از پوشه مبدا"""
        source_path = Path(source_dir).expanduser().resolve()
        dest_path = Path(dest_dir).expanduser().resolve()
        
        if not source_path.exists() or not source_path.is_dir():
            raise FileNotFoundError(f"پوشه منبع وجود ندارد: {source_path}")
        
        self.ensure_directory(dest_path)
        
        # جمع‌آوری فایل‌های اسکرین‌شات
        screenshot_files = []
        self.logger.info(f"جستجو در پوشه: {source_path}")
        
        for entry in source_path.rglob("*"):
            if self.is_screenshot_file(entry):
                screenshot_files.append(entry)
        
        if not screenshot_files:
            self.logger.info("فایل اسکرین‌شاتی یافت نشد")
            return 0
        
        self.logger.info(f"تعداد اسکرین‌شات‌های یافت شده: {len(screenshot_files)}")
        
        # پردازش فایل‌ها
        moved_count = 0
        if TQDM_AVAILABLE:
            progress_bar = tqdm(screenshot_files, desc="پردازش اسکرین‌شات‌ها")
        else:
            progress_bar = screenshot_files
        
        for screenshot_file in progress_bar:
            try:
                if move_files:
                    self.move_file_safe(screenshot_file, dest_path)
                else:
                    # کپی بدون حذف فایل اصلی
                    destination = dest_path / screenshot_file.name
                    counter = 1
                    while destination.exists():
                        stem, suffix = screenshot_file.stem, screenshot_file.suffix
                        destination = dest_path / f"{stem} ({counter}){suffix}"
                        counter += 1
                    shutil.copy2(str(screenshot_file), str(destination))
                    self.logger.info(f"کپی شد: {screenshot_file.name} -> {destination}")
                
                moved_count += 1
                
            except Exception as e:
                self.logger.error(f"خطا در پردازش {screenshot_file}: {e}")
        
        if TQDM_AVAILABLE:
            progress_bar.close()
        
        return moved_count
    
    def scan_and_report(self, source_dir: str) -> List[Path]:
        """اسکن و گزارش اسکرین‌شات‌ها بدون انتقال"""
        source_path = Path(source_dir).expanduser().resolve()
        
        if not source_path.exists():
            raise FileNotFoundError(f"پوشه منبع وجود ندارد: {source_path}")
        
        screenshot_files = []
        for entry in source_path.rglob("*"):
            if self.is_screenshot_file(entry):
                screenshot_files.append(entry)
        
        return screenshot_files


def main():
    """تابع اصلی"""
    parser = argparse.ArgumentParser(description="جمع‌آوری اسکرین‌شات‌ها")
    parser.add_argument("source", nargs='?', help="پوشه مبدا برای جستجو (اختیاری، از .env خوانده می‌شود)")
    parser.add_argument("destination", nargs='?', help="پوشه مقصد (اختیاری، از .env خوانده می‌شود)")
    parser.add_argument("--copy", action="store_true", help="کپی بدون حذف فایل‌های اصلی")
    parser.add_argument("--scan-only", action="store_true", help="فقط اسکن و گزارش")
    
    args = parser.parse_args()
    
    print("📸 جمع‌آوری کننده اسکرین‌شات‌ها")
    print("=" * 40)
    
    try:
        collector = ScreenshotCollector()
        
        # تعیین مسیرهای منبع و مقصد
        source_path = args.source or os.getenv("SCREENSHOT_SOURCE_DIR") or os.getenv("INPUT_DIRECTORY")
        dest_path = args.destination or os.getenv("SCREENSHOT_DEST_DIR") or os.getenv("OUTPUT_DIRECTORY")
        
        if not source_path:
            print("❌ خطا: پوشه منبع مشخص نشده")
            print("لطفاً مسیر را به عنوان آرگومان وارد کنید یا در فایل .env تنظیم کنید:")
            print("SCREENSHOT_SOURCE_DIR=/path/to/source")
            return 1
        
        if args.scan_only:
            # فقط اسکن و گزارش
            screenshots = collector.scan_and_report(source_path)
            print(f"\n📊 نتایج اسکن:")
            print(f"پوشه منبع: {source_path}")
            print(f"تعداد اسکرین‌شات‌های یافت شده: {len(screenshots)}")
            
            if screenshots:
                print("\nفایل‌های یافت شده:")
                for screenshot in screenshots[:10]:  # نمایش 10 فایل اول
                    print(f"  📸 {screenshot.name}")
                if len(screenshots) > 10:
                    print(f"  ... و {len(screenshots) - 10} فایل دیگر")
        
        else:
            # جمع‌آوری و انتقال
            if not dest_path:
                print("❌ خطا: پوشه مقصد مشخص نشده")
                print("لطفاً مسیر را به عنوان آرگومان وارد کنید یا در فایل .env تنظیم کنید:")
                print("SCREENSHOT_DEST_DIR=/path/to/destination")
                return 1
            
            print(f"📂 منبع: {source_path}")
            print(f"📂 مقصد: {dest_path}")
            
            move_files = not args.copy
            moved_count = collector.collect_screenshots(
                source_path, 
                dest_path, 
                move_files=move_files
            )
            
            action = "منتقل" if move_files else "کپی"
            print(f"\n✅ عملیات تکمیل شد")
            print(f"تعداد فایل‌های {action} شده: {moved_count}")
            print(f"مقصد: {dest_path}")
    
    except Exception as e:
        print(f"❌ خطا: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

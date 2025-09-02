#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سازماندهی فایل‌ها
سازماندهی و دسته‌بندی فایل‌های تصویری و ویدیویی بر اساس معیارهای مختلف
"""

import os
import shutil
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set
from collections import defaultdict

# کتابخانه‌های اختیاری
try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️ کتابخانه Pillow نصب نیست. استخراج اطلاعات EXIF محدود خواهد بود.")

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    print("⚠️ کتابخانه tqdm نصب نیست. نوار پیشرفت نمایش داده نمی‌شود.")

class FileOrganizer:
    """کلاس سازماندهی فایل‌ها"""
    
    def __init__(self):
        self.setup_logging()
        self.image_extensions = {
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff',
            '.webp', '.heic', '.dng', '.raw', '.svg', '.ico'
        }
        self.video_extensions = {
            '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv',
            '.webm', '.mpeg', '.mpg', '.ts', '.m4v', '.3gp'
        }
        self.screenshot_patterns = [
            'screenshot', 'snip', 'snipping', 'screen shot', 'screencast', 'اسکرین'
        ]
        
    def setup_logging(self):
        """تنظیم سیستم لاگینگ"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f'file_organizer_{timestamp}.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def get_file_info(self, file_path: Path) -> Dict:
        """استخراج اطلاعات فایل"""
        info = {
            'path': str(file_path),
            'name': file_path.name,
            'stem': file_path.stem,
            'suffix': file_path.suffix.lower(),
            'size': file_path.stat().st_size,
            'creation_time': datetime.fromtimestamp(file_path.stat().st_ctime),
            'modification_time': datetime.fromtimestamp(file_path.stat().st_mtime),
            'is_image': file_path.suffix.lower() in self.image_extensions,
            'is_video': file_path.suffix.lower() in self.video_extensions,
            'is_screenshot': self.is_screenshot(file_path),
            'camera_info': None,
            'dimensions': None
        }
        
        # استخراج اطلاعات EXIF برای تصاویر
        if info['is_image'] and PIL_AVAILABLE:
            try:
                exif_info = self.extract_exif_info(file_path)
                info.update(exif_info)
            except Exception as e:
                self.logger.debug(f"خطا در استخراج EXIF از {file_path}: {e}")
        
        return info
    
    def is_screenshot(self, file_path: Path) -> bool:
        """تشخیص اسکرین‌شات بودن فایل"""
        filename = file_path.name.lower()
        for pattern in self.screenshot_patterns:
            if pattern in filename:
                return True
        return False
    
    def extract_exif_info(self, file_path: Path) -> Dict:
        """استخراج اطلاعات EXIF از تصویر"""
        exif_info = {
            'camera_info': None,
            'dimensions': None,
            'date_taken': None,
            'gps_info': None
        }
        
        try:
            with Image.open(file_path) as img:
                # ابعاد تصویر
                exif_info['dimensions'] = f"{img.width}x{img.height}"
                
                # اطلاعات EXIF
                exif_data = img._getexif()
                if exif_data:
                    for tag_id, value in exif_data.items():
                        tag = TAGS.get(tag_id, tag_id)
                        
                        # اطلاعات دوربین
                        if tag == 'Make':
                            camera_make = value
                        elif tag == 'Model':
                            camera_model = value
                            if 'camera_make' in locals():
                                exif_info['camera_info'] = f"{camera_make} {camera_model}"
                            else:
                                exif_info['camera_info'] = camera_model
                        
                        # تاریخ گرفتن عکس
                        elif tag == 'DateTime':
                            try:
                                exif_info['date_taken'] = datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                            except:
                                pass
                        
                        # اطلاعات GPS
                        elif tag == 'GPSInfo':
                            exif_info['gps_info'] = "موجود"
                            
        except Exception as e:
            self.logger.debug(f"خطا در پردازش EXIF {file_path}: {e}")
        
        return exif_info
    
    def organize_by_date(self, files: List[Dict], output_dir: Path, date_format: str = "%Y/%m") -> Dict:
        """سازماندهی بر اساس تاریخ"""
        organized = defaultdict(list)
        
        for file_info in files:
            # اولویت با تاریخ گرفتن عکس
            date_to_use = file_info.get('date_taken') or file_info['creation_time']
            date_folder = date_to_use.strftime(date_format)
            
            dest_path = output_dir / "by_date" / date_folder
            organized[str(dest_path)].append(file_info)
        
        return dict(organized)
    
    def organize_by_type(self, files: List[Dict], output_dir: Path) -> Dict:
        """سازماندهی بر اساس نوع فایل"""
        organized = defaultdict(list)
        
        for file_info in files:
            if file_info['is_screenshot']:
                folder = "screenshots"
            elif file_info['is_image']:
                folder = "images"
            elif file_info['is_video']:
                folder = "videos"
            else:
                folder = "others"
            
            dest_path = output_dir / "by_type" / folder
            organized[str(dest_path)].append(file_info)
        
        return dict(organized)
    
    def organize_by_camera(self, files: List[Dict], output_dir: Path) -> Dict:
        """سازماندهی بر اساس دوربین"""
        organized = defaultdict(list)
        
        for file_info in files:
            if file_info.get('camera_info'):
                # پاک‌سازی نام دوربین برای استفاده در نام پوشه
                camera_name = file_info['camera_info'].replace('/', '_').replace('\\', '_')
                folder = f"camera_{camera_name}"
            else:
                folder = "unknown_camera"
            
            dest_path = output_dir / "by_camera" / folder
            organized[str(dest_path)].append(file_info)
        
        return dict(organized)
    
    def organize_by_size(self, files: List[Dict], output_dir: Path) -> Dict:
        """سازماندهی بر اساس اندازه فایل"""
        organized = defaultdict(list)
        
        for file_info in files:
            size_mb = file_info['size'] / (1024 * 1024)
            
            if size_mb < 1:
                folder = "small_under_1mb"
            elif size_mb < 10:
                folder = "medium_1_10mb"
            elif size_mb < 50:
                folder = "large_10_50mb"
            else:
                folder = "very_large_over_50mb"
            
            dest_path = output_dir / "by_size" / folder
            organized[str(dest_path)].append(file_info)
        
        return dict(organized)
    
    def organize_by_resolution(self, files: List[Dict], output_dir: Path) -> Dict:
        """سازماندهی بر اساس رزولوشن"""
        organized = defaultdict(list)
        
        for file_info in files:
            if not file_info['is_image'] or not file_info.get('dimensions'):
                dest_path = output_dir / "by_resolution" / "unknown"
                organized[str(dest_path)].append(file_info)
                continue
            
            try:
                width, height = map(int, file_info['dimensions'].split('x'))
                total_pixels = width * height
                
                if total_pixels < 1000000:  # کمتر از 1 مگاپیکسل
                    folder = "low_resolution"
                elif total_pixels < 5000000:  # 1-5 مگاپیکسل
                    folder = "medium_resolution"
                elif total_pixels < 20000000:  # 5-20 مگاپیکسل
                    folder = "high_resolution"
                else:  # بیش از 20 مگاپیکسل
                    folder = "ultra_high_resolution"
                
                dest_path = output_dir / "by_resolution" / folder
                organized[str(dest_path)].append(file_info)
                
            except:
                dest_path = output_dir / "by_resolution" / "unknown"
                organized[str(dest_path)].append(file_info)
        
        return dict(organized)
    
    def create_directories(self, organized_files: Dict) -> None:
        """ایجاد پوشه‌های مورد نیاز"""
        for dest_path in organized_files.keys():
            Path(dest_path).mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"پوشه ایجاد شد: {dest_path}")
    
    def move_files(self, organized_files: Dict, copy_mode: bool = False) -> Dict:
        """انتقال یا کپی فایل‌ها"""
        stats = {
            'moved': 0,
            'copied': 0,
            'errors': 0,
            'duplicates': 0
        }
        
        operation = "کپی" if copy_mode else "انتقال"
        self.logger.info(f"شروع {operation} فایل‌ها...")
        
        # محاسبه تعداد کل فایل‌ها برای نوار پیشرفت
        total_files = sum(len(files) for files in organized_files.values())
        
        if TQDM_AVAILABLE:
            progress_bar = tqdm(total=total_files, desc=f"{operation} فایل‌ها")
        else:
            progress_bar = None
        
        for dest_path, files in organized_files.items():
            dest_dir = Path(dest_path)
            
            for file_info in files:
                try:
                    source_path = Path(file_info['path'])
                    dest_file_path = dest_dir / source_path.name
                    
                    # مدیریت فایل‌های تکراری
                    counter = 1
                    while dest_file_path.exists():
                        stem = source_path.stem
                        suffix = source_path.suffix
                        dest_file_path = dest_dir / f"{stem}_{counter}{suffix}"
                        counter += 1
                        stats['duplicates'] += 1
                    
                    # انتقال یا کپی فایل
                    if copy_mode:
                        shutil.copy2(str(source_path), str(dest_file_path))
                        stats['copied'] += 1
                    else:
                        shutil.move(str(source_path), str(dest_file_path))
                        stats['moved'] += 1
                    
                    if progress_bar:
                        progress_bar.update(1)
                        
                except Exception as e:
                    self.logger.error(f"خطا در {operation} {file_info['path']}: {e}")
                    stats['errors'] += 1
                    if progress_bar:
                        progress_bar.update(1)
        
        if progress_bar:
            progress_bar.close()
        
        return stats
    
    def generate_report(self, organized_files: Dict, stats: Dict, output_dir: Path) -> str:
        """تولید گزارش سازماندهی"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = output_dir / f"organization_report_{timestamp}.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("گزارش سازماندهی فایل‌ها\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"تاریخ سازماندهی: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # آمار کلی
            f.write("آمار کلی:\n")
            f.write("-" * 20 + "\n")
            f.write(f"فایل‌های منتقل شده: {stats['moved']}\n")
            f.write(f"فایل‌های کپی شده: {stats['copied']}\n")
            f.write(f"خطاها: {stats['errors']}\n")
            f.write(f"فایل‌های تکراری: {stats['duplicates']}\n\n")
            
            # جزئیات پوشه‌ها
            f.write("جزئیات پوشه‌ها:\n")
            f.write("-" * 20 + "\n")
            for dest_path, files in organized_files.items():
                f.write(f"📁 {dest_path}: {len(files)} فایل\n")
            
            f.write("\n" + "=" * 50 + "\n")
        
        return str(report_path)
    
    def organize_files(self, source_dir: str, output_dir: str, 
                      organization_type: str, copy_mode: bool = False,
                      date_format: str = "%Y/%m") -> Dict:
        """سازماندهی کامل فایل‌ها"""
        source_path = Path(source_dir)
        output_path = Path(output_dir)
        
        if not source_path.exists():
            raise FileNotFoundError(f"پوشه منبع وجود ندارد: {source_path}")
        
        output_path.mkdir(parents=True, exist_ok=True)
        
        # جمع‌آوری اطلاعات فایل‌ها
        self.logger.info("جمع‌آوری اطلاعات فایل‌ها...")
        files_info = []
        
        for file_path in source_path.rglob("*"):
            if file_path.is_file() and (
                file_path.suffix.lower() in self.image_extensions or 
                file_path.suffix.lower() in self.video_extensions
            ):
                file_info = self.get_file_info(file_path)
                files_info.append(file_info)
        
        if not files_info:
            return {"error": "هیچ فایل تصویری یا ویدیویی یافت نشد"}
        
        self.logger.info(f"تعداد فایل‌های یافت شده: {len(files_info)}")
        
        # سازماندهی بر اساس نوع انتخاب شده
        if organization_type == "date":
            organized_files = self.organize_by_date(files_info, output_path, date_format)
        elif organization_type == "type":
            organized_files = self.organize_by_type(files_info, output_path)
        elif organization_type == "camera":
            organized_files = self.organize_by_camera(files_info, output_path)
        elif organization_type == "size":
            organized_files = self.organize_by_size(files_info, output_path)
        elif organization_type == "resolution":
            organized_files = self.organize_by_resolution(files_info, output_path)
        else:
            raise ValueError(f"نوع سازماندهی نامعتبر: {organization_type}")
        
        # ایجاد پوشه‌ها
        self.create_directories(organized_files)
        
        # انتقال یا کپی فایل‌ها
        stats = self.move_files(organized_files, copy_mode)
        
        # تولید گزارش
        report_path = self.generate_report(organized_files, stats, output_path)
        
        return {
            "organization_type": organization_type,
            "total_files": len(files_info),
            "folders_created": len(organized_files),
            "stats": stats,
            "report_path": report_path
        }


def main():
    """تابع اصلی"""
    parser = argparse.ArgumentParser(description="سازماندهی فایل‌های تصویری و ویدیویی")
    parser.add_argument("source", nargs='?', help="پوشه منبع (اختیاری، از .env خوانده می‌شود)")
    parser.add_argument("output", nargs='?', help="پوشه مقصد (اختیاری، از .env خوانده می‌شود)")
    parser.add_argument("-t", "--type", choices=["date", "type", "camera", "size", "resolution"],
                       help="نوع سازماندهی")
    parser.add_argument("--copy", action="store_true", help="کپی بدون حذف فایل‌های اصلی")
    parser.add_argument("--date-format", help="فرمت تاریخ برای سازماندهی (مثال: %%Y/%%m، %%Y-%%m-%%d)")
    
    args = parser.parse_args()
    
    print("📁 سازماندهی کننده فایل‌ها")
    print("=" * 40)
    
    try:
        organizer = FileOrganizer()
        
        # تعیین مسیرهای ورودی و خروجی
        source_path = args.source or os.getenv("INPUT_DIRECTORY")
        output_path = args.output or os.getenv("OUTPUT_DIRECTORY")
        
        if not source_path:
            print("❌ خطا: پوشه منبع مشخص نشده")
            print("لطفاً مسیر را به عنوان آرگومان وارد کنید یا در فایل .env تنظیم کنید:")
            print("INPUT_DIRECTORY=/path/to/source")
            return 1
            
        if not output_path:
            print("❌ خطا: پوشه مقصد مشخص نشده")
            print("لطفاً مسیر را به عنوان آرگومان وارد کنید یا در فایل .env تنظیم کنید:")
            print("OUTPUT_DIRECTORY=/path/to/output")
            return 1
        
        # تنظیمات از .env یا آرگومان‌ها
        organization_type = args.type or os.getenv("DEFAULT_ORGANIZATION_TYPE", "type")
        date_format = args.date_format or os.getenv("DATE_FORMAT", "%Y/%m")
        
        print(f"📂 پوشه منبع: {source_path}")
        print(f"📂 پوشه مقصد: {output_path}")
        print(f"🔧 نوع سازماندهی: {organization_type}")
        print(f"📋 حالت: {'کپی' if args.copy else 'انتقال'}")
        
        results = organizer.organize_files(
            source_path, 
            output_path, 
            organization_type,
            args.copy,
            date_format
        )
        
        if "error" in results:
            print(f"❌ خطا: {results['error']}")
            return 1
        
        # نمایش نتایج
        print("\n📊 نتایج سازماندهی:")
        print(f"📁 تعداد فایل‌ها: {results['total_files']}")
        print(f"📂 پوشه‌های ایجاد شده: {results['folders_created']}")
        
        stats = results['stats']
        if stats['moved'] > 0:
            print(f"✅ فایل‌های منتقل شده: {stats['moved']}")
        if stats['copied'] > 0:
            print(f"📋 فایل‌های کپی شده: {stats['copied']}")
        if stats['duplicates'] > 0:
            print(f"🔄 فایل‌های تکراری: {stats['duplicates']}")
        if stats['errors'] > 0:
            print(f"❌ خطاها: {stats['errors']}")
        
        print(f"\n📄 گزارش: {results['report_path']}")
        
    except KeyboardInterrupt:
        print("\n⏹️ عملیات توسط کاربر متوقف شد")
        return 1
    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

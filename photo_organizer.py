#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اسکریپت سازماندهی فایل‌های عکس و فیلم
قابل اجرا در ویندوز، مک و لینوکس
فقط از کتابخانه‌های پایتون استفاده می‌کند
"""

import os
import sys
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Tuple
import platform
import time

# کتابخانه‌های پایتون برای استخراج متادیتا
try:
    from hachoir.parser import createParser
    from hachoir.metadata import extractMetadata
    from hachoir.core.tools import makePrintable
    from hachoir.core.i18n import getTerminalCharset
except ImportError:
    print("خطا: کتابخانه hachoir نصب نشده است!")
    print("برای نصب: pip install hachoir")
    sys.exit(1)

class PhotoOrganizer:
    def __init__(self, config: Dict):
        self.config = config
        self.setup_logging()
        
    def setup_logging(self):
        """تنظیم سیستم لاگ"""
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        logging.basicConfig(
            level=logging.DEBUG,  # تغییر به DEBUG برای اطلاعات بیشتر
            format=log_format,
            handlers=[
                logging.FileHandler(self.config['log_file'], encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def create_directories(self):
        """ایجاد پوشه‌های مورد نیاز"""
        directories = [
            self.config['destination_folder'],
            self.config['unsorted_folder'],
            self.config['screenshot_folder']
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            self.logger.info(f"پوشه ایجاد/بررسی شد: {directory}")
            
    def get_file_type(self, file_path: Path) -> str:
        """تشخیص نوع فایل"""
        extension = file_path.suffix.lower()
        
        image_extensions = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.gif', '.heic', '.dng', '.psd', '.webp'}
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.m4v', '.3gp', '.webm'}
        
        if extension in image_extensions:
            return "image"
        elif extension in video_extensions:
            return "video"
        else:
            return "unknown"
            
    def extract_metadata(self, file_path: Path) -> Optional[Dict]:
        """استخراج متادیتا با استفاده از hachoir"""
        try:
            parser = createParser(str(file_path))
            if not parser:
                self.logger.debug(f"هیچ parser برای {file_path.name} یافت نشد")
                return None
                
            with parser:
                metadata = extractMetadata(parser)
                if not metadata:
                    self.logger.debug(f"متادیتا برای {file_path.name} یافت نشد")
                    return None
                    
            # تبدیل متادیتا به دیکشنری
            meta_dict = {}
            
            # تاریخ‌ها
            if hasattr(metadata, 'creation_date') and metadata.creation_date:
                meta_dict['creation_date'] = metadata.creation_date
                self.logger.debug(f"تاریخ ایجاد: {metadata.creation_date}")
            if hasattr(metadata, 'last_modification') and metadata.last_modification:
                meta_dict['last_modification'] = metadata.last_modification
                self.logger.debug(f"تاریخ تغییر: {metadata.last_modification}")
            
            # ابعاد
            if hasattr(metadata, 'width') and hasattr(metadata, 'height'):
                meta_dict['width'] = metadata.width
                meta_dict['height'] = metadata.height
                self.logger.debug(f"ابعاد: {metadata.width}x{metadata.height}")
                
            # اطلاعات دوربین
            if hasattr(metadata, 'camera_manufacturer') and metadata.camera_manufacturer:
                meta_dict['camera_manufacturer'] = metadata.camera_manufacturer
            if hasattr(metadata, 'camera_model') and metadata.camera_model:
                meta_dict['camera_model'] = metadata.camera_model
                
            # اطلاعات نرم‌افزار
            if hasattr(metadata, 'software') and metadata.software:
                meta_dict['software'] = metadata.software
                self.logger.debug(f"نرم‌افزار: {metadata.software}")
                
            # اطلاعات اضافی
            if hasattr(metadata, 'comment') and metadata.comment:
                meta_dict['comment'] = metadata.comment
                
            # اطلاعات اضافی از hachoir
            for key in dir(metadata):
                if not key.startswith('_') and key not in ['creation_date', 'last_modification', 'width', 'height', 'camera_manufacturer', 'camera_model', 'software', 'comment']:
                    try:
                        value = getattr(metadata, key)
                        if value and str(value).strip():
                            meta_dict[key] = value
                            self.logger.debug(f"{key}: {value}")
                    except:
                        continue
                        
            self.logger.debug(f"متادیتای استخراج شده برای {file_path.name}: {meta_dict}")
            return meta_dict
            
        except Exception as e:
            self.logger.error(f"خطا در استخراج متادیتا از {file_path}: {e}")
            return None
            
    def get_file_date(self, file_path: Path, file_type: str) -> Optional[datetime]:
        """استخراج تاریخ از فایل با استفاده از متادیتا"""
        try:
            metadata = self.extract_metadata(file_path)
            
            if metadata:
                self.logger.debug(f"متادیتا یافت شد برای {file_path.name}: {metadata}")
                
                # فقط از تاریخ ایجاد استفاده کنید
                if 'creation_date' in metadata and metadata['creation_date']:
                    self.logger.info(f"تاریخ ایجاد یافت: {metadata['creation_date']}")
                    return metadata['creation_date']
            
            # اگر تاریخ ایجاد موجود نبود، None برگردان
            self.logger.warning(f"تاریخ ایجاد برای فایل {file_path.name} یافت نشد")
            return None
                
        except Exception as e:
            self.logger.error(f"خطا در استخراج تاریخ از فایل {file_path}: {e}")
            return None
            
    def is_screenshot(self, file_path: Path) -> bool:
        """تشخیص اسکرین‌شات بر اساس متادیتا"""
        try:
            metadata = self.extract_metadata(file_path)
            if not metadata:
                return False
                
            # بررسی نرم‌افزار
            software = metadata.get('software', '').lower()
            if software:
                screenshot_keywords = ['screenshot', 'capture', 'grab', 'snip']
                if any(keyword in software for keyword in screenshot_keywords):
                    return True
                    
            # بررسی کامنت
            comment = metadata.get('comment', '').lower()
            if comment:
                screenshot_keywords = ['screenshot', 'capture', 'grab', 'snip']
                if any(keyword in comment for keyword in screenshot_keywords):
                    return True
                    
            # بررسی نام فایل
            filename = file_path.name.lower()
            if 'screenshot' in filename or 'capture' in filename:
                return True
                
            return False
            
        except Exception:
            return False
            
    def get_image_dimensions(self, file_path: Path) -> Optional[Tuple[int, int]]:
        """استخراج ابعاد تصویر از متادیتا"""
        try:
            metadata = self.extract_metadata(file_path)
            if not metadata:
                return None
                
            width = metadata.get('width')
            height = metadata.get('height')
            
            if width and height:
                return (int(width), int(height))
        except Exception as e:
            self.logger.error(f"خطا در استخراج ابعاد تصویر {file_path}: {e}")
            
        return None
        
    def process_file(self, file_path: Path) -> bool:
        """پردازش یک فایل"""
        try:
            file_type = self.get_file_type(file_path)
            
            if file_type == "unknown":
                self.logger.warning(f"نوع فایل پشتیبانی نمی‌شود: {file_path}")
                return False
            
            # تشخیص فایل‌های شبکه‌های اجتماعی (اولویت اول)
            social_media_platform = self.detect_social_media_file(file_path)
            
            # اگر از نام فایل تشخیص داده نشد، از متادیتا امتحان کن
            if not social_media_platform:
                metadata = self.extract_metadata(file_path)
                social_media_platform = self.detect_social_media_from_metadata(metadata)
            
            # اگر فایل شبکه‌های اجتماعی بود، انتقال به فولدر مربوطه
            if social_media_platform:
                self.logger.info(f"فایل شبکه‌های اجتماعی یافت شد: {file_path.name} -> {social_media_platform}")
                
                # انتقال به فولدر شبکه‌های اجتماعی با سازماندهی batch
                target_path = self.organize_social_media_files(file_path, social_media_platform)
                
                # بررسی تکراری بودن نام فایل
                target_path = self.get_unique_filename(target_path)
                
                shutil.move(str(file_path), str(target_path))
                self.logger.info(f"فایل شبکه‌های اجتماعی انتقال یافت: {file_path.name} -> social-media/{social_media_platform}/{target_path.name}")
                return True
            
            # بررسی تکراری بودن در فولدر منبع
            duplicate_in_source = self.is_duplicate_in_source(file_path)
            if duplicate_in_source:
                self.logger.info(f"فایل تکراری در منبع یافت شد: {file_path.name} (تکراری: {duplicate_in_source})")
                
                # انتقال به فولدر duplicate با سازماندهی در فولدرهای 500 تایی
                target_path = self.organize_duplicate_files(file_path)
                
                # بررسی تکراری بودن نام فایل
                target_path = self.get_unique_filename(target_path)
                
                shutil.move(str(file_path), str(target_path))
                self.logger.info(f"فایل تکراری به duplicate انتقال یافت: {file_path.name} -> {target_path}")
                return True
                
            # بررسی اسکرین‌شات
            if self.is_screenshot(file_path):
                target_path = Path(self.config['screenshot_folder']) / file_path.name
                # بررسی تکراری بودن نام فایل
                target_path = self.get_unique_filename(target_path)
                shutil.move(str(file_path), str(target_path))
                self.logger.info(f"اسکرین‌شات انتقال یافت: {file_path.name} -> {target_path}")
                return True
                
            # استخراج تاریخ
            file_date = self.get_file_date(file_path, file_type)
            
            if file_date:
                # ایجاد پوشه بر اساس تاریخ
                folder_name = file_date.strftime("%Y-%m-%d")
                target_folder = Path(self.config['destination_folder']) / folder_name
                target_folder.mkdir(parents=True, exist_ok=True)
                
                # بررسی فایل تکراری در فولدر مقصد
                original_target = target_folder / file_path.name
                if self.is_duplicate_file(file_path, original_target):
                    # فایل تکراری - انتقال به فولدر duplicate با سازماندهی در فولدرهای 500 تایی
                    target_path = self.organize_duplicate_files(file_path)
                    
                    # بررسی تکراری بودن نام فایل
                    target_path = self.get_unique_filename(target_path)
                    
                    shutil.move(str(file_path), str(target_path))
                    self.logger.info(f"فایل تکراری به duplicate انتقال یافت: {file_path.name} -> {target_path}")
                    return True
                else:
                    # فایل غیرتکراری - انتقال عادی
                    target_path = self.get_unique_filename(original_target)
                    
                    # اگر نام تغییر کرد، اطلاع بده
                    if target_path.name != file_path.name:
                        self.logger.info(f"نام فایل تغییر کرد: {file_path.name} -> {target_path.name}")
                    
                    shutil.move(str(file_path), str(target_path))
                    self.logger.info(f"فایل انتقال یافت: {file_path.name} -> {folder_name}/{target_path.name}")
                    return True
            else:
                # انتقال به پوشه unsorted با سازماندهی در فولدرهای 500 تایی
                target_path = self.organize_unsorted_files(file_path)
                
                # بررسی تکراری بودن نام فایل
                target_path = self.get_unique_filename(target_path)
                
                shutil.move(str(file_path), str(target_path))
                self.logger.warning(f"فایل بدون تاریخ به unsorted انتقال یافت: {file_path.name} -> {target_path}")
                return False
                
        except Exception as e:
            self.logger.error(f"خطا در پردازش فایل {file_path}: {e}")
            return False
            
    def is_duplicate_in_source(self, file_path: Path) -> Optional[Path]:
        """بررسی تکراری بودن فایل در کل فولدر منبع"""
        source_path = Path(self.config['source_folder'])
        
        for existing_file in source_path.rglob("*"):
            if existing_file.is_file() and existing_file != file_path:
                if (existing_file.name == file_path.name and 
                    existing_file.stat().st_size == file_path.stat().st_size):
                    return existing_file
        return None
    
    def is_duplicate_file(self, file_path: Path, target_path: Path) -> bool:
        """بررسی تکراری بودن فایل بر اساس نام و سایز"""
        if not target_path.exists():
            return False
            
        # بررسی سایز فایل
        source_size = file_path.stat().st_size
        target_size = target_path.stat().st_size
        
        # اگر نام و سایز یکسان باشد، تکراری است
        return source_size == target_size
    
    def get_unique_filename(self, file_path: Path) -> Path:
        """ایجاد نام فایل منحصر به فرد"""
        if not file_path.exists():
            return file_path
            
        counter = 1
        stem = file_path.stem
        suffix = file_path.suffix
        parent = file_path.parent
        
        # بررسی تکراری بودن نام فایل
        original_name = file_path.name
        while file_path.exists():
            new_name = f"{stem}_{counter}{suffix}"
            file_path = parent / new_name
            counter += 1
            
        # اگر نام تغییر کرد، اطلاع بده
        if file_path.name != original_name:
            self.logger.info(f"نام فایل تغییر کرد: {original_name} -> {file_path.name}")
            
        return file_path
            
    def organize_files(self):
        """سازماندهی اصلی فایل‌ها"""
        self.logger.info("شروع سازماندهی فایل‌ها...")
        
        source_path = Path(self.config['source_folder'])
        if not source_path.exists():
            self.logger.error(f"پوشه منبع وجود ندارد: {source_path}")
            return
            
        # دریافت لیست فایل‌ها
        files = list(source_path.rglob("*"))
        files = [f for f in files if f.is_file()]
        
        total_files = len(files)
        self.logger.info(f"تعداد کل فایل‌ها: {total_files}")
        
        if total_files == 0:
            self.logger.warning("هیچ فایلی در پوشه منبع یافت نشد.")
            return
            
        # پردازش فایل‌ها
        processed_count = 0
        success_count = 0
        start_time = time.time()
        
        for i, file_path in enumerate(files, 1):
            self.logger.info(f"پردازش فایل {i}/{total_files}: {file_path.name}")
            
            if self.process_file(file_path):
                success_count += 1
            processed_count += 1
            
            # نمایش پیشرفت
            if i % 50 == 0:
                progress = (i / total_files) * 100
                elapsed_time = time.time() - start_time
                estimated_total = (elapsed_time / i) * total_files
                remaining_time = estimated_total - elapsed_time
                
                self.logger.info(f"پیشرفت: {progress:.1f}% ({i}/{total_files})")
                self.logger.info(f"زمان باقی‌مانده: {remaining_time/60:.1f} دقیقه")
                
        total_time = time.time() - start_time
        
        self.logger.info(f"سازماندهی فایل‌ها به پایان رسید!")
        self.logger.info(f"فایل‌های پردازش شده: {processed_count}")
        self.logger.info(f"فایل‌های موفق: {success_count}")
        self.logger.info(f"زمان کل: {total_time/60:.1f} دقیقه")
        self.logger.info(f"فایل لاگ در: {self.config['log_file']}")

    def detect_social_media_file(self, file_path: Path) -> Optional[str]:
        """تشخیص فایل‌های شبکه‌های اجتماعی بر اساس نام فایل"""
        filename = file_path.name.lower()
        
        # تشخیص واتساپ
        whatsapp_patterns = ['wa', 'whatsapp', 'img-', 'img_']
        if any(pattern in filename for pattern in whatsapp_patterns):
            return "whatsapp"
        
        # تشخیص اینستاگرام
        instagram_patterns = ['ig', 'instagram', 'insta', 'ig_', 'insta_']
        if any(pattern in filename for pattern in instagram_patterns):
            return "instagram"
        
        # تشخیص تلگرام
        telegram_patterns = ['tg', 'telegram', 'photo_', 'document_', 'tg_']
        if any(pattern in filename for pattern in telegram_patterns):
            return "telegram"
        
        return None
    
    def detect_social_media_from_metadata(self, metadata: Dict) -> Optional[str]:
        """تشخیص فایل‌های شبکه‌های اجتماعی بر اساس متادیتا"""
        if not metadata:
            return None
            
        # بررسی نرم‌افزار
        software = metadata.get('software', '').lower()
        if software:
            if 'whatsapp' in software:
                return "whatsapp"
            elif 'instagram' in software or 'ig' in software:
                return "instagram"
            elif 'telegram' in software or 'tg' in software:
                return "telegram"
        
        # بررسی کامنت
        comment = metadata.get('comment', '').lower()
        if comment:
            if 'whatsapp' in comment:
                return "whatsapp"
            elif 'instagram' in comment or 'ig' in comment:
                return "instagram"
            elif 'telegram' in comment or 'tg' in comment:
                return "telegram"
        
        # بررسی سایر فیلدهای متادیتا
        for key, value in metadata.items():
            if isinstance(value, str) and value:
                value_lower = value.lower()
                if 'whatsapp' in value_lower:
                    return "whatsapp"
                elif 'instagram' in value_lower or 'ig' in value_lower:
                    return "instagram"
                elif 'telegram' in value_lower or 'tg' in value_lower:
                    return "telegram"
        
        return None
    
    def organize_social_media_files(self, file_path: Path, platform: str) -> Path:
        """سازماندهی فایل‌های شبکه‌های اجتماعی در فولدرهای batch"""
        social_media_folder = Path(self.config['destination_folder']) / "social-media" / platform
        
        # شمارش فایل‌های موجود در فولدر پلتفرم
        existing_files = list(social_media_folder.rglob("*"))
        existing_files = [f for f in existing_files if f.is_file()]
        total_files = len(existing_files)
        
        # محاسبه شماره فولدر (هر 500 فایل در یک فولدر)
        folder_number = (total_files // 500) + 1
        folder_name = f"batch_{folder_number:03d}"
        
        # ایجاد فولدر جدید
        target_folder = social_media_folder / folder_name
        target_folder.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"فایل {file_path.name} به فولدر social-media/{platform}/{folder_name} منتقل می‌شود")
        return target_folder / file_path.name
    
    def organize_duplicate_files(self, file_path: Path) -> Path:
        """سازماندهی فایل‌های duplicate در فولدرهای 500 تایی"""
        duplicate_folder = Path(self.config['destination_folder']) / "duplicate"
        
        # شمارش فایل‌های موجود در duplicate
        existing_files = list(duplicate_folder.rglob("*"))
        existing_files = [f for f in existing_files if f.is_file()]
        total_duplicates = len(existing_files)
        
        # محاسبه شماره فولدر (هر 500 فایل در یک فولدر)
        folder_number = (total_duplicates // 500) + 1
        folder_name = f"batch_{folder_number:03d}"
        
        # ایجاد فولدر جدید
        target_folder = duplicate_folder / folder_name
        target_folder.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"فایل تکراری {file_path.name} به فولدر duplicate/{folder_name} منتقل می‌شود")
        return target_folder / file_path.name
    
    def organize_unsorted_files(self, file_path: Path) -> Path:
        """سازماندهی فایل‌های unsorted در فولدرهای 500 تایی"""
        unsorted_folder = Path(self.config['unsorted_folder'])
        
        # شمارش فایل‌های موجود در unsorted
        existing_files = list(unsorted_folder.rglob("*"))
        existing_files = [f for f in existing_files if f.is_file()]
        total_unsorted = len(existing_files)
        
        # محاسبه شماره فولدر (هر 500 فایل در یک فولدر)
        folder_number = (total_unsorted // 500) + 1
        folder_name = f"batch_{folder_number:03d}"
        
        # ایجاد فولدر جدید
        target_folder = unsorted_folder / folder_name
        target_folder.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"فایل {file_path.name} به فولدر unsorted/{folder_name} منتقل می‌شود")
        return target_folder / file_path.name

def main():
    """تابع اصلی"""
    print("=" * 60)
    print("🎯 اسکریپت سازماندهی فایل‌های عکس و فیلم")
    print("=" * 60)
    
    # دریافت ورودی از کاربر
    print("\n📁 انتخاب فولدرها:")
    
    # فولدر منبع
    while True:
        source = input("🔍 مسیر فولدر منبع (عکس‌های شما): ").strip()
        if source:
            source_path = Path(source)
            if source_path.exists() and source_path.is_dir():
                break
            else:
                print("❌ فولدر وجود ندارد یا مسیر اشتباه است!")
        else:
            print("❌ لطفاً مسیر فولدر را وارد کنید!")
    
    # فولدر مقصد
    while True:
        destination = input("📂 مسیر فولدر مقصد (سازماندهی شده): ").strip()
        if destination:
            dest_path = Path(destination)
            try:
                dest_path.mkdir(parents=True, exist_ok=True)
                print(f"✅ فولدر مقصد ایجاد/بررسی شد: {dest_path}")
                break
            except Exception as e:
                print(f"❌ خطا در ایجاد فولدر: {e}")
        else:
            print("❌ لطفاً مسیر فولدر را وارد کنید!")
    
    # ایجاد خودکار فولدرهای مورد نیاز در فولدر مقصد
    unsorted = str(Path(destination) / "unsorted")
    screenshots = str(Path(destination) / "screenshots")
    log_file = str(Path(destination) / "photo_organizer.log")
    
    print(f"✅ فولدر unsorted: {unsorted}")
    print(f"✅ فولدر screenshots: {screenshots}")
    print(f"✅ فایل لاگ: {log_file}")
    
    # نمایش تنظیمات
    print("\n⚙️ تنظیمات انتخاب شده:")
    print(f"   📁 منبع: {source}")
    print(f"   📂 مقصد: {destination}")
    print(f"   ❓ بدون تاریخ: {unsorted}")
    print(f"   📸 اسکرین‌شات: {screenshots}")
    print(f"   📝 لاگ: {log_file}")
    
    # تأیید از کاربر
    confirm = input("\n❓ آیا می‌خواهید ادامه دهید؟ (y/n): ").strip().lower()
    if confirm not in ['y', 'yes', 'بله', 'ب', 'y']:
        print("❌ عملیات لغو شد!")
        return
    
    # تنظیمات
    config = {
        'source_folder': source,
        'destination_folder': destination,
        'unsorted_folder': unsorted,
        'screenshot_folder': screenshots,
        'log_file': log_file
    }
    
    print("\n�� شروع سازماندهی فایل‌ها...")
    
    # ایجاد نمونه و اجرا
    try:
        organizer = PhotoOrganizer(config)
        organizer.create_directories()
        organizer.organize_files()
    except KeyboardInterrupt:
        print("\n\n❌ عملیات توسط کاربر متوقف شد!")
    except Exception as e:
        print(f"\n❌ خطای غیرمنتظره: {e}")
        print("لطفاً فایل لاگ را بررسی کنید.")

if __name__ == "__main__":
    main() 
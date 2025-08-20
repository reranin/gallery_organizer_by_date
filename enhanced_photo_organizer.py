#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سیستم پیشرفته سازماندهی عکس و فیلم برای چند دستگاه
پشتیبانی از 5 دوربین و موبایل مختلف با سازماندهی بر اساس تاریخ
"""

import os
import sys
import shutil
import logging
import hashlib
import yaml
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from collections import defaultdict
import time

# کتابخانه‌های متادیتا
try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
except ImportError:
    print("خطا: کتابخانه Pillow نصب نشده است!")
    print("برای نصب: pip install Pillow")
    sys.exit(1)

try:
    from hachoir.parser import createParser
    from hachoir.metadata import extractMetadata
except ImportError:
    print("خطا: کتابخانه hachoir نصب نشده است!")
    print("برای نصب: pip install hachoir")
    sys.exit(1)

try:
    import exifread
except ImportError:
    print("خطا: کتابخانه exifread نصب نشده است!")
    print("برای نصب: pip install exifread")
    sys.exit(1)


class EnhancedPhotoOrganizer:
    """سیستم پیشرفته سازماندهی عکس و فیلم"""
    
    def __init__(self, config_file: str = "device_config.yaml"):
        """مقداردهی اولیه با فایل پیکربندی"""
        self.load_config(config_file)
        self.setup_logging()
        self.stats = {
            'total_files': 0,
            'processed': 0,
            'organized': 0,
            'duplicates': 0,
            'errors': 0,
            'by_device': defaultdict(int),
            'by_date': defaultdict(int),
            'by_type': defaultdict(int)
        }
        
    def load_config(self, config_file: str):
        """بارگذاری تنظیمات از فایل YAML"""
        config_path = Path(config_file)
        if not config_path.exists():
            self.logger.error(f"فایل پیکربندی {config_file} یافت نشد!")
            self.create_default_config()
        
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
            
        self.devices = self.config.get('devices', {})
        self.organization = self.config.get('organization', {})
        self.supported_formats = self.config.get('supported_formats', {})
        self.processing = self.config.get('processing', {})
        
    def create_default_config(self):
        """ایجاد پیکربندی پیش‌فرض"""
        self.config = {
            'devices': {},
            'organization': {
                'folder_structure': 'YYYY/YYYY-MM-DD/Device',
                'max_files_per_folder': 500,
                'merge_daily_events': True,
                'separate_raw_folder': True
            },
            'supported_formats': {
                'images': ['.jpg', '.jpeg', '.png', '.heic'],
                'videos': ['.mp4', '.mov', '.avi'],
                'raw': ['.cr2', '.nef', '.arw', '.dng']
            },
            'processing': {
                'use_metadata': True,
                'parallel_processing': True,
                'max_workers': 4
            }
        }
        
    def setup_logging(self):
        """راه‌اندازی سیستم لاگ پیشرفته"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"photo_organizer_{timestamp}.log"
        
        # فرمت لاگ
        log_format = '%(asctime)s | %(levelname)-8s | %(funcName)-20s | %(message)s'
        date_format = '%Y-%m-%d %H:%M:%S'
        
        # تنظیم handlers
        handlers = [
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
        
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            datefmt=date_format,
            handlers=handlers
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("=" * 80)
        self.logger.info("سیستم پیشرفته سازماندهی عکس و فیلم - شروع")
        self.logger.info(f"فایل لاگ: {log_file}")
        self.logger.info("=" * 80)
        
    def detect_device(self, file_path: Path) -> Optional[str]:
        """تشخیص دستگاه از متادیتا"""
        try:
            metadata = self.extract_all_metadata(file_path)
            
            # بررسی سازنده و مدل
            manufacturer = metadata.get('make', '').lower()
            model = metadata.get('model', '')
            software = metadata.get('software', '').lower()
            
            # بررسی هر دستگاه تعریف شده
            for device_id, device_info in self.devices.items():
                # بررسی سازنده
                if device_info.get('manufacturer', '').lower() in manufacturer:
                    return device_id
                    
                # بررسی مدل‌ها
                if 'models' in device_info:
                    for device_model in device_info['models']:
                        if device_model.lower() in model.lower():
                            return device_id
                            
                # بررسی الگوهای نرم‌افزار
                if 'software_patterns' in device_info:
                    for pattern in device_info['software_patterns']:
                        if pattern.lower() in software:
                            return device_id
                            
            # بررسی پسوند RAW برای تشخیص دستگاه
            extension = file_path.suffix.lower()
            for device_id, device_info in self.devices.items():
                if extension in device_info.get('raw_extensions', []):
                    return device_id
                    
            return None
            
        except Exception as e:
            self.logger.debug(f"خطا در تشخیص دستگاه {file_path.name}: {e}")
            return None
            
    def extract_all_metadata(self, file_path: Path) -> Dict:
        """استخراج کامل متادیتا از تمام منابع"""
        metadata = {}
        
        # 1. استخراج با Pillow (برای عکس‌ها)
        if self.is_image(file_path):
            pil_metadata = self.extract_pil_metadata(file_path)
            if pil_metadata:
                metadata.update(pil_metadata)
                
        # 2. استخراج با exifread
        exif_metadata = self.extract_exifread_metadata(file_path)
        if exif_metadata:
            metadata.update(exif_metadata)
            
        # 3. استخراج با hachoir
        hachoir_metadata = self.extract_hachoir_metadata(file_path)
        if hachoir_metadata:
            metadata.update(hachoir_metadata)
            
        return metadata
        
    def extract_pil_metadata(self, file_path: Path) -> Optional[Dict]:
        """استخراج متادیتا با PIL"""
        try:
            image = Image.open(file_path)
            exifdata = image.getexif()
            
            if not exifdata:
                return None
                
            metadata = {}
            
            for tag_id, value in exifdata.items():
                tag = TAGS.get(tag_id, tag_id)
                
                # تبدیل مقادیر خاص
                if tag == "DateTime":
                    try:
                        metadata['datetime'] = datetime.strptime(str(value), "%Y:%m:%d %H:%M:%S")
                    except:
                        metadata['datetime'] = value
                elif tag == "DateTimeOriginal":
                    try:
                        metadata['datetime_original'] = datetime.strptime(str(value), "%Y:%m:%d %H:%M:%S")
                    except:
                        metadata['datetime_original'] = value
                elif tag == "Make":
                    metadata['make'] = str(value)
                elif tag == "Model":
                    metadata['model'] = str(value)
                elif tag == "Software":
                    metadata['software'] = str(value)
                else:
                    metadata[tag] = value
                    
            # استخراج GPS
            if hasattr(image, '_getexif'):
                exif = image._getexif()
                if exif and 34853 in exif:  # GPSInfo tag
                    gps_data = {}
                    for key in exif[34853].keys():
                        decode = GPSTAGS.get(key, key)
                        gps_data[decode] = exif[34853][key]
                    metadata['gps'] = gps_data
                    
            return metadata
            
        except Exception as e:
            self.logger.debug(f"خطا در PIL metadata: {e}")
            return None
            
    def extract_exifread_metadata(self, file_path: Path) -> Optional[Dict]:
        """استخراج متادیتا با exifread"""
        try:
            with open(file_path, 'rb') as f:
                tags = exifread.process_file(f, details=False)
                
            if not tags:
                return None
                
            metadata = {}
            
            # استخراج اطلاعات مهم
            important_tags = {
                'EXIF DateTimeOriginal': 'datetime_original',
                'EXIF DateTimeDigitized': 'datetime_digitized',
                'Image DateTime': 'datetime',
                'Image Make': 'make',
                'Image Model': 'model',
                'Image Software': 'software',
                'EXIF LensModel': 'lens_model',
                'EXIF FocalLength': 'focal_length',
                'EXIF ISOSpeedRatings': 'iso',
                'EXIF ExposureTime': 'exposure_time',
                'EXIF FNumber': 'f_number'
            }
            
            for exif_tag, meta_key in important_tags.items():
                if exif_tag in tags:
                    value = str(tags[exif_tag])
                    
                    # تبدیل تاریخ
                    if 'DateTime' in exif_tag:
                        try:
                            metadata[meta_key] = datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                        except:
                            metadata[meta_key] = value
                    else:
                        metadata[meta_key] = value
                        
            return metadata
            
        except Exception as e:
            self.logger.debug(f"خطا در exifread metadata: {e}")
            return None
            
    def extract_hachoir_metadata(self, file_path: Path) -> Optional[Dict]:
        """استخراج متادیتا با hachoir"""
        try:
            parser = createParser(str(file_path))
            if not parser:
                return None
                
            with parser:
                hachoir_meta = extractMetadata(parser)
                if not hachoir_meta:
                    return None
                    
            metadata = {}
            
            # استخراج اطلاعات
            if hasattr(hachoir_meta, 'creation_date'):
                metadata['creation_date'] = hachoir_meta.creation_date
            if hasattr(hachoir_meta, 'last_modification'):
                metadata['last_modification'] = hachoir_meta.last_modification
            if hasattr(hachoir_meta, 'camera_manufacturer'):
                metadata['make'] = hachoir_meta.camera_manufacturer
            if hasattr(hachoir_meta, 'camera_model'):
                metadata['model'] = hachoir_meta.camera_model
            if hasattr(hachoir_meta, 'width'):
                metadata['width'] = hachoir_meta.width
            if hasattr(hachoir_meta, 'height'):
                metadata['height'] = hachoir_meta.height
            if hasattr(hachoir_meta, 'duration'):
                metadata['duration'] = hachoir_meta.duration
                
            return metadata
            
        except Exception as e:
            self.logger.debug(f"خطا در hachoir metadata: {e}")
            return None
            
    def get_file_date(self, file_path: Path) -> Optional[datetime]:
        """استخراج بهترین تاریخ موجود از فایل"""
        metadata = self.extract_all_metadata(file_path)
        
        # اولویت تاریخ‌ها
        date_fields = [
            'datetime_original',
            'datetime_digitized', 
            'datetime',
            'creation_date',
            'last_modification'
        ]
        
        for field in date_fields:
            if field in metadata and metadata[field]:
                date_value = metadata[field]
                if isinstance(date_value, datetime):
                    return date_value
                    
        # تلاش برای استخراج از نام فایل
        filename_date = self.extract_date_from_filename(file_path)
        if filename_date:
            return filename_date
            
        # استفاده از تاریخ سیستم فایل
        return datetime.fromtimestamp(file_path.stat().st_mtime)
        
    def extract_date_from_filename(self, file_path: Path) -> Optional[datetime]:
        """استخراج تاریخ از نام فایل"""
        filename = file_path.stem
        
        # الگوهای رایج تاریخ در نام فایل
        patterns = [
            (r'(\d{4})[-_](\d{2})[-_](\d{2})[-_](\d{2})[-_](\d{2})[-_](\d{2})', '%Y-%m-%d-%H-%M-%S'),
            (r'(\d{8})[-_](\d{6})', '%Y%m%d-%H%M%S'),
            (r'IMG[-_](\d{8})[-_](\d{6})', '%Y%m%d-%H%M%S'),
            (r'VID[-_](\d{8})[-_](\d{6})', '%Y%m%d-%H%M%S'),
            (r'(\d{4})(\d{2})(\d{2})[-_](\d{2})(\d{2})(\d{2})', '%Y%m%d-%H%M%S'),
        ]
        
        for pattern, date_format in patterns:
            match = re.search(pattern, filename)
            if match:
                try:
                    date_str = '-'.join(match.groups())
                    return datetime.strptime(date_str, date_format)
                except:
                    continue
                    
        return None
        
    def is_image(self, file_path: Path) -> bool:
        """بررسی فایل تصویری"""
        return file_path.suffix.lower() in self.supported_formats.get('images', [])
        
    def is_video(self, file_path: Path) -> bool:
        """بررسی فایل ویدیویی"""
        return file_path.suffix.lower() in self.supported_formats.get('videos', [])
        
    def is_raw(self, file_path: Path) -> bool:
        """بررسی فایل RAW"""
        return file_path.suffix.lower() in self.supported_formats.get('raw', [])
        
    def calculate_file_hash(self, file_path: Path, chunk_size: int = 8192) -> str:
        """محاسبه هش فایل برای تشخیص تکراری"""
        hash_md5 = hashlib.md5()
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                hash_md5.update(chunk)
                
        return hash_md5.hexdigest()
        
    def is_duplicate(self, file_path: Path, existing_files: Dict[str, Path]) -> bool:
        """بررسی تکراری بودن فایل"""
        file_hash = self.calculate_file_hash(file_path)
        return file_hash in existing_files
        
    def create_folder_structure(self, base_path: Path, file_date: datetime, 
                               device: Optional[str] = None) -> Path:
        """ایجاد ساختار فولدر بر اساس تاریخ و دستگاه"""
        # ساختار: سال/ماه/روز/دستگاه
        year = file_date.strftime("%Y")
        month = file_date.strftime("%m-%B")
        day = file_date.strftime("%d")
        date_folder = file_date.strftime("%Y-%m-%d")
        
        # ایجاد مسیر اصلی
        if self.organization.get('merge_daily_events', True):
            # همه رویدادهای یک روز در یک فولدر
            folder_path = base_path / year / month / date_folder
        else:
            folder_path = base_path / year / month / day
            
        # اضافه کردن فولدر دستگاه
        if device and device in self.devices:
            device_info = self.devices[device]
            device_folder = device_info.get('folder_prefix', device)
            folder_path = folder_path / device_folder
            
        # فولدر جداگانه برای RAW
        if self.is_raw(file_path) and self.organization.get('separate_raw_folder', True):
            folder_path = folder_path / "RAW"
            
        # ایجاد فولدر
        folder_path.mkdir(parents=True, exist_ok=True)
        
        return folder_path
        
    def organize_single_file(self, file_path: Path, destination: Path, 
                            existing_hashes: Dict[str, Path]) -> Dict:
        """سازماندهی یک فایل"""
        result = {
            'file': file_path.name,
            'status': 'pending',
            'device': None,
            'date': None,
            'destination': None,
            'error': None
        }
        
        try:
            # بررسی فرمت پشتیبانی شده
            if not (self.is_image(file_path) or self.is_video(file_path) or self.is_raw(file_path)):
                result['status'] = 'unsupported'
                result['error'] = 'فرمت پشتیبانی نمی‌شود'
                return result
                
            # بررسی تکراری
            file_hash = self.calculate_file_hash(file_path)
            if file_hash in existing_hashes:
                result['status'] = 'duplicate'
                result['error'] = f'تکراری از {existing_hashes[file_hash]}'
                
                # انتقال به فولدر تکراری
                dup_folder = destination / "Duplicates"
                dup_folder.mkdir(exist_ok=True)
                
                # ایجاد batch folder برای تکراری‌ها
                batch_num = (len(list(dup_folder.glob("*"))) // 500) + 1
                batch_folder = dup_folder / f"batch_{batch_num:03d}"
                batch_folder.mkdir(exist_ok=True)
                
                new_path = batch_folder / file_path.name
                new_path = self.get_unique_filename(new_path)
                shutil.move(str(file_path), str(new_path))
                
                result['destination'] = str(new_path.relative_to(destination))
                self.stats['duplicates'] += 1
                return result
                
            # تشخیص دستگاه
            device = self.detect_device(file_path)
            result['device'] = device
            
            if device:
                self.stats['by_device'][device] += 1
                
            # استخراج تاریخ
            file_date = self.get_file_date(file_path)
            result['date'] = file_date.strftime("%Y-%m-%d %H:%M:%S") if file_date else None
            
            if not file_date:
                # انتقال به unsorted
                unsorted_folder = destination / "Unsorted"
                unsorted_folder.mkdir(exist_ok=True)
                
                # ایجاد batch folder
                batch_num = (len(list(unsorted_folder.glob("*"))) // 500) + 1
                batch_folder = unsorted_folder / f"batch_{batch_num:03d}"
                batch_folder.mkdir(exist_ok=True)
                
                new_path = batch_folder / file_path.name
                new_path = self.get_unique_filename(new_path)
                shutil.move(str(file_path), str(new_path))
                
                result['status'] = 'unsorted'
                result['destination'] = str(new_path.relative_to(destination))
                return result
                
            # ایجاد ساختار فولدر
            target_folder = self.create_folder_structure(destination, file_date, device)
            
            # تعیین نام فایل جدید
            if device and self.organization.get('file_naming'):
                pattern = self.organization['file_naming'].get('pattern', '{original}')
                new_name = pattern.format(
                    device=self.devices[device].get('folder_prefix', device),
                    date=file_date.strftime("%Y%m%d"),
                    time=file_date.strftime("%H%M%S"),
                    original=file_path.stem
                ) + file_path.suffix
                new_path = target_folder / new_name
            else:
                new_path = target_folder / file_path.name
                
            # بررسی نام تکراری
            new_path = self.get_unique_filename(new_path)
            
            # انتقال فایل
            shutil.move(str(file_path), str(new_path))
            
            # ثبت هش
            existing_hashes[file_hash] = new_path
            
            result['status'] = 'organized'
            result['destination'] = str(new_path.relative_to(destination))
            
            # آمار
            self.stats['organized'] += 1
            date_key = file_date.strftime("%Y-%m-%d")
            self.stats['by_date'][date_key] += 1
            
            # نوع فایل
            if self.is_image(file_path):
                self.stats['by_type']['images'] += 1
            elif self.is_video(file_path):
                self.stats['by_type']['videos'] += 1
            elif self.is_raw(file_path):
                self.stats['by_type']['raw'] += 1
                
            return result
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            self.stats['errors'] += 1
            self.logger.error(f"خطا در پردازش {file_path.name}: {e}")
            return result
            
    def get_unique_filename(self, file_path: Path) -> Path:
        """ایجاد نام منحصر به فرد"""
        if not file_path.exists():
            return file_path
            
        counter = 1
        stem = file_path.stem
        suffix = file_path.suffix
        parent = file_path.parent
        
        while file_path.exists():
            new_name = f"{stem}_{counter:03d}{suffix}"
            file_path = parent / new_name
            counter += 1
            
        return file_path
        
    def organize_files(self, source_folder: str, destination_folder: str, 
                       recursive: bool = True):
        """سازماندهی همه فایل‌ها"""
        source_path = Path(source_folder)
        dest_path = Path(destination_folder)
        
        # بررسی وجود فولدر منبع
        if not source_path.exists():
            self.logger.error(f"فولدر منبع وجود ندارد: {source_path}")
            return
            
        # ایجاد فولدر مقصد
        dest_path.mkdir(parents=True, exist_ok=True)
        
        # جمع‌آوری فایل‌ها
        if recursive:
            files = list(source_path.rglob("*"))
        else:
            files = list(source_path.glob("*"))
            
        files = [f for f in files if f.is_file()]
        
        self.stats['total_files'] = len(files)
        self.logger.info(f"تعداد کل فایل‌ها: {len(files)}")
        
        if not files:
            self.logger.warning("هیچ فایلی یافت نشد!")
            return
            
        # دیکشنری هش‌ها برای تشخیص تکراری
        existing_hashes = {}
        
        # پردازش موازی
        if self.processing.get('parallel_processing', True):
            max_workers = self.processing.get('max_workers', 4)
            self.logger.info(f"پردازش موازی با {max_workers} ورکر")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                
                for file_path in files:
                    future = executor.submit(
                        self.organize_single_file,
                        file_path,
                        dest_path,
                        existing_hashes
                    )
                    futures.append(future)
                    
                # پردازش نتایج
                for i, future in enumerate(as_completed(futures), 1):
                    result = future.result()
                    self.stats['processed'] += 1
                    
                    # نمایش پیشرفت
                    if i % 50 == 0 or i == len(files):
                        progress = (i / len(files)) * 100
                        self.logger.info(
                            f"پیشرفت: {progress:.1f}% ({i}/{len(files)}) | "
                            f"سازماندهی: {self.stats['organized']} | "
                            f"تکراری: {self.stats['duplicates']} | "
                            f"خطا: {self.stats['errors']}"
                        )
        else:
            # پردازش سریال
            for i, file_path in enumerate(files, 1):
                result = self.organize_single_file(file_path, dest_path, existing_hashes)
                self.stats['processed'] += 1
                
                # نمایش پیشرفت
                if i % 50 == 0 or i == len(files):
                    progress = (i / len(files)) * 100
                    self.logger.info(
                        f"پیشرفت: {progress:.1f}% ({i}/{len(files)}) | "
                        f"سازماندهی: {self.stats['organized']} | "
                        f"تکراری: {self.stats['duplicates']} | "
                        f"خطا: {self.stats['errors']}"
                    )
                    
    def generate_report(self, output_file: str = "organization_report.json"):
        """تولید گزارش نهایی"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'statistics': self.stats,
            'devices_detected': list(self.stats['by_device'].keys()),
            'dates_processed': list(self.stats['by_date'].keys()),
            'summary': {
                'success_rate': (self.stats['organized'] / self.stats['total_files'] * 100) 
                                if self.stats['total_files'] > 0 else 0,
                'duplicate_rate': (self.stats['duplicates'] / self.stats['total_files'] * 100)
                                  if self.stats['total_files'] > 0 else 0,
                'error_rate': (self.stats['errors'] / self.stats['total_files'] * 100)
                              if self.stats['total_files'] > 0 else 0
            }
        }
        
        # ذخیره گزارش
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
            
        self.logger.info(f"گزارش ذخیره شد: {output_file}")
        
        # نمایش خلاصه
        self.logger.info("=" * 80)
        self.logger.info("📊 خلاصه عملیات:")
        self.logger.info(f"  • کل فایل‌ها: {self.stats['total_files']}")
        self.logger.info(f"  • پردازش شده: {self.stats['processed']}")
        self.logger.info(f"  • سازماندهی شده: {self.stats['organized']}")
        self.logger.info(f"  • تکراری: {self.stats['duplicates']}")
        self.logger.info(f"  • خطا: {self.stats['errors']}")
        self.logger.info("")
        self.logger.info("📱 دستگاه‌های شناسایی شده:")
        for device, count in self.stats['by_device'].items():
            device_name = self.devices[device].get('name', device)
            self.logger.info(f"  • {device_name}: {count} فایل")
        self.logger.info("")
        self.logger.info("📅 توزیع تاریخی:")
        sorted_dates = sorted(self.stats['by_date'].items())
        for date, count in sorted_dates[-10:]:  # نمایش 10 روز آخر
            self.logger.info(f"  • {date}: {count} فایل")
        self.logger.info("")
        self.logger.info("📁 انواع فایل:")
        for file_type, count in self.stats['by_type'].items():
            self.logger.info(f"  • {file_type}: {count} فایل")
        self.logger.info("=" * 80)
        
        return report


def main():
    """تابع اصلی برنامه"""
    print("=" * 80)
    print("🎯 سیستم پیشرفته سازماندهی عکس و فیلم")
    print("📱 پشتیبانی از 5 دوربین و موبایل مختلف")
    print("=" * 80)
    
    # بررسی آرگومان‌های خط فرمان
    if len(sys.argv) > 1:
        source = sys.argv[1]
        destination = sys.argv[2] if len(sys.argv) > 2 else "organized_photos"
        config_file = sys.argv[3] if len(sys.argv) > 3 else "device_config.yaml"
    else:
        # دریافت ورودی از کاربر
        print("\n📁 تنظیمات:")
        source = input("مسیر فولدر منبع: ").strip()
        destination = input("مسیر فولدر مقصد (پیش‌فرض: organized_photos): ").strip() or "organized_photos"
        config_file = input("فایل پیکربندی (پیش‌فرض: device_config.yaml): ").strip() or "device_config.yaml"
        
    # بررسی وجود فولدر منبع
    source_path = Path(source)
    if not source_path.exists():
        print(f"❌ فولدر منبع وجود ندارد: {source}")
        return
        
    # نمایش اطلاعات
    print(f"\n✅ فولدر منبع: {source}")
    print(f"✅ فولدر مقصد: {destination}")
    print(f"✅ فایل پیکربندی: {config_file}")
    
    # تأیید
    confirm = input("\nآیا می‌خواهید ادامه دهید؟ (y/n): ").strip().lower()
    if confirm not in ['y', 'yes', 'بله']:
        print("❌ عملیات لغو شد!")
        return
        
    # شروع سازماندهی
    print("\n🚀 شروع سازماندهی...")
    start_time = time.time()
    
    try:
        organizer = EnhancedPhotoOrganizer(config_file)
        organizer.organize_files(source, destination)
        
        # تولید گزارش
        report_file = Path(destination) / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        organizer.generate_report(str(report_file))
        
        elapsed_time = time.time() - start_time
        print(f"\n✅ سازماندهی با موفقیت انجام شد!")
        print(f"⏱️ زمان کل: {elapsed_time/60:.1f} دقیقه")
        print(f"📊 گزارش ذخیره شد: {report_file}")
        
    except KeyboardInterrupt:
        print("\n\n❌ عملیات توسط کاربر متوقف شد!")
    except Exception as e:
        print(f"\n❌ خطای غیرمنتظره: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
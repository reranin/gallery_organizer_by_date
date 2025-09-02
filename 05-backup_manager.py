#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مدیریت پشتیبان‌گیری
ایجاد، مدیریت و بازیابی پشتیبان‌گیری از فایل‌های مهم
"""

import os
import shutil
import hashlib
import argparse
import logging
import json
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

# کتابخانه‌های اختیاری
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    print("⚠️ کتابخانه tqdm نصب نیست. نوار پیشرفت نمایش داده نمی‌شود.")

@dataclass
class BackupInfo:
    """اطلاعات پشتیبان‌گیری"""
    backup_id: str
    source_path: str
    backup_path: str
    timestamp: str
    total_files: int
    total_size: int
    checksum: str
    compression: bool
    status: str = "created"

class BackupManager:
    """کلاس مدیریت پشتیبان‌گیری"""
    
    def __init__(self, backup_root: str = None):
        if backup_root is None:
            backup_root = os.getenv("BACKUP_ROOT_DIR", "./backups")
        self.backup_root = Path(backup_root)
        self.backup_root.mkdir(parents=True, exist_ok=True)
        self.setup_logging()
        
        # فایل ایندکس پشتیبان‌گیری‌ها
        self.index_file = self.backup_root / "backup_index.json"
        self.backups_index = self.load_backup_index()
        
        # پسوندهای پشتیبانی
        self.supported_extensions = {
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.heic',
            '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.mpeg',
            '.pdf', '.doc', '.docx', '.txt', '.zip', '.rar'
        }
    
    def setup_logging(self):
        """تنظیم سیستم لاگینگ"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.backup_root / f'backup_manager_{timestamp}.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_backup_index(self) -> List[BackupInfo]:
        """بارگذاری ایندکس پشتیبان‌گیری‌ها"""
        if not self.index_file.exists():
            return []
        
        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [BackupInfo(**item) for item in data]
        except Exception as e:
            self.logger.error(f"خطا در بارگذاری ایندکس: {e}")
            return []
    
    def save_backup_index(self):
        """ذخیره ایندکس پشتیبان‌گیری‌ها"""
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                data = [asdict(backup) for backup in self.backups_index]
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"خطا در ذخیره ایندکس: {e}")
    
    def calculate_checksum(self, file_path: Path) -> str:
        """محاسبه checksum فایل"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return ""
    
    def get_directory_info(self, directory: Path) -> Tuple[int, int]:
        """دریافت اطلاعات پوشه (تعداد فایل‌ها و اندازه کل)"""
        total_files = 0
        total_size = 0
        
        for file_path in directory.rglob("*"):
            if file_path.is_file():
                if file_path.suffix.lower() in self.supported_extensions:
                    total_files += 1
                    try:
                        total_size += file_path.stat().st_size
                    except:
                        pass
        
        return total_files, total_size
    
    def create_backup_simple(self, source_path: str, backup_name: str = None) -> BackupInfo:
        """ایجاد پشتیبان‌گیری ساده (کپی مستقیم)"""
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"مسیر منبع وجود ندارد: {source_path}")
        
        # تولید نام پشتیبان‌گیری
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if backup_name:
            backup_id = f"{backup_name}_{timestamp}"
        else:
            backup_id = f"backup_{source.name}_{timestamp}"
        
        backup_dir = self.backup_root / backup_id
        backup_dir.mkdir(exist_ok=True)
        
        self.logger.info(f"شروع پشتیبان‌گیری: {source} -> {backup_dir}")
        
        # محاسبه اطلاعات
        if source.is_file():
            total_files = 1
            total_size = source.stat().st_size
        else:
            total_files, total_size = self.get_directory_info(source)
        
        # کپی فایل‌ها
        copied_files = 0
        if source.is_file():
            shutil.copy2(source, backup_dir / source.name)
            copied_files = 1
        else:
            if TQDM_AVAILABLE:
                progress_bar = tqdm(total=total_files, desc="کپی فایل‌ها")
            else:
                progress_bar = None
            
            for file_path in source.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in self.supported_extensions:
                    try:
                        # حفظ ساختار پوشه‌ها
                        relative_path = file_path.relative_to(source)
                        dest_path = backup_dir / relative_path
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        shutil.copy2(file_path, dest_path)
                        copied_files += 1
                        
                        if progress_bar:
                            progress_bar.update(1)
                            
                    except Exception as e:
                        self.logger.error(f"خطا در کپی {file_path}: {e}")
            
            if progress_bar:
                progress_bar.close()
        
        # محاسبه checksum پوشه پشتیبان‌گیری
        backup_checksum = self.calculate_directory_checksum(backup_dir)
        
        # ایجاد اطلاعات پشتیبان‌گیری
        backup_info = BackupInfo(
            backup_id=backup_id,
            source_path=str(source),
            backup_path=str(backup_dir),
            timestamp=timestamp,
            total_files=copied_files,
            total_size=total_size,
            checksum=backup_checksum,
            compression=False,
            status="completed"
        )
        
        # اضافه کردن به ایندکس
        self.backups_index.append(backup_info)
        self.save_backup_index()
        
        self.logger.info(f"پشتیبان‌گیری تکمیل شد: {copied_files} فایل")
        return backup_info
    
    def create_backup_compressed(self, source_path: str, backup_name: str = None) -> BackupInfo:
        """ایجاد پشتیبان‌گیری فشرده (ZIP)"""
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"مسیر منبع وجود ندارد: {source_path}")
        
        # تولید نام پشتیبان‌گیری
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if backup_name:
            backup_id = f"{backup_name}_{timestamp}"
        else:
            backup_id = f"backup_{source.name}_{timestamp}"
        
        backup_file = self.backup_root / f"{backup_id}.zip"
        
        self.logger.info(f"شروع پشتیبان‌گیری فشرده: {source} -> {backup_file}")
        
        # محاسبه اطلاعات
        if source.is_file():
            total_files = 1
            total_size = source.stat().st_size
        else:
            total_files, total_size = self.get_directory_info(source)
        
        # ایجاد فایل ZIP
        compressed_files = 0
        with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if source.is_file():
                zipf.write(source, source.name)
                compressed_files = 1
            else:
                if TQDM_AVAILABLE:
                    progress_bar = tqdm(total=total_files, desc="فشرده‌سازی فایل‌ها")
                else:
                    progress_bar = None
                
                for file_path in source.rglob("*"):
                    if file_path.is_file() and file_path.suffix.lower() in self.supported_extensions:
                        try:
                            # حفظ ساختار پوشه‌ها در ZIP
                            arcname = file_path.relative_to(source)
                            zipf.write(file_path, arcname)
                            compressed_files += 1
                            
                            if progress_bar:
                                progress_bar.update(1)
                                
                        except Exception as e:
                            self.logger.error(f"خطا در فشرده‌سازی {file_path}: {e}")
                
                if progress_bar:
                    progress_bar.close()
        
        # محاسبه checksum فایل ZIP
        backup_checksum = self.calculate_checksum(backup_file)
        
        # ایجاد اطلاعات پشتیبان‌گیری
        backup_info = BackupInfo(
            backup_id=backup_id,
            source_path=str(source),
            backup_path=str(backup_file),
            timestamp=timestamp,
            total_files=compressed_files,
            total_size=backup_file.stat().st_size,
            checksum=backup_checksum,
            compression=True,
            status="completed"
        )
        
        # اضافه کردن به ایندکس
        self.backups_index.append(backup_info)
        self.save_backup_index()
        
        self.logger.info(f"پشتیبان‌گیری فشرده تکمیل شد: {compressed_files} فایل")
        return backup_info
    
    def calculate_directory_checksum(self, directory: Path) -> str:
        """محاسبه checksum پوشه"""
        hash_md5 = hashlib.md5()
        
        try:
            for file_path in sorted(directory.rglob("*")):
                if file_path.is_file():
                    # اضافه کردن نام فایل
                    hash_md5.update(str(file_path.relative_to(directory)).encode('utf-8'))
                    # اضافه کردن محتوای فایل
                    with open(file_path, 'rb') as f:
                        for chunk in iter(lambda: f.read(4096), b""):
                            hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return ""
    
    def verify_backup(self, backup_id: str) -> Dict:
        """تایید یکپارچگی پشتیبان‌گیری"""
        backup_info = self.get_backup_info(backup_id)
        if not backup_info:
            return {"error": f"پشتیبان‌گیری یافت نشد: {backup_id}"}
        
        backup_path = Path(backup_info.backup_path)
        if not backup_path.exists():
            return {"error": f"فایل پشتیبان‌گیری وجود ندارد: {backup_path}"}
        
        self.logger.info(f"تایید یکپارچگی پشتیبان‌گیری: {backup_id}")
        
        # محاسبه checksum جدید
        if backup_info.compression:
            current_checksum = self.calculate_checksum(backup_path)
        else:
            current_checksum = self.calculate_directory_checksum(backup_path)
        
        # مقایسه با checksum ذخیره شده
        is_intact = current_checksum == backup_info.checksum
        
        result = {
            "backup_id": backup_id,
            "is_intact": is_intact,
            "original_checksum": backup_info.checksum,
            "current_checksum": current_checksum,
            "backup_path": str(backup_path),
            "compression": backup_info.compression
        }
        
        if is_intact:
            self.logger.info("پشتیبان‌گیری سالم است ✅")
        else:
            self.logger.warning("پشتیبان‌گیری خراب است ⚠️")
        
        return result
    
    def restore_backup(self, backup_id: str, restore_path: str) -> Dict:
        """بازیابی پشتیبان‌گیری"""
        backup_info = self.get_backup_info(backup_id)
        if not backup_info:
            return {"error": f"پشتیبان‌گیری یافت نشد: {backup_id}"}
        
        backup_path = Path(backup_info.backup_path)
        if not backup_path.exists():
            return {"error": f"فایل پشتیبان‌گیری وجود ندارد: {backup_path}"}
        
        restore_dir = Path(restore_path)
        restore_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"بازیابی پشتیبان‌گیری {backup_id} به {restore_path}")
        
        try:
            if backup_info.compression:
                # بازیابی از فایل ZIP
                with zipfile.ZipFile(backup_path, 'r') as zipf:
                    zipf.extractall(restore_dir)
                    restored_files = len(zipf.namelist())
            else:
                # بازیابی از پوشه
                restored_files = 0
                for file_path in backup_path.rglob("*"):
                    if file_path.is_file():
                        relative_path = file_path.relative_to(backup_path)
                        dest_path = restore_dir / relative_path
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(file_path, dest_path)
                        restored_files += 1
            
            self.logger.info(f"بازیابی تکمیل شد: {restored_files} فایل")
            
            return {
                "backup_id": backup_id,
                "restore_path": str(restore_dir),
                "restored_files": restored_files,
                "success": True
            }
            
        except Exception as e:
            self.logger.error(f"خطا در بازیابی: {e}")
            return {"error": f"خطا در بازیابی: {str(e)}"}
    
    def list_backups(self) -> List[Dict]:
        """لیست پشتیبان‌گیری‌ها"""
        backups_list = []
        for backup in self.backups_index:
            backup_dict = asdict(backup)
            # بررسی وجود فایل پشتیبان‌گیری
            backup_path = Path(backup.backup_path)
            backup_dict['exists'] = backup_path.exists()
            if backup_dict['exists']:
                backup_dict['current_size'] = backup_path.stat().st_size
            else:
                backup_dict['current_size'] = 0
            backups_list.append(backup_dict)
        
        return backups_list
    
    def get_backup_info(self, backup_id: str) -> Optional[BackupInfo]:
        """دریافت اطلاعات پشتیبان‌گیری"""
        for backup in self.backups_index:
            if backup.backup_id == backup_id:
                return backup
        return None
    
    def delete_backup(self, backup_id: str) -> Dict:
        """حذف پشتیبان‌گیری"""
        backup_info = self.get_backup_info(backup_id)
        if not backup_info:
            return {"error": f"پشتیبان‌گیری یافت نشد: {backup_id}"}
        
        backup_path = Path(backup_info.backup_path)
        
        try:
            if backup_path.exists():
                if backup_path.is_file():
                    backup_path.unlink()
                else:
                    shutil.rmtree(backup_path)
            
            # حذف از ایندکس
            self.backups_index = [b for b in self.backups_index if b.backup_id != backup_id]
            self.save_backup_index()
            
            self.logger.info(f"پشتیبان‌گیری حذف شد: {backup_id}")
            return {"success": True, "message": f"پشتیبان‌گیری {backup_id} حذف شد"}
            
        except Exception as e:
            self.logger.error(f"خطا در حذف پشتیبان‌گیری: {e}")
            return {"error": f"خطا در حذف: {str(e)}"}
    
    def cleanup_old_backups(self, keep_count: int = 5) -> Dict:
        """پاک‌سازی پشتیبان‌گیری‌های قدیمی"""
        if len(self.backups_index) <= keep_count:
            return {"message": "تعداد پشتیبان‌گیری‌ها کمتر از حد مجاز است"}
        
        # مرتب‌سازی بر اساس تاریخ (جدیدترین اول)
        sorted_backups = sorted(self.backups_index, key=lambda x: x.timestamp, reverse=True)
        backups_to_delete = sorted_backups[keep_count:]
        
        deleted_count = 0
        for backup in backups_to_delete:
            result = self.delete_backup(backup.backup_id)
            if result.get("success"):
                deleted_count += 1
        
        return {
            "deleted_count": deleted_count,
            "remaining_count": len(self.backups_index),
            "message": f"{deleted_count} پشتیبان‌گیری قدیمی حذف شد"
        }
    
    def generate_report(self) -> str:
        """تولید گزارش پشتیبان‌گیری‌ها"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.backup_root / f"backup_report_{timestamp}.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("گزارش پشتیبان‌گیری‌ها\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"تاریخ گزارش: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"تعداد کل پشتیبان‌گیری‌ها: {len(self.backups_index)}\n\n")
            
            for backup in self.backups_index:
                f.write(f"شناسه: {backup.backup_id}\n")
                f.write(f"منبع: {backup.source_path}\n")
                f.write(f"مسیر: {backup.backup_path}\n")
                f.write(f"تاریخ: {backup.timestamp}\n")
                f.write(f"تعداد فایل‌ها: {backup.total_files}\n")
                f.write(f"اندازه: {backup.total_size:,} بایت\n")
                f.write(f"فشرده: {'بله' if backup.compression else 'خیر'}\n")
                f.write(f"وضعیت: {backup.status}\n")
                f.write("-" * 30 + "\n")
        
        return str(report_path)


def main():
    """تابع اصلی"""
    parser = argparse.ArgumentParser(description="مدیریت پشتیبان‌گیری")
    parser.add_argument("-r", "--root", help="پوشه ریشه پشتیبان‌گیری (از .env خوانده می‌شود)")
    
    subparsers = parser.add_subparsers(dest="action", help="عملیات‌ها")
    
    # ایجاد پشتیبان‌گیری
    create_parser = subparsers.add_parser("create", help="ایجاد پشتیبان‌گیری")
    create_parser.add_argument("source", nargs='?', help="مسیر منبع (از .env خوانده می‌شود)")
    create_parser.add_argument("-n", "--name", help="نام پشتیبان‌گیری")
    create_parser.add_argument("-c", "--compress", action="store_true", help="فشرده‌سازی")
    
    # لیست پشتیبان‌گیری‌ها
    subparsers.add_parser("list", help="لیست پشتیبان‌گیری‌ها")
    
    # تایید پشتیبان‌گیری
    verify_parser = subparsers.add_parser("verify", help="تایید یکپارچگی")
    verify_parser.add_argument("backup_id", help="شناسه پشتیبان‌گیری")
    
    # بازیابی پشتیبان‌گیری
    restore_parser = subparsers.add_parser("restore", help="بازیابی پشتیبان‌گیری")
    restore_parser.add_argument("backup_id", help="شناسه پشتیبان‌گیری")
    restore_parser.add_argument("restore_path", help="مسیر بازیابی")
    
    # حذف پشتیبان‌گیری
    delete_parser = subparsers.add_parser("delete", help="حذف پشتیبان‌گیری")
    delete_parser.add_argument("backup_id", help="شناسه پشتیبان‌گیری")
    
    # پاک‌سازی
    cleanup_parser = subparsers.add_parser("cleanup", help="پاک‌سازی پشتیبان‌گیری‌های قدیمی")
    cleanup_parser.add_argument("-k", "--keep", type=int, default=5, help="تعداد پشتیبان‌گیری‌های نگهداری")
    
    # گزارش
    subparsers.add_parser("report", help="تولید گزارش")
    
    args = parser.parse_args()
    
    if not args.action:
        parser.print_help()
        return 1
    
    print("💾 مدیر پشتیبان‌گیری")
    print("=" * 40)
    
    try:
        manager = BackupManager(args.root)
        
        if args.action == "create":
            # تعیین مسیر منبع
            source_path = args.source or os.getenv("INPUT_DIRECTORY")
            if not source_path:
                print("❌ خطا: مسیر منبع مشخص نشده")
                print("لطفاً مسیر را به عنوان آرگومان وارد کنید یا در فایل .env تنظیم کنید:")
                print("INPUT_DIRECTORY=/path/to/source")
                return 1
            
            # تعیین نوع فشرده‌سازی
            use_compression = args.compress
            if not args.compress:
                # اگر از خط فرمان مشخص نشده، از .env بخوان
                use_compression = os.getenv("DEFAULT_COMPRESSION", "false").lower() in {"1", "true", "yes"}
            
            print(f"📂 منبع: {source_path}")
            print(f"💾 نوع: {'فشرده' if use_compression else 'ساده'}")
            
            if use_compression:
                backup_info = manager.create_backup_compressed(source_path, args.name)
            else:
                backup_info = manager.create_backup_simple(source_path, args.name)
            
            print(f"\n✅ پشتیبان‌گیری ایجاد شد:")
            print(f"شناسه: {backup_info.backup_id}")
            print(f"مسیر: {backup_info.backup_path}")
            print(f"تعداد فایل‌ها: {backup_info.total_files}")
            print(f"اندازه: {backup_info.total_size:,} بایت")
        
        elif args.action == "list":
            backups = manager.list_backups()
            if not backups:
                print("هیچ پشتیبان‌گیری یافت نشد")
            else:
                print(f"تعداد پشتیبان‌گیری‌ها: {len(backups)}")
                print()
                for backup in backups:
                    status = "✅" if backup['exists'] else "❌"
                    print(f"{status} {backup['backup_id']}")
                    print(f"   منبع: {backup['source_path']}")
                    print(f"   تاریخ: {backup['timestamp']}")
                    print(f"   فایل‌ها: {backup['total_files']}")
                    print(f"   اندازه: {backup['current_size']:,} بایت")
                    print()
        
        elif args.action == "verify":
            result = manager.verify_backup(args.backup_id)
            if "error" in result:
                print(f"❌ {result['error']}")
                return 1
            
            status = "✅ سالم" if result['is_intact'] else "❌ خراب"
            print(f"پشتیبان‌گیری: {result['backup_id']}")
            print(f"وضعیت: {status}")
            if not result['is_intact']:
                print(f"Checksum اصلی: {result['original_checksum']}")
                print(f"Checksum فعلی: {result['current_checksum']}")
        
        elif args.action == "restore":
            result = manager.restore_backup(args.backup_id, args.restore_path)
            if "error" in result:
                print(f"❌ {result['error']}")
                return 1
            
            print(f"✅ بازیابی موفق:")
            print(f"مسیر: {result['restore_path']}")
            print(f"تعداد فایل‌ها: {result['restored_files']}")
        
        elif args.action == "delete":
            result = manager.delete_backup(args.backup_id)
            if "error" in result:
                print(f"❌ {result['error']}")
                return 1
            
            print(f"✅ {result['message']}")
        
        elif args.action == "cleanup":
            keep_count = args.keep or int(os.getenv("KEEP_BACKUP_COUNT", "5"))
            result = manager.cleanup_old_backups(keep_count)
            print(f"📊 {result['message']}")
            print(f"پشتیبان‌گیری‌های باقی‌مانده: {result['remaining_count']}")
        
        elif args.action == "report":
            report_path = manager.generate_report()
            print(f"📄 گزارش ایجاد شد: {report_path}")
        
    except KeyboardInterrupt:
        print("\n⏹️ عملیات توسط کاربر متوقف شد")
        return 1
    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

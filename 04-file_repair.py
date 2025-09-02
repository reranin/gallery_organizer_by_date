#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تعمیر فایل‌های خراب
تعمیر و بازیابی فایل‌های تصویری و ویدیویی خراب یا ناقص
"""

import os
import shutil
import argparse
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional

# کتابخانه‌های اختیاری
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️ کتابخانه Pillow نصب نیست. تعمیر تصاویر محدود خواهد بود.")

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    print("⚠️ کتابخانه tqdm نصب نیست. نوار پیشرفت نمایش داده نمی‌شود.")

class FileRepair:
    """کلاس تعمیر فایل‌های خراب"""
    
    def __init__(self):
        self.setup_logging()
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
        self.video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.mpeg', '.mpg', '.ts'}
        
    def setup_logging(self):
        """تنظیم سیستم لاگینگ"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f'file_repair_{timestamp}.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def is_ffmpeg_available(self) -> bool:
        """بررسی وجود ffmpeg"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def repair_image_with_pillow(self, input_path: str, output_path: str) -> Tuple[bool, str]:
        """تعمیر تصویر با استفاده از Pillow"""
        try:
            if not PIL_AVAILABLE:
                return False, "کتابخانه Pillow نصب نیست"
            
            with Image.open(input_path) as img:
                # تلاش برای بارگذاری کامل تصویر
                img.load()
                
                # تبدیل به RGB در صورت نیاز
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                
                # ذخیره با کیفیت بالا
                img.save(output_path, format='JPEG', quality=95, optimize=True)
                
            return True, "تصویر با موفقیت تعمیر شد"
            
        except Exception as e:
            return False, f"خطا در تعمیر تصویر: {str(e)}"
    
    def repair_image_truncated(self, input_path: str, output_path: str) -> Tuple[bool, str]:
        """تعمیر تصاویر ناقص (truncated)"""
        try:
            if not PIL_AVAILABLE:
                return False, "کتابخانه Pillow نصب نیست"
            
            # فعال‌سازی بارگذاری تصاویر ناقص
            from PIL import ImageFile
            ImageFile.LOAD_TRUNCATED_IMAGES = True
            
            with Image.open(input_path) as img:
                # بارگذاری تا جایی که ممکن است
                img.load()
                
                # تبدیل به RGB
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # ذخیره قسمت قابل بازیابی
                img.save(output_path, format='JPEG', quality=90)
            
            # غیرفعال‌سازی مجدد
            ImageFile.LOAD_TRUNCATED_IMAGES = False
            
            return True, "قسمت قابل بازیابی تصویر ذخیره شد"
            
        except Exception as e:
            return False, f"خطا در تعمیر تصویر ناقص: {str(e)}"
    
    def repair_video_with_ffmpeg(self, input_path: str, output_path: str, 
                                repair_mode: str = "copy") -> Tuple[bool, str]:
        """تعمیر ویدیو با استفاده از ffmpeg"""
        try:
            if not self.is_ffmpeg_available():
                return False, "ffmpeg نصب نیست"
            
            if repair_mode == "copy":
                # تعمیر با کپی stream ها
                cmd = [
                    'ffmpeg', '-y', '-i', input_path,
                    '-c', 'copy', '-avoid_negative_ts', 'make_zero',
                    output_path
                ]
            elif repair_mode == "re-encode":
                # تعمیر با re-encoding
                cmd = [
                    'ffmpeg', '-y', '-i', input_path,
                    '-c:v', 'libx264', '-c:a', 'aac',
                    '-preset', 'fast', '-crf', '23',
                    output_path
                ]
            elif repair_mode == "extract_frames":
                # استخراج فریم‌های قابل بازیابی
                frames_dir = Path(output_path).parent / "extracted_frames"
                frames_dir.mkdir(exist_ok=True)
                cmd = [
                    'ffmpeg', '-y', '-i', input_path,
                    '-vsync', 'vfr', '-q:v', '2',
                    str(frames_dir / "frame_%04d.jpg")
                ]
            else:
                return False, "حالت تعمیر نامعتبر"
            
            # اجرای دستور با timeout
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                return True, f"ویدیو با موفقیت تعمیر شد (حالت: {repair_mode})"
            else:
                error_msg = result.stderr if result.stderr else "خطای نامشخص"
                return False, f"خطا در تعمیر ویدیو: {error_msg}"
                
        except subprocess.TimeoutExpired:
            return False, "زمان تعمیر به پایان رسید (timeout)"
        except Exception as e:
            return False, f"خطا در تعمیر ویدیو: {str(e)}"
    
    def repair_video_metadata(self, input_path: str, output_path: str) -> Tuple[bool, str]:
        """تعمیر metadata ویدیو"""
        try:
            if not self.is_ffmpeg_available():
                return False, "ffmpeg نصب نیست"
            
            cmd = [
                'ffmpeg', '-y', '-i', input_path,
                '-c', 'copy', '-map_metadata', '0',
                '-movflags', 'faststart',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                return True, "metadata ویدیو تعمیر شد"
            else:
                return False, f"خطا در تعمیر metadata: {result.stderr}"
                
        except Exception as e:
            return False, f"خطا در تعمیر metadata: {str(e)}"
    
    def extract_audio_from_video(self, input_path: str, output_path: str) -> Tuple[bool, str]:
        """استخراج صدا از ویدیو خراب"""
        try:
            if not self.is_ffmpeg_available():
                return False, "ffmpeg نصب نیست"
            
            # تغییر پسوند به mp3
            audio_output = str(Path(output_path).with_suffix('.mp3'))
            
            cmd = [
                'ffmpeg', '-y', '-i', input_path,
                '-vn', '-acodec', 'mp3', '-ab', '192k',
                audio_output
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                return True, f"صدا استخراج شد: {audio_output}"
            else:
                return False, f"خطا در استخراج صدا: {result.stderr}"
                
        except Exception as e:
            return False, f"خطا در استخراج صدا: {str(e)}"
    
    def analyze_file(self, file_path: str) -> Dict:
        """تحلیل فایل برای تعیین نوع خرابی"""
        analysis = {
            'path': file_path,
            'exists': os.path.exists(file_path),
            'size': 0,
            'extension': '',
            'is_image': False,
            'is_video': False,
            'corruption_type': 'unknown',
            'repair_suggestions': []
        }
        
        if not analysis['exists']:
            analysis['corruption_type'] = 'missing'
            return analysis
        
        try:
            file_path_obj = Path(file_path)
            analysis['size'] = file_path_obj.stat().st_size
            analysis['extension'] = file_path_obj.suffix.lower()
            analysis['is_image'] = analysis['extension'] in self.image_extensions
            analysis['is_video'] = analysis['extension'] in self.video_extensions
            
            if analysis['size'] == 0:
                analysis['corruption_type'] = 'empty'
                return analysis
            
            # تحلیل تصاویر
            if analysis['is_image'] and PIL_AVAILABLE:
                try:
                    with Image.open(file_path) as img:
                        img.verify()
                    analysis['corruption_type'] = 'healthy'
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'truncated' in error_msg:
                        analysis['corruption_type'] = 'truncated'
                        analysis['repair_suggestions'].append('repair_truncated')
                    else:
                        analysis['corruption_type'] = 'corrupt'
                        analysis['repair_suggestions'].append('repair_basic')
            
            # تحلیل ویدیوها
            elif analysis['is_video']:
                if self.is_ffmpeg_available():
                    try:
                        cmd = ['ffmpeg', '-v', 'error', '-i', file_path, '-f', 'null', '-']
                        result = subprocess.run(cmd, capture_output=True, timeout=30)
                        if result.returncode == 0:
                            analysis['corruption_type'] = 'healthy'
                        else:
                            analysis['corruption_type'] = 'corrupt'
                            analysis['repair_suggestions'].extend([
                                'repair_copy', 'repair_re_encode', 'extract_audio'
                            ])
                    except:
                        analysis['corruption_type'] = 'corrupt'
                        analysis['repair_suggestions'].append('extract_audio')
                else:
                    analysis['corruption_type'] = 'unknown'
            
        except Exception as e:
            analysis['corruption_type'] = 'error'
            self.logger.error(f"خطا در تحلیل فایل {file_path}: {e}")
        
        return analysis
    
    def repair_file(self, input_path: str, output_dir: str, 
                   repair_methods: List[str] = None) -> Dict:
        """تعمیر فایل با روش‌های مختلف"""
        if repair_methods is None:
            repair_methods = ['auto']
        
        results = {
            'input_path': input_path,
            'analysis': self.analyze_file(input_path),
            'repairs': [],
            'success': False,
            'output_files': []
        }
        
        analysis = results['analysis']
        
        if analysis['corruption_type'] in ['healthy', 'missing', 'empty']:
            results['repairs'].append({
                'method': 'none',
                'success': analysis['corruption_type'] == 'healthy',
                'message': f"فایل {analysis['corruption_type']} است"
            })
            return results
        
        # تعیین روش‌های تعمیر
        if 'auto' in repair_methods:
            if analysis['is_image']:
                if analysis['corruption_type'] == 'truncated':
                    repair_methods = ['repair_truncated', 'repair_basic']
                else:
                    repair_methods = ['repair_basic']
            elif analysis['is_video']:
                repair_methods = ['repair_copy', 'repair_metadata', 'extract_audio']
        
        # ایجاد پوشه خروجی
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # اجرای روش‌های تعمیر
        for method in repair_methods:
            try:
                input_file = Path(input_path)
                method_output_dir = output_path / method
                method_output_dir.mkdir(exist_ok=True)
                
                if method == 'repair_basic' and analysis['is_image']:
                    output_file = method_output_dir / f"repaired_{input_file.name}"
                    success, message = self.repair_image_with_pillow(input_path, str(output_file))
                
                elif method == 'repair_truncated' and analysis['is_image']:
                    output_file = method_output_dir / f"recovered_{input_file.name}"
                    success, message = self.repair_image_truncated(input_path, str(output_file))
                
                elif method == 'repair_copy' and analysis['is_video']:
                    output_file = method_output_dir / f"repaired_{input_file.name}"
                    success, message = self.repair_video_with_ffmpeg(input_path, str(output_file), "copy")
                
                elif method == 'repair_re_encode' and analysis['is_video']:
                    output_file = method_output_dir / f"reencoded_{input_file.stem}.mp4"
                    success, message = self.repair_video_with_ffmpeg(input_path, str(output_file), "re-encode")
                
                elif method == 'repair_metadata' and analysis['is_video']:
                    output_file = method_output_dir / f"metadata_fixed_{input_file.name}"
                    success, message = self.repair_video_metadata(input_path, str(output_file))
                
                elif method == 'extract_audio' and analysis['is_video']:
                    output_file = method_output_dir / f"audio_{input_file.stem}.mp3"
                    success, message = self.extract_audio_from_video(input_path, str(output_file))
                
                elif method == 'extract_frames' and analysis['is_video']:
                    output_file = method_output_dir / "frames"
                    success, message = self.repair_video_with_ffmpeg(input_path, str(output_file), "extract_frames")
                
                else:
                    success, message = False, f"روش تعمیر پشتیبانی نمی‌شود: {method}"
                
                results['repairs'].append({
                    'method': method,
                    'success': success,
                    'message': message,
                    'output_file': str(output_file) if success else None
                })
                
                if success:
                    results['success'] = True
                    results['output_files'].append(str(output_file))
                    
            except Exception as e:
                results['repairs'].append({
                    'method': method,
                    'success': False,
                    'message': f"خطا در روش {method}: {str(e)}",
                    'output_file': None
                })
        
        return results
    
    def repair_directory(self, input_dir: str, output_dir: str, 
                        repair_methods: List[str] = None) -> Dict:
        """تعمیر تمام فایل‌های یک پوشه"""
        input_path = Path(input_dir)
        if not input_path.exists():
            return {"error": f"پوشه ورودی وجود ندارد: {input_dir}"}
        
        # جمع‌آوری فایل‌ها
        files_to_repair = []
        for file_path in input_path.rglob("*"):
            if (file_path.is_file() and 
                (file_path.suffix.lower() in self.image_extensions or 
                 file_path.suffix.lower() in self.video_extensions)):
                files_to_repair.append(str(file_path))
        
        if not files_to_repair:
            return {"error": "هیچ فایل تصویری یا ویدیویی یافت نشد"}
        
        self.logger.info(f"تعداد فایل‌های یافت شده: {len(files_to_repair)}")
        
        # تعمیر فایل‌ها
        results = {
            'total_files': len(files_to_repair),
            'successful_repairs': 0,
            'failed_repairs': 0,
            'repair_details': []
        }
        
        if TQDM_AVAILABLE:
            progress_bar = tqdm(files_to_repair, desc="تعمیر فایل‌ها")
        else:
            progress_bar = files_to_repair
        
        for file_path in progress_bar:
            try:
                file_output_dir = Path(output_dir) / Path(file_path).relative_to(input_path).parent
                repair_result = self.repair_file(file_path, str(file_output_dir), repair_methods)
                
                if repair_result['success']:
                    results['successful_repairs'] += 1
                else:
                    results['failed_repairs'] += 1
                
                results['repair_details'].append(repair_result)
                
            except Exception as e:
                self.logger.error(f"خطا در تعمیر {file_path}: {e}")
                results['failed_repairs'] += 1
        
        if TQDM_AVAILABLE:
            progress_bar.close()
        
        return results
    
    def generate_report(self, results: Dict, output_dir: str) -> str:
        """تولید گزارش تعمیر"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = Path(output_dir) / f"repair_report_{timestamp}.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("گزارش تعمیر فایل‌های خراب\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"تاریخ تعمیر: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            if 'total_files' in results:
                # گزارش تعمیر پوشه
                f.write("آمار کلی:\n")
                f.write("-" * 20 + "\n")
                f.write(f"تعداد کل فایل‌ها: {results['total_files']}\n")
                f.write(f"تعمیرات موفق: {results['successful_repairs']}\n")
                f.write(f"تعمیرات ناموفق: {results['failed_repairs']}\n\n")
                
                f.write("جزئیات تعمیرات:\n")
                f.write("-" * 20 + "\n")
                for detail in results['repair_details']:
                    f.write(f"فایل: {detail['input_path']}\n")
                    f.write(f"وضعیت: {'موفق' if detail['success'] else 'ناموفق'}\n")
                    for repair in detail['repairs']:
                        f.write(f"  - {repair['method']}: {repair['message']}\n")
                    f.write("-" * 30 + "\n")
            else:
                # گزارش تعمیر فایل واحد
                f.write(f"فایل: {results['input_path']}\n")
                f.write(f"تحلیل: {results['analysis']['corruption_type']}\n")
                f.write(f"نتیجه: {'موفق' if results['success'] else 'ناموفق'}\n\n")
                
                f.write("جزئیات تعمیرات:\n")
                f.write("-" * 20 + "\n")
                for repair in results['repairs']:
                    f.write(f"روش: {repair['method']}\n")
                    f.write(f"نتیجه: {repair['message']}\n")
                    if repair.get('output_file'):
                        f.write(f"خروجی: {repair['output_file']}\n")
                    f.write("-" * 10 + "\n")
        
        return str(report_path)


def main():
    """تابع اصلی"""
    parser = argparse.ArgumentParser(description="تعمیر فایل‌های خراب")
    parser.add_argument("input", nargs='?', help="فایل یا پوشه ورودی (اختیاری، از .env خوانده می‌شود)")
    parser.add_argument("-o", "--output", help="پوشه خروجی (اختیاری، از .env خوانده می‌شود)")
    parser.add_argument("-m", "--methods", nargs='+',
                       choices=['auto', 'repair_basic', 'repair_truncated', 'repair_copy', 
                               'repair_re_encode', 'repair_metadata', 'extract_audio', 'extract_frames'],
                       help="روش‌های تعمیر")
    
    args = parser.parse_args()
    
    print("🔧 تعمیرکار فایل‌های خراب")
    print("=" * 40)
    
    try:
        repairer = FileRepair()
        
        # تعیین مسیرهای ورودی و خروجی
        input_path_str = args.input or os.getenv("INPUT_DIRECTORY")
        output_path_str = args.output or os.getenv("REPAIR_OUTPUT_DIR") or os.getenv("OUTPUT_DIRECTORY", "./repaired")
        
        if not input_path_str:
            print("❌ خطا: فایل یا پوشه ورودی مشخص نشده")
            print("لطفاً مسیر را به عنوان آرگومان وارد کنید یا در فایل .env تنظیم کنید:")
            print("INPUT_DIRECTORY=/path/to/input")
            return 1
        
        # تنظیمات از .env یا آرگومان‌ها
        repair_methods = args.methods
        if not repair_methods:
            methods_str = os.getenv("DEFAULT_REPAIR_METHODS", "auto")
            repair_methods = [m.strip() for m in methods_str.split(",") if m.strip()]
        
        input_path = Path(input_path_str)
        if not input_path.exists():
            print(f"❌ فایل یا پوشه وجود ندارد: {input_path_str}")
            return 1
        
        print(f"📂 ورودی: {input_path_str}")
        print(f"📂 خروجی: {output_path_str}")
        print(f"🔧 روش‌های تعمیر: {repair_methods}")
        
        if input_path.is_file():
            # تعمیر فایل واحد
            results = repairer.repair_file(input_path_str, output_path_str, repair_methods)
            
            print(f"\n📊 نتیجه تعمیر:")
            print(f"فایل: {results['input_path']}")
            print(f"تحلیل: {results['analysis']['corruption_type']}")
            print(f"وضعیت: {'موفق ✅' if results['success'] else 'ناموفق ❌'}")
            
            if results['success']:
                print(f"فایل‌های خروجی:")
                for output_file in results['output_files']:
                    print(f"  📄 {output_file}")
        
        else:
            # تعمیر پوشه
            results = repairer.repair_directory(input_path_str, output_path_str, repair_methods)
            
            if "error" in results:
                print(f"❌ خطا: {results['error']}")
                return 1
            
            print(f"\n📊 نتایج تعمیر:")
            print(f"📁 تعداد کل فایل‌ها: {results['total_files']}")
            print(f"✅ تعمیرات موفق: {results['successful_repairs']}")
            print(f"❌ تعمیرات ناموفق: {results['failed_repairs']}")
        
        # تولید گزارش
        report_path = repairer.generate_report(results, output_path_str)
        print(f"\n📄 گزارش: {report_path}")
        
    except KeyboardInterrupt:
        print("\n⏹️ عملیات توسط کاربر متوقف شد")
        return 1
    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

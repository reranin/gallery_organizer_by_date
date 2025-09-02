# شناسایی‌کننده فایل‌های خراب (تصویر و ویدیو)

این ابزار پوشه‌های بزرگ شامل عکس و ویدیو را اسکن می‌کند، خرابی یا مشکوک‌بودن فایل‌ها را تشخیص می‌دهد، گزارش متنی و JSON تولید می‌کند و در صورت نیاز فایل‌های خراب/مشکوک را به پوشه‌ای جدا منتقل می‌کند.

## ویژگی‌ها
- اسکن بازگشتی پوشه و فیلتر بر اساس پسوندهای تصویر/ویدیو
- تشخیص سلامت تصویر با Pillow (verify و load)
- تشخیص سلامت ویدیو با OpenCV (خواندن چند فریم، بررسی ابعاد، تحمل fps/frame_count نامعتبر)
- اجرای چندریسمانی برای سرعت بیشتر
- پردازش دسته‌ای و ذخیره تدریجی نتایج
- گزارش متنی و JSON با خلاصه و جزئیات
- انتقال خودکار فایل‌های خراب/مشکوک به پوشه جدا (با زیرپوشه نوع فایل)
- لاگ‌برداری کامل در فایل زمان‌دار

## پیش‌نیازها
- Python 3.9 یا جدیدتر (پیشنهادی)
- ویندوز 10 یا جدیدتر (سایر سیستم‌عامل‌ها نیز ممکن است کار کنند)

## نصب
1) (اختیاری) ساخت و فعال‌سازی محیط مجازی:
```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
```

2) نصب وابستگی‌ها:
```powershell
pip install -r requirements.txt
```

3) (اختیاری) برای بارگذاری خودکار تنظیمات از فایل .env:
```powershell
pip install python-dotenv
```

## پیکربندی
برنامه از متغیرهای محیطی و (در صورت نصب python-dotenv) از فایل `.env` برای پیکربندی استفاده می‌کند. فایل `.env` را در ریشه پروژه قرار دهید.

نمونه کلیدهای `.env` برای اسکریپت اصلی:
```env
# مسیرها
INPUT_DIRECTORY=F:\RECOVERY\Recovered\Lost Partition-1\BY-YEARS\2019\2019
OUTPUT_DIRECTORY=F:\RECOVERY\Recovered\Lost Partition-1\BY-YEARS\2019\2019\Corrupt_Files

# کنترل عملکرد
THREAD_COUNT=8
TIMEOUT_SECONDS=30
BATCH_SIZE=1000
SAVE_PROGRESS_INTERVAL=100
ENABLE_INCREMENTAL_SAVE=true

# محدودیت‌ها
MAX_FILE_SIZE_MB=10000
MIN_FILE_SIZE_BYTES=100
MAX_MEMORY_USAGE_MB=2000

# گزارش و انتقال
SAVE_DETAILED_REPORT=true
SAVE_JSON_REPORT=true
MOVE_CORRUPTED_FILES=true
CORRUPTED_FILES_FOLDER=corrupted_files
CREATE_SUBFOLDERS=true
```

کلیدهای پیکربندی:
- مسیرها: `INPUT_DIRECTORY`, `OUTPUT_DIRECTORY`
- عملکرد: `THREAD_COUNT`, `TIMEOUT_SECONDS`
- دسته‌ای و ذخیره تدریجی: `BATCH_SIZE`, `SAVE_PROGRESS_INTERVAL`, `ENABLE_INCREMENTAL_SAVE`
- محدودیت‌ها: `MAX_FILE_SIZE_MB`, `MIN_FILE_SIZE_BYTES`, `MAX_MEMORY_USAGE_MB`
- گزارش: `SAVE_DETAILED_REPORT`, `SAVE_JSON_REPORT`
- انتقال فایل خراب: `MOVE_CORRUPTED_FILES`, `CORRUPTED_FILES_FOLDER`, `CREATE_SUBFOLDERS`

اگر متغیری تنظیم نشود، مقدار پیش‌فرض امن داخل کد استفاده می‌شود.

## اسکریپت جمع‌آوری اسکرین‌شات‌ها
این اسکریپت تمام تصاویر اسکرین‌شات را از یک پوشه منبع به یک پوشه مقصد منتقل می‌کند. مسیرها و الگوها از `.env` خوانده می‌شود.

متغیرهای `.env` مورد نیاز:
```env
# مسیر پوشه‌ای که اسکرین‌شات‌ها در آن قرار می‌گیرند
SOURCE_DIR=C:\\Users\\YOUR_USER\\Pictures\\Screenshots

# مسیر پوشه مقصد برای جمع‌آوری همه اسکرین‌شات‌ها
DEST_DIR=D:\\Screenshots\\All

# (اختیاری) الگوهای نام‌گذاری اسکرین‌شات‌ها، با کاما جدا شوند
SCREENSHOT_NAME_PATTERNS=Screenshot,Snip,Snipping,Screen Shot,ScreenShot,اسکرین

# (اختیاری) پسوندهای مجاز تصاویر، با کاما جدا شوند
IMAGE_EXTENSIONS=png,jpg,jpeg,bmp,webp
```

اجرا:
```powershell
python collect_screenshots.py
```

نکات:
- در صورت تکراری‌بودن نام فایل در مقصد، نام به صورت `name (1).ext`, `name (2).ext` و ... تغییر می‌کند.
- تطبیق نام به‌صورت شامل (substring) و همچنین الگوهای رایج مانند `Screen Shot` انجام می‌شود.

## اجرا
در پوشه پروژه اجرا کنید:
```powershell
python damage_detector.py
```

در شروع اجرا، مسیر ورودی/خروجی و تنظیمات کلیدی چاپ می‌شود. پس از پایان اسکن، خلاصه نتایج نمایش داده می‌شود.

## خروجی‌ها
- گزارش متنی: `damage_report_YYYYMMDD_HHMMSS.txt`
- گزارش JSON: `damage_report_YYYYMMDD_HHMMSS.json`
- گزارش انتقال: `move_report_YYYYMMDD_HHMMSS.txt`
- ذخیره‌های تدریجی (در صورت فعال‌بودن): `damage_report_partial_YYYYMMDD_HHMMSS.json`
- فایل لاگ: `damage_detector_YYYYMMDD_HHMMSS.log`

نکته: چون بعد از گزارش، فایل‌های خراب منتقل می‌شوند، مسیرهای گزارش اصلی ممکن است با مکان نهایی فرق داشته باشد. برای جزئیات انتقال از `move_report_*.txt` استفاده کنید.

## نکات عملکرد و دقت
- `THREAD_COUNT` و `BATCH_SIZE` را متناسب با منابع سیستم تنظیم کنید.
- برای پوشه‌های بسیار بزرگ، `ENABLE_INCREMENTAL_SAVE=true` و `SAVE_PROGRESS_INTERVAL` مناسب انتخاب شود.
- برخی فرمت‌ها مانند `.heic`, `.raw`, `.dng` ممکن است به افزونه‌ها/کدک‌های اضافی نیاز داشته باشند.

## ساختار
- فایل اصلی: `damage_detector.py`
- کلاس‌ها: `Config`, `FileInfo`, `DamageDetector`

## مجوز
این پروژه بدون مجوز مشخص منتشر شده است. در صورت نیاز، فایل `LICENSE` اضافه کنید.

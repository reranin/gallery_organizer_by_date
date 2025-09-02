# ابزارهای مستقل مدیریت فایل

این مجموعه شامل ۵ ابزار مستقل برای مدیریت، سازماندهی و نگهداری فایل‌های تصویری و ویدیویی است.

## 📋 فهرست ابزارها

1. **جمع‌آوری اسکرین‌شات‌ها** (`screenshot_collector.py`)
2. **شناسایی فایل‌های خراب** (`damage_detector.py`)
3. **سازماندهی فایل‌ها** (`file_organizer.py`)
4. **تعمیر فایل‌های خراب** (`file_repair.py`)
5. **مدیریت پشتیبان‌گیری** (`backup_manager.py`)

## 🔧 نیازمندی‌ها

### پایه (ضروری):
```bash
pip install Pillow tqdm python-dotenv
```

### اختیاری (برای قابلیت‌های پیشرفته):
```bash
pip install opencv-python hachoir
```

### ابزارهای خارجی:
- **FFmpeg** (برای تعمیر ویدیوها)

## 📸 1. جمع‌آوری اسکرین‌شات‌ها

### استفاده:
```bash
# جمع‌آوری از پوشه منبع به مقصد
python screenshot_collector.py /path/to/source /path/to/destination

# کپی بدون حذف فایل‌های اصلی
python screenshot_collector.py /path/to/source /path/to/destination --copy

# فقط اسکن و گزارش
python screenshot_collector.py /path/to/source --scan-only
```

### ویژگی‌ها:
- تشخیص خودکار اسکرین‌شات‌ها بر اساس نام
- پشتیبانی از الگوهای مختلف (Screenshot، Snip، اسکرین و ...)
- مدیریت فایل‌های تکراری
- گزارش کامل عملیات

## 🔍 2. شناسایی فایل‌های خراب

### استفاده:
```bash
# اسکن پوشه
python damage_detector.py /path/to/directory

# تعیین پوشه خروجی
python damage_detector.py /path/to/directory -o /path/to/output

# تنظیم تعداد thread ها
python damage_detector.py /path/to/directory -t 8

# تنظیم حداکثر اندازه فایل (MB)
python damage_detector.py /path/to/directory --max-size 5000
```

### ویژگی‌ها:
- تشخیص فایل‌های تصویری خراب (JPEG، PNG، GIF و ...)
- تشخیص فایل‌های ویدیویی خراب
- بررسی با PIL و OpenCV/FFmpeg
- پردازش چندنخی برای سرعت بالا
- گزارش‌های جامع (TXT و JSON)

## 📁 3. سازماندهی فایل‌ها

### استفاده:
```bash
# سازماندهی بر اساس نوع فایل
python file_organizer.py /path/to/source /path/to/output -t type

# سازماندهی بر اساس تاریخ
python file_organizer.py /path/to/source /path/to/output -t date

# سازماندهی بر اساس دوربین
python file_organizer.py /path/to/source /path/to/output -t camera

# سازماندهی بر اساس اندازه فایل
python file_organizer.py /path/to/source /path/to/output -t size

# سازماندهی بر اساس رزولوشن
python file_organizer.py /path/to/source /path/to/output -t resolution

# کپی بدون حذف فایل‌های اصلی
python file_organizer.py /path/to/source /path/to/output --copy

# تنظیم فرمت تاریخ
python file_organizer.py /path/to/source /path/to/output -t date --date-format "%Y-%m-%d"
```

### ویژگی‌ها:
- ۵ نوع سازماندهی مختلف
- استخراج اطلاعات EXIF از تصاویر
- تشخیص اسکرین‌شات‌ها
- مدیریت فایل‌های تکراری
- حفظ ساختار پوشه‌ها

## 🔧 4. تعمیر فایل‌های خراب

### استفاده:
```bash
# تعمیر فایل واحد
python file_repair.py /path/to/damaged/file.jpg -o /path/to/output

# تعمیر کل پوشه
python file_repair.py /path/to/damaged/directory -o /path/to/output

# انتخاب روش‌های تعمیر
python file_repair.py /path/to/file -m repair_basic repair_truncated

# تعمیر ویدیوها
python file_repair.py /path/to/video.mp4 -m repair_copy repair_re_encode extract_audio
```

### روش‌های تعمیر:
- **auto**: انتخاب خودکار بهترین روش
- **repair_basic**: تعمیر پایه تصاویر
- **repair_truncated**: تعمیر تصاویر ناقص
- **repair_copy**: تعمیر ویدیو با کپی stream
- **repair_re_encode**: تعمیر ویدیو با re-encoding
- **repair_metadata**: تعمیر metadata ویدیو
- **extract_audio**: استخراج صدا از ویدیو خراب
- **extract_frames**: استخراج فریم‌های قابل بازیابی

## 💾 5. مدیریت پشتیبان‌گیری

### استفاده:

#### ایجاد پشتیبان‌گیری:
```bash
# پشتیبان‌گیری ساده
python backup_manager.py create /path/to/source

# پشتیبان‌گیری فشرده
python backup_manager.py create /path/to/source --compress

# پشتیبان‌گیری با نام خاص
python backup_manager.py create /path/to/source -n "my_backup"
```

#### مدیریت پشتیبان‌گیری‌ها:
```bash
# لیست پشتیبان‌گیری‌ها
python backup_manager.py list

# تایید یکپارچگی
python backup_manager.py verify backup_id

# بازیابی
python backup_manager.py restore backup_id /path/to/restore

# حذف
python backup_manager.py delete backup_id

# پاک‌سازی پشتیبان‌گیری‌های قدیمی (نگهداری ۳ عدد)
python backup_manager.py cleanup -k 3

# تولید گزارش
python backup_manager.py report
```

## ⚙️ تنظیمات محیطی با فایل .env

### راه‌اندازی سریع:
برای راحتی، فایل `.env` را کپی کنید:
```bash
cp env_template.txt .env
```

سپس مسیرهای مورد نیاز را در فایل `.env` تنظیم کنید:

```env
# =============== مسیرهای کلی ===============
INPUT_DIRECTORY=/path/to/your/input/folder
OUTPUT_DIRECTORY=/path/to/your/output/folder

# =============== تنظیمات اختیاری ===============
# برای اسکرین‌شات‌ها
SCREENSHOT_SOURCE_DIR=/path/to/screenshots/source
SCREENSHOT_DEST_DIR=/path/to/screenshots/destination

# برای پشتیبان‌گیری
BACKUP_ROOT_DIR=/path/to/backups

# تنظیمات عملکرد
THREAD_COUNT=8
MAX_FILE_SIZE_MB=10000
```

### مزایای استفاده از .env:
✅ **آسان‌تر**: نیازی به تایپ مسیرهای طولانی نیست  
✅ **سریع‌تر**: فقط نام ابزار را اجرا کنید  
✅ **ایمن‌تر**: مسیرهای حساس در فایل محلی ذخیره می‌شوند  
✅ **قابل تنظیم**: تنظیمات مختلف برای پروژه‌های مختلف  

### استفاده بدون آرگومان:
```bash
# بعد از تنظیم .env می‌توانید سادگی اجرا کنید:
python screenshot_collector.py
python damage_detector.py  
python file_organizer.py
python file_repair.py
python backup_manager.py create
```

## 📊 خروجی‌ها

### گزارش‌ها:
- **TXT**: گزارش‌های خوانا برای انسان
- **JSON**: داده‌های ساختاریافته برای پردازش
- **Log**: فایل‌های لاگ عملیات

### فایل‌های خروجی:
- فایل‌های تعمیر شده
- پشتیبان‌گیری‌های فشرده (ZIP)
- فایل‌های سازماندهی شده

## 🎯 نکات مهم

1. **امنیت**: تمام ابزارها پشتیبان‌گیری ایمن ارائه می‌دهند
2. **سرعت**: پردازش چندنخی برای حجم زیاد فایل‌ها
3. **سازگاری**: عملکرد در ویندوز، مک و لینوکس
4. **انعطاف**: هر ابزار مستقل و قابل تنظیم است
5. **گزارش‌دهی**: گزارش‌های کامل از تمام عملیات

## 🚀 مثال‌های کاربردی

### سناریو ۱: پردازش فایل‌های بازیابی شده (با .env)
```bash
# تنظیم فایل .env:
# INPUT_DIRECTORY=/path/to/recovered/files
# OUTPUT_DIRECTORY=/path/to/output

# ۱. اسکن و شناسایی فایل‌های خراب
python damage_detector.py

# ۲. تعمیر فایل‌های خراب
python file_repair.py

# ۳. سازماندهی فایل‌های سالم
python file_organizer.py -t date

# ۴. پشتیبان‌گیری از نتیجه نهایی
python backup_manager.py create --compress -n "recovered_files"
```

### سناریو ۲: پردازش فایل‌های بازیابی شده (بدون .env)
```bash
# ۱. اسکن و شناسایی فایل‌های خراب
python damage_detector.py /recovered/files -o ./analysis

# ۲. تعمیر فایل‌های خراب
python file_repair.py /recovered/files -o ./repaired

# ۳. سازماندهی فایل‌های سالم
python file_organizer.py /recovered/files ./organized -t date

# ۴. پشتیبان‌گیری از نتیجه نهایی
python backup_manager.py create ./organized --compress -n "recovered_files"
```

### سناریو ۳: تمیزکاری پوشه دانلود
```bash
# جدا کردن اسکرین‌شات‌ها
python screenshot_collector.py ~/Downloads ~/Pictures/Screenshots

# سازماندهی بقیه فایل‌ها
python file_organizer.py ~/Downloads ~/Pictures/Organized -t type
```

## 📞 پشتیبانی

برای مشکلات یا پیشنهادات، فایل‌های لاگ تولید شده را بررسی کنید.

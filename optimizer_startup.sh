#!/bin/bash
echo "==== اسکریپت بهینه‌سازی و راه‌اندازی ربات تلگرام ===="

# 1. پاکسازی فایل‌های قفل و موقت
echo "🧹 در حال پاکسازی فایل‌های قفل و موقت..."
find /tmp -name "telegram_bot_lock" -type f -delete
find /tmp -name "youtube_cookies_*.txt" -type f -delete
find /tmp -name "*_part" -type f -delete
find /tmp -name "*.ytdl" -type f -delete

# 2. بهینه‌سازی محیط
echo "⚙️ در حال بهینه‌سازی محیط..."

# تنظیم متغیرهای محیطی برای کارایی بهتر
export YTDLP_NO_ARIA2="1"
export HTTP_DOWNLOADER="native"
export YTDLP_DOWNLOADER="native"
export NO_EXTERNAL_DOWNLOADER="1"
export PYTHONUNBUFFERED="1"
export PYTHONDONTWRITEBYTECODE="1"

# 3. پاکسازی کش به صورت دستی
if [ -d "./downloads" ]; then
    echo "🗑️ در حال پاکسازی حافظه کش..."
    
    # حذف فایل‌های قدیمی (بیشتر از 3 روز)
    find ./downloads -type f -mtime +3 -delete
    
    # حذف دایرکتوری‌های خالی
    find ./downloads -type d -empty -delete
    
    # محدود کردن کل اندازه کش به 1GB
    DOWNLOADS_SIZE=$(du -sm ./downloads | cut -f1)
    if [ $DOWNLOADS_SIZE -gt 1000 ]; then
        echo "⚠️ حجم کش بیش از 1GB است، در حال پاکسازی فایل‌های قدیمی‌تر..."
        find ./downloads -type f -printf '%T@ %p\n' | sort -n | head -n 50 | awk '{print $2}' | xargs rm -f
    fi
    
    echo "✅ پاکسازی کش انجام شد."
else
    echo "📁 ایجاد دایرکتوری دانلود..."
    mkdir -p ./downloads
fi

# 4. اجرای اسکریپت پاکسازی aria2c در صورت وجود
if [ -f "./complete_aria2_removal.py" ]; then
    echo "🔄 در حال اجرای اسکریپت حذف وابستگی aria2c..."
    python ./complete_aria2_removal.py
fi

# 5. اجرای بهینه‌ساز کش در صورت وجود
if [ -f "./cache_optimizer.py" ]; then
    echo "📊 در حال اجرای بهینه‌ساز کش..."
    python ./cache_optimizer.py
fi

# 6. اطمینان از تنظیمات صحیح سیستم
echo "🔍 در حال بررسی سیستم..."
FFMPEG_PATH=$(which ffmpeg)
if [ -z "$FFMPEG_PATH" ]; then
    echo "⚠️ ffmpeg یافت نشد! ممکن است برخی قابلیت‌ها کار نکنند."
else
    echo "✅ ffmpeg پیدا شد: $FFMPEG_PATH"
fi

TELEGRAM_TOKEN=${TELEGRAM_BOT_TOKEN}
if [ -z "$TELEGRAM_TOKEN" ]; then
    echo "⚠️ توکن ربات تلگرام تنظیم نشده است! لطفاً متغیر محیطی TELEGRAM_BOT_TOKEN را تنظیم کنید."
else
    echo "✅ توکن ربات تلگرام پیدا شد."
fi

# 7. نمایش اطلاعات سیستم
echo "📊 اطلاعات سیستم:"
echo "- Python: $(python --version 2>&1)"
echo "- تعداد CPU: $(grep -c processor /proc/cpuinfo)"
echo "- RAM کل: $(free -h | grep -i mem | awk '{print $2}')"
echo "- فضای دیسک: $(df -h . | grep -v Filesystem | awk '{print $4}') آزاد"

# 8. راه‌اندازی ربات
echo "🚀 در حال راه‌اندازی ربات تلگرام..."
python telegram_downloader.py

exit 0
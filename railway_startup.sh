#!/bin/bash

# اسکریپت راه‌اندازی در پلتفرم Railway
# توجه: این اسکریپت تمام اشارات به aria2 را از سیستم حذف می‌کند

echo "====== Railway Startup Script ======"
echo "Starting the aria2 removal process..."

# 1. حذف هرگونه بسته مرتبط با aria2
apt-get update
apt-get remove -y aria2 libaria2-0 ||:
apt-get autoremove -y
apt-get clean
rm -rf /var/lib/apt/lists/*

# 2. حذف فایل باینری aria2c از کل سیستم
find / -name "aria2c" -type f -delete 2>/dev/null
find / -name "*aria2*" -type f -delete 2>/dev/null ||:

# 3. تنظیم متغیرهای محیطی برای جلوگیری از استفاده از aria2
export YDL_NO_ARIA2C=1
export YTDLP_NO_ARIA2=1
export HTTP_DOWNLOADER=native
export YTDLP_DOWNLOADER=native
export NO_EXTERNAL_DOWNLOADER=1

# 4. اجرای اسکریپت حذف کامل aria2
echo "Running complete aria2 removal script..."
python complete_aria2_removal.py

# 5. اجرای سایر اسکریپت‌های پاکسازی
echo "Running additional cleanup scripts..."
python clean_ytdlp_patch.py ||:
python disable_aria2c.py ||:
python yt_dlp_custom_override.py ||:

# 6. تایید حذف کامل aria2
if command -v aria2c > /dev/null 2>&1; then
    echo "WARNING: aria2c command is still available in the system!"
    # تلاش نهایی برای حذف اجباری
    which aria2c > /dev/null 2>&1 && rm -f $(which aria2c) ||:
else
    echo "SUCCESS: aria2c command is not available in the system."
fi

# 7. بررسی نهایی
SITE_PACKAGES=$(python -c "import site; print(site.getsitepackages()[0])")
echo "Checking for any remaining aria2 files in Python packages..."
find "$SITE_PACKAGES" -type f -name "*aria2*" -delete 2>/dev/null ||:
grep -r "aria2" "$SITE_PACKAGES/yt_dlp" --include="*.py" 2>/dev/null ||:

echo "======= Optimizer and Performance Improvement ======="
# اجرای بهینه‌ساز کش
if [ -f "cache_optimizer.py" ]; then
    echo "Running cache optimizer..."
    python cache_optimizer.py
fi

# اجرای بهینه‌ساز yt-dlp
if [ -f "yt_dlp_optimizer.py" ]; then
    echo "Running yt-dlp optimizer..."
    python yt_dlp_optimizer.py
fi

echo "======= Starting the Telegram Bot ======="
# اجرای ربات تلگرام
python telegram_downloader.py
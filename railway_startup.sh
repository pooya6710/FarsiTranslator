#!/bin/bash

# اسکریپت راه‌اندازی در پلتفرم Railway
# توجه: این اسکریپت تمام اشارات به aria2 را از سیستم حذف می‌کند

echo "====== Railway Startup Script ======"
echo "Starting the aria2 removal process..."

# تنظیم متغیرهای محیطی برای جلوگیری از استفاده از aria2 - قبل از هر عملیات
export YDL_NO_ARIA2C=1
export YTDLP_NO_ARIA2=1
export HTTP_DOWNLOADER=native
export YTDLP_DOWNLOADER=native
export NO_EXTERNAL_DOWNLOADER=1
export ARIA2C_DISABLED=1
export DISABLE_ARIA2C=true
export YTDLP_CONFIG='{"external_downloader":null,"external_downloader_args":null}'

# حذف فایل باینری aria2c از کل سیستم - فقط مسیرهای امن
echo "Removing aria2c binary from safe paths..."
for dir in /usr/bin /usr/local/bin /bin /sbin /usr/sbin ~/.local/bin; do
    if [ -f "$dir/aria2c" ]; then
        echo "Found aria2c in $dir - removing..."
        rm -f "$dir/aria2c"
    fi
done

# اجرای اسکریپت‌های پاکسازی پایتون
echo "Running Python cleanup scripts..."
python -c "import yt_dlp; print('YT-DLP version:', yt_dlp.version.__version__)" || true
python clean_ytdlp_patch.py || true
python complete_aria2_removal.py || true
python disable_aria2c.py || true

# بررسی اینکه آیا باینری aria2c هنوز موجود است
echo "Final check for aria2c binary..."
if command -v aria2c > /dev/null 2>&1; then
    echo "WARNING: aria2c command is still available in the system!"
    which aria2c > /dev/null 2>&1 && ls -la $(which aria2c) || true
    
    # تلاش نهایی برای حذف
    for path in $(which aria2c 2>/dev/null); do
        if [ -f "$path" ]; then
            echo "Removing $path..."
            rm -f "$path" || true
        fi
    done
else
    echo "SUCCESS: aria2c command is not available in the system."
fi

# تنظیم مجدد متغیرهای محیطی برای اطمینان بیشتر
export YDL_NO_ARIA2C=1
export YTDLP_NO_ARIA2=1
export HTTP_DOWNLOADER=native
export YTDLP_DOWNLOADER=native
export NO_EXTERNAL_DOWNLOADER=1

echo "======= Starting the Telegram Bot ======="
python telegram_downloader.py

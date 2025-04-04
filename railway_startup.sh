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

# حذف باینری aria2c با تمام روش‌های ممکن
echo "Removing aria2c binary by all means possible..."
apt-get update > /dev/null 2>&1 || true
apt-get remove -y aria2 libaria2-0 > /dev/null 2>&1 || true
apt-get autoremove -y > /dev/null 2>&1 || true
apt-get clean > /dev/null 2>&1 || true

# حذف فایل باینری aria2c از کل سیستم - فقط مسیرهای امن
echo "Removing aria2c binary from safe paths..."
for dir in /usr/bin /usr/local/bin /bin /sbin /usr/sbin ~/.local/bin; do
    if [ -f "$dir/aria2c" ]; then
        echo "Found aria2c in $dir - removing..."
        rm -f "$dir/aria2c"
    else
        # ایجاد یک فایل بلوکه به جای aria2c
        echo -e '#!/bin/sh\necho "aria2c is blocked by Railway"\nexit 1' > "$dir/aria2c"
        chmod +x "$dir/aria2c"
        echo "Created blocking script for aria2c in $dir"
    fi
done

# اجرای اسکریپت‌های پاکسازی پایتون
echo "Running Python cleanup scripts..."
python block_aria2_completely.py || true
python clean_ytdlp_patch.py || true
python complete_aria2_removal.py || true

# بررسی اینکه آیا باینری aria2c هنوز موجود است
echo "Final check for aria2c binary..."
if command -v aria2c > /dev/null 2>&1; then
    echo "WARNING: aria2c command is still available in the system!"
    which aria2c || true
    
    # تلاش نهایی برای حذف
    rm -f $(which aria2c) || true
    
    # ایجاد یک اسکریپت بلوکه به جای آن
    echo -e '#!/bin/sh\necho "aria2c is blocked by Railway"\nexit 1' > "$(which aria2c)"
    chmod +x "$(which aria2c)"
    echo "Created blocking script to replace aria2c"
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

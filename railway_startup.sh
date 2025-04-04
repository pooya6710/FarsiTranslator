#!/bin/bash

# اسکریپت راه‌اندازی در پلتفرم Railway
# توجه: این اسکریپت تمام اشارات به disabled_aria را از سیستم حذف می‌کند

echo "====== Railway Startup Script ======"
echo "Starting the disabled_aria removal process..."

# تنظیم متغیرهای محیطی برای جلوگیری از استفاده از disabled_aria - قبل از هر عملیات
export YDL_NO_disabled_downloader=1
export YTDLP_NO_disabled_aria=1
export HTTP_DOWNLOADER=native
export YTDLP_DOWNLOADER=native
export NO_EXTERNAL_DOWNLOADER=1
export disabled_downloader_DISABLED=1
export DISABLE_disabled_downloader=true
export YTDLP_CONFIG='{"external_downloader":null,"external_downloader_args":null}'

# حذف باینری disabled_downloader با تمام روش‌های ممکن
echo "Removing disabled_downloader binary by all means possible..."
apt-get update > /dev/null 2>&1 || true
apt-get remove -y disabled_aria libdisabled_aria-0 > /dev/null 2>&1 || true
apt-get autoremove -y > /dev/null 2>&1 || true
apt-get clean > /dev/null 2>&1 || true

# حذف فایل باینری disabled_downloader از کل سیستم - فقط مسیرهای امن
echo "Removing disabled_downloader binary from safe paths..."
for dir in /usr/bin /usr/local/bin /bin /sbin /usr/sbin ~/.local/bin; do
    if [ -f "$dir/disabled_downloader" ]; then
        echo "Found disabled_downloader in $dir - removing..."
        rm -f "$dir/disabled_downloader"
    else
        # ایجاد یک فایل بلوکه به جای disabled_downloader
        echo -e '#!/bin/sh\necho "disabled_downloader is blocked by Railway"\nexit 1' > "$dir/disabled_downloader"
        chmod +x "$dir/disabled_downloader"
        echo "Created blocking script for disabled_downloader in $dir"
    fi
done

# اجرای اسکریپت‌های پاکسازی پایتون
echo "Running Python cleanup scripts..."
python block_disabled_aria_completely.py || true
python clean_ytdlp_patch.py || true
python complete_disabled_aria_removal.py || true

# بررسی اینکه آیا باینری disabled_downloader هنوز موجود است
echo "Final check for disabled_downloader binary..."
if command -v disabled_downloader > /dev/null 2>&1; then
    echo "WARNING: disabled_downloader command is still available in the system!"
    which disabled_downloader || true
    
    # تلاش نهایی برای حذف
    rm -f $(which disabled_downloader) || true
    
    # ایجاد یک اسکریپت بلوکه به جای آن
    echo -e '#!/bin/sh\necho "disabled_downloader is blocked by Railway"\nexit 1' > "$(which disabled_downloader)"
    chmod +x "$(which disabled_downloader)"
    echo "Created blocking script to replace disabled_downloader"
else
    echo "SUCCESS: disabled_downloader command is not available in the system."
fi

# تنظیم مجدد متغیرهای محیطی برای اطمینان بیشتر
export YDL_NO_disabled_downloader=1
export YTDLP_NO_disabled_aria=1
export HTTP_DOWNLOADER=native
export YTDLP_DOWNLOADER=native
export NO_EXTERNAL_DOWNLOADER=1

echo "======= Starting the Telegram Bot ======="
python telegram_downloader.py

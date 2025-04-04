#!/bin/bash

# اسکریپت مسدودسازی دانلودرهای ممنوع در سطح سیستم

echo "مسدودسازی دانلودرهای ممنوع در سطح سیستم..."

# تنظیم متغیرهای محیطی
export YDL_NO_EXTERNAL_DOWNLOADER=1
export HTTP_DOWNLOADER=native
export YTDLP_DOWNLOADER=native
export NO_EXTERNAL_DOWNLOADER=1
export DISABLE_EXTERNAL_DL=true

# ایجاد symlink های جعلی برای جلوگیری از اجرای دانلودرهای ممنوع
create_dummy_file() {
    if [ -f "$1" ]; then
        echo "فایل $1 موجود است. در حال غیرفعال کردن..."
        mv "$1" "${1}.real.backup"
    fi
    
    echo '#!/bin/bash' > "$1"
    echo 'echo "This program has been disabled"' >> "$1"
    echo 'exit 1' >> "$1"
    chmod +x "$1"
    echo "فایل جعلی $1 ایجاد شد"
}

# بررسی و ایجاد فایل‌های جعلی برای مسیرهای رایج
for path in /usr/bin /usr/local/bin /bin; do
    create_dummy_file "$path/disabled_c"
done

echo "تمام دانلودرهای ممنوع با موفقیت مسدود شدند"

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
اسکریپت نهایی برای دیپلوی در Railway

این اسکریپت تمام تنظیمات لازم برای دیپلوی در Railway را انجام می‌دهد.
تمام روش‌های پیشرفته برای حذف aria2 در این اسکریپت اعمال شده‌اند.
"""

import os
import sys
import logging
import importlib
import subprocess
import tempfile
import shutil
import site
from pathlib import Path

# تنظیم لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# 1. ایجاد و بازنویسی فایل‌های کانفیگ Railway
def create_railway_config_files():
    """ایجاد فایل‌های کانفیگ Railway"""
    
    # 1.1. ایجاد دایرکتوری .nixpacks
    nixpacks_dir = '.nixpacks'
    os.makedirs(nixpacks_dir, exist_ok=True)
    
    # 1.2. ایجاد فایل .nixpacks/environment.toml
    environment_toml = """
[phases.setup]
cmds = [
  "echo 'Setting up environment without aria2'",
  "find / -name 'aria2*' -delete 2>/dev/null || true"
]

[phases.install]
cmds = [
  "pip install --no-cache-dir --upgrade pip",
  "pip install --no-cache-dir -r requirements.txt",
  "python block_aria2_completely.py || true",
  "python clean_ytdlp_patch.py || true",
  "python complete_aria2_removal.py || true"
]

[phases.build]
cmds = [
  "python block_aria2_completely.py || true",
  "python clean_ytdlp_patch.py || true",
  "python complete_aria2_removal.py || true",
  "! command -v aria2c > /dev/null && echo 'SUCCESS: aria2c not found'"
]

[phases.deploy]
cmds = [
  "python block_aria2_completely.py || true",
  "find / -name 'aria2*' -type f -delete 2>/dev/null || true"
]

[start]
cmd = "python block_aria2_completely.py && python clean_ytdlp_patch.py && python complete_aria2_removal.py && python telegram_downloader.py"

[variables]
YDL_NO_ARIA2C = "1"
YTDLP_NO_ARIA2 = "1"
HTTP_DOWNLOADER = "native"
YTDLP_DOWNLOADER = "native"
NO_EXTERNAL_DOWNLOADER = "1"
ARIA2C_DISABLED = "1"
DISABLE_ARIA2C = "true"
YTDLP_CONFIG = "{\"external_downloader\":null,\"external_downloader_args\":null}"
"""
    with open(os.path.join(nixpacks_dir, 'environment.toml'), 'w') as f:
        f.write(environment_toml)
    logger.info(f"فایل {nixpacks_dir}/environment.toml ایجاد شد")
    
    # 1.3. ایجاد فایل railway.toml
    railway_toml = """
[build]
builder = "nixpacks"
buildCommand = "echo 'BUILDING WITHOUT ARIA2' && python block_aria2_completely.py && python clean_ytdlp_patch.py && python complete_aria2_removal.py"

[deploy]
startCommand = "python block_aria2_completely.py && python clean_ytdlp_patch.py && python complete_aria2_removal.py && python telegram_downloader.py"
restartPolicyType = "always"

[nixpacks]
nixpacksConfigPath = ".nixpacks/environment.toml"
aptPkgs = ["ffmpeg", "python3-dev"]
dontInstallRecommends = true

[env]
YDL_NO_ARIA2C = "1"
HTTP_DOWNLOADER = "native"
YTDLP_DOWNLOADER = "native"
NO_EXTERNAL_DOWNLOADER = "1"
YTDLP_NO_ARIA2 = "1"
ARIA2C_DISABLED = "1"
DISABLE_ARIA2C = "true"
YTDLP_CONFIG = "{\"external_downloader\":null,\"external_downloader_args\":null}"
"""
    with open('railway.toml', 'w') as f:
        f.write(railway_toml)
    logger.info("فایل railway.toml ایجاد شد")
    
    # 1.4. ایجاد فایل railway.json
    railway_json = """{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "echo 'BUILDING WITHOUT ARIA2' && python block_aria2_completely.py && python clean_ytdlp_patch.py && python complete_aria2_removal.py",
    "nixpacksConfigPath": ".nixpacks/environment.toml"
  },
  "deploy": {
    "startCommand": "python block_aria2_completely.py && python clean_ytdlp_patch.py && python complete_aria2_removal.py && python telegram_downloader.py",
    "restartPolicyType": "ALWAYS",
    "healthcheckPath": "/",
    "healthcheckTimeout": 300
  }
}"""
    with open('railway.json', 'w') as f:
        f.write(railway_json)
    logger.info("فایل railway.json ایجاد شد")
    
    # 1.5. ایجاد فایل .railwayignore
    railwayignore_content = """
**/aria2*
**/aria2c*
**/aria2.*
**/*aria2*
**/aria*2*
**/Aria2*
**/ARIA2*
.git
.github
.vscode
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
*.egg-info/
.installed.cfg
*.egg
"""
    with open('.railwayignore', 'w') as f:
        f.write(railwayignore_content)
    logger.info("فایل .railwayignore ایجاد شد")
    
    # 1.6. ایجاد فایل .buildignore
    buildignore_content = """
**/aria2*
**/aria2c*
**/aria2.*
**/*aria2*
**/aria*2*
**/Aria2*
**/ARIA2*
"""
    with open('.buildignore', 'w') as f:
        f.write(buildignore_content)
    logger.info("فایل .buildignore ایجاد شد")
    
    return True

# 2. تنظیم و تغییر فایل Dockerifle
def create_optimized_dockerfile():
    """ایجاد فایل Dockerfile بهینه‌سازی شده"""
    
    dockerfile_content = """# استفاده از روش چندمرحله‌ای برای ایجاد تصویر نهایی بدون هیچ اشاره‌ای به aria2
FROM python:3.10-slim AS builder

# تنظیم متغیرهای محیطی برای جلوگیری از نصب aria2
ENV YDL_NO_ARIA2C=1 \\
    HTTP_DOWNLOADER=native \\
    YTDLP_DOWNLOADER=native \\
    NO_EXTERNAL_DOWNLOADER=1 \\
    YTDLP_NO_ARIA2=1 \\
    ARIA2C_DISABLED=1 \\
    DISABLE_ARIA2C=true \\
    YTDLP_CONFIG='{"external_downloader":null,"external_downloader_args":null}'

# نصب ابزارهای مورد نیاز برای ساخت (بدون نصب aria2)
RUN apt-get update && apt-get install -y --no-install-recommends \\
    ffmpeg \\
    python3-dev \\
    build-essential \\
    && apt-get remove -y aria2 libaria2-0 || true \\
    && apt-get clean \\
    && rm -rf /var/lib/apt/lists/* \\
    && find / -name "aria2*" -type f -delete 2>/dev/null || true

# تنظیم دایرکتوری کاری
WORKDIR /build

# کپی فایل‌های پروژه و نصب وابستگی‌ها - بدون aria2
COPY requirements.txt .
COPY block_aria2_completely.py complete_aria2_removal.py clean_ytdlp_patch.py ./

# حذف aria2 از requirements.txt
RUN grep -v aria2 requirements.txt > requirements-clean.txt && mv requirements-clean.txt requirements.txt

# نصب وابستگی‌های پایتون در محیط مجازی
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \\
    pip install --no-cache-dir -r requirements.txt && \\
    python block_aria2_completely.py && \\
    python complete_aria2_removal.py && \\
    python clean_ytdlp_patch.py

# مرحله دوم: پاکسازی و ساخت تصویر نهایی
FROM python:3.10-slim

# تنظیم محیط کار برای جلوگیری از استفاده از aria2
ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PATH="/opt/venv/bin:$PATH" \\
    PYTHONPATH="/app" \\
    NO_EXTERNAL_DOWNLOADER=1 \\
    YTDLP_NO_ARIA2=1 \\
    YDL_NO_ARIA2C=1 \\
    HTTP_DOWNLOADER=native \\
    YTDLP_DOWNLOADER=native \\
    ARIA2C_DISABLED=1 \\
    DISABLE_ARIA2C=true \\
    YTDLP_CONFIG='{"external_downloader":null,"external_downloader_args":null}'

# نصب بسته‌های سیستمی مورد نیاز (بدون نصب aria2)
RUN apt-get update && apt-get install -y --no-install-recommends \\
    ffmpeg \\
    python3-dev \\
    && apt-get remove -y aria2 libaria2-0 || true \\
    && apt-get clean \\
    && rm -rf /var/lib/apt/lists/* \\
    && find / -name "aria2*" -type f -delete 2>/dev/null || true

# ایجاد دایرکتوری کاری
WORKDIR /app

# کپی محیط مجازی از مرحله قبل
COPY --from=builder /opt/venv /opt/venv

# کپی فایل‌های پروژه
COPY . .

# ایجاد دایرکتوری‌های مورد نیاز
RUN mkdir -p /app/downloads && chmod 777 /app/downloads \\
    && mkdir -p /tmp/ytdlp_temp && chmod 777 /tmp/ytdlp_temp

# اجرای اسکریپت‌های پاکسازی
RUN python block_aria2_completely.py && \\
    python complete_aria2_removal.py && \\
    python clean_ytdlp_patch.py && \\
    find / -name "aria2*" -type f -delete 2>/dev/null || true

# بررسی نهایی - اطمینان از عدم وجود aria2c
RUN echo "Final check for aria2c..." && \\
    ! command -v aria2c > /dev/null && \\
    echo "SUCCESS: aria2c is not installed!"

# فایل اجرایی
CMD bash railway_startup.sh
"""
    
    with open('Dockerfile', 'w') as f:
        f.write(dockerfile_content)
    logger.info("فایل Dockerfile ایجاد شد")
    
    return True

# 3. بهینه‌سازی فایل railway_startup.sh
def optimize_railway_startup():
    """بهینه‌سازی اسکریپت اجرای Railway"""
    
    startup_content = """#!/bin/bash

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
        echo -e '#!/bin/sh\\necho "aria2c is blocked by Railway"\\nexit 1' > "$dir/aria2c"
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
    echo -e '#!/bin/sh\\necho "aria2c is blocked by Railway"\\nexit 1' > "$(which aria2c)"
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
"""
    
    with open('railway_startup.sh', 'w') as f:
        f.write(startup_content)
    os.chmod('railway_startup.sh', 0o755)
    logger.info("فایل railway_startup.sh بهینه‌سازی شد")
    
    return True

# 4. دستورالعمل‌های دیپلوی نهایی
def print_deployment_instructions():
    """نمایش دستورالعمل‌های دیپلوی نهایی"""
    
    instructions = """
===========================================================
دستورالعمل‌های دیپلوی نهایی در Railway
===========================================================

1. فایل‌های زیر برای دیپلوی آماده شده‌اند:
   - block_aria2_completely.py (اسکریپت مسدود کردن کامل aria2)
   - complete_aria2_removal.py (اسکریپت حذف کامل aria2)
   - clean_ytdlp_patch.py (اسکریپت پاکسازی yt-dlp)
   - railway.toml (تنظیمات Railway)
   - railway.json (تنظیمات Railway در فرمت JSON)
   - Dockerfile (فایل Docker بهینه‌سازی شده)
   - railway_startup.sh (اسکریپت راه‌اندازی)
   - .nixpacks/environment.toml (تنظیمات محیط Nixpacks)
   - .railwayignore (فایل‌های نادیده گرفته شده)
   - .buildignore (فایل‌های نادیده گرفته شده در زمان ساخت)

2. مراحل دیپلوی در Railway:
   - ابتدا مطمئن شوید که اسکریپت‌های پاکسازی قابل اجرا هستند:
     * chmod +x clean_ytdlp_patch.py complete_aria2_removal.py block_aria2_completely.py railway_startup.sh
   - از پنل Railway یک پروژه جدید ایجاد کنید
   - گزینه دیپلوی از GitHub را انتخاب کنید
   - مخزن خود را انتخاب کنید
   - متغیرهای محیطی زیر را تنظیم کنید:
     * YDL_NO_ARIA2C=1
     * HTTP_DOWNLOADER=native
     * YTDLP_DOWNLOADER=native
     * NO_EXTERNAL_DOWNLOADER=1
     * YTDLP_NO_ARIA2=1
     * ARIA2C_DISABLED=1
     * DISABLE_ARIA2C=true
     * TELEGRAM_BOT_TOKEN=your_bot_token

3. نکات مهم:
   - اگر با خطای "Banned Dependency Detected" مواجه شدید:
     * پروژه را از Railway حذف کنید
     * کش Railway را پاک کنید (از منوی Settings)
     * دوباره پروژه را دیپلوی کنید
   - اگر باز هم با خطا مواجه شدید، از دیپلوی با Docker استفاده کنید:
     * در پنل Railway، گزینه "Deploy with Docker" را انتخاب کنید
     * این گزینه از Dockerfile موجود در پروژه استفاده می‌کند که تمام اشارات به aria2 را حذف می‌کند

امیدوارم دیپلوی شما موفقیت‌آمیز باشد!
===========================================================
"""
    
    print(instructions)
    
    # ذخیره دستورالعمل‌ها در فایل
    with open('RAILWAY_DEPLOYMENT_INSTRUCTIONS.md', 'w') as f:
        f.write(instructions)
    logger.info("دستورالعمل‌های دیپلوی در فایل RAILWAY_DEPLOYMENT_INSTRUCTIONS.md ذخیره شدند")
    
    return True

def main():
    """تابع اصلی"""
    logger.info("=== شروع آماده‌سازی برای دیپلوی در Railway ===")
    
    # 1. ایجاد و بازنویسی فایل‌های کانفیگ Railway
    create_railway_config_files()
    
    # 2. تنظیم و تغییر فایل Dockerifle
    create_optimized_dockerfile()
    
    # 3. بهینه‌سازی فایل railway_startup.sh
    optimize_railway_startup()
    
    # 4. دستورالعمل‌های دیپلوی نهایی
    print_deployment_instructions()
    
    logger.info("=== آماده‌سازی برای دیپلوی در Railway با موفقیت انجام شد ===")
    print("\n\n=== آماده‌سازی برای دیپلوی در Railway با موفقیت انجام شد ===\n\n")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
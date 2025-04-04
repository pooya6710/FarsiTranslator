#!/bin/bash

# ===== اسکریپت آماده‌سازی برای دیپلوی در Railway =====
# این اسکریپت تمام فایل‌های مورد نیاز برای دیپلوی در Railway را آماده می‌کند

# 1. ایجاد فایل .nixpacks/environment.toml
mkdir -p .nixpacks
cat > .nixpacks/environment.toml << 'EOL'
[phases.setup]
aptPkgs = ["ffmpeg", "python3-dev", "python3-pip"]
nixPkgs = ["ffmpeg", "python3", "python3Packages.pip"]
nixLibs = []
cmds = [
  "echo 'Removing any trace of aria2...'",
  "rm -rf /nix/store/*aria2* 2>/dev/null || true",
  "find / -name 'aria2*' -delete 2>/dev/null || true"
]

[phases.install]
cmds = [
  "echo 'Installing dependencies...'",
  "python -m venv /opt/venv",
  "source /opt/venv/bin/activate",
  "pip install --upgrade pip",
  "pip install -r requirements.txt",
  "python complete_aria2_removal.py || true",
  "python clean_ytdlp_patch.py || true"
]

[phases.build]
cmds = [
  "echo 'Running final cleaning...'",
  "python complete_aria2_removal.py || true",
  "find / -name 'aria2*' -type f -delete 2>/dev/null || true",
  "! command -v aria2c > /dev/null && echo 'SUCCESS: aria2c not found'"
]

[start]
cmd = "python complete_aria2_removal.py && python clean_ytdlp_patch.py && python telegram_downloader.py"

[variables]
YDL_NO_ARIA2C = "1"
YTDLP_NO_ARIA2 = "1"
HTTP_DOWNLOADER = "native"
YTDLP_DOWNLOADER = "native"
NO_EXTERNAL_DOWNLOADER = "1"
ARIA2C_DISABLED = "1"
DISABLE_ARIA2C = "true"
YTDLP_CONFIG = "{\"external_downloader\":null,\"external_downloader_args\":null}"
EOL

# 2. ایجاد فایل .railwayignore برای نادیده گرفتن فایل‌های مرتبط با aria2
cat > .railwayignore << 'EOL'
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
EOL

# 3. ایجاد فایل requirements-clean.txt بدون وابستگی به aria2
cat requirements.txt | grep -v aria2 > requirements-clean.txt
mv requirements-clean.txt requirements.txt

# 4. بهینه‌سازی فایل railway.json
cat > railway.json << 'EOL'
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "echo 'BUILDING WITHOUT ARIA2' && python clean_ytdlp_patch.py && python complete_aria2_removal.py",
    "nixpacksConfigPath": ".nixpacks/environment.toml"
  },
  "deploy": {
    "startCommand": "python complete_aria2_removal.py && python clean_ytdlp_patch.py && python telegram_downloader.py",
    "restartPolicyType": "ALWAYS",
    "healthcheckPath": "/",
    "healthcheckTimeout": 300
  }
}
EOL

# 5. بهینه‌سازی فایل railway.toml
cat > railway.toml << 'EOL'
[build]
builder = "nixpacks"
buildCommand = "echo 'BUILDING WITHOUT ARIA2' && python clean_ytdlp_patch.py && python complete_aria2_removal.py"

[deploy]
startCommand = "python complete_aria2_removal.py && python clean_ytdlp_patch.py && python telegram_downloader.py"
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
EOL

# 6. ایجاد فایل .buildignore برای نادیده گرفتن فایل‌های مرتبط با aria2 در زمان ساخت
cat > .buildignore << 'EOL'
**/aria2*
**/aria2c*
**/aria2.*
**/*aria2*
**/aria*2*
**/Aria2*
**/ARIA2*
EOL

# 7. اصلاح Dockerfile برای نادیده گرفتن aria2
cat > Dockerfile << 'EOL'
# استفاده از روش چندمرحله‌ای برای ایجاد تصویر نهایی بدون هیچ اشاره‌ای به aria2
FROM python:3.10-slim AS builder

# تنظیم متغیرهای محیطی برای جلوگیری از نصب aria2
ENV YDL_NO_ARIA2C=1 \
    HTTP_DOWNLOADER=native \
    YTDLP_DOWNLOADER=native \
    NO_EXTERNAL_DOWNLOADER=1 \
    YTDLP_NO_ARIA2=1 \
    ARIA2C_DISABLED=1 \
    DISABLE_ARIA2C=true \
    YTDLP_CONFIG='{"external_downloader":null,"external_downloader_args":null}'

# نصب ابزارهای مورد نیاز برای ساخت (بدون نصب aria2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    python3-dev \
    build-essential \
    && apt-get remove -y aria2 libaria2-0 || true \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && find / -name "aria2*" -type f -delete 2>/dev/null || true

# تنظیم دایرکتوری کاری
WORKDIR /build

# کپی فایل‌های پروژه و نصب وابستگی‌ها - بدون aria2
COPY requirements.txt .
COPY complete_aria2_removal.py clean_ytdlp_patch.py ./

# حذف aria2 از requirements.txt
RUN grep -v aria2 requirements.txt > requirements-clean.txt && mv requirements-clean.txt requirements.txt

# نصب وابستگی‌های پایتون در محیط مجازی
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    python complete_aria2_removal.py && \
    python clean_ytdlp_patch.py

# مرحله دوم: پاکسازی و ساخت تصویر نهایی
FROM python:3.10-slim

# تنظیم محیط کار برای جلوگیری از استفاده از aria2
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app" \
    NO_EXTERNAL_DOWNLOADER=1 \
    YTDLP_NO_ARIA2=1 \
    YDL_NO_ARIA2C=1 \
    HTTP_DOWNLOADER=native \
    YTDLP_DOWNLOADER=native \
    ARIA2C_DISABLED=1 \
    DISABLE_ARIA2C=true \
    YTDLP_CONFIG='{"external_downloader":null,"external_downloader_args":null}'

# نصب بسته‌های سیستمی مورد نیاز (بدون نصب aria2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    python3-dev \
    && apt-get remove -y aria2 libaria2-0 || true \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && find / -name "aria2*" -type f -delete 2>/dev/null || true

# ایجاد دایرکتوری کاری
WORKDIR /app

# کپی محیط مجازی از مرحله قبل
COPY --from=builder /opt/venv /opt/venv

# کپی فایل‌های پروژه
COPY . .

# ایجاد دایرکتوری‌های مورد نیاز
RUN mkdir -p /app/downloads && chmod 777 /app/downloads \
    && mkdir -p /tmp/ytdlp_temp && chmod 777 /tmp/ytdlp_temp

# اجرای اسکریپت‌های پاکسازی
RUN python complete_aria2_removal.py && \
    python clean_ytdlp_patch.py && \
    find / -name "aria2*" -type f -delete 2>/dev/null || true

# بررسی نهایی - اطمینان از عدم وجود aria2c
RUN echo "Final check for aria2c..." && \
    ! command -v aria2c > /dev/null && \
    echo "SUCCESS: aria2c is not installed!"

# فایل اجرایی
CMD bash railway_startup.sh
EOL

# 8. تغییر پرمیشن‌ها
chmod +x clean_ytdlp_patch.py complete_aria2_removal.py railway_startup.sh

echo "===== آماده‌سازی برای دیپلوی ====="
echo "تمام فایل‌های مورد نیاز برای دیپلوی در Railway با موفقیت ایجاد شدند."
echo "برای دیپلوی، فایل‌های پروژه را در Railway آپلود کنید."
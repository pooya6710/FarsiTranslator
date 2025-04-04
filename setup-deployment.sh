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
  "echo 'Removing any trace of disabled_aria...'",
  "rm -rf /nix/store/*disabled_aria* 2>/dev/null || true",
  "find / -name 'disabled_aria*' -delete 2>/dev/null || true"
]

[phases.install]
cmds = [
  "echo 'Installing dependencies...'",
  "python -m venv /opt/venv",
  "source /opt/venv/bin/activate",
  "pip install --upgrade pip",
  "pip install -r requirements.txt",
  "python complete_disabled_aria_removal.py || true",
  "python clean_ytdlp_patch.py || true"
]

[phases.build]
cmds = [
  "echo 'Running final cleaning...'",
  "python complete_disabled_aria_removal.py || true",
  "find / -name 'disabled_aria*' -type f -delete 2>/dev/null || true",
  "! command -v disabled_downloader > /dev/null && echo 'SUCCESS: disabled_downloader not found'"
]

[start]
cmd = "python complete_disabled_aria_removal.py && python clean_ytdlp_patch.py && python telegram_downloader.py"

[variables]
YDL_NO_disabled_downloader = "1"
YTDLP_NO_disabled_aria = "1"
HTTP_DOWNLOADER = "native"
YTDLP_DOWNLOADER = "native"
NO_EXTERNAL_DOWNLOADER = "1"
disabled_downloader_DISABLED = "1"
DISABLE_disabled_downloader = "true"
YTDLP_CONFIG = "{\"external_downloader\":null,\"external_downloader_args\":null}"
EOL

# 2. ایجاد فایل .railwayignore برای نادیده گرفتن فایل‌های مرتبط با disabled_aria
cat > .railwayignore << 'EOL'
**/disabled_aria*
**/disabled_downloader*
**/disabled_aria.*
**/*disabled_aria*
**/aria*2*
**/disabled_aria*
**/disabled_aria*
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

# 3. ایجاد فایل requirements-clean.txt بدون وابستگی به disabled_aria
cat requirements.txt | grep -v disabled_aria > requirements-clean.txt
mv requirements-clean.txt requirements.txt

# 4. بهینه‌سازی فایل railway.json
cat > railway.json << 'EOL'
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "echo 'BUILDING WITHOUT disabled_aria' && python clean_ytdlp_patch.py && python complete_disabled_aria_removal.py",
    "nixpacksConfigPath": ".nixpacks/environment.toml"
  },
  "deploy": {
    "startCommand": "python complete_disabled_aria_removal.py && python clean_ytdlp_patch.py && python telegram_downloader.py",
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
buildCommand = "echo 'BUILDING WITHOUT disabled_aria' && python clean_ytdlp_patch.py && python complete_disabled_aria_removal.py"

[deploy]
startCommand = "python complete_disabled_aria_removal.py && python clean_ytdlp_patch.py && python telegram_downloader.py"
restartPolicyType = "always"

[nixpacks]
nixpacksConfigPath = ".nixpacks/environment.toml"
aptPkgs = ["ffmpeg", "python3-dev"]
dontInstallRecommends = true

[env]
YDL_NO_disabled_downloader = "1"
HTTP_DOWNLOADER = "native"
YTDLP_DOWNLOADER = "native"
NO_EXTERNAL_DOWNLOADER = "1"
YTDLP_NO_disabled_aria = "1"
disabled_downloader_DISABLED = "1"
DISABLE_disabled_downloader = "true"
YTDLP_CONFIG = "{\"external_downloader\":null,\"external_downloader_args\":null}"
EOL

# 6. ایجاد فایل .buildignore برای نادیده گرفتن فایل‌های مرتبط با disabled_aria در زمان ساخت
cat > .buildignore << 'EOL'
**/disabled_aria*
**/disabled_downloader*
**/disabled_aria.*
**/*disabled_aria*
**/aria*2*
**/disabled_aria*
**/disabled_aria*
EOL

# 7. اصلاح Dockerfile برای نادیده گرفتن disabled_aria
cat > Dockerfile << 'EOL'
# استفاده از روش چندمرحله‌ای برای ایجاد تصویر نهایی بدون هیچ اشاره‌ای به disabled_aria
FROM python:3.10-slim AS builder

# تنظیم متغیرهای محیطی برای جلوگیری از نصب disabled_aria
ENV YDL_NO_disabled_downloader=1 \
    HTTP_DOWNLOADER=native \
    YTDLP_DOWNLOADER=native \
    NO_EXTERNAL_DOWNLOADER=1 \
    YTDLP_NO_disabled_aria=1 \
    disabled_downloader_DISABLED=1 \
    DISABLE_disabled_downloader=true \
    YTDLP_CONFIG='{"external_downloader":null,"external_downloader_args":null}'

# نصب ابزارهای مورد نیاز برای ساخت (بدون نصب disabled_aria)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    python3-dev \
    build-essential \
    && apt-get remove -y disabled_aria libdisabled_aria-0 || true \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && find / -name "disabled_aria*" -type f -delete 2>/dev/null || true

# تنظیم دایرکتوری کاری
WORKDIR /build

# کپی فایل‌های پروژه و نصب وابستگی‌ها - بدون disabled_aria
COPY requirements.txt .
COPY complete_disabled_aria_removal.py clean_ytdlp_patch.py ./

# حذف disabled_aria از requirements.txt
RUN grep -v disabled_aria requirements.txt > requirements-clean.txt && mv requirements-clean.txt requirements.txt

# نصب وابستگی‌های پایتون در محیط مجازی
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    python complete_disabled_aria_removal.py && \
    python clean_ytdlp_patch.py

# مرحله دوم: پاکسازی و ساخت تصویر نهایی
FROM python:3.10-slim

# تنظیم محیط کار برای جلوگیری از استفاده از disabled_aria
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app" \
    NO_EXTERNAL_DOWNLOADER=1 \
    YTDLP_NO_disabled_aria=1 \
    YDL_NO_disabled_downloader=1 \
    HTTP_DOWNLOADER=native \
    YTDLP_DOWNLOADER=native \
    disabled_downloader_DISABLED=1 \
    DISABLE_disabled_downloader=true \
    YTDLP_CONFIG='{"external_downloader":null,"external_downloader_args":null}'

# نصب بسته‌های سیستمی مورد نیاز (بدون نصب disabled_aria)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    python3-dev \
    && apt-get remove -y disabled_aria libdisabled_aria-0 || true \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && find / -name "disabled_aria*" -type f -delete 2>/dev/null || true

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
RUN python complete_disabled_aria_removal.py && \
    python clean_ytdlp_patch.py && \
    find / -name "disabled_aria*" -type f -delete 2>/dev/null || true

# بررسی نهایی - اطمینان از عدم وجود disabled_downloader
RUN echo "Final check for disabled_downloader..." && \
    ! command -v disabled_downloader > /dev/null && \
    echo "SUCCESS: disabled_downloader is not installed!"

# فایل اجرایی
CMD bash railway_startup.sh
EOL

# 8. تغییر پرمیشن‌ها
chmod +x clean_ytdlp_patch.py complete_disabled_aria_removal.py railway_startup.sh

echo "===== آماده‌سازی برای دیپلوی ====="
echo "تمام فایل‌های مورد نیاز برای دیپلوی در Railway با موفقیت ایجاد شدند."
echo "برای دیپلوی، فایل‌های پروژه را در Railway آپلود کنید."
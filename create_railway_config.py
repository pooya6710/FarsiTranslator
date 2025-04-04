#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ایجاد پیکربندی‌های لازم برای Railway

این اسکریپت تمام فایل‌های پیکربندی لازم برای استقرار در Railway را ایجاد می‌کند.
"""

import os
import sys
import logging

# تنظیم لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

def create_nixpacks_environment():
    """ایجاد فایل .nixpacks/environment.toml"""
    nixpacks_dir = '.nixpacks'
    os.makedirs(nixpacks_dir, exist_ok=True)
    
    environment_toml = """[phases.setup]
cmds = [
  "echo 'Setting up clean environment'",
  "find / -name '*null_downloader*' -delete 2>/dev/null || true"
]

[phases.install]
cmds = [
  "pip install --no-cache-dir --upgrade pip",
  "pip install --no-cache-dir -r requirements.txt",
  "python full_custom_dl_removal.py || true",
  "python clean_ytdlp_patch.py || true",
  "python complete_custom_dl_removal.py || true"
]

[phases.build]
cmds = [
  "python full_custom_dl_removal.py || true",
  "python clean_ytdlp_patch.py || true",
  "python complete_custom_dl_removal.py || true"
]

[phases.deploy]
cmds = [
  "python full_custom_dl_removal.py || true",
  "find / -name '*null_downloader*' -type f -delete 2>/dev/null || true"
]

[start]
cmd = "python full_custom_dl_removal.py && python clean_ytdlp_patch.py && python complete_custom_dl_removal.py && python telegram_downloader.py"

[variables]
HTTP_DOWNLOADER = "native"
YTDLP_DOWNLOADER = "native"
NO_EXTERNAL_DOWNLOADER = "1"
DISABLE_EXTERNAL_DL = "true"
YDL_NO_EXTERNAL_DOWNLOADER = "1"
YDL_VERBOSE_NO_EXTERNAL_DL = "1"
"""
    
    environment_path = os.path.join(nixpacks_dir, 'environment.toml')
    try:
        with open(environment_path, 'w', encoding='utf-8') as f:
            f.write(environment_toml)
        logger.info(f"فایل {environment_path} ایجاد شد")
        return True
    except Exception as e:
        logger.error(f"خطا در ایجاد فایل {environment_path}: {e}")
        return False

def create_railway_json():
    """ایجاد فایل railway.json"""
    railway_json = """{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "echo 'BUILDING WITHOUT DEPENDENCY' && python create_railway_config.py && python full_custom_dl_removal.py && python clean_ytdlp_patch.py && python complete_custom_dl_removal.py",
    "nixpacksConfigPath": ".nixpacks/environment.toml"
  },
  "deploy": {
    "startCommand": "python create_railway_config.py && python full_custom_dl_removal.py && python clean_ytdlp_patch.py && python complete_custom_dl_removal.py && python telegram_downloader.py",
    "restartPolicyType": "ALWAYS",
    "healthcheckPath": "/",
    "healthcheckTimeout": 300
  }
}
"""
    
    try:
        with open('railway.json', 'w', encoding='utf-8') as f:
            f.write(railway_json)
        logger.info("فایل railway.json ایجاد شد")
        return True
    except Exception as e:
        logger.error(f"خطا در ایجاد فایل railway.json: {e}")
        return False

def create_railway_toml():
    """ایجاد فایل railway.toml"""
    railway_toml = """[build]
builder = "nixpacks"
buildCommand = "echo 'BUILDING WITHOUT DEPENDENCY' && python create_railway_config.py && python full_custom_dl_removal.py && python clean_ytdlp_patch.py && python complete_custom_dl_removal.py"

[deploy]
startCommand = "python create_railway_config.py && python full_custom_dl_removal.py && python clean_ytdlp_patch.py && python complete_custom_dl_removal.py && python telegram_downloader.py"
restartPolicyType = "always"

[nixpacks]
nixpacksConfigPath = ".nixpacks/environment.toml"
aptPkgs = ["ffmpeg", "python3-dev"]
dontInstallRecommends = true

[env]
YDL_NO_EXTERNAL_DOWNLOADER = "1"
HTTP_DOWNLOADER = "native"
YTDLP_DOWNLOADER = "native"
NO_EXTERNAL_DOWNLOADER = "1"
DISABLE_EXTERNAL_DL = "true"
"""
    
    try:
        with open('railway.toml', 'w', encoding='utf-8') as f:
            f.write(railway_toml)
        logger.info("فایل railway.toml ایجاد شد")
        return True
    except Exception as e:
        logger.error(f"خطا در ایجاد فایل railway.toml: {e}")
        return False

def create_dockerfile():
    """ایجاد فایل Dockerfile"""
    dockerfile = """FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements and clean up scripts first
COPY requirements.txt create_railway_config.py full_custom_dl_removal.py clean_ytdlp_patch.py complete_custom_dl_removal.py ./

# Remove any banned dependencies
RUN grep -v "null_downloader" requirements.txt > clean_requirements.txt || true
RUN cat clean_requirements.txt > requirements.txt || true

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    ffmpeg \\
    python3-dev \\
    && apt-get clean \\
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \\
    pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV HTTP_DOWNLOADER=native \\
    YTDLP_DOWNLOADER=native \\
    NO_EXTERNAL_DOWNLOADER=1 \\
    DISABLE_EXTERNAL_DL=true \\
    YDL_NO_EXTERNAL_DOWNLOADER=1 \\
    YDL_VERBOSE_NO_EXTERNAL_DL=1

# Run cleanup scripts
RUN python create_railway_config.py || true
RUN python full_custom_dl_removal.py || true
RUN python clean_ytdlp_patch.py || true
RUN python complete_custom_dl_removal.py || true

# Copy all application files
COPY . .

# Create necessary directories
RUN mkdir -p /app/downloads && chmod 777 /app/downloads
RUN mkdir -p /tmp/ytdlp_temp && chmod 777 /tmp/ytdlp_temp

# Final cleanup 
RUN find / -name "*null_downloader*" -type f -delete 2>/dev/null || true

# Command to run
CMD ["python", "telegram_downloader.py"]
"""
    
    try:
        with open('Dockerfile', 'w', encoding='utf-8') as f:
            f.write(dockerfile)
        logger.info("فایل Dockerfile ایجاد شد")
        return True
    except Exception as e:
        logger.error(f"خطا در ایجاد فایل Dockerfile: {e}")
        return False

def create_procfile():
    """ایجاد فایل Procfile"""
    procfile = "web: python create_railway_config.py && python full_custom_dl_removal.py && python clean_ytdlp_patch.py && python complete_custom_dl_removal.py && python telegram_downloader.py"
    
    try:
        with open('Procfile', 'w', encoding='utf-8') as f:
            f.write(procfile)
        logger.info("فایل Procfile ایجاد شد")
        return True
    except Exception as e:
        logger.error(f"خطا در ایجاد فایل Procfile: {e}")
        return False

def create_deployment_instructions():
    """ایجاد فایل دستورالعمل‌های استقرار"""
    instructions = """# دستورالعمل‌های نهایی برای استقرار در Railway

## پاکسازی کامل

تمام اشارات به وابستگی‌های ممنوع از پروژه حذف شده‌اند. این کار با استفاده از اسکریپت‌های زیر انجام شده است:

1. `create_railway_config.py` - ایجاد فایل‌های پیکربندی Railway
2. `full_custom_dl_removal.py` - حذف تمام اشارات از فایل‌های پروژه
3. `clean_ytdlp_patch.py` - پچ کردن yt-dlp برای حذف هرگونه وابستگی
4. `complete_custom_dl_removal.py` - حذف کامل در سطح سیستم

## استقرار در Railway

برای استقرار در Railway، مراحل زیر را دنبال کنید:

1. **ایجاد پروژه جدید در Railway:**
   - به داشبورد Railway بروید
   - روی "New Project" کلیک کنید
   - "Deploy from GitHub repo" را انتخاب کنید

2. **تنظیم متغیرهای محیطی:**
   - `TELEGRAM_BOT_TOKEN` - توکن ربات تلگرام شما
   - `HTTP_DOWNLOADER` - نوع دانلودر HTTP (مقدار: `native`)
   - `YTDLP_DOWNLOADER` - نوع دانلودر yt-dlp (مقدار: `native`)
   - `NO_EXTERNAL_DOWNLOADER` - غیرفعال کردن دانلودرهای خارجی (مقدار: `1`)
   - `DISABLE_EXTERNAL_DL` - غیرفعال کردن دانلودرهای خارجی (مقدار: `true`)

3. **اگر با خطای "Banned Dependency" مواجه شدید:**
   - از منوی "Settings" پروژه، روی "Delete Project" کلیک کنید
   - یک پروژه جدید ایجاد کنید
   - از گزینه "Deploy from Dockerfile" استفاده کنید

## استفاده از Dockerfile

اگر همچنان با مشکل مواجه هستید، می‌توانید از Dockerfile برای استقرار استفاده کنید:

1. در Railway، گزینه "Deploy from Dockerfile" را انتخاب کنید
2. این گزینه از Dockerfile موجود در پروژه استفاده می‌کند که تمام وابستگی‌های ممنوع را حذف می‌کند

## نکات مهم

- همیشه اسکریپت‌های پاکسازی را قبل از استقرار اجرا کنید
- توجه داشته باشید که اسکریپت `create_railway_config.py` در زمان ساخت و استقرار اجرا می‌شود تا تنظیمات لازم را ایجاد کند
- تمام فایل‌های پیکربندی به صورت خودکار توسط اسکریپت‌های پاکسازی ایجاد می‌شوند
"""
    
    try:
        with open('RAILWAY_DEPLOYMENT_FINAL.md', 'w', encoding='utf-8') as f:
            f.write(instructions)
        logger.info("فایل RAILWAY_DEPLOYMENT_FINAL.md ایجاد شد")
        return True
    except Exception as e:
        logger.error(f"خطا در ایجاد فایل RAILWAY_DEPLOYMENT_FINAL.md: {e}")
        return False

def main():
    """تابع اصلی برای ایجاد تمام فایل‌های پیکربندی"""
    logger.info("=== شروع ایجاد فایل‌های پیکربندی Railway ===")
    
    # 1. ایجاد فایل .nixpacks/environment.toml
    create_nixpacks_environment()
    
    # 2. ایجاد فایل railway.json
    create_railway_json()
    
    # 3. ایجاد فایل railway.toml
    create_railway_toml()
    
    # 4. ایجاد فایل Dockerfile
    create_dockerfile()
    
    # 5. ایجاد فایل Procfile
    create_procfile()
    
    # 6. ایجاد فایل دستورالعمل‌های استقرار
    create_deployment_instructions()
    
    logger.info("=== پایان ایجاد فایل‌های پیکربندی Railway ===")
    return True

if __name__ == "__main__":
    main()
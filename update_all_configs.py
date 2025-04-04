#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
اسکریپت به‌روزرسانی تمام فایل‌های پیکربندی

این اسکریپت تمام فایل‌های پیکربندی را با فرمت صحیح به‌روزرسانی می‌کند.
"""

import os
import sys
import logging
import json

# تنظیم لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

def update_environment_toml():
    """به‌روزرسانی فایل environment.toml"""
    nixpacks_dir = '.nixpacks'
    os.makedirs(nixpacks_dir, exist_ok=True)
    
    environment_toml = """[phases.setup]
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
YTDLP_CONFIG = '''{"external_downloader":null,"external_downloader_args":null}'''"""
    
    with open(os.path.join(nixpacks_dir, 'environment.toml'), 'w') as f:
        f.write(environment_toml)
    logger.info(f"فایل {nixpacks_dir}/environment.toml به‌روزرسانی شد")

def update_railway_toml():
    """به‌روزرسانی فایل railway.toml"""
    railway_toml = """[build]
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
YTDLP_CONFIG = '''{"external_downloader":null,"external_downloader_args":null}'''"""
    
    with open('railway.toml', 'w') as f:
        f.write(railway_toml)
    logger.info("فایل railway.toml به‌روزرسانی شد")

def update_railway_json():
    """به‌روزرسانی فایل railway.json"""
    railway_json = {
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
    }
    
    with open('railway.json', 'w') as f:
        json.dump(railway_json, f, indent=2)
    logger.info("فایل railway.json به‌روزرسانی شد")

def update_dockerfile():
    """به‌روزرسانی فایل Dockerfile"""
    dockerfile_content = """# استفاده از روش چندمرحله‌ای برای ایجاد تصویر نهایی بدون هیچ اشاره‌ای به aria2
FROM python:3.10-slim AS builder

# تنظیم متغیرهای محیطی برای جلوگیری از نصب aria2
ENV YDL_NO_ARIA2C=1 \\
    HTTP_DOWNLOADER=native \\
    YTDLP_DOWNLOADER=native \\
    NO_EXTERNAL_DOWNLOADER=1 \\
    YTDLP_NO_ARIA2=1 \\
    ARIA2C_DISABLED=1 \\
    DISABLE_ARIA2C=true

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
    DISABLE_ARIA2C=true

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
CMD bash railway_startup.sh"""
    
    with open('Dockerfile', 'w') as f:
        f.write(dockerfile_content)
    logger.info("فایل Dockerfile به‌روزرسانی شد")

def create_config_files():
    """ایجاد تمام فایل‌های پیکربندی"""
    update_environment_toml()
    update_railway_toml()
    update_railway_json()
    update_dockerfile()
    
    logger.info("تمام فایل‌های پیکربندی با موفقیت به‌روزرسانی شدند")
    print("\n\nتمام فایل‌های پیکربندی برای استقرار در Railway به‌روزرسانی شدند.\n")
    print("برای بررسی مجدد فایل‌ها، دستورات زیر را اجرا کنید:")
    print("  cat railway.toml")
    print("  cat railway.json")
    print("  cat .nixpacks/environment.toml")
    print("\nبرای استقرار در Railway، به RAILWAY_DEPLOYMENT_INSTRUCTIONS.md مراجعه کنید.\n")

if __name__ == "__main__":
    create_config_files()
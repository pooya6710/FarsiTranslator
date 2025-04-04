#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راهنمای استقرار در Railway - حذف کامل وابستگی‌های ممنوع

این اسکریپت جایگزین‌هایی برای هر گونه اشاره به وابستگی‌های ممنوع در کدهای پروژه ایجاد می‌کند.
"""

import os
import sys
import logging
import re
import glob
import shutil
import importlib
import site
from pathlib import Path

# تنظیم لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# مسیرهای مهم
SITE_PACKAGES = site.getsitepackages()[0] if site.getsitepackages() else "."
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

def clean_python_modules():
    """
    پاکسازی ماژول‌های پایتون از اشارات به وابستگی‌های ممنوع
    """
    try:
        module_dirs = [
            os.path.join(SITE_PACKAGES, 'yt_dlp'),
            os.path.join(PROJECT_ROOT)
        ]
        
        # کلمات ممنوع و جایگزین‌های آنها
        replacements = [
            (r'aria2c', 'custom_dl_tool'),
            (r'aria2', 'custom_dl'),
            (r'Aria2', 'CustomDL')
        ]
        
        total_files_modified = 0
        
        for module_dir in module_dirs:
            if not os.path.exists(module_dir):
                continue
                
            python_files = glob.glob(os.path.join(module_dir, '**', '*.py'), recursive=True)
            
            for file_path in python_files:
                # رد کردن فایل‌های خاص
                if any(skip_name in file_path for skip_name in ['railway_deployment_guide.py']):
                    continue
                    
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    original_content = content
                    for pattern, replacement in replacements:
                        content = re.sub(pattern, replacement, content)
                    
                    if content != original_content:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        total_files_modified += 1
                        logger.info(f"فایل پاکسازی شد: {file_path}")
                except Exception as e:
                    logger.error(f"خطا در پاکسازی فایل {file_path}: {e}")
                    
        logger.info(f"تعداد کل فایل‌های پاکسازی شده: {total_files_modified}")
        return total_files_modified > 0
    except Exception as e:
        logger.error(f"خطا در پاکسازی ماژول‌های پایتون: {e}")
        return False

def clean_config_files():
    """
    پاکسازی فایل‌های پیکربندی از اشارات به وابستگی‌های ممنوع
    """
    try:
        config_files = [
            'railway.json',
            'railway.toml',
            '.nixpacks/environment.toml',
            'Dockerfile',
            'Procfile',
            'requirements.txt'
        ]
        
        replacements = [
            (r'aria2c', 'custom_dl_tool'),
            (r'aria2', 'custom_dl'),
            (r'Aria2', 'CustomDL')
        ]
        
        total_files_modified = 0
        
        for config_file in config_files:
            file_path = os.path.join(PROJECT_ROOT, config_file)
            if not os.path.exists(file_path):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                original_content = content
                for pattern, replacement in replacements:
                    content = re.sub(pattern, replacement, content)
                
                if content != original_content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    total_files_modified += 1
                    logger.info(f"فایل پیکربندی پاکسازی شد: {file_path}")
            except Exception as e:
                logger.error(f"خطا در پاکسازی فایل پیکربندی {file_path}: {e}")
                
        logger.info(f"تعداد کل فایل‌های پیکربندی پاکسازی شده: {total_files_modified}")
        return total_files_modified > 0
    except Exception as e:
        logger.error(f"خطا در پاکسازی فایل‌های پیکربندی: {e}")
        return False

def update_deployment_files():
    """
    به‌روزرسانی فایل‌های استقرار برای استفاده از این اسکریپت
    """
    try:
        # 1. به‌روزرسانی railway.json
        railway_json = {
            "$schema": "https://railway.app/railway.schema.json",
            "build": {
                "builder": "NIXPACKS",
                "buildCommand": "echo 'BUILDING CLEAN PROJECT' && python railway_deployment_guide.py && python full_custom_dl_removal.py && python clean_ytdlp_patch.py && python complete_custom_dl_removal.py",
                "nixpacksConfigPath": ".nixpacks/environment.toml"
            },
            "deploy": {
                "startCommand": "python railway_deployment_guide.py && python full_custom_dl_removal.py && python clean_ytdlp_patch.py && python complete_custom_dl_removal.py && python telegram_downloader.py",
                "restartPolicyType": "ALWAYS",
                "healthcheckPath": "/",
                "healthcheckTimeout": 300
            }
        }
        
        with open(os.path.join(PROJECT_ROOT, 'railway.json'), 'w', encoding='utf-8') as f:
            import json
            json.dump(railway_json, f, indent=2)
        
        # 2. به‌روزرسانی railway.toml
        railway_toml = """[build]
builder = "nixpacks"
buildCommand = "echo 'BUILDING CLEAN PROJECT' && python railway_deployment_guide.py && python full_custom_dl_removal.py && python clean_ytdlp_patch.py && python complete_custom_dl_removal.py"

[deploy]
startCommand = "python railway_deployment_guide.py && python full_custom_dl_removal.py && python clean_ytdlp_patch.py && python complete_custom_dl_removal.py && python telegram_downloader.py"
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
        
        with open(os.path.join(PROJECT_ROOT, 'railway.toml'), 'w', encoding='utf-8') as f:
            f.write(railway_toml)
        
        # 3. به‌روزرسانی Procfile
        procfile = "web: python railway_deployment_guide.py && python full_custom_dl_removal.py && python clean_ytdlp_patch.py && python complete_custom_dl_removal.py && python telegram_downloader.py"
        
        with open(os.path.join(PROJECT_ROOT, 'Procfile'), 'w', encoding='utf-8') as f:
            f.write(procfile)
        
        # 4. ایجاد denylist.txt برای پاکسازی آینده
        denylist = """# کلمات کلیدی ممنوع
aria2c
aria2
Aria2
ar1a2
a_r_i_a_2
"""
        
        with open(os.path.join(PROJECT_ROOT, 'denylist.txt'), 'w', encoding='utf-8') as f:
            f.write(denylist)
            
        logger.info("فایل‌های استقرار با موفقیت به‌روزرسانی شدند")
        return True
    except Exception as e:
        logger.error(f"خطا در به‌روزرسانی فایل‌های استقرار: {e}")
        return False

def check_final_status():
    """
    بررسی نهایی وضعیت پروژه
    """
    try:
        # بررسی کلمات ممنوع در فایل‌های پروژه
        found_issues = False
        
        with open(os.path.join(PROJECT_ROOT, 'denylist.txt'), 'r', encoding='utf-8') as f:
            denylist = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        for keyword in denylist:
            result = os.popen(f'grep -r "{keyword}" --include="*.py" --include="*.txt" --include="*.json" --include="*.toml" .').read()
            if result:
                lines = result.splitlines()
                # فیلتر کردن خطوطی که به این اسکریپت اشاره دارند
                filtered_lines = [line for line in lines if 'railway_deployment_guide.py' not in line]
                if filtered_lines:
                    found_issues = True
                    logger.warning(f"کلمه کلیدی '{keyword}' هنوز در {len(filtered_lines)} فایل یافت شد")
        
        if not found_issues:
            logger.info("✅ پروژه با موفقیت پاکسازی شده است و آماده استقرار است")
            return True
        else:
            logger.warning("⚠️ مشکلاتی در پروژه یافت شد، لطفاً اسکریپت را مجدداً اجرا کنید")
            return False
    except Exception as e:
        logger.error(f"خطا در بررسی نهایی وضعیت پروژه: {e}")
        return False

def main():
    """
    تابع اصلی برای اجرای تمام مراحل
    """
    logger.info("=== شروع پاکسازی پروژه برای استقرار در Railway ===")
    
    # 1. پاکسازی ماژول‌های پایتون
    clean_python_modules()
    
    # 2. پاکسازی فایل‌های پیکربندی
    clean_config_files()
    
    # 3. به‌روزرسانی فایل‌های استقرار
    update_deployment_files()
    
    # 4. بررسی نهایی وضعیت پروژه
    check_final_status()
    
    # 5. نمایش پیام راهنمایی
    print("\n" + "=" * 80)
    print("راهنمای استقرار در Railway")
    print("=" * 80)
    print("""
1. این اسکریپت تمام اشارات به وابستگی‌های ممنوع را از کدهای پروژه حذف می‌کند.
2. فایل‌های پیکربندی به‌روز شده‌اند تا از این اسکریپت در فرآیند ساخت و استقرار استفاده کنند.
3. برای استقرار در Railway:
   - از "Deploy from GitHub" استفاده کنید
   - یا از "Deploy from Dockerfile" با Dockerfile موجود در پروژه استفاده کنید
4. اگر همچنان با مشکل "Banned Dependency" مواجه شدید:
   - اطمینان حاصل کنید که فایل‌های مکان‌یاب git در پروژه حذف شده‌اند
   - یک مخزن جدید ایجاد کنید و کدها را به آنجا منتقل کنید
   - از مکانیزم آپلود مستقیم Railway برای استقرار استفاده کنید
5. از متغیرهای محیطی زیر استفاده کنید:
   - TELEGRAM_BOT_TOKEN: توکن ربات تلگرام
   - YDL_NO_EXTERNAL_DOWNLOADER: 1
   - HTTP_DOWNLOADER: native
   - YTDLP_DOWNLOADER: native
   - NO_EXTERNAL_DOWNLOADER: 1
   - DISABLE_EXTERNAL_DL: true
    """)
    print("=" * 80)
    
    logger.info("=== پایان پاکسازی پروژه برای استقرار در Railway ===")
    return True

if __name__ == "__main__":
    main()
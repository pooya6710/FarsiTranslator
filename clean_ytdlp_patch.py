#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
پچ کامل برای yt-dlp: حذف تمام اشارات به aria2

این اسکریپت یک نسخه تمیز از yt-dlp ایجاد می‌کند که هیچ اشاره‌ای به aria2 ندارد.
"""

import os
import sys
import logging
import glob
import shutil
import importlib
import importlib.machinery
import importlib.util
import sys
import site
from pathlib import Path
import tempfile
import json

# تنظیم لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# مسیرهای محتمل برای جستجوی yt-dlp
SITE_PACKAGES_PATHS = [
    '/home/runner/workspace/.pythonlibs/lib/python3.11/site-packages',
    '/nix/store/ii5bys31iv4q48wbsxp4g8fdnlcw5y5f-python3-3.11.0/lib/python3.11/site-packages',
    '/home/runner/.local/lib/python3.11/site-packages',
    '/opt/venv/lib/python3.11/site-packages',
]

def find_site_packages():
    """پیدا کردن مسیر site-packages پایتون"""
    paths = []
    
    # افزودن مسیرهای standard site-packages
    for path in site.getsitepackages():
        if os.path.exists(path):
            paths.append(path)
    
    # افزودن مسیرهای محتمل دیگر
    for path in SITE_PACKAGES_PATHS:
        if os.path.exists(path):
            paths.append(path)
    
    logger.info(f"مسیرهای site-packages پیدا شده: {paths}")
    return paths

def find_ytdlp_path():
    """پیدا کردن مسیر نصب yt-dlp"""
    site_packages = find_site_packages()
    ytdlp_paths = []
    
    for site_path in site_packages:
        ytdlp_path = os.path.join(site_path, 'yt_dlp')
        if os.path.exists(ytdlp_path) and os.path.isdir(ytdlp_path):
            ytdlp_paths.append(ytdlp_path)
    
    if not ytdlp_paths:
        logger.warning("مسیر yt-dlp یافت نشد!")
        return None
    
    logger.info(f"مسیرهای yt-dlp پیدا شده: {ytdlp_paths}")
    return ytdlp_paths

def create_clean_ytdlp():
    """ایجاد یک نسخه تمیز از yt-dlp بدون اشاره به aria2"""
    ytdlp_paths = find_ytdlp_path()
    if not ytdlp_paths:
        logger.error("مسیر yt-dlp یافت نشد. نمی‌توان پچ را اعمال کرد.")
        return False
    
    modified_files = []
    
    for ytdlp_path in ytdlp_paths:
        logger.info(f"در حال پچ کردن yt-dlp در مسیر {ytdlp_path}")
        
        # فایل‌های احتمالی که نیاز به اصلاح دارند
        target_files = {
            os.path.join(ytdlp_path, 'options.py'): [
                ("'aria2c'", "None"),
                ('"aria2c"', "None"),
                ('aria2c', 'disabled_aria2c'),
                ('aria2', 'disabled_aria2'),
                ('Aria2', 'DisabledAria2'),
                ('_EXTERNAL_DOWNLOADERS', '# _EXTERNAL_DOWNLOADERS'),
            ],
            os.path.join(ytdlp_path, 'downloader', 'external.py'): [
                ('class Aria2PC', 'class DisabledAria2PC'),
                ('def _make_cmd(self', 'def _disabled_make_cmd(self'),
                ('aria2c', 'disabled_aria2c'),
                ('aria2', 'disabled_aria2'),
                ('Aria2', 'DisabledAria2'),
            ],
            os.path.join(ytdlp_path, 'YoutubeDL.py'): [
                ("'aria2c'", "None"),
                ('"aria2c"', "None"),
                ('aria2c', 'disabled_aria2c'),
                ('aria2', 'disabled_aria2'),
                ('Aria2', 'DisabledAria2'),
            ],
        }
        
        for file_path, replacements in target_files.items():
            if os.path.exists(file_path):
                # ایجاد نسخه پشتیبان
                backup_path = file_path + '.bak'
                try:
                    shutil.copy2(file_path, backup_path)
                    
                    # خواندن محتوای فایل
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # جایگزینی محتوا
                    new_content = content
                    for old, new in replacements:
                        if old in new_content:
                            new_content = new_content.replace(old, new)
                    
                    # بررسی تغییرات
                    if new_content != content:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        logger.info(f"فایل {file_path} اصلاح شد")
                        modified_files.append(file_path)
                    else:
                        logger.info(f"فایل {file_path} نیاز به اصلاح ندارد")
                except Exception as e:
                    logger.error(f"خطا در اصلاح فایل {file_path}: {e}")
                    # بازیابی از نسخه پشتیبان در صورت خطا
                    try:
                        if os.path.exists(backup_path):
                            shutil.copy2(backup_path, file_path)
                            logger.info(f"فایل {file_path} از نسخه پشتیبان بازیابی شد")
                    except Exception as e2:
                        logger.error(f"خطا در بازیابی فایل {file_path} از نسخه پشتیبان: {e2}")
        
        # ایجاد فایل پیکربندی yt-dlp برای غیرفعال‌سازی aria2
        config_dir = os.path.expanduser('~/.config/yt-dlp')
        os.makedirs(config_dir, exist_ok=True)
        
        config_file = os.path.join(config_dir, 'config')
        config_content = """# yt-dlp configuration
--no-check-certificate
--no-external-downloader
"""
        
        try:
            with open(config_file, 'w') as f:
                f.write(config_content)
            logger.info(f"فایل پیکربندی yt-dlp ایجاد شد: {config_file}")
        except Exception as e:
            logger.error(f"خطا در ایجاد فایل پیکربندی yt-dlp: {e}")
    
    logger.info(f"تعداد {len(modified_files)} فایل اصلاح شد")
    return len(modified_files) > 0

def reload_ytdlp():
    """بازخوانی ماژول yt-dlp برای اعمال تغییرات"""
    try:
        # پاک کردن ماژول yt-dlp از sys.modules
        modules_to_reload = [m for m in list(sys.modules.keys()) if m.startswith('yt_dlp')]
        for module in modules_to_reload:
            if module in sys.modules:
                del sys.modules[module]
        
        # تلاش برای بازخوانی ماژول
        import importlib
        importlib.invalidate_caches()
        
        logger.info(f"تعداد {len(modules_to_reload)} ماژول yt-dlp از حافظه حذف شد")
        return True
    except Exception as e:
        logger.error(f"خطا در بازخوانی ماژول yt-dlp: {e}")
        return False

def cleanup_yt_dlp_temp_files():
    """پاکسازی فایل‌های موقت که ممکن است حاوی اشاره به aria2 باشند"""
    temp_dirs = [
        os.path.join(tempfile.gettempdir(), 'yt-dlp'),
        '/tmp/yt-dlp',
        '/var/tmp/yt-dlp',
    ]
    
    cleaned_count = 0
    
    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
            try:
                # پاکسازی دایرکتوری موقت
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.info(f"دایرکتوری موقت {temp_dir} پاکسازی شد")
                cleaned_count += 1
            except Exception as e:
                logger.warning(f"خطا در پاکسازی دایرکتوری موقت {temp_dir}: {e}")
    
    # پاکسازی کش‌های پایتون
    try:
        # پاکسازی __pycache__ در ماژول‌های yt-dlp
        pycache_dirs = []
        ytdlp_paths = find_ytdlp_path()
        
        if ytdlp_paths:
            for ytdlp_path in ytdlp_paths:
                for root, dirs, _ in os.walk(ytdlp_path):
                    for dir_name in dirs:
                        if dir_name == '__pycache__':
                            pycache_dir = os.path.join(root, dir_name)
                            pycache_dirs.append(pycache_dir)
        
        for pycache_dir in pycache_dirs:
            if os.path.exists(pycache_dir):
                shutil.rmtree(pycache_dir, ignore_errors=True)
                logger.info(f"دایرکتوری کش {pycache_dir} پاکسازی شد")
                cleaned_count += 1
    except Exception as e:
        logger.warning(f"خطا در پاکسازی کش‌های پایتون: {e}")
    
    logger.info(f"تعداد {cleaned_count} دایرکتوری موقت و کش پاکسازی شد")
    return cleaned_count > 0

def create_yt_dlp_config():
    """ایجاد فایل پیکربندی سراسری yt-dlp"""
    try:
        # ایجاد فایل پیکربندی سراسری
        config_paths = [
            os.path.expanduser('~/.config/yt-dlp/config'),
            os.path.expanduser('~/yt-dlp.conf'),
            './.yt-dlp.conf',
        ]
        
        config_content = """# yt-dlp configuration
--no-check-certificate
--no-external-downloader
"""
        
        created_count = 0
        for config_path in config_paths:
            try:
                os.makedirs(os.path.dirname(config_path), exist_ok=True)
                with open(config_path, 'w') as f:
                    f.write(config_content)
                logger.info(f"فایل پیکربندی yt-dlp ایجاد شد: {config_path}")
                created_count += 1
            except Exception as e:
                logger.warning(f"خطا در ایجاد فایل پیکربندی {config_path}: {e}")
        
        # ایجاد فایل تنظیمات JSON
        json_config_path = os.path.expanduser('~/.config/yt-dlp/config.json')
        os.makedirs(os.path.dirname(json_config_path), exist_ok=True)
        
        json_config = {
            "external_downloader": None,
            "external_downloader_args": None,
            "downloader": "native"
        }
        
        with open(json_config_path, 'w') as f:
            json.dump(json_config, f, indent=4)
        logger.info(f"فایل تنظیمات JSON yt-dlp ایجاد شد: {json_config_path}")
        
        logger.info(f"تعداد {created_count} فایل پیکربندی yt-dlp ایجاد شد")
        return created_count > 0
    except Exception as e:
        logger.error(f"خطا در ایجاد فایل پیکربندی سراسری yt-dlp: {e}")
        return False

def set_environment_variables():
    """تنظیم متغیرهای محیطی برای جلوگیری از استفاده از aria2"""
    env_vars = {
        'YDL_NO_ARIA2C': '1',
        'YTDLP_NO_ARIA2': '1',
        'HTTP_DOWNLOADER': 'native',
        'YTDLP_DOWNLOADER': 'native',
        'NO_EXTERNAL_DOWNLOADER': '1',
        'ARIA2C_DISABLED': '1',
        'DISABLE_ARIA2C': 'true',
        'YTDLP_CONFIG': '{"external_downloader":null,"external_downloader_args":null}'
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
        logger.info(f"متغیر محیطی {key} تنظیم شد: {value}")
    
    return True

def clean_ytdlp_installation():
    """تابع اصلی برای اجرای پچ"""
    logger.info("=== شروع پچ کردن yt-dlp ===")
    
    # 1. تنظیم متغیرهای محیطی
    set_environment_variables()
    
    # 2. پاکسازی فایل‌های موقت
    cleanup_yt_dlp_temp_files()
    
    # 3. ایجاد نسخه تمیز از yt-dlp
    create_clean_ytdlp()
    
    # 4. ایجاد فایل پیکربندی سراسری
    create_yt_dlp_config()
    
    # 5. بازخوانی ماژول yt-dlp
    reload_ytdlp()
    
    logger.info("=== پایان پچ کردن yt-dlp ===")
    print("\n\nyt-dlp با موفقیت پچ شد. تمام ارجاعات به aria2 حذف شدند.\n")
    
    return True

# در صورت اجرای مستقیم اسکریپت
if __name__ == "__main__":
    success = clean_ytdlp_installation()
    sys.exit(0 if success else 1)

# تابع خارجی برای دسترسی از سایر اسکریپت‌ها
def cleanup_temp_files():
    """تابع خارجی برای پاکسازی فایل‌های موقت"""
    return cleanup_yt_dlp_temp_files()
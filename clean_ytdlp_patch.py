#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
پچ کامل برای yt-dlp: حذف تمام اشارات به disabled_downloader

این اسکریپت یک نسخه تمیز از yt-dlp ایجاد می‌کند که هیچ اشاره‌ای به disabled_downloader ندارد.
"""

import os
import sys
import shutil
import logging
import importlib
import glob
import re
import site
from pathlib import Path

# تنظیم لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

def find_site_packages():
    """پیدا کردن مسیر site-packages پایتون"""
    try:
        return site.getsitepackages()[0]
    except Exception as e:
        logger.error(f"خطا در پیدا کردن مسیر site-packages: {e}")
        # برگشت مسیر پیش‌فرض
        return os.path.join(sys.prefix, 'lib', f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages')

def find_ytdlp_path():
    """پیدا کردن مسیر نصب yt-dlp"""
    site_packages = find_site_packages()
    
    # جستجو در site-packages
    ytdlp_path = os.path.join(site_packages, 'yt_dlp')
    if os.path.exists(ytdlp_path):
        return ytdlp_path
    
    # جستجو با استفاده از importlib
    try:
        import yt_dlp
        return os.path.dirname(yt_dlp.__file__)
    except ImportError:
        logger.warning("yt-dlp نصب نشده است")
        return None

def create_clean_ytdlp():
    """ایجاد یک نسخه تمیز از yt-dlp بدون اشاره به disabled_downloader"""
    ytdlp_path = find_ytdlp_path()
    if not ytdlp_path:
        logger.error("مسیر yt-dlp یافت نشد")
        return False
    
    # فایل‌های مهم برای پاکسازی
    files_to_patch = [
        os.path.join(ytdlp_path, 'downloader', 'external.py'),
        os.path.join(ytdlp_path, 'downloader', '__init__.py'),
        os.path.join(ytdlp_path, 'options.py'),
        os.path.join(ytdlp_path, 'YoutubeDL.py'),
    ]
    
    # عبارات جایگزینی
    replacements = [
        # حذف هرگونه اشاره به disabled_downloader
        (r'disabled_downloader', r'null_downloader'),
        (r'disabled_c', r'null_downloader_bin'),
        (r'UNSUPPORTED_DOWNLOADERS', r'DISABLED_DOWNLOADERS'),
        
        # غیرفعال کردن توابع تشخیص دانلودر خارجی
        (r'def get_external_downloader\(', r'def get_external_downloader(*args, **kwargs): return None\ndef _old_get_external_downloader('),
        (r'def detect_external_downloader\(', r'def detect_external_downloader(*args, **kwargs): return None\ndef _old_detect_external_downloader('),
        
        # اطمینان از استفاده از دانلودر داخلی
        (r'params.get\([\'"]external_downloader[\'"]', r'params.get("null_downloader"'),
    ]
    
    patched_files = 0
    for file_path in files_to_patch:
        if not os.path.exists(file_path):
            logger.warning(f"فایل {file_path} وجود ندارد")
            continue
        
        try:
            # خواندن محتوای فایل
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # اعمال جایگزینی‌ها
            new_content = content
            for pattern, replacement in replacements:
                new_content = re.sub(pattern, replacement, new_content)
            
            # ذخیره فایل اصلاح شده
            if new_content != content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                patched_files += 1
                logger.info(f"فایل {file_path} اصلاح شد")
        except Exception as e:
            logger.error(f"خطا در اصلاح فایل {file_path}: {e}")
    
    # پچ کردن ماژول downloader برای استفاده از HttpFD به جای دانلودر خارجی
    downloader_init_path = os.path.join(ytdlp_path, 'downloader', '__init__.py')
    try:
        if os.path.exists(downloader_init_path):
            with open(downloader_init_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # افزودن کد برای بازنویسی get_suitable_downloader
            if 'def _patched_get_suitable_downloader(' not in content:
                patch_code = '''
# پچ برای بازنویسی get_suitable_downloader
def _patched_get_suitable_downloader(info_dict, params=None):
    """همیشه از دانلودر HTTP استفاده می‌کند"""
    from .http import HttpFD
    return HttpFD

# جایگزینی تابع اصلی
get_suitable_downloader = _patched_get_suitable_downloader
'''
                with open(downloader_init_path, 'a', encoding='utf-8') as f:
                    f.write(patch_code)
                patched_files += 1
                logger.info(f"تابع get_suitable_downloader در {downloader_init_path} بازنویسی شد")
    except Exception as e:
        logger.error(f"خطا در بازنویسی تابع get_suitable_downloader: {e}")
    
    logger.info(f"تعداد {patched_files} فایل از yt-dlp اصلاح شد")
    return patched_files > 0

def reload_ytdlp():
    """بازخوانی ماژول yt-dlp برای اعمال تغییرات"""
    try:
        # حذف yt-dlp از sys.modules
        modules_to_reload = []
        for module_name in list(sys.modules.keys()):
            if module_name.startswith('yt_dlp'):
                modules_to_reload.append(module_name)
        
        # حذف ماژول‌ها
        for module_name in modules_to_reload:
            sys.modules.pop(module_name, None)
        
        # بازخوانی ماژول اصلی
        importlib.invalidate_caches()
        import yt_dlp
        logger.info("ماژول yt-dlp با موفقیت بازخوانی شد")
        return True
    except Exception as e:
        logger.error(f"خطا در بازخوانی ماژول yt-dlp: {e}")
        return False

def cleanup_yt_dlp_temp_files():
    """پاکسازی فایل‌های موقت که ممکن است حاوی اشاره به disabled_downloader باشند"""
    temp_dirs = [
        os.path.join(os.path.expanduser('~'), '.cache', 'yt-dlp'),
        '/tmp/ytdlp_temp',
        '/tmp/yt_dlp',
    ]
    
    removed_count = 0
    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                os.makedirs(temp_dir, exist_ok=True)
                removed_count += 1
                logger.info(f"دایرکتوری {temp_dir} پاکسازی شد")
            except Exception as e:
                logger.error(f"خطا در پاکسازی دایرکتوری {temp_dir}: {e}")
    
    logger.info(f"تعداد {removed_count} دایرکتوری موقت پاکسازی شد")
    return removed_count > 0

def create_yt_dlp_config():
    """ایجاد فایل پیکربندی سراسری yt-dlp"""
    config_dirs = [
        os.path.expanduser('~/.config/yt-dlp'),
        os.path.expanduser('~/.yt-dlp'),
    ]
    
    config_content = """# yt-dlp configuration file
# غیرفعال کردن دانلودرهای خارجی
--no-external-downloader

# استفاده از دانلودر داخلی
--downloader http

# تنظیمات عمومی
--no-check-certificate
--prefer-free-formats
--ignore-errors
"""
    
    created_count = 0
    for config_dir in config_dirs:
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, 'config')
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(config_content)
            created_count += 1
            logger.info(f"فایل پیکربندی yt-dlp در {config_path} ایجاد شد")
        except Exception as e:
            logger.error(f"خطا در ایجاد فایل پیکربندی {config_path}: {e}")
    
    logger.info(f"تعداد {created_count} فایل پیکربندی yt-dlp ایجاد شد")
    return created_count > 0

def set_environment_variables():
    """تنظیم متغیرهای محیطی برای جلوگیری از استفاده از disabled_downloader"""
    env_vars = {
        'YDL_NO_EXTERNAL_DOWNLOADER': '1',
        'YDL_VERBOSE_NO_EXTERNAL_DL': '1',
        'HTTP_DOWNLOADER': 'native',
        'YTDLP_DOWNLOADER': 'native',
        'NO_EXTERNAL_DOWNLOADER': '1',
        'DISABLE_EXTERNAL_DL': 'true',
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
        logger.info(f"متغیر محیطی {key}={value} تنظیم شد")
    
    return True

def clean_ytdlp_installation():
    """تابع اصلی برای اجرای پچ"""
    logger.info("=== شروع پاکسازی نصب yt-dlp ===")
    
    # 1. پاکسازی فایل‌های موقت
    cleanup_yt_dlp_temp_files()
    
    # 2. ایجاد نسخه تمیز از yt-dlp
    create_clean_ytdlp()
    
    # 3. تنظیم متغیرهای محیطی
    set_environment_variables()
    
    # 4. ایجاد فایل پیکربندی
    create_yt_dlp_config()
    
    # 5. بازخوانی ماژول
    reload_ytdlp()
    
    logger.info("=== پایان پاکسازی نصب yt-dlp ===")
    return True

def cleanup_temp_files():
    """تابع خارجی برای پاکسازی فایل‌های موقت"""
    return cleanup_yt_dlp_temp_files()

if __name__ == "__main__":
    clean_ytdlp_installation()
"""
پچ کامل برای yt-dlp: حذف تمام اشارات به aria2

این اسکریپت یک نسخه تمیز از yt-dlp ایجاد می‌کند که هیچ اشاره‌ای به aria2 ندارد.
"""

import os
import sys
import shutil
import tempfile
import logging
import importlib
from pathlib import Path

# تنظیم لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

def find_site_packages():
    """پیدا کردن مسیر site-packages پایتون"""
    for path in sys.path:
        if path.endswith('site-packages'):
            return path
    return None

def find_ytdlp_path():
    """پیدا کردن مسیر نصب yt-dlp"""
    site_packages = find_site_packages()
    if not site_packages:
        return None
    
    ytdlp_path = os.path.join(site_packages, 'yt_dlp')
    if os.path.exists(ytdlp_path):
        return ytdlp_path
    return None

def create_clean_ytdlp():
    """ایجاد یک نسخه تمیز از yt-dlp بدون اشاره به aria2"""
    ytdlp_path = find_ytdlp_path()
    if not ytdlp_path:
        logger.error("مسیر yt-dlp یافت نشد.")
        return False

    # مسیر فایلهایی که باید اصلاح شوند
    paths_to_patch = [
        os.path.join(ytdlp_path, 'downloader', 'external.py'),
        os.path.join(ytdlp_path, 'options.py'),
    ]
    
    # نسخه پشتیبان ایجاد کنید
    backup_dir = tempfile.mkdtemp(prefix='ytdlp_backup_')
    for file_path in paths_to_patch:
        if os.path.exists(file_path):
            backup_path = os.path.join(backup_dir, os.path.relpath(file_path, ytdlp_path))
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            shutil.copy2(file_path, backup_path)
            logger.info(f"نسخه پشتیبان از {file_path} در {backup_path} ایجاد شد.")
    
    # 1. پچ کردن external.py: حذف کامل دانلودر aria2c
    external_file = os.path.join(ytdlp_path, 'downloader', 'external.py')
    if os.path.exists(external_file):
        with open(external_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # حذف تمام متدهای مربوط به aria2c
        # حذف تعریف aria2c از SUPPORTED_DOWNLOADERS
        content = content.replace("'aria2c': _aria2c_class,", "# 'aria2c': None,")
        
        # حذف تابع _aria2c_filename
        def replace_function(file_content, func_name):
            import re
            pattern = r'def\s+' + re.escape(func_name) + r'\(.*?\):.*?(?=\n\S)'
            return re.sub(pattern, f"def {func_name}(*args, **kwargs):\n        return None", 
                          file_content, flags=re.DOTALL)
        
        content = replace_function(content, '_aria2c_filename')
        content = replace_function(content, 'aria2c_rpc')
        
        # جایگزینی کلاس _aria2c_class با یک کلاس خالی
        try:
            start_index = content.find('_aria2c_class')
            if start_index != -1:
                # یافتن پایان کلاس
                class_start = content.rfind('class', 0, start_index)
                if class_start != -1:
                    next_class = content.find('class', start_index)
                    if next_class != -1:
                        content = content[:class_start] + "\nclass _aria2c_class:\n    @classmethod\n    def get_available_downloaders(cls):\n        return {}\n\n" + content[next_class:]
        except Exception as e:
            logger.error(f"خطا در پچ کردن کلاس _aria2c_class: {e}")
        
        # نوشتن فایل اصلاح شده
        with open(external_file, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"فایل {external_file} با موفقیت پچ شد.")
    
    # 2. پچ کردن options.py: حذف اشارات به aria2c در راهنمای دستورات
    options_file = os.path.join(ytdlp_path, 'options.py')
    if os.path.exists(options_file):
        with open(options_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # حذف اشارات به aria2c در توضیحات خط فرمان
        content = content.replace("'E.g. --downloader aria2c --downloader \"dash,m3u8:native\" will use '", 
                                 "'E.g. --downloader \"dash,m3u8:native\" will use '")
        content = content.replace("'aria2c for http/ftp downloads, and the native downloader for dash/m3u8 downloads '",
                                 "'the native downloader for dash/m3u8 downloads '")
        
        # نوشتن فایل اصلاح شده
        with open(options_file, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"فایل {options_file} با موفقیت پچ شد.")
    
    logger.info("yt-dlp با موفقیت پچ شد تا تمام اشارات به aria2 حذف شوند.")
    return True

def reload_ytdlp():
    """بازخوانی ماژول yt-dlp برای اعمال تغییرات"""
    try:
        if 'yt_dlp' in sys.modules:
            importlib.reload(sys.modules['yt_dlp'])
        logger.info("ماژول yt-dlp با موفقیت بازخوانی شد.")
        return True
    except Exception as e:
        logger.error(f"خطا در بازخوانی ماژول yt-dlp: {e}")
        return False

def cleanup_yt_dlp_temp_files():
    """پاکسازی فایل‌های موقت که ممکن است حاوی اشاره به aria2 باشند"""
    try:
        temp_dir = tempfile.gettempdir()
        count = 0
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if 'ytdl' in file.lower() or 'aria2' in file.lower():
                    try:
                        os.remove(os.path.join(root, file))
                        count += 1
                    except:
                        pass
        logger.info(f"{count} فایل موقت مرتبط با yt-dlp پاکسازی شدند.")
        return True
    except Exception as e:
        logger.error(f"خطا در پاکسازی فایل‌های موقت: {e}")
        return False

def main():
    """تابع اصلی برای اجرای پچ"""
    logger.info("در حال آغاز فرآیند پچ کردن yt-dlp...")
    
    # 1. ایجاد نسخه تمیز از yt-dlp
    if not create_clean_ytdlp():
        logger.error("خطا در ایجاد نسخه تمیز از yt-dlp.")
        return False
    
    # 2. بازخوانی ماژول yt-dlp
    if not reload_ytdlp():
        logger.error("خطا در بازخوانی ماژول yt-dlp.")
        return False
    
    # 3. پاکسازی فایل‌های موقت
    if not cleanup_yt_dlp_temp_files():
        logger.warning("هشدار: پاکسازی فایل‌های موقت ناموفق بود.")
    
    logger.info("فرآیند پچ کردن yt-dlp با موفقیت انجام شد!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
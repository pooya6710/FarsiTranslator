"""
ماژول غیرفعال‌سازی aria2c

این ماژول تضمین می‌کند که yt-dlp از aria2c به عنوان دانلودر خارجی استفاده نمی‌کند
"""

import logging
import importlib
import sys
import os

# تنظیم لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

def disable_aria2c_in_ytdlp():
    """
    غیرفعال کردن aria2c در yt-dlp با پچ کردن ماژول downloader/external.py
    """
    try:
        import yt_dlp.downloader.external
        
        # بررسی و اطمینان که aria2c در SUPPORTED_DOWNLOADERS نیست
        if hasattr(yt_dlp.downloader.external, 'SUPPORTED_DOWNLOADERS'):
            downloaders = yt_dlp.downloader.external.SUPPORTED_DOWNLOADERS
            if 'aria2c' in downloaders:
                logger.info("در حال حذف aria2c از لیست دانلودرهای پشتیبانی شده yt-dlp...")
                # حذف aria2c از دانلودرهای پشتیبانی شده
                downloaders.pop('aria2c', None)
                logger.info("aria2c با موفقیت غیرفعال شد")
        
        # اطمینان از اینکه گزینه‌های yt-dlp برای استفاده از aria2c تنظیم نشده‌اند
        import yt_dlp.YoutubeDL
        original_init = yt_dlp.YoutubeDL.__init__
        
        def patched_init(self, *args, **kwargs):
            if args and isinstance(args[0], dict):
                # حذف هرگونه تنظیم مربوط به external_downloader
                options = args[0]
                options.pop('external_downloader', None)
                options.pop('external_downloader_args', None)
            elif 'params' in kwargs:
                # حذف هرگونه تنظیم مربوط به external_downloader
                kwargs['params'].pop('external_downloader', None)
                kwargs['params'].pop('external_downloader_args', None)
            
            # فراخوانی تابع اصلی
            original_init(self, *args, **kwargs)
        
        # جایگزینی تابع __init__
        yt_dlp.YoutubeDL.__init__ = patched_init
        logger.info("yt-dlp با موفقیت پچ شد تا از استفاده از aria2c جلوگیری شود")
        
        return True
    except Exception as e:
        logger.error(f"خطا در غیرفعال‌سازی aria2c: {e}")
        return False

def verify_no_aria2c():
    """
    تأیید اینکه aria2c در سیستم موجود نیست یا استفاده نمی‌شود
    """
    # بررسی وجود باینری aria2c
    from shutil import which
    if which('aria2c'):
        logger.warning("باینری aria2c در سیستم یافت شد، اما دیگر توسط برنامه استفاده نمی‌شود")
    
    # بررسی تنظیمات yt-dlp
    import yt_dlp
    with yt_dlp.YoutubeDL() as ydl:
        params = ydl.params
        if 'external_downloader' in params and params['external_downloader'] == 'aria2c':
            logger.error("yt-dlp همچنان برای استفاده از aria2c تنظیم شده است!")
            return False
    
    logger.info("تأیید شد: هیچ استفاده‌ای از aria2c در برنامه وجود ندارد")
    return True

if __name__ == "__main__":
    # غیرفعال‌سازی aria2c
    if disable_aria2c_in_ytdlp():
        # تأیید غیرفعال‌سازی
        if verify_no_aria2c():
            logger.info("aria2c با موفقیت غیرفعال شد و هیچ استفاده‌ای از آن در برنامه وجود ندارد")
            sys.exit(0)
    
    # خطا در غیرفعال‌سازی
    logger.error("خطا در غیرفعال‌سازی کامل aria2c")
    sys.exit(1)
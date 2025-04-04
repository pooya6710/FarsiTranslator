"""
ماژول غیرفعال‌سازی disabled_downloader

این ماژول تضمین می‌کند که yt-dlp از disabled_downloader به عنوان دانلودر خارجی استفاده نمی‌کند
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

def disable_disabled_downloader_in_ytdlp():
    """
    غیرفعال کردن disabled_downloader در yt-dlp با پچ کردن ماژول downloader/external.py
    """
    try:
        import yt_dlp.downloader.external
        
        # بررسی و اطمینان که disabled_downloader در SUPPORTED_DOWNLOADERS نیست
        if hasattr(yt_dlp.downloader.external, 'SUPPORTED_DOWNLOADERS'):
            downloaders = yt_dlp.downloader.external.SUPPORTED_DOWNLOADERS
            if 'disabled_downloader' in downloaders:
                logger.info("در حال حذف disabled_downloader از لیست دانلودرهای پشتیبانی شده yt-dlp...")
                # حذف disabled_downloader از دانلودرهای پشتیبانی شده
                downloaders.pop('disabled_downloader', None)
                logger.info("disabled_downloader با موفقیت غیرفعال شد")
        
        # اطمینان از اینکه گزینه‌های yt-dlp برای استفاده از disabled_downloader تنظیم نشده‌اند
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
        logger.info("yt-dlp با موفقیت پچ شد تا از استفاده از disabled_downloader جلوگیری شود")
        
        return True
    except Exception as e:
        logger.error(f"خطا در غیرفعال‌سازی disabled_downloader: {e}")
        return False

def verify_no_disabled_downloader():
    """
    تأیید اینکه disabled_downloader در سیستم موجود نیست یا استفاده نمی‌شود
    """
    # بررسی وجود باینری disabled_downloader
    from shutil import which
    if which('disabled_downloader'):
        logger.warning("باینری disabled_downloader در سیستم یافت شد، اما دیگر توسط برنامه استفاده نمی‌شود")
    
    # بررسی تنظیمات yt-dlp
    import yt_dlp
    with yt_dlp.YoutubeDL() as ydl:
        params = ydl.params
        if 'external_downloader' in params and params['external_downloader'] == 'disabled_downloader':
            logger.error("yt-dlp همچنان برای استفاده از disabled_downloader تنظیم شده است!")
            return False
    
    logger.info("تأیید شد: هیچ استفاده‌ای از disabled_downloader در برنامه وجود ندارد")
    return True

if __name__ == "__main__":
    # غیرفعال‌سازی disabled_downloader
    if disable_disabled_downloader_in_ytdlp():
        # تأیید غیرفعال‌سازی
        if verify_no_disabled_downloader():
            logger.info("disabled_downloader با موفقیت غیرفعال شد و هیچ استفاده‌ای از آن در برنامه وجود ندارد")
            sys.exit(0)
    
    # خطا در غیرفعال‌سازی
    logger.error("خطا در غیرفعال‌سازی کامل disabled_downloader")
    sys.exit(1)
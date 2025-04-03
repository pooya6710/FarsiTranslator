"""
پچ سفارشی برای غیرفعال‌سازی کامل aria2 در yt-dlp

این فایل همه ارجاعات به aria2c را در ماژول yt-dlp مانک می‌کند
"""

import sys
import os
import logging
from importlib.util import find_spec

# تنظیم لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

def patch_ytdlp():
    """
    پچ کردن yt-dlp برای حذف کامل aria2c
    """
    try:
        # حذف aria2c از مسیر سیستم (اگر به هر نحوی نصب شده باشد)
        os.environ['PATH'] = ':'.join(
            path for path in os.environ.get('PATH', '').split(':')
            if not os.path.exists(os.path.join(path, 'aria2c'))
        )
        
        # بررسی وجود yt-dlp
        if find_spec('yt_dlp') is None:
            logger.error("ماژول yt-dlp یافت نشد. آیا آن را نصب کرده‌اید؟")
            return False
        
        # مانک کردن ماژول external.py در yt-dlp
        import yt_dlp.downloader
        
        # بررسی وجود ماژول external
        if not hasattr(yt_dlp.downloader, 'external'):
            logger.info("ماژول external.py در yt-dlp یافت نشد، احتمالاً پروژه غیرفعال سازی شده است.")
            return True
        
        # حذف aria2c از دانلودرهای پشتیبانی شده
        if hasattr(yt_dlp.downloader.external, 'SUPPORTED_DOWNLOADERS'):
            downloaders = yt_dlp.downloader.external.SUPPORTED_DOWNLOADERS
            if 'aria2c' in downloaders:
                logger.info("در حال حذف aria2c از دانلودرهای پشتیبانی شده yt-dlp...")
                downloaders.pop('aria2c', None)
                logger.info("aria2c با موفقیت از دانلودرهای پشتیبانی شده حذف شد.")
        
        # تغییر تابع detect_external_downloader برای جلوگیری از تشخیص aria2c
        original_detect = getattr(yt_dlp.downloader.external, '_detect_external_downloader', None)
        if original_detect:
            def patched_detect(command):
                if command == 'aria2c':
                    return False
                return original_detect(command)
            
            yt_dlp.downloader.external._detect_external_downloader = patched_detect
            logger.info("تابع تشخیص دانلودر خارجی پچ شد.")
        
        # اطمینان از اینکه ExternalDownloader هرگز از aria2c استفاده نمی‌کند
        original_get_available = getattr(yt_dlp.downloader.external, 'get_available_downloaders', None)
        if original_get_available:
            def patched_get_available():
                downloaders = original_get_available()
                return {name: cls for name, cls in downloaders.items() if name != 'aria2c'}
            
            yt_dlp.downloader.external.get_available_downloaders = patched_get_available
            logger.info("تابع get_available_downloaders پچ شد.")
        
        logger.info("yt-dlp با موفقیت پچ شد تا از استفاده از aria2c جلوگیری شود.")
        return True
    except Exception as e:
        logger.error(f"خطا در پچ کردن yt-dlp: {e}")
        return False

if __name__ == "__main__":
    if patch_ytdlp():
        logger.info("پچ با موفقیت اعمال شد. yt-dlp دیگر از aria2c استفاده نخواهد کرد.")
        sys.exit(0)
    else:
        logger.error("خطا در اعمال پچ.")
        sys.exit(1)
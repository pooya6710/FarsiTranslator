"""
پچ سفارشی برای غیرفعال‌سازی کامل disabled_aria در yt-dlp

این فایل همه ارجاعات به disabled_downloader را در ماژول yt-dlp مانک می‌کند
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
    پچ کردن yt-dlp برای حذف کامل disabled_downloader
    """
    try:
        # حذف disabled_downloader از مسیر سیستم (اگر به هر نحوی نصب شده باشد)
        os.environ['PATH'] = ':'.join(
            path for path in os.environ.get('PATH', '').split(':')
            if not os.path.exists(os.path.join(path, 'disabled_downloader'))
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
        
        # حذف disabled_downloader از دانلودرهای پشتیبانی شده
        if hasattr(yt_dlp.downloader.external, 'SUPPORTED_DOWNLOADERS'):
            downloaders = yt_dlp.downloader.external.SUPPORTED_DOWNLOADERS
            if 'disabled_downloader' in downloaders:
                logger.info("در حال حذف disabled_downloader از دانلودرهای پشتیبانی شده yt-dlp...")
                downloaders.pop('disabled_downloader', None)
                logger.info("disabled_downloader با موفقیت از دانلودرهای پشتیبانی شده حذف شد.")
        
        # تغییر تابع detect_external_downloader برای جلوگیری از تشخیص disabled_downloader
        original_detect = getattr(yt_dlp.downloader.external, '_detect_external_downloader', None)
        if original_detect:
            def patched_detect(command):
                if command == 'disabled_downloader':
                    return False
                return original_detect(command)
            
            yt_dlp.downloader.external._detect_external_downloader = patched_detect
            logger.info("تابع تشخیص دانلودر خارجی پچ شد.")
        
        # اطمینان از اینکه ExternalDownloader هرگز از disabled_downloader استفاده نمی‌کند
        original_get_available = getattr(yt_dlp.downloader.external, 'get_available_downloaders', None)
        if original_get_available:
            def patched_get_available():
                downloaders = original_get_available()
                return {name: cls for name, cls in downloaders.items() if name != 'disabled_downloader'}
            
            yt_dlp.downloader.external.get_available_downloaders = patched_get_available
            logger.info("تابع get_available_downloaders پچ شد.")
        
        logger.info("yt-dlp با موفقیت پچ شد تا از استفاده از disabled_downloader جلوگیری شود.")
        return True
    except Exception as e:
        logger.error(f"خطا در پچ کردن yt-dlp: {e}")
        return False

if __name__ == "__main__":
    if patch_ytdlp():
        logger.info("پچ با موفقیت اعمال شد. yt-dlp دیگر از disabled_downloader استفاده نخواهد کرد.")
        sys.exit(0)
    else:
        logger.error("خطا در اعمال پچ.")
        sys.exit(1)
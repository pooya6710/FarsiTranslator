#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
اسکریپت اعمال پچ برای حل مشکل دانلود یوتیوب در ربات تلگرام

این اسکریپت فایل‌های ربات تلگرام را برای استفاده از ماژول YoutubeHandler اصلاح می‌کند.
"""

import os
import re
import shutil
import logging
import importlib.util
import sys
from typing import List, Optional, Dict

# تنظیم لاگر
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def backup_file(file_path: str) -> bool:
    """
    ایجاد نسخه پشتیبان از فایل
    
    Args:
        file_path: مسیر فایل
        
    Returns:
        True در صورت موفقیت، False در صورت خطا
    """
    try:
        backup_path = file_path + ".backup_youtube"
        shutil.copy2(file_path, backup_path)
        logger.info(f"نسخه پشتیبان ایجاد شد: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"خطا در ایجاد نسخه پشتیبان: {str(e)}")
        return False

def embed_youtube_handler(file_path: str) -> bool:
    """
    افزودن کد YoutubeHandler به فایل telegram_downloader.py
    
    Args:
        file_path: مسیر فایل
        
    Returns:
        True در صورت موفقیت، False در صورت خطا
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # بررسی اینکه آیا قبلاً اضافه شده است
        if "from youtube_integration import YoutubeHandler" in content:
            logger.info("کد YoutubeHandler قبلاً اضافه شده است.")
            return True
        
        # افزودن import
        import_pattern = r'(import\s+os.*?import\s+.*?$)'
        import_replacement = r'\1\n\n# ماژول دانلود یوتیوب\nfrom youtube_integration import YoutubeHandler'
        content = re.sub(import_pattern, import_replacement, content, flags=re.DOTALL | re.MULTILINE)
        
        # جایگزینی کلاس YouTubeDownloader
        youtube_downloader_pattern = r'(class\s+YouTubeDownloader:.*?)def\s+__init__\s*\(self\)(.*?)'
        youtube_downloader_replacement = r'\1def __init__(self)\2\n        # استفاده از ماژول youtube_integration\n        self.yt_handler = YoutubeHandler(download_dir=DEFAULT_DOWNLOAD_DIR)\n        '
        content = re.sub(youtube_downloader_pattern, youtube_downloader_replacement, content, flags=re.DOTALL)
        
        # ذخیره تغییرات
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"کد YoutubeHandler به {file_path} اضافه شد.")
        return True
    
    except Exception as e:
        logger.error(f"خطا در افزودن کد YoutubeHandler: {str(e)}")
        return False

def patch_download_video_method(file_path: str) -> bool:
    """
    اصلاح متد download_video در فایل telegram_downloader.py
    
    Args:
        file_path: مسیر فایل
        
    Returns:
        True در صورت موفقیت، False در صورت خطا
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # متد جدید download_video
        new_download_video = '''
    async def download_video(self, url: str, format_option: str) -> Optional[str]:
        """
        دانلود ویدیوی یوتیوب
        
        Args:
            url: آدرس ویدیوی یوتیوب
            format_option: فرمت انتخاب شده برای دانلود
            
        Returns:
            مسیر فایل دانلود شده یا None در صورت خطا
        """
        try:
            # بررسی کش
            cache_key = f"{url}_{format_option}"
            cached_file = get_from_cache(cache_key)
            if cached_file:
                logger.info(f"فایل از کش برگردانده شد: {cached_file}")
                return cached_file
                
            # پاکسازی URL
            clean_url = self.clean_youtube_url(url)
            
            # بررسی نوع درخواست (صوتی یا ویدیویی)
            is_audio_request = 'audio' in format_option.lower() or format_option.lower() == 'bestaudio'
            
            if is_audio_request:
                # دانلود صدا
                logger.info(f"درخواست دانلود صدا: {clean_url}")
                downloaded_file = await self.yt_handler.download_audio(clean_url)
            else:
                # تبدیل format_option به کیفیت استاندارد
                quality = self._map_format_to_quality(format_option)
                logger.info(f"درخواست دانلود ویدیو با کیفیت {quality}: {clean_url}")
                downloaded_file = await self.yt_handler.download_video(clean_url, quality)
            
            # افزودن به کش
            if downloaded_file and os.path.exists(downloaded_file):
                add_to_cache(cache_key, downloaded_file)
                logger.info(f"فایل به کش اضافه شد: {downloaded_file}")
            
            return downloaded_file
                
        except Exception as e:
            logger.error(f"خطا در دانلود ویدیوی یوتیوب: {str(e)}")
            import traceback
            logger.error(f"جزئیات خطا: {traceback.format_exc()}")
            return None
            
    def _map_format_to_quality(self, format_option: str) -> str:
        """تبدیل format_option به کیفیت استاندارد"""
        if "1080" in format_option:
            return "1080p"
        elif "720" in format_option:
            return "720p"
        elif "480" in format_option:
            return "480p"
        elif "360" in format_option:
            return "360p"
        elif "240" in format_option:
            return "240p"
        else:
            return "best"'''
        
        # جایگزینی متد download_video
        download_video_pattern = r'async\s+def\s+download_video\s*\(\s*self\s*,\s*url\s*:\s*str\s*,\s*format_option\s*:\s*str\s*\)\s*->\s*Optional\s*\[\s*str\s*\].*?(?=^\s{4}[^\s])'
        download_video_replacement = new_download_video
        
        content = re.sub(download_video_pattern, download_video_replacement, content, flags=re.DOTALL | re.MULTILINE)
        
        # متد جدید download_audio
        new_download_audio = '''
    async def download_audio(self, url: str) -> Optional[str]:
        """
        دانلود فقط صدای ویدیوی یوتیوب
        
        Args:
            url: آدرس ویدیوی یوتیوب
            
        Returns:
            مسیر فایل صوتی دانلود شده یا None در صورت خطا
        """
        try:
            # بررسی کش
            cache_key = f"{url}_audio"
            cached_file = get_from_cache(cache_key)
            if cached_file:
                logger.info(f"فایل صوتی از کش برگردانده شد: {cached_file}")
                return cached_file
                
            # دانلود صدا با استفاده از YoutubeHandler
            clean_url = self.clean_youtube_url(url)
            downloaded_file = await self.yt_handler.download_audio(clean_url)
            
            # افزودن به کش
            if downloaded_file and os.path.exists(downloaded_file):
                add_to_cache(cache_key, downloaded_file)
                logger.info(f"فایل صوتی به کش اضافه شد: {downloaded_file}")
            
            return downloaded_file
                
        except Exception as e:
            logger.error(f"خطا در دانلود صدای یوتیوب: {str(e)}")
            return None'''
            
        # جایگزینی متد download_audio
        download_audio_pattern = r'async\s+def\s+download_audio\s*\(\s*self\s*,\s*url\s*:\s*str\s*\)\s*->\s*Optional\s*\[\s*str\s*\].*?(?=^\s{4}[^\s])'
        download_audio_replacement = new_download_audio
        
        content = re.sub(download_audio_pattern, download_audio_replacement, content, flags=re.DOTALL | re.MULTILINE)
        
        # ذخیره تغییرات
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"متدهای download_video و download_audio در {file_path} اصلاح شدند.")
        return True
    
    except Exception as e:
        logger.error(f"خطا در اصلاح متدهای download_video و download_audio: {str(e)}")
        return False

def patch_handle_youtube_callback(file_path: str) -> bool:
    """
    اصلاح هندلر handle_youtube_callback در فایل telegram_downloader.py
    این متد را برای استفاده از کیفیت‌های استاندارد اصلاح می‌کند.
    
    Args:
        file_path: مسیر فایل
        
    Returns:
        True در صورت موفقیت، False در صورت خطا
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # اصلاح بخش مربوط به انتخاب کیفیت در handle_youtube_callback
        youtube_callback_pattern = r'(\s+# نگاشت مستقیم شماره گزینه به کیفیت متناظر با تضمین دریافت ویدیو.*?option_num == 0:.*?)format_option = "bestvideo\[ext=mp4\]\[height<=1080\]\+bestaudio\[ext=m4a\].*?option_num == 4:'
        
        youtube_callback_replacement = r'''
            # نگاشت مستقیم شماره گزینه به کیفیت متناظر با تضمین دریافت ویدیو
            # گزینه‌های یوتیوب معمولاً: 0: 1080p, 1: 720p, 2: 480p, 3: 360p, 4: 240p, 5: audio
            if option_num == 0:
                format_option = "1080p"  # استفاده از فرمت ساده‌شده برای YoutubeHandler
                quality = "1080p"
                quality_display = "کیفیت Full HD (1080p)"
            elif option_num == 1:
                format_option = "720p"  # استفاده از فرمت ساده‌شده برای YoutubeHandler
                quality = "720p"
                quality_display = "کیفیت HD (720p)"
            elif option_num == 2:
                format_option = "480p"  # استفاده از فرمت ساده‌شده برای YoutubeHandler
                quality = "480p"
                quality_display = "کیفیت متوسط (480p)"
            elif option_num == 3:
                format_option = "360p"  # استفاده از فرمت ساده‌شده برای YoutubeHandler
                quality = "360p"
                quality_display = "کیفیت پایین (360p)"
            elif option_num == 4:'''
        
        content = re.sub(youtube_callback_pattern, youtube_callback_replacement, content, flags=re.DOTALL)
        
        # بخش دوم برای گزینه 4 (240p)
        pattern_240p = r'(option_num == 4:.*?)format_option = "bestvideo\[ext=mp4\]\[height<=240\]\+bestaudio\[ext=m4a\].*?elif option_num == 5:'
        replacement_240p = r'''option_num == 4:
                format_option = "240p"  # استفاده از فرمت ساده‌شده برای YoutubeHandler
                quality = "240p"
                quality_display = "کیفیت خیلی پایین (240p)"
            elif option_num == 5:'''
        
        content = re.sub(pattern_240p, replacement_240p, content, flags=re.DOTALL)
        
        # ذخیره تغییرات
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"هندلر handle_youtube_callback در {file_path} اصلاح شد.")
        return True
    
    except Exception as e:
        logger.error(f"خطا در اصلاح هندلر handle_youtube_callback: {str(e)}")
        return False

def patch_get_download_options(file_path: str) -> bool:
    """
    اصلاح متد get_download_options در فایل telegram_downloader.py
    
    Args:
        file_path: مسیر فایل
        
    Returns:
        True در صورت موفقیت، False در صورت خطا
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # محل تقریبی شروع متد get_download_options
        get_options_pattern = r'async\s+def\s+get_download_options\s*\(\s*self\s*,\s*url\s*:\s*str\s*\)\s*->\s*List\s*\[\s*Dict\s*\]:'
        
        # بررسی آیا متد وجود دارد
        if not re.search(get_options_pattern, content):
            logger.warning(f"متد get_download_options در {file_path} یافت نشد.")
            return False
        
        # متد جدید
        new_get_options = '''
    async def get_download_options(self, url: str) -> List[Dict]:
        """
        دریافت گزینه‌های دانلود برای ویدیوی یوتیوب (نسخه بهبود یافته)
        
        Args:
            url: آدرس ویدیوی یوتیوب
            
        Returns:
            لیستی از گزینه‌های دانلود با ساختار استاندارد
        """
        try:
            # استفاده از YoutubeHandler برای دریافت گزینه‌ها
            options = await self.yt_handler.get_download_options(url)
            logger.info(f"تعداد گزینه‌های دانلود ایجاد شده: {len(options)}")
            return options
            
        except Exception as e:
            logger.error(f"خطا در دریافت گزینه‌های دانلود یوتیوب: {str(e)}")
            logger.error(f"جزئیات خطا: {traceback.format_exc()}")
            
            # در صورت خطا، گزینه‌های پیش‌فرض را برمی‌گردانیم
            return [
                {
                    'quality': 'best',
                    'display_name': 'بهترین کیفیت',
                    'priority': 1
                },
                {
                    'quality': '1080p',
                    'display_name': 'کیفیت Full HD (1080p)',
                    'priority': 2
                },
                {
                    'quality': '720p',
                    'display_name': 'کیفیت HD (720p)',
                    'priority': 3
                },
                {
                    'quality': '480p',
                    'display_name': 'کیفیت متوسط (480p)',
                    'priority': 4
                },
                {
                    'quality': '360p',
                    'display_name': 'کیفیت پایین (360p)',
                    'priority': 5
                },
                {
                    'quality': '240p',
                    'display_name': 'کیفیت خیلی پایین (240p)',
                    'priority': 6
                },
                {
                    'quality': 'audio',
                    'display_name': 'فقط صدا (MP3)',
                    'type': 'audio',
                    'priority': 7
                }
            ]'''
        
        # جایگزینی کل متد
        pattern = r'async\s+def\s+get_download_options\s*\(\s*self\s*,\s*url\s*:\s*str\s*\)\s*->\s*List\s*\[\s*Dict\s*\].*?(?=^\s{4}[^\s])'
        content = re.sub(pattern, new_get_options, content, flags=re.DOTALL | re.MULTILINE)
        
        # ذخیره تغییرات
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"متد get_download_options در {file_path} اصلاح شد.")
        return True
    
    except Exception as e:
        logger.error(f"خطا در اصلاح متد get_download_options: {str(e)}")
        return False

def check_required_files() -> bool:
    """
    بررسی وجود فایل‌های مورد نیاز
    
    Returns:
        True اگر همه فایل‌ها موجود هستند، False در غیر این صورت
    """
    required_files = [
        "telegram_downloader.py",
        "youtube_extractor.py",
        "youtube_integration.py",
        "direct_youtube_downloader.py"
    ]
    
    for file in required_files:
        if not os.path.exists(file):
            logger.error(f"فایل مورد نیاز یافت نشد: {file}")
            return False
    
    logger.info("همه فایل‌های مورد نیاز موجود هستند.")
    return True

def main():
    """
    تابع اصلی اجرای پچ
    """
    logger.info("شروع اعمال پچ برای حل مشکل دانلود یوتیوب...")
    
    # بررسی وجود فایل‌های مورد نیاز
    if not check_required_files():
        logger.error("یک یا چند فایل مورد نیاز یافت نشدند. لطفاً آن‌ها را ایجاد کنید.")
        return False
    
    # مسیر فایل اصلی
    file_path = "telegram_downloader.py"
    
    # ایجاد نسخه پشتیبان
    if not backup_file(file_path):
        logger.error("خطا در ایجاد نسخه پشتیبان. پچ اعمال نشد.")
        return False
    
    # اعمال پچ‌ها
    steps = [
        ("افزودن کد YoutubeHandler", embed_youtube_handler),
        ("اصلاح متدهای download_video و download_audio", patch_download_video_method),
        ("اصلاح هندلر handle_youtube_callback", patch_handle_youtube_callback),
        ("اصلاح متد get_download_options", patch_get_download_options)
    ]
    
    success = True
    for step_name, step_func in steps:
        logger.info(f"در حال {step_name}...")
        if not step_func(file_path):
            logger.error(f"خطا در {step_name}. پچ به طور کامل اعمال نشد.")
            success = False
            break
    
    if success:
        logger.info("پچ با موفقیت اعمال شد.")
        print("=== راهنمای استفاده ===")
        print("1. ربات تلگرام را مجدداً راه‌اندازی کنید.")
        print("2. لینک یوتیوب را به ربات ارسال کنید.")
        print("3. گزینه‌های دانلود را بررسی کنید.")
        print("4. اکنون باید دانلود ویدیوی یوتیوب با کیفیت‌های مختلف به درستی کار کند.")
    else:
        logger.warning("می‌توانید فایل اصلی را از نسخه پشتیبان بازیابی کنید:")
        print(f"cp {file_path}.backup_youtube {file_path}")
    
    return success

if __name__ == "__main__":
    main()
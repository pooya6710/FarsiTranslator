#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
اسکریپت ادغام ماژول YoutubeHandler با ربات تلگرام

این اسکریپت نحوه‌ی ادغام ماژول YoutubeHandler با کد اصلی ربات را نشان می‌دهد.
"""

import os
import logging
import asyncio
import traceback
from typing import Dict, List, Optional, Tuple, Union

# تنظیم لاگر
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# واردسازی ماژول‌های پروژه
from youtube_integration import YoutubeHandler

def run_sample_test():
    """
    اجرای یک تست ساده برای بررسی عملکرد ماژول
    """
    # نمونه URL برای تست
    test_url = "https://www.youtube.com/shorts/imZkuPNfKas"
    
    # ایجاد نمونه از کلاس YoutubeHandler
    yt_handler = YoutubeHandler()
    
    async def test():
        # دریافت اطلاعات ویدیو
        logger.info("دریافت اطلاعات ویدیو...")
        info = await yt_handler.get_video_info(test_url)
        if info:
            logger.info(f"عنوان ویدیو: {info.get('title')}")
        
        # دریافت گزینه‌های دانلود
        logger.info("دریافت گزینه‌های دانلود...")
        options = await yt_handler.get_download_options(test_url)
        for i, option in enumerate(options):
            logger.info(f"گزینه {i+1}: {option.get('quality')} - {option.get('display_name')}")
        
        # دانلود ویدیو با کیفیت‌های مختلف
        qualities = ["720p", "480p", "360p"]
        for quality in qualities:
            logger.info(f"دانلود ویدیو با کیفیت {quality}...")
            video_path = await yt_handler.download_video(test_url, quality)
            if video_path:
                logger.info(f"ویدیو با کیفیت {quality} دانلود شد: {video_path}")
            else:
                logger.error(f"دانلود ویدیو با کیفیت {quality} ناموفق بود")
        
        # دانلود صدا
        logger.info("دانلود صدا...")
        audio_path = await yt_handler.download_audio(test_url)
        if audio_path:
            logger.info(f"صدا دانلود شد: {audio_path}")
        else:
            logger.error("دانلود صدا ناموفق بود")
        
    # اجرای تست غیرهمزمان
    asyncio.run(test())

def integrate_with_telegram_bot():
    """
    نحوه ادغام ماژول با کد ربات تلگرام
    
    Note: این کد فقط نمونه‌ای برای نمایش نحوه ادغام است و باید با کد اصلی ربات ترکیب شود.
    """
    # این قسمت‌ها باید در فایل telegram_downloader.py اضافه شوند
    code_example = """
    # در بخش واردسازی‌ها اضافه کنید
    from youtube_integration import YoutubeHandler
    
    # در ابتدای کلاس YouTubeDownloader یا بخش مناسب دیگر:
    def __init__(self):
        # مقداردهی اولیه
        self.yt_handler = YoutubeHandler(download_dir=DEFAULT_DOWNLOAD_DIR)
    
    # جایگزین روش دانلود ویدیو:
    async def download_video(self, url: str, format_option: str) -> Optional[str]:
        \"\"\"
        دانلود ویدیوی یوتیوب
        
        Args:
            url: آدرس ویدیوی یوتیوب
            format_option: کیفیت مورد نظر
            
        Returns:
            مسیر فایل دانلود شده یا None در صورت خطا
        \"\"\"
        try:
            if format_option == "bestaudio" or "audio" in format_option:
                # دانلود صدا
                return await self.yt_handler.download_audio(url)
            else:
                # تبدیل format_option به کیفیت استاندارد
                quality = self._map_format_to_quality(format_option)
                # دانلود ویدیو
                return await self.yt_handler.download_video(url, quality)
        except Exception as e:
            logger.error(f"خطا در دانلود ویدیو: {str(e)}")
            return None
            
    # تابع کمکی برای تبدیل format_option به کیفیت استاندارد
    def _map_format_to_quality(self, format_option: str) -> str:
        \"\"\"تبدیل format_option به کیفیت استاندارد\"\"\"
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
            return "best"
    
    # جایگزین روش دریافت گزینه‌های دانلود:
    async def get_download_options(self, url: str) -> List[Dict]:
        \"\"\"دریافت گزینه‌های دانلود\"\"\"
        try:
            return await self.yt_handler.get_download_options(url)
        except Exception as e:
            logger.error(f"خطا در دریافت گزینه‌های دانلود: {str(e)}")
            return []
    """
    
    print("کد نمونه برای ادغام ماژول با ربات تلگرام:")
    print(code_example)

if __name__ == "__main__":
    print("این اسکریپت فقط برای نمایش نحوه استفاده از ماژول YoutubeHandler است.")
    print("برای تست عملکرد ماژول، می‌توانید run_sample_test() را فراخوانی کنید.")
    print("برای دیدن نحوه ادغام با ربات تلگرام، می‌توانید integrate_with_telegram_bot() را فراخوانی کنید.")
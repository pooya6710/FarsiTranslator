# -*- coding: utf-8 -*-
"""
ماژول جایگزین برای غیرفعال کردن کامل دانلودرهای خارجی
"""

import logging
import os
import sys

logger = logging.getLogger(__name__)

# غیرفعال کردن تمام توابع دانلودر خارجی
def disable_external_downloaders():
    """غیرفعال کردن کامل تمام دانلودرهای خارجی"""
    try:
        import yt_dlp
        
        # جایگزینی توابع با توابع بی‌اثر
        if hasattr(yt_dlp.downloader, 'get_suitable_downloader'):
            original_get_suitable = yt_dlp.downloader.get_suitable_downloader
            def disabled_get_suitable(*args, **kwargs):
                dl = original_get_suitable(*args, **kwargs)
                if 'external' in str(dl).lower():
                    return yt_dlp.downloader.http.HttpFD
                return dl
            yt_dlp.downloader.get_suitable_downloader = disabled_get_suitable
        
        # غیرفعال کردن متغیرهای کلاس
        if hasattr(yt_dlp, 'YoutubeDL'):
            yt_dlp.YoutubeDL.params = {
                **yt_dlp.YoutubeDL.params,
                'external_downloader': None,
                'external_downloader_args': None,
            }
        
        # تنظیم متغیرهای محیطی
        os.environ['YDL_NO_EXTERNAL_DOWNLOADER'] = '1'
        os.environ['HTTP_DOWNLOADER'] = 'native'
        os.environ['YTDLP_DOWNLOADER'] = 'native'
        
        logger.info("تمام دانلودرهای خارجی با موفقیت غیرفعال شدند")
        return True
    except Exception as e:
        logger.error(f"خطا در غیرفعال‌سازی دانلودرهای خارجی: {e}")
        return False

# اجرای تابع غیرفعال‌سازی به صورت خودکار
disable_external_downloaders()

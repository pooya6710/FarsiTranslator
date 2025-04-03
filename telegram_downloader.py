#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
دانلودر تلگرام ویدیوهای اینستاگرام و یوتیوب

این اسکریپت یک ربات تلگرام برای دانلود ویدیوهای اینستاگرام و یوتیوب ایجاد می‌کند.
کاربران می‌توانند لینک ویدیوهای اینستاگرام یا یوتیوب را برای ربات ارسال کنند و
ویدیو را با کیفیت‌های مختلف دانلود کنند.

نحوه استفاده:
1. مطمئن شوید که همه وابستگی‌های مورد نیاز را نصب کرده‌اید:
   pip install python-telegram-bot yt-dlp instaloader requests

2. متغیر محیطی TELEGRAM_BOT_TOKEN را تنظیم کنید.

3. اسکریپت را اجرا کنید:
   python telegram_downloader.py

این برنامه در ابتدا تست‌های خودکار را اجرا می‌کند و سپس ربات را راه‌اندازی می‌کند.
برای راه‌اندازی بدون اجرای تست‌ها، از آرگومان --skip-tests استفاده کنید:
   python telegram_downloader.py --skip-tests
"""

import os
import re
import uuid
import time
import asyncio
import logging
import tempfile
import requests
import subprocess
import shutil
import sys
import argparse
import traceback
from datetime import datetime
from urllib.parse import urlparse
from typing import Dict, List, Any, Optional, Tuple, Union

# سعی می‌کنیم ماژول‌های بهینه‌سازی شده را وارد کنیم
try:
    from enhanced_telegram_handler import get_enhanced_handler, setup_bot_with_enhancements, update_telegram_bot
    ENHANCED_MODE = True
    logging.info("ماژول‌های بهینه‌سازی با موفقیت بارگذاری شدند")
except ImportError:
    ENHANCED_MODE = False
    logging.warning("ماژول‌های بهینه‌سازی یافت نشدند، از حالت معمولی استفاده می‌شود")

# سعی می‌کنیم ماژول بهینه‌سازی کش را وارد کنیم
try:
    from cache_optimizer import run_optimization as optimize_cache, start_background_optimization
    CACHE_OPTIMIZER_AVAILABLE = True
    logging.info("ماژول بهینه‌سازی کش با موفقیت بارگذاری شد")
    # راه‌اندازی بهینه‌سازی خودکار در پس‌زمینه
    start_background_optimization()
except ImportError:
    CACHE_OPTIMIZER_AVAILABLE = False
    logging.warning("ماژول بهینه‌سازی کش یافت نشد")
    def optimize_cache():
        pass

# سعی می‌کنیم ماژول بهینه‌سازی دانلود یوتیوب را وارد کنیم
try:
    from youtube_downloader_optimizer import (
        optimize_yt_dlp_for_speed, download_with_optimized_settings, 
        get_youtube_video_info, extract_video_id_from_url, optimize_video_for_upload
    )
    YOUTUBE_OPTIMIZER_AVAILABLE = True
    logging.info("ماژول بهینه‌سازی دانلود یوتیوب با موفقیت بارگذاری شد")
    # بهینه‌سازی yt-dlp
    optimize_yt_dlp_for_speed()
except ImportError:
    YOUTUBE_OPTIMIZER_AVAILABLE = False
    logging.warning("ماژول بهینه‌سازی دانلود یوتیوب یافت نشد")

# سعی می‌کنیم ماژول پردازش ویدیو را وارد کنیم
try:
    from video_processor import (
        convert_video_quality, extract_audio as vp_extract_audio, 
        optimize_for_telegram, get_video_info
    )
    VIDEO_PROCESSOR_AVAILABLE = True
    logging.info("ماژول پردازش ویدیو با موفقیت بارگذاری شد")
except ImportError:
    VIDEO_PROCESSOR_AVAILABLE = False
    logging.warning("ماژول پردازش ویدیو یافت نشد")

# ماژول پردازش صوتی
try:
    from audio_processing import extract_audio, is_video_file, is_audio_file
except ImportError:
    if VIDEO_PROCESSOR_AVAILABLE:
        # استفاده از ماژول پردازش ویدیو برای استخراج صدا
        extract_audio = vp_extract_audio
        
        def is_video_file(file_path: str) -> bool:
            """بررسی می‌کند که آیا فایل، یک فایل ویدیویی است"""
            video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm']
            ext = os.path.splitext(file_path)[1].lower()
            return ext in video_extensions
            
        def is_audio_file(file_path: str) -> bool:
            """بررسی می‌کند که آیا فایل، یک فایل صوتی است"""
            audio_extensions = ['.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg']
            ext = os.path.splitext(file_path)[1].lower()
            return ext in audio_extensions
    else:
        # تعریف توابع جایگزین در صورت عدم وجود ماژول
        def extract_audio(video_path: str, output_format: str = 'mp3', bitrate: str = '192k') -> Optional[str]:
            logging.warning(f"هشدار: ماژول audio_processing نصب نشده، استخراج صدا انجام نمی‌شود: {video_path}")
            return None
            
        def is_video_file(file_path: str) -> bool:
            """بررسی می‌کند که آیا فایل، یک فایل ویدیویی است"""
            video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm']
            ext = os.path.splitext(file_path)[1].lower()
            return ext in video_extensions
            
        def is_audio_file(file_path: str) -> bool:
            """بررسی می‌کند که آیا فایل، یک فایل صوتی است"""
            audio_extensions = ['.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg']
            ext = os.path.splitext(file_path)[1].lower()
            return ext in audio_extensions

# کش دانلود در حافظه
download_cache = {}

# پوشه‌ی موقت برای دانلود فایل‌ها
TEMP_DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)

# مسیر پوشه برای دیباگ
DEBUG_DIR = os.path.join(TEMP_DOWNLOAD_DIR, "debug")
os.makedirs(DEBUG_DIR, exist_ok=True)

def get_unique_filename(directory: str, base_filename: str) -> str:
    """
    ایجاد یک نام فایل یکتا برای جلوگیری از رونویسی فایل‌های موجود
    
    Args:
        directory: مسیر دایرکتوری
        base_filename: نام پایه فایل
        
    Returns:
        مسیر کامل فایل با نام یکتا
    """
    if not os.path.exists(os.path.join(directory, base_filename)):
        return os.path.join(directory, base_filename)
        
    name, ext = os.path.splitext(base_filename)
    counter = 1
    
    while os.path.exists(os.path.join(directory, f"{name}_{counter}{ext}")):
        counter += 1
        
    return os.path.join(directory, f"{name}_{counter}{ext}")

def add_to_cache(cache_key: str, file_path: str, quality: Optional[str] = None) -> None:
    """
    افزودن فایل به کش با کلید مشخص
    
    Args:
        cache_key: کلید کش (معمولاً URL)
        file_path: مسیر فایل
        quality: کیفیت فایل (اختیاری)
    """
    global download_cache
    
    # بررسی وجود فایل قبل از افزودن به کش
    if os.path.exists(file_path):
        download_cache[cache_key] = (time.time(), file_path)
        # استفاده از logger در سطح ریشه برای هماهنگی با توابع تست
        quality_info = f"کیفیت {quality}" if quality else "بدون تعیین کیفیت"
        logging.info(f"فایل به کش اضافه شد ({quality_info}): {file_path}")
    else:
        logging.warning(f"فایل موجود نیست و به کش اضافه نشد: {file_path}")

# تلاش برای وارد کردن کتابخانه‌های خارجی
try:
    import yt_dlp
    from telegram.ext import (
        Application, CommandHandler, MessageHandler, 
        CallbackQueryHandler, ContextTypes, filters
    )
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
    import instaloader
except ImportError as e:
    print(f"خطا در وارد کردن کتابخانه‌های مورد نیاز: {e}")
    print("لطفاً اطمینان حاصل کنید که تمام وابستگی‌ها را نصب کرده‌اید:")
    print("pip install python-telegram-bot yt-dlp instaloader requests")
    exit(1)

# تنظیمات لاگینگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# دیکشنری برای ذخیره اطلاعات دانلود هر کاربر
user_download_data = {}

# ذخیره‌سازی پایدار برای URL ها (به عنوان جایگزین برای context.user_data)
# این روش از مشکل "لینک منقضی شده" در صورت راه‌اندازی مجدد ربات جلوگیری می‌کند
persistent_url_storage = {}

# ذخیره‌سازی اطلاعات گزینه‌های دانلود برای هر URL
# این مخزن برای جلوگیری از مشکل از دست رفتن گزینه‌های دانلود استفاده می‌شود
option_cache = {}

# دیکشنری برای ذخیره آخرین دکمه‌های فشرده شده توسط کاربران
# این برای کمک به حل مشکل "لینک منقضی شده" استفاده می‌شود
recent_button_clicks = {}

"""
بخش 1: تنظیمات و ثابت‌ها
"""

# حداکثر حجم فایل برای ارسال در تلگرام (50 مگابایت)
MAX_TELEGRAM_FILE_SIZE = 50 * 1024 * 1024

# زمان TTL (Time To Live) برای کش (به ثانیه)
CACHE_TTL = 3600 * 24  # 24 ساعت

# پیام‌های خطا
ERROR_MESSAGES = {
    "invalid_url": "❌ لینک نامعتبر است. لطفاً یک لینک معتبر اینستاگرام یا یوتیوب ارسال کنید.",
    "extraction_failed": "❌ استخراج اطلاعات ویدیو با خطا مواجه شد. لطفاً مجدداً تلاش کنید.",
    "download_failed": "❌ دانلود ویدیو با خطا مواجه شد. لطفاً مجدداً تلاش کنید.",
    "file_too_large": "❌ حجم فایل بیش از حد مجاز برای ارسال در تلگرام است (حداکثر 50 مگابایت).",
    "link_expired": "❌ لینک منقضی شده است. لطفاً دوباره لینک را ارسال کنید.",
    "instagram_login_required": "❌ برای دانلود این پست باید وارد حساب اینستاگرام شوید.",
    "network_error": "❌ خطا در اتصال به سرور. لطفاً اتصال اینترنت خود را بررسی کنید.",
    "rate_limit": "❌ محدودیت درخواست‌ها. لطفاً کمی بعد مجدداً تلاش کنید.",
    "video_unavailable": "❌ ویدیو در دسترس نیست یا خصوصی شده است.",
    "unknown_error": "❌ خطای ناشناخته رخ داده است. لطفاً مجدداً تلاش کنید."
}

# پیام‌های وضعیت
STATUS_MESSAGES = {
    "downloading": "⏳ در حال دانلود ویدیو... لطفاً صبر کنید.",
    "processing": "⚙️ در حال پردازش فایل... لطفاً صبر کنید.",
    "preparing": "🔄 در حال آماده‌سازی ویدیو... لطفاً صبر کنید.",
    "uploading": "📤 دانلود کامل شد. در حال ارسال فایل... لطفاً صبر کنید.",
    "getting_options": "🔍 در حال دریافت اطلاعات ویدیو... لطفاً صبر کنید."
}

"""
بخش 2: کلاس‌ها و توابع کمکی
"""

def human_readable_size(size_bytes: int) -> str:
    """
    تبدیل اندازه فایل به فرمت خوانا
    
    Args:
        size_bytes: اندازه فایل به بایت
        
    Returns:
        رشته نمایشی اندازه فایل
    """
    for unit in ['بایت', 'کیلوبایت', 'مگابایت', 'گیگابایت']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} ترابایت"

def get_format_label(format_info: Dict) -> str:
    """
    ایجاد برچسب خوانا برای فرمت ویدیو
    
    Args:
        format_info: اطلاعات فرمت
        
    Returns:
        برچسب فرمت
    """
    resolution = format_info.get('format_note', '')
    
    if 'height' in format_info:
        height = format_info['height']
        if height:
            if height >= 720:
                quality = "HD"
            elif height >= 480:
                quality = "SD"
            else:
                quality = "کیفیت پایین"
        else:
            quality = "نامشخص"
    else:
        quality = "نامشخص"
        
    if 'filesize' in format_info and format_info['filesize']:
        filesize = human_readable_size(format_info['filesize'])
    elif 'filesize_approx' in format_info and format_info['filesize_approx']:
        filesize = human_readable_size(format_info['filesize_approx']) + " (تقریبی)"
    else:
        filesize = "نامشخص"
        
    if 'ext' in format_info:
        ext = format_info['ext'].upper()
    else:
        ext = "ناشناخته"
        
    vcodec = format_info.get('vcodec', 'نامشخص')
    acodec = format_info.get('acodec', 'نامشخص')
    
    if vcodec == 'none' and acodec != 'none':
        return f"🎵 فقط صدا - {filesize} - {ext}"
    elif resolution:
        return f"🎬 {resolution} {quality} - {filesize} - {ext}"
    else:
        return f"🎬 {quality} - {filesize} - {ext}"

def combine_labels(format_info_list: List[Dict]) -> List[Tuple[Dict, str]]:
    """
    ترکیب برچسب‌های فرمت و حذف موارد تکراری
    
    Args:
        format_info_list: لیست اطلاعات فرمت
        
    Returns:
        لیست ترکیبی از اطلاعات فرمت و برچسب‌ها
    """
    seen_labels = set()
    result = []
    
    for format_info in format_info_list:
        label = get_format_label(format_info)
        # حذف موارد تکراری با برچسب یکسان
        if label not in seen_labels:
            seen_labels.add(label)
            result.append((format_info, label))
            
    return result

def extract_url(text: str) -> Optional[str]:
    """
    استخراج URL از متن
    
    Args:
        text: متن ورودی
        
    Returns:
        URL استخراج شده یا None در صورت عدم وجود
    """
    # الگوی URL
    url_pattern = r'https?://[^\s]+'
    match = re.search(url_pattern, text)
    
    if match:
        return match.group(0)
    return None

def is_youtube_url(url: str) -> bool:
    """
    بررسی می‌کند که آیا URL از یوتیوب است
    
    Args:
        url: آدرس URL
        
    Returns:
        True اگر URL از یوتیوب باشد، False در غیر این صورت
    """
    if ENHANCED_MODE:
        from enhanced_telegram_handler import EnhancedTelegramHandler
        return EnhancedTelegramHandler.is_youtube_url(url)
    else:
        # الگوی URL یوتیوب
        youtube_patterns = [
            r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})'
        ]
        
        for pattern in youtube_patterns:
            match = re.search(pattern, url)
            if match:
                return True
        return False

def is_youtube_shorts(url: str) -> bool:
    """
    بررسی می‌کند که آیا URL از یوتیوب شورتز است
    
    Args:
        url: آدرس URL
        
    Returns:
        True اگر URL از یوتیوب شورتز باشد، False در غیر این صورت
    """
    if ENHANCED_MODE:
        from enhanced_telegram_handler import EnhancedTelegramHandler
        return EnhancedTelegramHandler.is_youtube_shorts(url)
    else:
        # الگوی URL یوتیوب شورتز
        shorts_pattern = r'youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})'
        match = re.search(shorts_pattern, url)
        return bool(match)

def is_youtube_playlist(url: str) -> bool:
    """
    بررسی می‌کند که آیا URL از پلی‌لیست یوتیوب است
    
    Args:
        url: آدرس URL
        
    Returns:
        True اگر URL از پلی‌لیست یوتیوب باشد، False در غیر این صورت
    """
    if ENHANCED_MODE:
        from enhanced_telegram_handler import EnhancedTelegramHandler
        return EnhancedTelegramHandler.is_youtube_playlist(url)
    else:
        # الگوی URL پلی‌لیست یوتیوب
        playlist_pattern = r'youtube\.com\/playlist\?list=([a-zA-Z0-9_-]+)'
        match = re.search(playlist_pattern, url)
        return bool(match)

def is_instagram_url(url: str) -> bool:
    """
    بررسی می‌کند که آیا URL از اینستاگرام است
    
    Args:
        url: آدرس URL
        
    Returns:
        True اگر URL از اینستاگرام باشد، False در غیر این صورت
    """
    if ENHANCED_MODE:
        from enhanced_telegram_handler import EnhancedTelegramHandler
        return EnhancedTelegramHandler.is_instagram_url(url)
    else:
        # بررسی دامنه اینستاگرام
        return 'instagram.com' in url or 'instagr.am' in url

def extract_instagram_shortcode(url: str) -> Optional[str]:
    """
    استخراج کد کوتاه پست اینستاگرام از URL
    
    Args:
        url: آدرس URL اینستاگرام
        
    Returns:
        کد کوتاه یا None در صورت عدم وجود
    """
    # الگوهای مختلف URL اینستاگرام با پشتیبانی از انواع مختلف لینک‌ها
    patterns = [
        r'instagram\.com\/p\/([^\/\?]+)',
        r'instagram\.com\/reel\/([^\/\?]+)',
        r'instagram\.com\/tv\/([^\/\?]+)',
        r'instagram\.com\/stories\/[^\/]+\/([^\/\?]+)',
        r'instagr\.am\/p\/([^\/\?]+)',
        r'instagr\.am\/reel\/([^\/\?]+)',
        r'instagr\.am\/tv\/([^\/\?]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            shortcode = match.group(1)
            logger.info(f"کد کوتاه اینستاگرام استخراج شد: {shortcode} از URL: {url}")
            return shortcode
    
    # تلاش برای استخراج کد کوتاه از آخرین قسمت URL
    parts = url.rstrip('/').split('/')
    if len(parts) > 0 and len(parts[-1]) > 5:  # کد کوتاه معمولاً طولش بیش از 5 کاراکتر است
        potential_shortcode = parts[-1].split('?')[0]  # حذف پارامترهای URL
        logger.info(f"استخراج کد کوتاه احتمالی از URL: {potential_shortcode}")
        return potential_shortcode
    
    logger.error(f"نمی‌توان کد کوتاه را از URL استخراج کرد: {url}")
    return None

def extract_youtube_id(url: str) -> Optional[str]:
    """
    استخراج شناسه ویدیوی یوتیوب از URL
    
    Args:
        url: آدرس URL یوتیوب
        
    Returns:
        شناسه ویدیو یا None در صورت عدم وجود
    """
    if YOUTUBE_OPTIMIZER_AVAILABLE:
        return extract_video_id_from_url(url)
    else:
        # الگوهای مختلف URL یوتیوب
        patterns = [
            r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None

"""
بخش 3: کلاس‌های دانلود
"""

class YoutubeDownloader:
    """کلاس دانلود ویدیوهای یوتیوب"""
    
    def __init__(self):
        self.ydl_opts_base = {
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'nocheckcertificate': True,
            'check_formats': True,
            'outtmpl': os.path.join(TEMP_DOWNLOAD_DIR, '%(id)s_%(format_id)s.%(ext)s'),
            'retries': 5,
            'fragment_retries': 5,
            'skip_unavailable_fragments': True
        }
    
    async def get_video_info(self, url: str) -> Optional[Dict]:
        """
        دریافت اطلاعات ویدیوی یوتیوب
        
        Args:
            url: آدرس URL ویدیوی یوتیوب
            
        Returns:
            دیکشنری حاوی اطلاعات ویدیو یا None در صورت خطا
        """
        if YOUTUBE_OPTIMIZER_AVAILABLE:
            return get_youtube_video_info(url)
        else:
            try:
                # تنظیمات برای استخراج اطلاعات بدون دانلود
                ydl_opts = self.ydl_opts_base.copy()
                ydl_opts.update({
                    'format': 'best',
                    'skip_download': True,
                    'youtube_include_dash_manifest': False
                })
                
                # اجرای yt-dlp در ترد جداگانه برای جلوگیری از انسداد
                loop = asyncio.get_event_loop()
                
                def extract_info():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        return ydl.extract_info(url, download=False)
                        
                info = await loop.run_in_executor(None, extract_info)
                
                if not info:
                    logger.warning(f"اطلاعات ویدیو برای URL استخراج نشد: {url}")
                    return None
                    
                return info
                
            except Exception as e:
                logger.error(f"خطا در دریافت اطلاعات ویدیوی یوتیوب: {str(e)}")
                traceback.print_exc()
                return None
    
    async def get_download_options(self, url: str) -> List[Dict]:
        """
        دریافت گزینه‌های دانلود برای ویدیوی یوتیوب
        
        Args:
            url: آدرس URL ویدیوی یوتیوب
            
        Returns:
            لیست گزینه‌های دانلود
        """
        try:
            # بررسی کش
            if url in option_cache:
                logger.info(f"استفاده از گزینه‌های دانلود ذخیره شده برای: {url}")
                return option_cache[url]
                
            # دریافت اطلاعات ویدیو
            info = await self.get_video_info(url)
            
            if not info:
                logger.warning(f"اطلاعات ویدیو دریافت نشد: {url}")
                return []
                
            # لیست فرمت‌های موجود
            formats = info.get('formats', [])
            
            # فیلتر کردن فرمت‌های مفید
            filtered_formats = []
            
            # افزودن گزینه‌های ویدیویی
            video_formats = [f for f in formats if 
                            f.get('resolution') != 'audio only' and 
                            not f.get('acodec') == 'none']
                            
            # افزودن گزینه‌های صوتی
            audio_formats = [f for f in formats if f.get('resolution') == 'audio only']
            
            # افزودن برچسب‌های خوانا
            video_options = combine_labels(video_formats)
            audio_options = combine_labels(audio_formats)
            
            # ترکیب گزینه‌ها
            filtered_formats = [f[0] for f in video_options] + [f[0] for f in audio_options]
            
            # افزودن یک گزینه برای دانلود فقط صدا به فرمت MP3
            mp3_option = {
                'format_id': 'bestaudio/best',
                'ext': 'mp3',
                'audio_only': True,
                'format_note': 'فایل MP3',
                'filesize': next((f.get('filesize', 0) for f in audio_formats if f.get('filesize')), 0),
                'vcodec': 'none',
                'acodec': 'mp3'
            }
            filtered_formats.append(mp3_option)
            
            # ذخیره گزینه‌ها در کش
            option_cache[url] = filtered_formats
            
            return filtered_formats
            
        except Exception as e:
            logger.error(f"خطا در دریافت گزینه‌های دانلود یوتیوب: {str(e)}")
            traceback.print_exc()
            return []
    
    async def download_audio(self, url: str) -> Optional[str]:
        """
        دانلود فقط صدای ویدیوی یوتیوب
        
        Args:
            url: آدرس URL ویدیوی یوتیوب
            
        Returns:
            مسیر فایل صوتی دانلود شده یا None در صورت خطا
        """
        # بررسی کش
        cache_key = f"{url}_audio"
        if cache_key in download_cache:
            timestamp, file_path = download_cache[cache_key]
            if os.path.exists(file_path) and time.time() - timestamp < CACHE_TTL:
                logger.info(f"استفاده از فایل صوتی کش شده: {file_path}")
                return file_path
                
        if YOUTUBE_OPTIMIZER_AVAILABLE:
            # استفاده از ماژول بهینه‌سازی دانلود یوتیوب
            video_id = extract_youtube_id(url)
            if not video_id:
                logger.error(f"شناسه ویدیو استخراج نشد: {url}")
                return None
                
            output_path = os.path.join(TEMP_DOWNLOAD_DIR, f"{video_id}.mp3")
            file_path = await asyncio.to_thread(download_with_optimized_settings, url, "mp3", output_path)
            
            if file_path and os.path.exists(file_path):
                # افزودن به کش
                add_to_cache(cache_key, file_path, "mp3")
                return file_path
                
            return None
        else:
            try:
                # تنظیمات برای دانلود فقط صدا با فرمت MP3
                ydl_opts = self.ydl_opts_base.copy()
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'outtmpl': os.path.join(TEMP_DOWNLOAD_DIR, '%(id)s.%(ext)s'),
                    'keepvideo': False
                })
                
                # اجرای yt-dlp در ترد جداگانه
                loop = asyncio.get_event_loop()
                
                def download_audio():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        if info:
                            video_id = info.get('id')
                            if video_id:
                                return os.path.join(TEMP_DOWNLOAD_DIR, f"{video_id}.mp3")
                    return None
                    
                file_path = await loop.run_in_executor(None, download_audio)
                
                if file_path and os.path.exists(file_path):
                    # افزودن به کش
                    add_to_cache(cache_key, file_path, "mp3")
                    return file_path
                    
                return None
                
            except Exception as e:
                logger.error(f"خطا در دانلود صدای یوتیوب: {str(e)}")
                traceback.print_exc()
                return None
    
    async def download_video(self, url: str, format_id: str = 'best') -> Optional[str]:
        """
        دانلود ویدیوی یوتیوب
        
        Args:
            url: آدرس URL ویدیوی یوتیوب
            format_id: شناسه فرمت برای دانلود
            
        Returns:
            مسیر فایل ویدیویی دانلود شده یا None در صورت خطا
        """
        # بررسی کش
        cache_key = f"{url}_{format_id}"
        if cache_key in download_cache:
            timestamp, file_path = download_cache[cache_key]
            if os.path.exists(file_path) and time.time() - timestamp < CACHE_TTL:
                logger.info(f"استفاده از ویدیوی کش شده: {file_path}")
                return file_path
                
        if YOUTUBE_OPTIMIZER_AVAILABLE and format_id in ['1080p', '720p', '480p', '360p', '240p', 'mp3']:
            # استفاده از ماژول بهینه‌سازی دانلود یوتیوب
            video_id = extract_youtube_id(url)
            if not video_id:
                logger.error(f"شناسه ویدیو استخراج نشد: {url}")
                return None
                
            output_path = os.path.join(TEMP_DOWNLOAD_DIR, f"{video_id}_{format_id}.mp4")
            if format_id == 'mp3':
                output_path = os.path.join(TEMP_DOWNLOAD_DIR, f"{video_id}.mp3")
                
            file_path = await asyncio.to_thread(download_with_optimized_settings, url, format_id, output_path)
            
            if file_path and os.path.exists(file_path):
                # بهینه‌سازی فایل برای آپلود اگر حجم آن زیاد است
                file_size = os.path.getsize(file_path)
                if file_size > MAX_TELEGRAM_FILE_SIZE and VIDEO_PROCESSOR_AVAILABLE:
                    logger.info(f"بهینه‌سازی فایل برای آپلود: {file_path}")
                    optimized_path = await asyncio.to_thread(optimize_for_telegram, file_path)
                    if optimized_path and os.path.exists(optimized_path):
                        file_path = optimized_path
                
                # افزودن به کش
                add_to_cache(cache_key, file_path, format_id)
                return file_path
                
            return None
        else:
            try:
                # تنظیمات برای دانلود ویدیو با فرمت مشخص
                ydl_opts = self.ydl_opts_base.copy()
                
                if format_id == 'bestaudio/best':
                    # برای فرمت صوتی
                    ydl_opts.update({
                        'format': 'bestaudio/best',
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '192',
                        }],
                        'outtmpl': os.path.join(TEMP_DOWNLOAD_DIR, '%(id)s.%(ext)s'),
                        'keepvideo': False
                    })
                else:
                    # برای فرمت ویدیویی
                    ydl_opts.update({
                        'format': format_id,
                        'outtmpl': os.path.join(TEMP_DOWNLOAD_DIR, '%(id)s_%(format_id)s.%(ext)s')
                    })
                
                # اجرای yt-dlp در ترد جداگانه
                loop = asyncio.get_event_loop()
                
                def download_video():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        if info:
                            video_id = info.get('id')
                            if video_id:
                                if format_id == 'bestaudio/best':
                                    return os.path.join(TEMP_DOWNLOAD_DIR, f"{video_id}.mp3")
                                else:
                                    filenames = [
                                        f for f in os.listdir(TEMP_DOWNLOAD_DIR) 
                                        if f.startswith(f"{video_id}_") and f.endswith('.mp4')
                                    ]
                                    if filenames:
                                        return os.path.join(TEMP_DOWNLOAD_DIR, filenames[0])
                    return None
                    
                file_path = await loop.run_in_executor(None, download_video)
                
                if file_path and os.path.exists(file_path):
                    # بهینه‌سازی فایل برای آپلود اگر حجم آن زیاد است
                    file_size = os.path.getsize(file_path)
                    if file_size > MAX_TELEGRAM_FILE_SIZE and VIDEO_PROCESSOR_AVAILABLE:
                        logger.info(f"بهینه‌سازی فایل برای آپلود: {file_path}")
                        optimized_path = await asyncio.to_thread(optimize_for_telegram, file_path)
                        if optimized_path and os.path.exists(optimized_path):
                            file_path = optimized_path
                    
                    # افزودن به کش
                    add_to_cache(cache_key, file_path, format_id)
                    return file_path
                    
                return None
                
            except Exception as e:
                logger.error(f"خطا در دانلود ویدیوی یوتیوب: {str(e)}")
                traceback.print_exc()
                return None

class InstagramDownloader:
    """کلاس دانلود ویدیوهای اینستاگرام"""
    
    def __init__(self):
        # کنترل تلاش‌های دانلود اینستاگرام
        self.max_retries = 3
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Connection': 'keep-alive',
            'Referer': 'https://www.instagram.com/'
        })
        
        # آماده‌سازی instaloader برای دانلود پست‌هایی که با روش مستقیم دانلود نمی‌شوند
        try:
            import instaloader
            self.loader = instaloader.Instaloader(
                download_videos=True,
                download_video_thumbnails=False,
                download_geotags=False,
                download_comments=False,
                save_metadata=False,
                compress_json=False,
                filename_pattern="{shortcode}",
                quiet=True
            )
            self.instaloader_available = True
            logger.info("instaloader با موفقیت آماده شد.")
        except Exception as e:
            self.instaloader_available = False
            logger.error(f"خطا در آماده‌سازی instaloader: {str(e)}")
    
    async def direct_download(self, url: str, quality: str = None) -> Optional[str]:
        """
        دانلود مستقیم ویدیوی اینستاگرام با درخواست HTTP - نسخه پیشرفته با پشتیبانی بهتر
        
        Args:
            url: آدرس URL پست اینستاگرام
            quality: کیفیت ویدیو (اختیاری)
            
        Returns:
            مسیر فایل دانلود شده یا None در صورت خطا
        """
        try:
            # استخراج کد کوتاه
            shortcode = extract_instagram_shortcode(url)
            if not shortcode:
                logger.error(f"استخراج کد کوتاه اینستاگرام ناموفق بود: {url}")
                return None
                
            # بررسی کش
            cache_key = f"{url}_{quality}" if quality else url
            if cache_key in download_cache:
                timestamp, file_path = download_cache[cache_key]
                if os.path.exists(file_path) and time.time() - timestamp < CACHE_TTL:
                    logger.info(f"استفاده از فایل کش شده: {file_path}")
                    return file_path
            
            # هدرهای بهبود یافته برای جلوگیری از محدودیت‌ها
            enhanced_headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
                'Referer': 'https://www.instagram.com/',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'cross-site',
                'Pragma': 'no-cache',
                'Cache-Control': 'no-cache'
            }
            
            # به‌روزرسانی هدرهای session
            self.session.headers.update(enhanced_headers)
            
            # دریافت HTML صفحه با چند بار تلاش
            max_retries = 3
            html_content = None
            
            for retry in range(max_retries):
                try:
                    logger.info(f"تلاش {retry+1}/{max_retries} برای دریافت HTML صفحه از {url}")
                    response = self.session.get(url, timeout=15)
                    response.raise_for_status()
                    html_content = response.text
                    break
                except Exception as e:
                    logger.warning(f"خطا در دریافت HTML صفحه (تلاش {retry+1}): {str(e)}")
                    await asyncio.sleep(1)  # کمی صبر قبل از تلاش مجدد
            
            if not html_content:
                logger.error(f"دریافت HTML صفحه پس از {max_retries} تلاش ناموفق بود: {url}")
                return None
            
            # استخراج URL ویدیو از HTML با الگوهای پیشرفته‌تر
            video_url = None
            
            # الگوهای پیشرفته برای استخراج URL ویدیو
            video_patterns = [
                r'"video_url"\s*:\s*"([^"]+)"',
                r'"contentUrl"\s*:\s*"([^"]+)"',
                r'<meta property="og:video" content="([^"]+)"',
                r'<meta property="og:video:secure_url" content="([^"]+)"',
                r'"video_url":"([^"]+)"',
                r'"video":\{"id":"[^"]+","shortcode":"[^"]+","dimensions":\{[^\}]+\},"display_url":"[^"]+","video_url":"([^"]+)"',
                r'<script[^>]*>window\.__additionalDataLoaded\([^{]+(.*\bvideo_url\b.*?)\);</script>',
                r'"video_versions":\[(.*?)\]',
                r'"url":"([^"]+)"[^}]*"type"[^}]*"video"',
                r'property="og:video" content="([^"]+)"',
                # الگوهای جدید برای پست‌های جدید اینستاگرام
                r'"playable_url_quality_hd":"([^"]+)"',
                r'"playable_url":"([^"]+)"',
                r'"dash_manifest":"(.*?)"',
                r'<meta property="og:video:url" content="([^"]+)"',
                r'<meta property="og:url" content="([^"]+)".*?property="og:video"'
            ]
            
            for pattern in video_patterns:
                match = re.search(pattern, html_content)
                if match:
                    # برخی الگوها گروه 1 و برخی گروه 2 را برمی‌گردانند
                    if "video_versions" in pattern:
                        try:
                            # استخراج از آرایه video_versions
                            versions_json = match.group(1)
                            # پیدا کردن اولین URL
                            url_match = re.search(r'"url":"([^"]+)"', versions_json)
                            if url_match:
                                extracted_url = url_match.group(1)
                                # ویدیو را از فرمت JSON خارج می‌کنیم و کاراکترهای escape را درست می‌کنیم
                                video_url = extracted_url.replace('\\u0026', '&').replace('\\/', '/').replace('\\\\', '\\')
                                # حذف escape های اضافی در URL
                                video_url = re.sub(r'\\+([^\\])', r'\1', video_url)
                                logger.info(f"URL ویدیو استخراج شد: {video_url}")
                                break
                        except Exception as e:
                            logger.warning(f"خطا در استخراج URL از video_versions: {str(e)}")
                            continue
                    else:
                        try:
                            # استخراج مستقیم URL
                            extracted_url = match.group(1)
                            # ویدیو را از فرمت JSON خارج می‌کنیم و کاراکترهای escape را درست می‌کنیم
                            video_url = extracted_url.replace('\\u0026', '&').replace('\\/', '/').replace('\\\\', '\\')
                            # حذف escape های اضافی در URL
                            video_url = re.sub(r'\\+([^\\])', r'\1', video_url)
                            logger.info(f"URL ویدیو استخراج شد: {video_url}")
                            break
                        except Exception as e:
                            logger.warning(f"خطا در استخراج مستقیم URL: {str(e)}")
                            continue
                    
            if not video_url:
                logger.error(f"استخراج URL ویدیو ناموفق بود: {url}")
                return None
            
            # تنظیم مسیر خروجی
            final_filename = f"instagram_{shortcode}.mp4"
            final_path = get_unique_filename(TEMP_DOWNLOAD_DIR, final_filename)
            
            # هدرهای مخصوص برای دانلود ویدیو
            download_headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1',
                'Accept': '*/*',
                'Accept-Encoding': 'identity;q=1, *;q=0',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': url,
                'Range': 'bytes=0-',
                'Sec-Fetch-Dest': 'video',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Site': 'cross-site'
            }
            
            # دانلود ویدیو با مدیریت خطای پیشرفته
            loop = asyncio.get_event_loop()
            
            # تابع دانلود - اجرا در thread pool با مدیریت خطای پیشرفته
            def download_file():
                max_dl_retries = 3
                dl_success = False
                
                for dl_retry in range(max_dl_retries):
                    try:
                        # یک بار url را اصلاح می‌کنیم تا کاراکترهای escape باقی‌مانده را درست کنیم
                        cleaned_url = video_url
                        if '\\' in video_url:
                            # حذف کامل همه escape های موجود
                            cleaned_url = video_url.replace('\\u0026', '&').replace('\\/', '/').replace('\\\\', '\\')
                            cleaned_url = re.sub(r'\\+([^\\])', r'\1', cleaned_url)
                            logger.info(f"URL تمیز شده برای دانلود: {cleaned_url}")

                        dl_response = requests.get(cleaned_url, headers=download_headers, stream=True, timeout=30)
                        dl_response.raise_for_status()
                        
                        # بررسی نوع محتوا
                        content_type = dl_response.headers.get('Content-Type', '')
                        if 'video' not in content_type and 'octet-stream' not in content_type:
                            logger.warning(f"هشدار: نوع محتوای دریافتی ویدیو نیست: {content_type}")
                        
                        with open(final_path, 'wb') as f:
                            for chunk in dl_response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        
                        file_size = os.path.getsize(final_path)
                        if file_size > 0:
                            logger.info(f"ویدیو با موفقیت دانلود شد! حجم: {file_size/1024/1024:.2f} MB")
                            dl_success = True
                            break
                        else:
                            logger.warning(f"حجم فایل دانلود شده صفر است! تلاش مجدد {dl_retry+1}/{max_dl_retries}")
                    except Exception as e:
                        logger.warning(f"خطا در دانلود ویدیو (تلاش {dl_retry+1}): {str(e)}")
                        if os.path.exists(final_path):
                            os.remove(final_path)
                
                return dl_success
                
            success = await loop.run_in_executor(None, download_file)
            
            if success:
                # افزودن به کش با کیفیت
                cache_key = f"{url}_{quality}"
                add_to_cache(cache_key, final_path)
                logger.info(f"دانلود با درخواست مستقیم موفق بود: {final_path}")
                return final_path
            else:
                logger.warning("دانلود مستقیم ناموفق بود")
                return None
                
        except Exception as e:
            logger.error(f"خطا در دانلود با درخواست مستقیم: {str(e)}")
            return None
            
    async def get_download_options(self, url: str) -> List[Dict]:
        """
        دریافت گزینه‌های دانلود برای ویدیوی اینستاگرام
        
        Args:
            url: آدرس URL ویدیوی اینستاگرام
            
        Returns:
            لیست گزینه‌های دانلود
        """
        try:
            # بررسی کش
            if url in option_cache:
                logger.info(f"استفاده از گزینه‌های دانلود ذخیره شده برای: {url}")
                return option_cache[url]
                
            # تلاش برای دانلود مستقیم برای بررسی وجود ویدیو
            test_download = await self.direct_download(url)
            
            options = []
            
            if test_download:
                # فایل ویدیویی یافت شد، اضافه کردن گزینه‌های کیفیت
                file_size = os.path.getsize(test_download)
                
                if file_size > 0:
                    # گزینه‌های نمایشی
                    options = [
                        {
                            'format_id': 'fallback_1080p',
                            'format_note': '1080p',
                            'ext': 'mp4',
                            'filesize': file_size,
                            'height': 1080,
                            'vcodec': 'h264',
                            'acodec': 'aac'
                        },
                        {
                            'format_id': 'fallback_720p',
                            'format_note': '720p',
                            'ext': 'mp4',
                            'filesize': file_size * 0.75,
                            'height': 720,
                            'vcodec': 'h264',
                            'acodec': 'aac'
                        },
                        {
                            'format_id': 'fallback_360p',
                            'format_note': '360p',
                            'ext': 'mp4',
                            'filesize': file_size * 0.5,
                            'height': 360,
                            'vcodec': 'h264',
                            'acodec': 'aac'
                        },
                        {
                            'format_id': 'fallback_240p',
                            'format_note': '240p',
                            'ext': 'mp4',
                            'filesize': file_size * 0.3,
                            'height': 240,
                            'vcodec': 'h264',
                            'acodec': 'aac'
                        },
                        {
                            'format_id': 'mp3',
                            'format_note': 'فقط صدا',
                            'ext': 'mp3',
                            'filesize': file_size * 0.1,
                            'vcodec': 'none',
                            'acodec': 'mp3',
                            'resolution': 'audio only'
                        }
                    ]
            
            # ذخیره گزینه‌ها در کش
            option_cache[url] = options
            
            return options
            
        except Exception as e:
            logger.error(f"خطا در دریافت گزینه‌های دانلود اینستاگرام: {str(e)}")
            return []
    
    async def download_with_quality(self, url: str, quality: str) -> Optional[str]:
        """
        دانلود ویدیوی اینستاگرام با کیفیت مشخص
        
        Args:
            url: آدرس URL ویدیوی اینستاگرام
            quality: کیفیت مورد نظر
            
        Returns:
            مسیر فایل دانلود شده یا None در صورت خطا
        """
        try:
            # بررسی کش
            cache_key = f"{url}_{quality}"
            if cache_key in download_cache:
                timestamp, file_path = download_cache[cache_key]
                if os.path.exists(file_path) and time.time() - timestamp < CACHE_TTL:
                    logger.info(f"استفاده از فایل کش شده: {file_path}")
                    return file_path
            
            # استخراج کد کوتاه
            shortcode = extract_instagram_shortcode(url)
            if not shortcode:
                logger.error(f"استخراج کد کوتاه اینستاگرام ناموفق بود: {url}")
                return None
                
            # ابتدا با دانلود مستقیم تلاش می‌کنیم
            input_file = await self.direct_download(url)
            
            if not input_file or not os.path.exists(input_file):
                logger.error(f"دانلود مستقیم فایل شکست خورد: {url}")
                return None
                
            # بررسی نوع درخواست
            if 'mp3' in quality or quality == 'audio':
                # استخراج صدا
                audio_path = os.path.join(
                    TEMP_DOWNLOAD_DIR, 
                    f"instagram_{shortcode}_audio_{int(time.time())%1000000:06d}.mp3"
                )
                
                if VIDEO_PROCESSOR_AVAILABLE:
                    output_path = await asyncio.to_thread(vp_extract_audio, input_file, audio_path)
                else:
                    output_path = extract_audio(input_file, audio_path)
                    
                if output_path and os.path.exists(output_path):
                    # افزودن به کش
                    add_to_cache(cache_key, output_path, quality)
                    return output_path
                else:
                    logger.error(f"استخراج صدا ناموفق بود: {input_file}")
                    return None
            elif quality in ['fallback_1080p', 'fallback_720p', 'fallback_480p', 'fallback_360p', 'fallback_240p']:
                # تبدیل کیفیت
                resolution = quality.replace('fallback_', '')
                
                if VIDEO_PROCESSOR_AVAILABLE:
                    converted_path = get_unique_filename(
                        TEMP_DOWNLOAD_DIR, 
                        f"instagram_{shortcode}_{resolution}.mp4"
                    )
                    
                    output_path = await asyncio.to_thread(
                        convert_video_quality, 
                        input_file, 
                        resolution, 
                        converted_path
                    )
                    
                    if output_path and os.path.exists(output_path):
                        # افزودن به کش
                        add_to_cache(cache_key, output_path, quality)
                        return output_path
                    else:
                        # برگشت به فایل اصلی
                        logger.warning(f"تبدیل کیفیت ناموفق بود. استفاده از فایل اصلی: {input_file}")
                        add_to_cache(cache_key, input_file, quality)
                        return input_file
                else:
                    # بدون تبدیل کیفیت، فایل اصلی را برمی‌گردانیم
                    logger.warning(f"ماژول پردازش ویدیو در دسترس نیست. استفاده از فایل اصلی: {input_file}")
                    add_to_cache(cache_key, input_file, quality)
                    return input_file
            else:
                # فایل اصلی را برمی‌گردانیم
                add_to_cache(cache_key, input_file, quality)
                return input_file
                
        except Exception as e:
            logger.error(f"خطا در دانلود ویدیوی اینستاگرام با کیفیت {quality}: {str(e)}")
            return None

"""
بخش 4: توابع پردازش درخواست‌های تلگرام
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پاسخ به دستور /start
    
    Args:
        update: شیء آپدیت تلگرام
        context: شیء کانتکست تلگرام
    """
    user = update.effective_user
    await update.message.reply_text(
        f"👋 سلام {user.first_name}!\n\n"
        "🎬 من یک ربات دانلود ویدیو برای اینستاگرام و یوتیوب هستم.\n\n"
        "📱 برای استفاده، لینک ویدیوی اینستاگرام یا یوتیوب را برای من ارسال کنید.\n\n"
        "📝 همچنین می‌توانید از دستور /help برای مشاهده راهنما استفاده کنید."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پاسخ به دستور /help
    
    Args:
        update: شیء آپدیت تلگرام
        context: شیء کانتکست تلگرام
    """
    await update.message.reply_text(
        "🔍 راهنمای استفاده:\n\n"
        "1️⃣ برای دانلود ویدیو از اینستاگرام یا یوتیوب، کافی است لینک آن را برای من ارسال کنید.\n\n"
        "2️⃣ پس از ارسال لینک، فهرستی از کیفیت‌های موجود برای دانلود را دریافت خواهید کرد.\n\n"
        "3️⃣ با انتخاب کیفیت مورد نظر، فرآیند دانلود آغاز می‌شود.\n\n"
        "4️⃣ پس از تکمیل دانلود، فایل ویدیو یا صوتی برای شما ارسال خواهد شد.\n\n"
        "📌 نکات مهم:\n"
        "• حداکثر حجم فایل قابل ارسال 50 مگابایت است.\n"
        "• برای دانلود فقط صدا، گزینه 'فقط صدا' را انتخاب کنید.\n"
        "• به دلیل محدودیت‌های تلگرام، ممکن است زمان دانلود طولانی شود."
    )

async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش پیام‌های ورودی
    
    Args:
        update: شیء آپدیت تلگرام
        context: شیء کانتکست تلگرام
    """
    # بررسی وجود URL در پیام
    text = update.message.text
    url = extract_url(text)
    
    if not url:
        await update.message.reply_text(
            "❌ لینک شناسایی نشد. لطفاً یک لینک معتبر از اینستاگرام یا یوتیوب ارسال کنید."
        )
        return
        
    # بررسی نوع URL
    if ENHANCED_MODE:
        # استفاده از حالت بهینه‌سازی شده
        enhanced_handler = get_enhanced_handler()
        
        if enhanced_handler.is_youtube_url(url):
            await enhanced_handler.handle_youtube_url(update, context, url)
            return
    else:
        if is_youtube_url(url):
            # در صورت استفاده از حالت استاندارد
            await process_youtube_link(update, context, url)
            return
            
    if is_instagram_url(url):
        await process_instagram_link(update, context, url)
        return
        
    # URL ناشناخته
    await update.message.reply_text(
        "❌ لینک شناسایی نشد. لطفاً یک لینک معتبر از اینستاگرام یا یوتیوب ارسال کنید."
    )

async def process_youtube_link(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str) -> None:
    """
    پردازش لینک یوتیوب
    
    Args:
        update: شیء آپدیت تلگرام
        context: شیء کانتکست تلگرام
        url: آدرس URL یوتیوب
    """
    chat_id = update.effective_chat.id
    
    # ذخیره URL در حافظه پایدار
    persistent_url_storage[chat_id] = url
    
    # ارسال پیام در حال دریافت اطلاعات
    processing_message = await update.message.reply_text(STATUS_MESSAGES["getting_options"])
    
    # ایجاد دانلودر یوتیوب
    downloader = YoutubeDownloader()
    
    # دریافت اطلاعات ویدیو
    info = await downloader.get_video_info(url)
    
    if not info:
        await processing_message.edit_text(ERROR_MESSAGES["extraction_failed"])
        return
        
    # دریافت گزینه‌های دانلود
    formats = await downloader.get_download_options(url)
    
    if not formats:
        await processing_message.edit_text(ERROR_MESSAGES["extraction_failed"])
        return
        
    # ذخیره اطلاعات ویدیو در context.user_data
    if 'video_info' not in context.user_data:
        context.user_data['video_info'] = {}
        
    video_id = info.get('id', 'unknown')
    context.user_data['video_info'][video_id] = info
    context.user_data['current_url'] = url
    
    # ایجاد دکمه‌های انتخاب کیفیت
    keyboard = []
    
    # دکمه‌های کیفیت‌های ویدیویی
    video_buttons = []
    for fmt in formats:
        if fmt.get('resolution') != 'audio only' and fmt.get('vcodec') != 'none':
            label = get_format_label(fmt)
            format_id = fmt.get('format_id', '')
            
            # ایجاد کلید درون‌خطی با سقف 2 دکمه در هر ردیف
            video_buttons.append(
                InlineKeyboardButton(label, callback_data=f"yt_{video_id}_{format_id}")
            )
            
            # اگر تعداد دکمه‌ها به 2 رسید، یک ردیف جدید اضافه می‌کنیم
            if len(video_buttons) == 2:
                keyboard.append(video_buttons)
                video_buttons = []
    
    # اضافه کردن دکمه‌های باقیمانده
    if video_buttons:
        keyboard.append(video_buttons)
    
    # دکمه‌های صوتی
    audio_buttons = []
    for fmt in formats:
        if fmt.get('resolution') == 'audio only' or fmt.get('vcodec') == 'none' or 'mp3' in fmt.get('format_id', ''):
            label = get_format_label(fmt)
            format_id = fmt.get('format_id', '')
            
            audio_buttons.append(
                InlineKeyboardButton(label, callback_data=f"yt_{video_id}_{format_id}")
            )
    
    if audio_buttons:
        keyboard.append(audio_buttons)
    
    # اطلاعات ویدیو
    title = info.get('title', 'ویدیوی ناشناس')
    uploader = info.get('uploader', 'کاربر ناشناس')
    duration = info.get('duration')
    duration_str = f"{duration//60}:{duration%60:02d}" if duration else "نامشخص"
    
    # ارسال پیام با اطلاعات ویدیو و دکمه‌های انتخاب کیفیت
    await processing_message.edit_text(
        f"🎬 <b>{title}</b>\n\n"
        f"👤 کانال: {uploader}\n"
        f"⏱ مدت: {duration_str}\n\n"
        "📊 لطفاً کیفیت مورد نظر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def process_instagram_link(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str) -> None:
    """
    پردازش لینک اینستاگرام با قابلیت‌های پیشرفته
    
    Args:
        update: شیء آپدیت تلگرام
        context: شیء کانتکست تلگرام
        url: آدرس URL اینستاگرام
    """
    chat_id = update.effective_chat.id
    
    # ذخیره URL در حافظه پایدار
    persistent_url_storage[chat_id] = url
    
    # ارسال پیام در حال دریافت اطلاعات با آیکون زیباتر
    processing_message = await update.message.reply_text(
        "🔍 در حال پردازش لینک اینستاگرام...\n"
        "⏳ لطفاً کمی صبر کنید..."
    )
    
    # ایجاد دانلودر اینستاگرام
    downloader = InstagramDownloader()
    
    # استخراج کد کوتاه ابتدا
    shortcode = extract_instagram_shortcode(url)
    if not shortcode:
        await processing_message.edit_text("❌ خطا: نمی‌توان کد شناسایی پست اینستاگرام را استخراج کرد.\nلطفاً لینک معتبری وارد کنید.")
        return
        
    # پیام مرحله‌ای - اعلام استخراج اطلاعات
    await processing_message.edit_text(
        f"🎬 پست اینستاگرام شناسایی شد: <code>{shortcode}</code>\n"
        "📥 در حال دانلود ویدیو...",
        parse_mode='HTML'
    )
    
    # تلاش برای دانلود مستقیم
    try:
        test_file = await downloader.direct_download(url)
        
        if not test_file:
            await processing_message.edit_text(
                "❌ دانلود ویدیو ناموفق بود!\n\n"
                "احتمالاً این پست خصوصی است یا ویدیو ندارد.\n"
                "لطفاً از لینک پست عمومی که شامل ویدیو است استفاده کنید."
            )
            return
            
        # اعلام موفقیت در دانلود
        file_size = os.path.getsize(test_file)
        size_str = f"{file_size/1024/1024:.1f} MB" if file_size > 1024*1024 else f"{file_size/1024:.1f} KB"
        
        await processing_message.edit_text(
            f"✅ ویدیو با موفقیت دانلود شد! ({size_str})\n"
            "⚙️ در حال آماده‌سازی گزینه‌های کیفیت..."
        )
        
        # دریافت گزینه‌های دانلود
        formats = await downloader.get_download_options(url)
        
        # ذخیره اطلاعات در context.user_data
        if 'insta_info' not in context.user_data:
            context.user_data['insta_info'] = {}
            
        context.user_data['insta_info'][shortcode] = {
            'url': url,
            'formats': formats
        }
        context.user_data['current_url'] = url
        
        # ایجاد دکمه‌های انتخاب کیفیت با طراحی زیباتر
        keyboard = []
        
        # دکمه‌های کیفیت‌های ویدیویی
        video_buttons = []
        
        # آیکون‌های مناسب برای هر کیفیت
        quality_icons = {
            '1080p': '🎞️',
            '720p': '📹',
            '480p': '📱',
            '360p': '💻',
            '240p': '📲',
            'mp3': '🎵'
        }
        
        for fmt in formats:
            if fmt.get('resolution') != 'audio only' and fmt.get('vcodec') != 'none':
                format_id = fmt.get('format_id', '')
                format_note = fmt.get('format_note', '')
                
                # انتخاب آیکون مناسب برای کیفیت
                icon = quality_icons.get(format_note, '🎥')
                
                # حجم تقریبی
                file_size = fmt.get('filesize', 0)
                size_text = f"{file_size/1024/1024:.1f}MB" if file_size else "نامشخص"
                
                # برچسب دکمه با فرمت زیبا
                label = f"{icon} {format_note} ({size_text})"
                
                video_buttons.append(
                    InlineKeyboardButton(label, callback_data=f"ig_{shortcode}_{format_id}")
                )
                
                if len(video_buttons) == 2:
                    keyboard.append(video_buttons)
                    video_buttons = []
        
        if video_buttons:
            keyboard.append(video_buttons)
        
        # دکمه صوتی با طراحی زیباتر
        if any(fmt.get('resolution') == 'audio only' or fmt.get('vcodec') == 'none' for fmt in formats):
            keyboard.append([
                InlineKeyboardButton("🎵 فقط صدا (MP3)", callback_data=f"ig_{shortcode}_mp3")
            ])
        
        # دکمه‌های اضافی برای کاربردپذیری بیشتر
        keyboard.append([
            InlineKeyboardButton("♻️ بروزرسانی", callback_data=f"refresh_ig_{shortcode}"),
            InlineKeyboardButton("❌ لغو", callback_data="cancel")
        ])
        
        # افزودن دکمه دانلود کارت پست (عکس+متن)
        keyboard.append([
            InlineKeyboardButton("🖼️ دانلود کارت پست", callback_data=f"card_ig_{shortcode}")
        ])
        
        # ارسال پیام با اطلاعات پست و دکمه‌های انتخاب کیفیت
        await processing_message.edit_text(
            f"📱 <b>پست اینستاگرام</b>\n\n"
            f"🔖 شناسه: <code>{shortcode}</code>\n"
            f"🔗 <a href='{url}'>مشاهده در اینستاگرام</a>\n\n"
            "📊 لطفاً کیفیت مورد نظر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML',
            disable_web_page_preview=True
        )
    except Exception as e:
        # مدیریت خطاها با پیام‌های راهنمای کاربر
        import traceback
        logger.error(f"خطا در پردازش لینک اینستاگرام: {str(e)}")
        logger.error(traceback.format_exc())
        
        error_message = (
            "❌ متأسفانه خطایی در پردازش این لینک رخ داد.\n\n"
            "لطفاً موارد زیر را بررسی کنید:\n"
            "• لینک معتبر و عمومی باشد (پست‌های خصوصی قابل دانلود نیستند)\n"
            "• پست حاوی ویدیو باشد (تصاویر قابل دانلود نیستند)\n"
            "• از لینک کامل استفاده کنید (مثال: https://www.instagram.com/p/CODE/)\n\n"
            "می‌توانید با لینک دیگری مجدداً تلاش کنید."
        )
        
        await processing_message.edit_text(error_message)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش دکمه‌های فشرده شده
    
    Args:
        update: شیء آپدیت تلگرام
        context: شیء کانتکست تلگرام
    """
    query = update.callback_query
    await query.answer()
    
    # دریافت اطلاعات دکمه
    data = query.data
    chat_id = update.effective_chat.id
    
    # ذخیره آخرین دکمه برای حل مشکل لینک منقضی شده
    recent_button_clicks[chat_id] = data
    
    if data == "cancel":
        # لغو عملیات فعلی با پیام دوستانه‌تر
        await query.edit_message_text(
            "⚠️ عملیات لغو شد.\n\n"
            "می‌توانید لینک دیگری ارسال کنید یا از دستور /help برای راهنمایی استفاده کنید."
        )
        return
        
    elif data.startswith("refresh_ig_"):
        # بروزرسانی کیفیت‌های دریافتی برای پست اینستاگرام
        shortcode = data.split("_", 2)[2]
        
        # اعلام به کاربر که بروزرسانی در حال انجام است
        await query.edit_message_text(
            "♻️ در حال بروزرسانی اطلاعات پست اینستاگرام...\n"
            "⏳ لطفاً کمی صبر کنید."
        )
        
        # URL اصلی از کش
        if 'insta_info' in context.user_data and shortcode in context.user_data['insta_info']:
            url = context.user_data['insta_info'][shortcode].get('url')
            
            if url:
                try:
                    # دریافت مجدد اطلاعات با پردازش کامل
                    await process_instagram_link(update, context, url)
                    return
                except Exception as e:
                    # مدیریت خطا در بروزرسانی
                    logger.error(f"خطا در بروزرسانی اطلاعات اینستاگرام: {str(e)}")
                    await query.edit_message_text(
                        "❌ متأسفانه بروزرسانی اطلاعات با خطا مواجه شد.\n\n"
                        "لطفاً لینک را مجدداً ارسال کنید یا لینک دیگری امتحان کنید."
                    )
                    return
        
        # اگر اطلاعات یافت نشد
        await query.edit_message_text(
            "❌ اطلاعات پست برای بروزرسانی پیدا نشد.\n\n"
            "لطفاً لینک را دوباره ارسال کنید."
        )
        
    elif data.startswith("yt_"):
        # دکمه‌های یوتیوب
        _, video_id, format_id = data.split("_", 2)
        
        # بررسی اطلاعات ویدیو در context.user_data
        video_info = context.user_data.get('video_info', {}).get(video_id)
        
        if not video_info:
            # اطلاعات ویدیو وجود ندارد - احتمالاً لینک منقضی شده
            await query.edit_message_text(ERROR_MESSAGES["link_expired"])
            return
            
        # بررسی آیا فرمت فقط صوتی است
        is_audio = format_id == 'bestaudio/best' or format_id == 'mp3'
        
        # ارسال پیام در حال دانلود
        await query.edit_message_text(STATUS_MESSAGES["downloading"])
        
        # ایجاد دانلودر یوتیوب
        downloader = YoutubeDownloader()
        
        # URL اصلی
        url = context.user_data.get('current_url') or video_info.get('webpage_url')
        
        if not url:
            # URL وجود ندارد
            await query.edit_message_text(ERROR_MESSAGES["link_expired"])
            return
            
        # انتخاب روش دانلود بر اساس نوع فایل
        if is_audio:
            # دانلود فقط صدا
            if ENHANCED_MODE:
                enhanced_handler = get_enhanced_handler()
                await enhanced_handler.download_youtube_with_quality(update, context, video_id, 'mp3')
                return
            else:
                downloaded_file = await downloader.download_audio(url)
        else:
            # دانلود ویدیو با فرمت مشخص
            if ENHANCED_MODE and format_id in ['1080p', '720p', '480p', '360p', '240p']:
                enhanced_handler = get_enhanced_handler()
                await enhanced_handler.download_youtube_with_quality(update, context, video_id, format_id)
                return
            else:
                downloaded_file = await downloader.download_video(url, format_id)
        
        # بررسی موفقیت دانلود
        if not downloaded_file or not os.path.exists(downloaded_file):
            await query.edit_message_text(ERROR_MESSAGES["download_failed"])
            return
            
        # بررسی حجم فایل
        file_size = os.path.getsize(downloaded_file)
        if file_size > MAX_TELEGRAM_FILE_SIZE:
            await query.edit_message_text(ERROR_MESSAGES["file_too_large"])
            return
            
        # ارسال پیام در حال آپلود
        await query.edit_message_text(STATUS_MESSAGES["uploading"])
        
        # ارسال فایل بر اساس نوع آن
        if is_audio or downloaded_file.endswith(('.mp3', '.m4a', '.aac', '.wav')):
            # ارسال فایل صوتی
            with open(downloaded_file, 'rb') as audio_file:
                caption = f"🎵 صدای دانلود شده از یوتیوب\n💾 حجم: {human_readable_size(file_size)}"
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=audio_file,
                    caption=caption,
                    title=video_info.get('title'),
                    performer=video_info.get('uploader')
                )
        else:
            # ارسال ویدیو
            with open(downloaded_file, 'rb') as video_file:
                caption = f"🎬 {video_info.get('title')}\n💾 حجم: {human_readable_size(file_size)}"
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=video_file,
                    caption=caption,
                    supports_streaming=True
                )
                
        # پاکسازی پیام قبلی
        await query.edit_message_text("✅ دانلود و ارسال با موفقیت انجام شد.")
        
    elif data.startswith("card_ig_"):
        # دکمه کارت پست اینستاگرام
        _, _, shortcode = data.split("_", 2)
        
        # بررسی اطلاعات پست در context.user_data
        post_info = context.user_data.get('insta_info', {}).get(shortcode)
        
        if not post_info:
            # اطلاعات پست وجود ندارد - احتمالاً لینک منقضی شده
            await query.edit_message_text(ERROR_MESSAGES["link_expired"])
            return
            
        # URL اصلی
        url = post_info.get('url') or context.user_data.get('current_url')
        
        if not url:
            # URL وجود ندارد
            await query.edit_message_text(ERROR_MESSAGES["link_expired"])
            return
            
        # نمایش پیام مرحله‌ای
        await query.edit_message_text(
            "🖼️ در حال ایجاد کارت پست اینستاگرام...\n\n"
            "⏳ لطفاً صبر کنید، این عملیات ممکن است کمی طول بکشد."
        )
        
        try:
            # دانلود مستقیم برای دریافت تصویر بندانگشتی
            downloader = InstagramDownloader()
            video_file = await downloader.direct_download(url)
            
            if not video_file:
                await query.edit_message_text("❌ دانلود محتوای پست برای ایجاد کارت پست ناموفق بود.")
                return
                
            # استخراج فریم از ویدیو برای استفاده به عنوان تصویر کارت پست
            thumbnail_path = os.path.join(TEMP_DOWNLOAD_DIR, f"card_thumbnail_{shortcode}.jpg")
            
            # استفاده از ffmpeg برای استخراج فریم
            import subprocess
            cmd = [
                'ffmpeg', '-i', video_file, 
                '-ss', '00:00:01', '-vframes', '1', 
                '-q:v', '2', thumbnail_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd, 
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            _, stderr = await process.communicate()
            
            if process.returncode != 0 or not os.path.exists(thumbnail_path):
                logger.error(f"استخراج فریم ناموفق بود: {stderr.decode()}")
                await query.edit_message_text("❌ ایجاد کارت پست ناموفق بود - خطا در استخراج تصویر.")
                return
                
            # ارسال تصویر با کپشن زیبا
            with open(thumbnail_path, 'rb') as photo_file:
                caption = (
                    f"📱 <b>پست اینستاگرام</b>\n\n"
                    f"🔖 <code>{shortcode}</code>\n"
                    f"👁️ <a href='{url}'>مشاهده پست اصلی</a>\n\n"
                    f"⬇️ با استفاده از ربات @{context.bot.username} می‌توانید ویدیوهای اینستاگرام و یوتیوب را دانلود کنید."
                )
                
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo_file,
                    caption=caption,
                    parse_mode='HTML'
                )
                
            # پاکسازی پیام قبلی
            await query.edit_message_text("✅ کارت پست با موفقیت ایجاد و ارسال شد.")
            
            # پاکسازی فایل‌های موقت
            try:
                if os.path.exists(thumbnail_path):
                    os.remove(thumbnail_path)
            except Exception as e:
                logger.warning(f"خطا در پاکسازی فایل موقت: {e}")
                
        except Exception as e:
            import traceback
            logger.error(f"خطا در ایجاد کارت پست: {str(e)}")
            logger.error(traceback.format_exc())
            
            await query.edit_message_text(
                "❌ متأسفانه خطایی در ایجاد کارت پست رخ داد.\n"
                "لطفاً دوباره تلاش کنید."
            )
            
    elif data.startswith("ig_"):
        # دکمه‌های اینستاگرام
        _, shortcode, format_id = data.split("_", 2)
        
        # بررسی اطلاعات پست در context.user_data
        post_info = context.user_data.get('insta_info', {}).get(shortcode)
        
        if not post_info:
            # اطلاعات پست وجود ندارد - احتمالاً لینک منقضی شده
            await query.edit_message_text(ERROR_MESSAGES["link_expired"])
            return
            
        # URL اصلی
        url = post_info.get('url') or context.user_data.get('current_url')
        
        if not url:
            # URL وجود ندارد
            await query.edit_message_text(ERROR_MESSAGES["link_expired"])
            return
            
        # نمایش پیام مرحله‌ای دانلود با استفاده از ایموجی‌های جذاب
        await query.edit_message_text(
            "📥 در حال دانلود ویدیوی اینستاگرام...\n\n"
            "⏳ لطفاً صبر کنید، این عملیات ممکن است کمی طول بکشد."
        )
        
        # ایجاد دانلودر اینستاگرام
        downloader = InstagramDownloader()
        
        # انتخاب روش دانلود بر اساس نوع فایل
        is_audio = format_id == 'mp3'
        
        try:
            if is_audio:
                # به روزرسانی پیام با اطلاعات مرحله فعلی
                await query.edit_message_text(
                    "🔍 دریافت ویدیوی اصلی از اینستاگرام...\n"
                    "🎵 آماده‌سازی برای استخراج صدا..."
                )
                
                # دانلود مستقیم اولیه
                source_file = await downloader.direct_download(url)
                
                if not source_file or not os.path.exists(source_file):
                    await query.edit_message_text(
                        "❌ دانلود ویدیو ناموفق بود!\n\n"
                        "احتمالاً این پست خصوصی است یا محتوای آن تغییر کرده است.\n"
                        "لطفاً دوباره تلاش کنید یا از لینک دیگری استفاده کنید."
                    )
                    return
                    
                # استخراج صدا با پیام مرحله‌ای جدید
                await query.edit_message_text(
                    "🎬 ویدیو با موفقیت دانلود شد!\n"
                    "🔊 در حال استخراج صدا از ویدیو...\n\n"
                    "⚙️ این مرحله نیاز به پردازش دارد، لطفاً صبر کنید."
                )
                
                # ایجاد نام فایل خروجی منحصر به فرد
                unique_id = f"{int(time.time())%1000000:06d}"
                output_path = os.path.join(
                    TEMP_DOWNLOAD_DIR, 
                    f"instagram_{shortcode}_audio_{unique_id}.mp3"
                )
                
                # انتخاب روش مناسب برای استخراج صدا
                if VIDEO_PROCESSOR_AVAILABLE:
                    downloaded_file = await asyncio.to_thread(vp_extract_audio, source_file, output_path)
                else:
                    # اگر ماژول پردازش پیشرفته در دسترس نیست از روش استاندارد استفاده می‌کنیم
                    downloaded_file = extract_audio(source_file, 'mp3', '192k')
                    
                if not downloaded_file or not os.path.exists(downloaded_file):
                    # تلاش با روش جایگزین در صورت شکست
                    logger.warning(f"روش اول استخراج صدا شکست خورد، تلاش با روش دوم برای: {source_file}")
                    # پیام به کاربر
                    await query.edit_message_text(
                        "⚠️ استخراج صدا با روش اول ناموفق بود.\n"
                        "🔄 در حال تلاش با روش جایگزین..."
                    )
                    
                    # استفاده از تابع استخراج صدا از ماژول audio_processing
                    from audio_processing import extract_audio as extract_audio_fallback
                    downloaded_file = extract_audio_fallback(source_file, 'mp3', '192k')
                
                if not downloaded_file or not os.path.exists(downloaded_file):
                    logger.error(f"تمام روش‌های استخراج صدا شکست خورد برای فایل: {source_file}")
                    await query.edit_message_text(
                        "❌ استخراج صدا ناموفق بود.\n\n"
                        "متأسفانه ویدیوی مورد نظر قابلیت استخراج صدا را ندارد یا فرمت آن پشتیبانی نمی‌شود.\n"
                        "لطفاً یک گزینه ویدیویی را انتخاب کنید."
                    )
                    return
                    
                # افزودن به کش با کیفیت
                add_to_cache(url, downloaded_file, "audio")
                
                # به روزرسانی پیام با موفقیت استخراج صدا
                await query.edit_message_text(
                    "✅ صدا با موفقیت استخراج شد!\n"
                    "📤 در حال آپلود فایل صوتی به تلگرام..."
                )
                
            else:
                # دانلود محتوا با فرمت انتخاب شده
                format_option = format_id
                logger.info(f"فرمت انتخاب شده برای دانلود ویدیو: {format_option}")
                
                # پیام مرحله‌ای جدید با اطلاعات کیفیت
                format_name = format_option.replace('fallback_', '')
                await query.edit_message_text(
                    f"📥 در حال دانلود ویدیو با کیفیت {format_name}...\n"
                    "🔄 این عملیات ممکن است چند لحظه طول بکشد."
                )
                
                downloaded_file = await downloader.download_with_quality(url, format_option)
                
                # اگر دانلود ناموفق بود، تلاش مجدد با روش مستقیم
                if not downloaded_file or not os.path.exists(downloaded_file):
                    await query.edit_message_text(
                        "⚠️ دانلود با کیفیت انتخاب شده ناموفق بود.\n"
                        "🔄 در حال تلاش با روش جایگزین..."
                    )
                    
                    # تلاش با دانلود مستقیم
                    downloaded_file = await downloader.direct_download(url)
            
            # بررسی موفقیت دانلود
            if not downloaded_file or not os.path.exists(downloaded_file):
                await query.edit_message_text(
                    "❌ دانلود ناموفق بود!\n\n"
                    "احتمالاً پست از دسترس خارج شده یا خصوصی است.\n"
                    "لطفاً دوباره تلاش کنید یا از لینک دیگری استفاده کنید."
                )
                return
                
            # بررسی حجم فایل
            file_size = os.path.getsize(downloaded_file)
            if file_size > MAX_TELEGRAM_FILE_SIZE:
                await query.edit_message_text(
                    "❌ حجم فایل بیشتر از محدودیت تلگرام است!\n\n"
                    f"حجم فایل: {human_readable_size(file_size)}\n"
                    f"حداکثر مجاز: {human_readable_size(MAX_TELEGRAM_FILE_SIZE)}\n\n"
                    "لطفاً کیفیت پایین‌تری را انتخاب کنید."
                )
                return
                
            # ارسال پیام آماده‌سازی برای آپلود
            # اضافه کردن اندازه فایل به پیام برای اطلاع کاربر
            size_str = human_readable_size(file_size)
            await query.edit_message_text(
                f"✅ دانلود با موفقیت انجام شد! ({size_str})\n"
                "📤 در حال آپلود به تلگرام...\n\n"
                "⏳ بسته به سرعت اینترنت و اندازه فایل، این عملیات ممکن است کمی طول بکشد."
            )
            
            # ارسال فایل با رابط کاربری بهتر
            if is_audio or downloaded_file.endswith(('.mp3', '.m4a', '.aac', '.wav')):
                # ارسال فایل صوتی با کپشن جذاب‌تر
                with open(downloaded_file, 'rb') as audio_file:
                    # کپشن غنی‌تر با اطلاعات بیشتر
                    caption = (
                        f"🎵 <b>صدای دانلود شده از اینستاگرام</b>\n\n"
                        f"🔖 <code>{shortcode}</code>\n"
                        f"💾 حجم: {human_readable_size(file_size)}\n"
                        f"🔗 <a href='{url}'>مشاهده پست اصلی</a>"
                    )
                    
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=audio_file,
                        caption=caption,
                        title=f"Instagram Audio - {shortcode}",
                        parse_mode='HTML',
                        performer="Instagram Audio"
                    )
            else:
                # ارسال ویدیو با کپشن غنی‌تر
                with open(downloaded_file, 'rb') as video_file:
                    # متن کپشن جذاب‌تر با اطلاعات بیشتر
                    format_name = format_id.replace('fallback_', '')
                    caption = (
                        f"📱 <b>ویدیوی اینستاگرام</b>\n\n"
                        f"🔖 <code>{shortcode}</code>\n"
                        f"📊 کیفیت: {format_name}\n"
                        f"💾 حجم: {human_readable_size(file_size)}\n"
                        f"🔗 <a href='{url}'>مشاهده پست اصلی</a>"
                    )
                    
                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=video_file,
                        caption=caption,
                        supports_streaming=True,
                        parse_mode='HTML'
                    )
                    
            # پیام تأیید نهایی با ایموجی‌های شاد
            await query.edit_message_text(
                "✅ دانلود و ارسال با موفقیت انجام شد! 🎉\n\n"
                "می‌توانید لینک دیگری ارسال کنید یا از دستور /help برای راهنمایی استفاده کنید."
            )
            
        except Exception as e:
            # مدیریت خطاها با پیام‌های دوستانه و راهنمایی
            import traceback
            logger.error(f"خطا در پردازش دکمه اینستاگرام: {str(e)}")
            logger.error(traceback.format_exc())
            
            # ارسال پیام خطای کاربرپسند به کاربر
            await query.edit_message_text(
                "❌ متأسفانه خطایی در پردازش درخواست شما رخ داد.\n\n"
                "این می‌تواند به دلایل زیر باشد:\n"
                "• محدودیت‌های اینستاگرام برای دانلود\n"
                "• تغییر در محتوای پست یا حذف آن\n"
                "• خصوصی شدن پست پس از ارسال لینک\n\n"
                "لطفاً دوباره تلاش کنید یا لینک دیگری ارسال کنید."
            )

"""
بخش 5: آزمایش و خطایابی
"""

def run_tests() -> bool:
    """
    اجرای تست‌های اساسی برای اطمینان از صحت عملکرد
    
    Returns:
        نتیجه تست‌ها (True در صورت موفقیت، False در صورت شکست)
    """
    print("🧪 در حال اجرای تست‌های ربات...")
    
    test_results = []
    
    # تست 1: وضعیت وابستگی‌ها
    try:
        import yt_dlp
        import telegram
        test_results.append(True)
        print("✅ تست وابستگی‌ها: وابستگی‌های اصلی با موفقیت نصب شده‌اند")
    except ImportError as e:
        test_results.append(False)
        print(f"❌ تست وابستگی‌ها: {e}")
    
    # تست 2: دسترسی به توکن تلگرام
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        test_results.append(True)
        print("✅ تست توکن تلگرام: توکن موجود است")
    else:
        test_results.append(False)
        print("❌ تست توکن تلگرام: توکن تنظیم نشده است")
    
    # تست 3: دسترسی به دایرکتوری دانلود
    if os.path.exists(TEMP_DOWNLOAD_DIR) and os.access(TEMP_DOWNLOAD_DIR, os.W_OK):
        test_results.append(True)
        print(f"✅ تست دایرکتوری دانلود: {TEMP_DOWNLOAD_DIR} قابل دسترسی است")
    else:
        try:
            os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
            test_results.append(True)
            print(f"✅ تست دایرکتوری دانلود: {TEMP_DOWNLOAD_DIR} ایجاد شد")
        except Exception as e:
            test_results.append(False)
            print(f"❌ تست دایرکتوری دانلود: {e}")
    
    # تست 4: استخراج URL
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    extracted = extract_url(f"لطفاً این ویدیو را دانلود کنید: {test_url}")
    if extracted == test_url:
        test_results.append(True)
        print("✅ تست استخراج URL: URL با موفقیت استخراج شد")
    else:
        test_results.append(False)
        print(f"❌ تست استخراج URL: '{extracted}' != '{test_url}'")
    
    # تست 5: تشخیص نوع URL
    if is_youtube_url(test_url):
        test_results.append(True)
        print("✅ تست تشخیص URL یوتیوب: URL یوتیوب با موفقیت تشخیص داده شد")
    else:
        test_results.append(False)
        print(f"❌ تست تشخیص URL یوتیوب: '{test_url}' به عنوان URL یوتیوب تشخیص داده نشد")
    
    # تست 6: استخراج شناسه ویدیوی یوتیوب
    video_id = extract_youtube_id(test_url)
    if video_id == "dQw4w9WgXcQ":
        test_results.append(True)
        print("✅ تست استخراج شناسه ویدیوی یوتیوب: شناسه با موفقیت استخراج شد")
    else:
        test_results.append(False)
        print(f"❌ تست استخراج شناسه ویدیوی یوتیوب: '{video_id}' != 'dQw4w9WgXcQ'")
    
    # نتیجه کلی
    total_tests = len(test_results)
    passed_tests = sum(test_results)
    
    print(f"\n🧮 نتیجه: {passed_tests}/{total_tests} تست با موفقیت انجام شد")
    return all(test_results)

def clean_cache() -> None:
    """
    پاکسازی فایل‌های قدیمی از کش
    """
    try:
        # پاکسازی فایل‌های موقت
        if os.path.exists(TEMP_DOWNLOAD_DIR):
            current_time = time.time()
            count = 0
            for filename in os.listdir(TEMP_DOWNLOAD_DIR):
                file_path = os.path.join(TEMP_DOWNLOAD_DIR, filename)
                # حذف فایل‌های قدیمی‌تر از 24 ساعت
                if os.path.isfile(file_path) and current_time - os.path.getmtime(file_path) > CACHE_TTL:
                    try:
                        os.remove(file_path)
                        count += 1
                    except Exception as e:
                        logger.warning(f"خطا در حذف فایل موقت {file_path}: {e}")
            
            logger.info(f"پاکسازی کش: {count} فایل حذف شد")
        
        # پاکسازی کش حافظه
        keys_to_remove = []
        current_time = time.time()
        for key, (timestamp, _) in download_cache.items():
            if current_time - timestamp > CACHE_TTL:
                keys_to_remove.append(key)
                
        for key in keys_to_remove:
            del download_cache[key]
            
        logger.info(f"پاکسازی کش حافظه: {len(keys_to_remove)} مورد حذف شد")
        
    except Exception as e:
        logger.error(f"خطا در پاکسازی کش: {e}")

def main() -> None:
    """
    تابع اصلی برنامه
    """
    # تجزیه آرگومان‌های خط فرمان
    parser = argparse.ArgumentParser(description='ربات دانلود ویدیوهای اینستاگرام و یوتیوب')
    parser.add_argument('--skip-tests', action='store_true', help='اجرای ربات بدون انجام تست‌ها')
    args = parser.parse_args()
    
    # بررسی وجود توکن
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ خطا: متغیر محیطی TELEGRAM_BOT_TOKEN تنظیم نشده است.")
        print("لطفاً با دستور زیر آن را تنظیم کنید:")
        print("export TELEGRAM_BOT_TOKEN=your_token_here")
        return
    
    # اجرای تست‌ها (اختیاری)
    if not args.skip_tests:
        tests_passed = run_tests()
        if not tests_passed:
            print("\n⚠️ برخی از تست‌ها با شکست مواجه شدند.")
            response = input("آیا می‌خواهید ربات را با وجود خطاهای فوق اجرا کنید؟ (بله/خیر) ")
            if response.lower() not in ["بله", "آره", "yes", "y"]:
                print("اجرای ربات لغو شد.")
                return
    
    print("\n🚀 در حال راه‌اندازی ربات تلگرام...")
    
    # بهینه‌سازی کش
    if CACHE_OPTIMIZER_AVAILABLE:
        optimize_cache()
    else:
        # پاکسازی دستی کش
        clean_cache()
    
    # راه‌اندازی ربات
    application = Application.builder().token(token).build()
    
    # اگر ماژول‌های بهینه‌سازی در دسترس باشند، آن‌ها را راه‌اندازی می‌کنیم
    if ENHANCED_MODE:
        update_telegram_bot(application.bot, application)
    
    # افزودن هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # راه‌اندازی با polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
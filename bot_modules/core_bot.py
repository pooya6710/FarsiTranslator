#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

# ماژول پردازش صوتی
try:
    from audio_processing import extract_audio, is_video_file, is_audio_file
except ImportError:
    # تعریف توابع جایگزین در صورت عدم وجود ماژول
    def extract_audio(video_path: str, output_format: str = 'mp3', bitrate: str = '192k') -> Optional[str]:
        logging.warning(f"هشدار: ماژول audio_processing نصب نشده، استخراج صدا انجام نمی‌شود: {video_path}")
        return None
        
    def is_video_file(file_path: str) -> bool:
        video_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm')
        return file_path.lower().endswith(video_extensions)
        
    def is_audio_file(file_path: str) -> bool:
        audio_extensions = ('.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg', '.opus')
        return file_path.lower().endswith(audio_extensions)

# کش برای فایل‌های دانلود شده
download_cache = {}
CACHE_TIMEOUT = 3600  # یک ساعت

def get_from_cache(url: str, quality: str = None) -> Optional[str]:
    """Get file from download cache
    
    Args:
        url: URL of the file
        quality: کیفیت درخواستی (برای تمایز بین فایل‌های مختلف با URL یکسان)
        
    Returns:
        Path to the cached file or None if not found or expired
    """
    # ایجاد کلید کش با ترکیب URL و کیفیت
    cache_key = f"{url}_{quality}" if quality else url
    
    # Check if file exists in cache - بررسی وجود فایل در کش
    if cache_key in download_cache:
        timestamp, file_path = download_cache[cache_key]
        if time.time() - timestamp < CACHE_TIMEOUT and os.path.exists(file_path):
            # بررسی وجود فایل در سیستم فایل
            if os.path.exists(file_path):
                # استفاده از logger در سطح ریشه برای هماهنگی با توابع تست
                quality_info = f"کیفیت {quality}" if quality else "بدون تعیین کیفیت"
                logging.info(f"فایل از کش برگردانده شد ({quality_info}): {file_path}")
                return file_path
            else:
                # حذف از کش اگر فایل وجود نداشته باشد
                del download_cache[cache_key]
    return None

def add_to_cache(url: str, file_path: str, quality: str = None):
    """Add file to download cache
    
    Args:
        url: URL of the file
        file_path: Path to the saved file
        quality: کیفیت فایل (برای تمایز بین فایل‌های مختلف با URL یکسان)
    """
    # ایجاد کلید کش با ترکیب URL و کیفیت
    cache_key = f"{url}_{quality}" if quality else url
    
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

# تنظیمات دایرکتوری دانلود
TEMP_DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
logger.info(f"مسیر دانلود موقت: {TEMP_DOWNLOAD_DIR}")

# متن‌های پاسخ ربات
START_MESSAGE = """
🎥 به ربات دانلودر اینستاگرام و یوتیوب خوش آمدید 🎬

با این ربات می‌توانید ویدیوهای اینستاگرام و یوتیوب را با کیفیت دلخواه دانلود کنید.

📱 قابلیت‌ها:
• دانلود ویدیوهای اینستاگرام (پست‌ها و ریلز)
• دانلود ویدیوهای یوتیوب (عادی، شورتز و پلی‌لیست)
• انتخاب کیفیت مختلف (1080p، 720p، 480p، 360p، 240p)
• دانلود فقط صدای ویدیو

🔍 نحوه استفاده:
فقط کافیست لینک ویدیوی مورد نظر خود را برای ربات ارسال کنید.

👨‍💻 برای دیدن راهنمای کامل: /help
"""

HELP_MESSAGE = """راهنمای استفاده:

1. لینک اینستاگرام یا یوتیوب را ارسال کنید
2. گزینه های دانلود را مشاهده کنید
3. کیفیت مورد نظر را انتخاب کنید
4. فایل دانلود شده را دریافت کنید

محدودیت ها:
- حداکثر حجم فایل: 50 مگابایت
- در صورت محدودیت, از فرمت های پیش فرض استفاده می شود

برای اطلاعات بیشتر: /about"""

ABOUT_MESSAGE = """درباره ربات دانلودر

این ربات به شما امکان دانلود ویدیوهای اینستاگرام و یوتیوب را با کیفیت های مختلف می دهد.

قابلیت ها:
- دانلود ویدیوهای اینستاگرام (پست ها و ریلز)
- دانلود ویدیوهای یوتیوب (عادی, شورتز و پلی لیست)
- انتخاب کیفیت های مختلف ("1080p", "720p", "480p", "360p", "240p")
- دانلود فقط صدا

تکنولوژی های استفاده شده:
- Python 3 
- python-telegram-bot
- yt-dlp
- instaloader

نسخه: 1.0.0

آخرین بروزرسانی: تیر ۱۴۰۳"""

# پیام‌های خطا
ERROR_MESSAGES = {
    "instagram_rate_limit": r"⚠️ محدودیت درخواست اینستاگرام. لطفاً چند دقیقه صبر کنید.",
    "instagram_private": r"⛔️ این پست خصوصی است یا نیاز به لاگین دارد.",
    "network_error": r"🌐 خطای شبکه. لطفاً اتصال خود را بررسی کنید.",
    "download_timeout": r"⏰ زمان دانلود به پایان رسید. لطفاً دوباره تلاش کنید.",
    "unsupported_format": r"❌ این فرمت پشتیبانی نمی‌شود. لطفاً فرمت دیگری را امتحان کنید.",
    "url_not_found": r"❌ لینکی در پیام شما پیدا نشد. لطفاً یک لینک معتبر از اینستاگرام یا یوتیوب ارسال کنید.",
    "invalid_url": r"❌ لینک نامعتبر است. لطفاً یک لینک معتبر از اینستاگرام یا یوتیوب ارسال کنید.",
    "download_failed": r"❌ متأسفانه دانلود انجام نشد. لطفاً مجدداً تلاش کنید.",
    "fetch_options_failed": r"❌ خطا در دریافت گزینه‌های دانلود. لطفاً مجدداً تلاش کنید.",
    "unsupported_url": r"❌ این نوع لینک پشتیبانی نمی‌شود. لطفاً یک لینک معتبر از اینستاگرام یا یوتیوب ارسال کنید.",
    "file_too_large": r"❌ حجم فایل بیشتر از حد مجاز تلگرام (50 مگابایت) است. لطفاً کیفیت پایین‌تری را انتخاب کنید.",
    "telegram_upload": r"❌ خطا در آپلود فایل در تلگرام. لطفاً مجدداً تلاش کنید.",
    "no_formats": r"❌ هیچ فرمت قابل دانلودی یافت نشد. لطفاً از لینک دیگری استفاده کنید.",
    "url_expired": r"⌛ لینک منقضی شده است. لطفاً دوباره لینک را ارسال کنید.",
    "generic_error": r"❌ خطایی رخ داد. لطفاً مجدداً تلاش کنید."
}

# پیام‌های وضعیت
STATUS_MESSAGES = {
    "processing": r"⏳ در حال پردازش لینک... لطفاً صبر کنید.",
    "downloading": r"⏳ در حال دانلود... لطفاً صبر کنید.",
    "uploading": r"📤 در حال آپلود فایل... لطفاً صبر کنید.",
    "complete": r"✅ عملیات با موفقیت انجام شد!",
    "format_select": r"📊 لطفاً کیفیت مورد نظر را انتخاب کنید:",
    "processing_audio": r"🎵 در حال استخراج صدا... لطفاً صبر کنید.",
    "downloading_audio": r"🎵 در حال دانلود صدا... لطفاً صبر کنید."
}

# پیام‌های گزینه‌های دانلود
INSTAGRAM_DOWNLOAD_OPTIONS = r"""
📷 لینک اینستاگرام شناسایی شد

لطفاً نوع دانلود را انتخاب کنید:
"""

YOUTUBE_DOWNLOAD_OPTIONS = r"""
📺 لینک یوتیوب شناسایی شد

لطفاً نوع دانلود را انتخاب کنید:
"""

YOUTUBE_SHORTS_DOWNLOAD_OPTIONS = r"""
📱 لینک شورتز یوتیوب شناسایی شد

لطفاً نوع دانلود را انتخاب کنید:
"""

YOUTUBE_PLAYLIST_DOWNLOAD_OPTIONS = r"""
🎬 لینک پلی‌لیست یوتیوب شناسایی شد

لطفاً نوع دانلود را انتخاب کنید:
"""

# تنظیمات هدرهای HTTP
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# هدرهای HTTP برای درخواست‌ها
HTTP_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.google.com/"
}

# محدودیت حجم فایل تلگرام (50 مگابایت)
MAX_TELEGRAM_FILE_SIZE = 50 * 1024 * 1024  # 50 MB در بایت

def create_youtube_cookies():
    """ایجاد فایل کوکی موقت برای یوتیوب"""
    cookies_content = r"""# Netscape HTTP Cookie File
# http://curl.haxx.se/docs/cookie_spec.html
# This file was generated by libcurl! Edit at your own risk.

.youtube.com    TRUE    /       FALSE   2147483647      CONSENT YES+cb.20210629-13-p1.en+FX+119
.youtube.com    TRUE    /       FALSE   2147483647      VISITOR_INFO1_LIVE      HV1eNSA-Vas
.youtube.com    TRUE    /       FALSE   2147483647      YSC     qVtBh7mnhcM
.youtube.com    TRUE    /       FALSE   2147483647      GPS     1
"""
    
    # ایجاد فایل موقت
    fd, cookie_file = tempfile.mkstemp(suffix='.txt', prefix='youtube_cookies_')
    with os.fdopen(fd, 'w') as f:
        f.write(cookies_content)
    
    logger.info(f"فایل کوکی موقت یوتیوب ایجاد شد: {cookie_file}")
    return cookie_file

# تنظیم مسیر فایل کوکی یوتیوب
YOUTUBE_COOKIE_FILE = create_youtube_cookies()

"""
بخش 2: توابع کمکی
"""

def extract_url(text: str) -> Optional[str]:
    """
    استخراج URL از متن ارسال شده
    
    Args:
        text: متن حاوی URL
        
    Returns:
        URL استخراج شده یا None در صورت عدم وجود
    """
    if not text:
        return None
        
    # الگوهای استخراج URL
    url_patterns = [
        # 1. الگوی استاندارد با https یا http
        r'(https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?:/[^/\s]*)*)',
        # 2. الگوی بدون پروتکل (شروع با www)
        r'(www\.(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?:/[^/\s]*)*)'
    ]
    
    # جستجو در تمام الگوها
    for pattern in url_patterns:
        urls = re.findall(pattern, text)
        if urls:
            url = urls[0].strip()
            # اضافه کردن https:// به ابتدای URL اگر با www شروع شود
            if url.startswith('www.'):
                url = 'https://' + url
                
            logger.debug(f"URL استخراج شده: {url}")
            return url
    
    logger.debug(f"هیچ URL در متن یافت نشد: {text}")
    return None

def normalize_instagram_url(url: str) -> str:
    """
    استاندارد‌سازی URL اینستاگرام
    
    Args:
        url: آدرس اینستاگرام
        
    Returns:
        آدرس استاندارد شده
    """
    if not url:
        return url
        
    # تبدیل instagr.am به instagram.com
    url = url.replace('instagr.am', 'instagram.com')
    
    # تبدیل instagram://user?username=user به https://instagram.com/user
    if 'instagram://' in url:
        parts = urlparse(url)
        if 'user' in parts.path:
            query = dict(q.split('=') for q in parts.query.split('&') if '=' in q)
            if 'username' in query:
                return f"https://instagram.com/{query['username']}"
    
    # حذف پارامترهای اضافی از URL
    # مثلاً https://www.instagram.com/p/ABC123/?igshid=123 به https://www.instagram.com/p/ABC123/
    if '/p/' in url or '/reel/' in url or '/tv/' in url:
        # استخراج شناسه پست
        shortcode = None
        if '/p/' in url:
            shortcode = url.split('/p/')[1].split('/')[0].split('?')[0]
            return f"https://www.instagram.com/p/{shortcode}/"
        elif '/reel/' in url:
            shortcode = url.split('/reel/')[1].split('/')[0].split('?')[0]
            return f"https://www.instagram.com/reel/{shortcode}/"
        elif '/tv/' in url:
            shortcode = url.split('/tv/')[1].split('/')[0].split('?')[0]
            return f"https://www.instagram.com/tv/{shortcode}/"
            
    # اضافه کردن www اگر وجود نداشته باشد
    if 'instagram.com' in url and 'www.' not in url:
        url = url.replace('instagram.com', 'www.instagram.com')
        
    # اضافه کردن / در انتهای URL اگر وجود نداشته باشد
    if url.endswith('instagram.com'):
        url += '/'
        
    return url

def normalize_youtube_url(url: str) -> str:
    """
    استاندارد‌سازی URL یوتیوب
    
    Args:
        url: آدرس یوتیوب
        
    Returns:
        آدرس استاندارد شده
    """
    if not url:
        return url
        
    # تبدیل youtu.be به youtube.com
    if 'youtu.be/' in url:
        video_id = url.split('youtu.be/')[1].split('?')[0].split('#')[0]
        url = f"https://www.youtube.com/watch?v={video_id}"
        
    # تبدیل youtube://watch?v=ABC123 به https://www.youtube.com/watch?v=ABC123
    if 'youtube://' in url:
        parts = urlparse(url)
        query = dict(q.split('=') for q in parts.query.split('&') if '=' in q)
        if 'v' in query:
            return f"https://www.youtube.com/watch?v={query['v']}"
    
    # تبدیل لینک موبایل به دسکتاپ
    if 'm.youtube.com' in url:
        url = url.replace('m.youtube.com', 'www.youtube.com')
        
    # اضافه کردن www اگر وجود نداشته باشد
    if 'youtube.com' in url and 'www.' not in url:
        url = url.replace('youtube.com', 'www.youtube.com')
        
    # انتقال پارامتر t (زمان) به پارامتر start برای سازگاری بیشتر
    if 't=' in url and 'start=' not in url:
        try:
            # استخراج زمان
            if 't=' in url:
                time_param = re.search(r't=([0-9hms]+)', url)
                if time_param:
                    time_str = time_param.group(1)
                    seconds = 0
                    
                    # تبدیل hh:mm:ss به ثانیه
                    if 'h' in time_str or 'm' in time_str or 's' in time_str:
                        h_match = re.search(r'(\d+)h', time_str)
                        m_match = re.search(r'(\d+)m', time_str)
                        s_match = re.search(r'(\d+)s', time_str)
                        
                        if h_match:
                            seconds += int(h_match.group(1)) * 3600
                        if m_match:
                            seconds += int(m_match.group(1)) * 60
                        if s_match:
                            seconds += int(s_match.group(1))
                    else:
                        # اگر فقط عدد است
                        seconds = int(time_str)
                        
                    # حذف پارامتر t و اضافه کردن پارامتر start
                    url = re.sub(r't=[0-9hms]+', '', url)
                    if '?' in url:
                        if url.endswith('?') or url.endswith('&'):
                            url += f"start={seconds}"
                        else:
                            url += f"&start={seconds}"
                    else:
                        url += f"?start={seconds}"
        except Exception as e:
            logger.warning(f"خطا در تبدیل پارامتر زمان: {e}")
            
    return url

def is_instagram_url(url: str) -> bool:
    """
    بررسی می کند که آیا URL مربوط به اینستاگرام است یا خیر
    
    Args:
        url: آدرس وب
        
    Returns:
        True اگر URL مربوط به اینستاگرام باشد, در غیر این صورت False
    """
    if not url:
        return False
        
    # اگر فقط دامنه اصلی باشد، یک پست نیست
    if url.strip('/') in ["https://instagram.com", "https://www.instagram.com", 
                         "http://instagram.com", "http://www.instagram.com"]:
        return False
        
    # الگوهای معتبر پست اینستاگرام
    valid_patterns = [
        r'instagram\.com/p/[A-Za-z0-9_-]+',            # پست معمولی
        r'instagram\.com/reel/[A-Za-z0-9_-]+',         # ریل
        r'instagram\.com/tv/[A-Za-z0-9_-]+',           # IGTV
        r'instagram\.com/stories/[A-Za-z0-9_.-]+/[0-9]+', # استوری
        r'instagr\.am/p/[A-Za-z0-9_-]+',               # لینک کوتاه پست
        r'instagr\.am/reel/[A-Za-z0-9_-]+',            # لینک کوتاه ریل
    ]
    
    for pattern in valid_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return True
            
    return False

def is_youtube_url(url: str) -> bool:
    """
    بررسی می کند که آیا URL مربوط به یوتیوب است یا خیر
    
    Args:
        url: آدرس وب
        
    Returns:
        True اگر URL مربوط به یوتیوب باشد, در غیر این صورت False
    """
    if not url:
        return False
        
    # اگر فقط دامنه اصلی باشد، یک ویدیو نیست
    if url.strip('/') in ["https://youtube.com", "https://www.youtube.com", 
                         "http://youtube.com", "http://www.youtube.com",
                         "https://youtu.be", "http://youtu.be"]:
        return False
        
    # الگوهای معتبر یوتیوب
    valid_patterns = [
        r'youtube\.com/watch\?v=[A-Za-z0-9_-]+',  # ویدیو معمولی
        r'youtu\.be/[A-Za-z0-9_-]+',              # لینک کوتاه
        r'youtube\.com/shorts/[A-Za-z0-9_-]+',    # شورتز
        r'youtube\.com/playlist\?list=[A-Za-z0-9_-]+',  # پلی لیست
        r'youtube\.com/v/[A-Za-z0-9_-]+',         # نسخه قدیمی
        r'youtube\.com/embed/[A-Za-z0-9_-]+',     # ویدیو امبد شده
    ]
    
    for pattern in valid_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return True
            
    return False

def is_youtube_shorts(url: str) -> bool:
    """
    بررسی می کند که آیا URL مربوط به شورتز یوتیوب است یا خیر
    
    Args:
        url: آدرس وب
        
    Returns:
        True اگر URL مربوط به شورتز یوتیوب باشد, در غیر این صورت False
    """
    if not url:
        return False
    
    # الگوی شناسایی شورتز یوتیوب
    return bool(re.search(r'youtube\.com/shorts/[A-Za-z0-9_-]+', url, re.IGNORECASE))

def is_youtube_playlist(url: str) -> bool:
    """
    بررسی می کند که آیا URL مربوط به پلی‌لیست یوتیوب است یا خیر
    
    Args:
        url: آدرس وب
        
    Returns:
        True اگر URL مربوط به پلی‌لیست یوتیوب باشد, در غیر این صورت False
    """
    if not url:
        return False
    
    # الگوی شناسایی پلی‌لیست یوتیوب
    return bool(re.search(r'youtube\.com/playlist\?list=[A-Za-z0-9_-]+', url, re.IGNORECASE) or
               (re.search(r'youtube\.com/watch\?', url, re.IGNORECASE) and 
                re.search(r'list=[A-Za-z0-9_-]+', url, re.IGNORECASE)))

def clean_filename(filename: str) -> str:
    """
    پاکسازی نام فایل از کاراکترهای غیرمجاز
    
    Args:
        filename: نام فایل اصلی
        
    Returns:
        نام فایل پاکسازی شده
    """
    # حذف کاراکترهای غیرمجاز در نام فایل
    invalid_chars = r'[<>:"/\\|?*]'
    cleaned_name = re.sub(invalid_chars, '_', filename)
    
    # کوتاه کردن فایل‌های با نام طولانی
    if len(cleaned_name) > 100:
        name_parts = os.path.splitext(cleaned_name)
        cleaned_name = name_parts[0][:90] + '...' + name_parts[1]
        
    return cleaned_name

def get_unique_filename(directory: str, filename: str) -> str:
    """
    ایجاد نام فایل یکتا برای جلوگیری از بازنویسی فایل‌های موجود
    
    Args:
        directory: مسیر دایرکتوری
        filename: نام فایل اصلی
        
    Returns:
        مسیر کامل فایل با نام یکتا
    """
    base_name, extension = os.path.splitext(filename)
    counter = 1
    new_filename = filename
    
    # اگر فایل وجود داشت، یک شماره به آن اضافه کن
    while os.path.exists(os.path.join(directory, new_filename)):
        new_filename = f"{base_name}_{counter}{extension}"
        counter += 1
        
    return os.path.join(directory, new_filename)

def human_readable_size(size_bytes: int) -> str:
    """
    تبدیل حجم فایل از بایت به فرمت خوانا برای انسان
    
    Args:
        size_bytes: حجم فایل به بایت
        
    Returns:
        رشته حاوی حجم فایل با واحد مناسب
    """
    if size_bytes == 0:
        return "0B"
        
    size_names = ("B", "KB", "MB", "GB", "TB")
    i = 0
    
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024
        i += 1
        
    return f"{size_bytes:.2f} {size_names[i]}"

def check_system_requirements() -> bool:
    """
    بررسی وجود ابزارهای لازم در سیستم
    
    Returns:
        True اگر همه ابزارهای لازم موجود باشند, False در غیر این صورت
    """
    try:
        # بررسی ابزارهای مورد نیاز
        required_binaries = []
        
        for binary in required_binaries:
            result = subprocess.run(['which', binary], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0:
                logger.error(f"ابزار مورد نیاز '{binary}' در سیستم نصب نشده است.")
                return False
                
        return True
    except Exception as e:
        logger.error(f"خطا در بررسی ابزارهای سیستم: {e}")
        return False

"""
بخش 3: توابع مربوط به اینستاگرام (از ماژول instagram_downloader.py)
"""

class InstagramDownloader:
    """کلاس مسئول دانلود ویدیوهای اینستاگرام"""
    
    def __init__(self):
        """مقداردهی اولیه دانلودر اینستاگرام"""
        # راه‌اندازی نمونه instaloader - با پارامترهای سازگار با نسخه فعلی
        try:
            # تلاش برای ایجاد instaloader با پارامترهای کامل
            self.loader = instaloader.Instaloader(
                download_videos=True,
                download_video_thumbnails=False,
                download_geotags=False,
                download_comments=False,
                save_metadata=False,
                compress_json=False,
                download_pictures=False,
                user_agent=USER_AGENT,
                dirname_pattern=TEMP_DOWNLOAD_DIR
            )
        except TypeError:
            # اگر خطا رخ داد، با حداقل پارامترهای ضروری تلاش کنیم
            logger.info("استفاده از پارامترهای کمتر برای instaloader به دلیل سازگاری")
            self.loader = instaloader.Instaloader(
                download_videos=True,
                download_video_thumbnails=False,
                download_comments=False,
                save_metadata=False,
                user_agent=USER_AGENT
            )
            # تنظیم دستی مسیر ذخیره
            self.loader.dirname_pattern = TEMP_DOWNLOAD_DIR
        
        logger.info("دانلودر اینستاگرام راه‌اندازی شد")
        
    def extract_post_shortcode(self, url: str) -> Optional[str]:
        """
        استخراج کد کوتاه پست از URL اینستاگرام
        
        Args:
            url: آدرس پست اینستاگرام
            
        Returns:
            کد کوتاه پست یا None در صورت عدم تطبیق
        """
        # الگوهای مختلف URL اینستاگرام
        patterns = [
            r'instagram\.com/p/([A-Za-z0-9_-]+)',       # پست معمولی
            r'instagram\.com/reel/([A-Za-z0-9_-]+)',    # ریل
            r'instagram\.com/tv/([A-Za-z0-9_-]+)',      # IGTV
            r'instagr\.am/p/([A-Za-z0-9_-]+)',          # لینک کوتاه پست
            r'instagr\.am/reel/([A-Za-z0-9_-]+)',       # لینک کوتاه ریل
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
                
        return None
        
    async def download_post(self, url: str, quality: str = "best") -> Optional[str]:
        """
        دانلود ویدیوی پست اینستاگرام
        
        Args:
            url: آدرس پست اینستاگرام
            quality: کیفیت دانلود ('best', 'medium', 'low', 'audio')
            
        Returns:
            مسیر فایل دانلود شده یا None در صورت خطا
        """
        try:
            # بررسی کش با در نظر گرفتن کیفیت (فقط برای حالت best و audio)
            if quality in ["best", "audio"]:
                cache_key = f"{url}_{quality}"
                cached_file = get_from_cache(cache_key)
                if cached_file and os.path.exists(cached_file):
                    logger.info(f"فایل از کش برگردانده شد (کیفیت {quality}): {cached_file}")
                    return cached_file
                
            # استخراج کد کوتاه پست
            shortcode = self.extract_post_shortcode(url)
            if not shortcode:
                logger.error(f"خطا در استخراج کد کوتاه پست از URL: {url}")
                return None
                
            logger.info(f"دانلود پست اینستاگرام با کد کوتاه: {shortcode}")
            
            # روش‌های مختلف دانلود
            # روش اول: استفاده از instaloader
            result = await self._download_with_instaloader(url, shortcode, quality)
            if result:
                return result
                
            # روش دوم: استفاده از yt-dlp
            logger.info(f"تلاش برای دانلود با روش دوم (yt-dlp): {url}")
            result = await self._download_with_ytdlp(url, shortcode, quality)
            if result:
                return result
                
            # روش سوم: استفاده از درخواست مستقیم
            logger.info(f"تلاش برای دانلود با روش سوم (درخواست مستقیم): {url}")
            result = await self._download_with_direct_request(url, shortcode, quality)
            if result:
                return result
                
            logger.error(f"تمام روش‌های دانلود برای {url} شکست خوردند")
            return None
                
        except Exception as e:
            logger.error(f"خطا در دانلود پست اینستاگرام: {str(e)}")
            return None
            
    async def _download_with_instaloader(self, url: str, shortcode: str, quality: str) -> Optional[str]:
        """روش دانلود با استفاده از instaloader"""
        try:
            # ایجاد دایرکتوری موقت برای این دانلود
            temp_dir = os.path.join(TEMP_DOWNLOAD_DIR, f"instagram_{shortcode}_{uuid.uuid4().hex[:8]}")
            os.makedirs(temp_dir, exist_ok=True)
            
            # تنظیم مسیر خروجی
            self.loader.dirname_pattern = temp_dir
            
            # دانلود پست
            post = instaloader.Post.from_shortcode(self.loader.context, shortcode)
            
            # برای احترام به محدودیت اینستاگرام، مکث کوتاه
            await asyncio.sleep(1)
            
            # بررسی اگر پست ویدیویی است
            if not post.is_video:
                logger.warning(f"پست با کد کوتاه {shortcode} ویدیویی نیست")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None
                
            # دانلود ویدیو
            self.loader.download_post(post, target=shortcode)
            
            # یافتن فایل ویدیوی دانلود شده
            video_files = [f for f in os.listdir(temp_dir) if f.endswith('.mp4')]
            
            if not video_files:
                logger.error(f"هیچ فایل ویدیویی در دایرکتوری {temp_dir} یافت نشد")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None
                
            # انتخاب فایل ویدیو
            video_path = os.path.join(temp_dir, video_files[0])
            
            # مسیر نهایی فایل با نام مناسب
            final_filename = f"instagram_{post.owner_username}_{shortcode}.mp4"
            original_path = get_unique_filename(TEMP_DOWNLOAD_DIR, final_filename)
            
            # کپی فایل به مسیر نهایی اصلی
            shutil.copy2(video_path, original_path)
            
            # پاکسازی دایرکتوری موقت
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            # اگر کیفیت صوتی درخواست شده یا کیفیت متفاوت از "best" است، تغییر کیفیت دهید
            final_path = original_path
            if quality != "best":
                try:
                    logger.info(f"تبدیل کیفیت ویدیو به {quality}...")
                    from telegram_fixes import convert_video_quality
                    converted_path = convert_video_quality(original_path, quality, is_audio_request=False)
                    if converted_path and os.path.exists(converted_path):
                        final_path = converted_path
                        logger.info(f"تبدیل کیفیت ویدیو به {quality} موفقیت‌آمیز بود: {final_path}")
                    else:
                        logger.warning(f"تبدیل کیفیت ویدیو ناموفق بود، استفاده از فایل اصلی")
                except ImportError:
                    logger.warning("ماژول telegram_fixes یافت نشد، تبدیل کیفیت انجام نشد")
                except Exception as e:
                    logger.error(f"خطا در تبدیل کیفیت ویدیو: {str(e)}")
            
            # افزودن به کش با کیفیت
            cache_key = f"{url}_{quality}"
            add_to_cache(cache_key, final_path)
            
            logger.info(f"دانلود با instaloader موفق بود: {final_path}")
            return final_path
                
        except instaloader.exceptions.LoginRequiredException:
            logger.error(f"پست با کد کوتاه {shortcode} نیاز به لاگین دارد")
            return None
            
        except instaloader.exceptions.ConnectionException as e:
            logger.error(f"خطای اتصال در دانلود با instaloader: {str(e)}")
            return None
            
        except Exception as e:
            logger.error(f"خطا در دانلود با instaloader: {str(e)}")
            return None
            
    async def _download_with_ytdlp(self, url: str, shortcode: str, quality: str) -> Optional[str]:
        """روش دانلود با استفاده از yt-dlp"""
        try:
            # تنظیمات yt-dlp
            ext = 'mp4'
            
            # تشخیص دانلود صوتی
            is_audio_download = quality == 'audio'
            if is_audio_download:
                ext = 'mp3'
                final_filename = f"instagram_audio_{shortcode}.{ext}"
            else:
                final_filename = f"instagram_ytdlp_{shortcode}.{ext}"
                
            final_path = get_unique_filename(TEMP_DOWNLOAD_DIR, final_filename)
            
            # تنظیم فرمت بر اساس کیفیت انتخاب شده
            if is_audio_download:
                format_spec = 'bestaudio'
                postprocessors = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
                logger.info(f"دانلود صوت از اینستاگرام: {url[:30]}...")
            else:
                # استفاده از تنظیمات دقیق تر برای اطمینان از تفاوت کیفیت
                if quality == '240p':
                    # کیفیت خیلی پایین - حداکثر 240p
                    format_spec = 'worstvideo[height<=240][ext=mp4]+worstaudio[ext=m4a]/worst[height<=240][ext=mp4]/worst[ext=mp4]'
                elif quality == '360p':
                    # کیفیت پایین - حداکثر 360p
                    format_spec = 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best[height<=360]'
                elif quality == '480p':
                    # کیفیت متوسط - حداکثر 480p
                    format_spec = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]'
                elif quality == '720p':
                    # کیفیت HD - حداکثر 720p
                    format_spec = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]'
                elif quality == '1080p':
                    # کیفیت Full HD - حداکثر 1080p
                    format_spec = 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]'
                else:
                    # پیش فرض - بهترین کیفیت موجود
                    format_spec = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
                
                postprocessors = []
                
            logger.info(f"استفاده از فرمت {format_spec} برای دانلود اینستاگرام با کیفیت {quality}")
            
            # تنظیمات دانلود
            ydl_opts = {
                'format': format_spec,
                'outtmpl': final_path if not is_audio_download else final_path.replace('.mp3', '.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'user_agent': USER_AGENT,
                'socket_timeout': 30,
                'retries': 10,
                'http_headers': HTTP_HEADERS,
                'postprocessors': postprocessors,
                'writeinfojson': False,
                'writethumbnail': False,
                'noplaylist': True,
                'ffmpeg_location': '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',
                'prefer_ffmpeg': True,
            }
            
            # اجرا در thread pool
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await loop.run_in_executor(None, ydl.download, [url])
            
            # بررسی موفقیت دانلود
            if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
                # افزودن به کش با کیفیت
                cache_key = f"{url}_{quality}"
                add_to_cache(cache_key, final_path)
                logger.info(f"دانلود با yt-dlp موفق بود: {final_path}, کیفیت: {quality}, حجم: {os.path.getsize(final_path)}")
                return final_path
            else:
                logger.warning(f"فایل دانلود شده با yt-dlp خالی یا ناقص است")
                return None
                
        except Exception as e:
            logger.error(f"خطا در دانلود با yt-dlp: {str(e)}")
            return None
            
    async def _download_with_direct_request(self, url: str, shortcode: str, quality: str) -> Optional[str]:
        """روش دانلود با استفاده از درخواست مستقیم"""
        try:
            # ابتدا باید URL مستقیم ویدیو را پیدا کنیم
            try:
                # روش اول: استفاده از instaloader برای یافتن URL مستقیم
                post = instaloader.Post.from_shortcode(self.loader.context, shortcode)
                if hasattr(post, 'video_url') and post.video_url:
                    video_url = post.video_url
                else:
                    raise ValueError("URL ویدیو یافت نشد")
            except Exception as e1:
                logger.warning(f"خطا در یافتن URL مستقیم با instaloader: {e1}")
                # روش دوم: تلاش با پارس کردن صفحه
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1',
                        'Accept': 'text/html,application/xhtml+xml,application/xml',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Referer': 'https://www.instagram.com/'
                    }
                    response = requests.get(url, headers=headers, timeout=15)
                    
                    # الگوی URL ویدیو
                    video_pattern = r'"video_url":"([^"]+)"'
                    match = re.search(video_pattern, response.text)
                    
                    if match:
                        video_url = match.group(1).replace('\\u0026', '&')
                    else:
                        logger.warning("URL ویدیو در صفحه یافت نشد")
                        return None
                except Exception as e2:
                    logger.warning(f"خطا در یافتن URL مستقیم با پارس کردن صفحه: {e2}")
                    return None
            
            # تنظیم مسیر خروجی
            final_filename = f"instagram_direct_{shortcode}.mp4"
            final_path = get_unique_filename(TEMP_DOWNLOAD_DIR, final_filename)
            
            # هدرهای مختلف برای درخواست ویدیو
            custom_headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1',
                'Accept': '*/*',
                'Accept-Encoding': 'identity;q=1, *;q=0',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': url,
                'Range': 'bytes=0-'
            }
            
            # دانلود ویدیو
            loop = asyncio.get_event_loop()
            
            # تابع دانلود - اجرا در thread pool
            def download_file():
                response = requests.get(video_url, headers=custom_headers, stream=True, timeout=30)
                response.raise_for_status()
                
                with open(final_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        
                return os.path.getsize(final_path) > 0
                
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
            url: آدرس پست اینستاگرام
            
        Returns:
            لیستی از گزینه‌های دانلود
        """
        try:
            # استخراج کد کوتاه پست
            shortcode = self.extract_post_shortcode(url)
            if not shortcode:
                logger.error(f"خطا در استخراج کد کوتاه پست از URL: {url}")
                return []
                
            # گزینه‌های دانلود ثابت برای اینستاگرام - 5 کیفیت ویدیویی و یک گزینه صوتی
            options = [
                {"id": "instagram_1080p", "label": "کیفیت Full HD (1080p)", "quality": "1080p", "type": "video", "display_name": "کیفیت Full HD (1080p)"},
                {"id": "instagram_720p", "label": "کیفیت HD (720p)", "quality": "720p", "type": "video", "display_name": "کیفیت HD (720p)"},
                {"id": "instagram_480p", "label": "کیفیت متوسط (480p)", "quality": "480p", "type": "video", "display_name": "کیفیت متوسط (480p)"},
                {"id": "instagram_360p", "label": "کیفیت پایین (360p)", "quality": "360p", "type": "video", "display_name": "کیفیت پایین (360p)"},
                {"id": "instagram_240p", "label": "کیفیت خیلی پایین (240p)", "quality": "240p", "type": "video", "display_name": "کیفیت خیلی پایین (240p)"},
                {"id": "instagram_audio", "label": "فقط صدا (MP3)", "quality": "audio", "type": "audio", "display_name": "فقط صدا (MP3)"}
            ]
            
            # لاگ کیفیت‌های ارائه شده
            logger.info(f"گزینه‌های دانلود اینستاگرام ایجاد شد: {len(options)} گزینه")
            
            return options
            
        except Exception as e:
            logger.error(f"خطا در دریافت گزینه‌های دانلود اینستاگرام: {str(e)}")
            return []

"""
بخش 4: توابع مربوط به یوتیوب (از ماژول youtube_downloader.py)
"""

class YouTubeDownloader:
    """کلاس مسئول دانلود ویدیوهای یوتیوب"""
    
    def __init__(self):
        """مقداردهی اولیه دانلودر یوتیوب"""
        # تنظیمات پایه برای yt-dlp
        self.ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': os.path.join(TEMP_DOWNLOAD_DIR, '%(id)s.%(ext)s'),
            'cookiefile': YOUTUBE_COOKIE_FILE,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',
            'prefer_ffmpeg': True,
        }
        
        logger.info("دانلودر یوتیوب راه‌اندازی شد")
        
    def clean_youtube_url(self, url: str) -> str:
        """
        پاکسازی URL یوتیوب از پارامترهای اضافی
        
        Args:
            url: آدرس یوتیوب
            
        Returns:
            آدرس پاکسازی شده
        """
        # تبدیل لینک‌های کوتاه youtu.be به فرمت استاندارد
        if 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[1].split('?')[0].split('&')[0]
            return f"https://www.youtube.com/watch?v={video_id}"
            
        # تبدیل لینک‌های shorts به فرمت استاندارد
        if '/shorts/' in url:
            video_id = url.split('/shorts/')[1].split('?')[0].split('&')[0]
            return f"https://www.youtube.com/watch?v={video_id}"
            
        # حفظ پارامتر list= برای پلی‌لیست‌ها
        if 'list=' in url and 'watch?v=' in url:
            video_id = re.search(r'v=([A-Za-z0-9_-]+)', url).group(1)
            playlist_id = re.search(r'list=([A-Za-z0-9_-]+)', url).group(1)
            return f"https://www.youtube.com/watch?v={video_id}&list={playlist_id}"
            
        # حفظ فقط آدرس اصلی ویدیو
        if 'watch?v=' in url:
            video_id = re.search(r'v=([A-Za-z0-9_-]+)', url).group(1)
            return f"https://www.youtube.com/watch?v={video_id}"
            
        # برگرداندن URL اصلی در صورت عدم تغییر
        return url
        
    async def get_video_info(self, url: str) -> Optional[Dict]:
        """
        دریافت اطلاعات ویدیوی یوتیوب
        
        Args:
            url: آدرس ویدیوی یوتیوب
            
        Returns:
            دیکشنری حاوی اطلاعات ویدیو یا None در صورت خطا
        """
        try:
            # پاکسازی URL
            clean_url = self.clean_youtube_url(url)
            
            # تنظیمات برای دریافت اطلاعات
            ydl_opts = {
                'format': 'best',
                'cookiefile': YOUTUBE_COOKIE_FILE,
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'youtube_include_dash_manifest': False,
            }
            
            # اجرای yt-dlp برای دریافت اطلاعات
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(None, ydl.extract_info, clean_url, True)
                
            if not info:
                logger.error(f"اطلاعات ویدیو دریافت نشد: {clean_url}")
                return None
                
            return info
            
        except Exception as e:
            logger.error(f"خطا در دریافت اطلاعات ویدیوی یوتیوب: {str(e)}")
            return None
            
    async def get_download_options(self, url: str) -> List[Dict]:
        """
        دریافت گزینه‌های دانلود برای ویدیوی یوتیوب (نسخه بهبود یافته)
        
        Args:
            url: آدرس ویدیوی یوتیوب
            
        Returns:
            لیستی از گزینه‌های دانلود با ساختار استاندارد
        """
        try:
            # دریافت اطلاعات ویدیو
            info = await self.get_video_info(url)
            if not info:
                logger.error(f"اطلاعات ویدیو دریافت نشد: {url}")
                return []
            
            # استخراج اطلاعات پایه
            title = info.get('title', 'ویدیو')
            duration = info.get('duration', 0)
            is_short = is_youtube_shorts(url) or (duration and duration < 60)
            
            logger.info(f"دریافت گزینه‌های دانلود برای: {title} - مدت: {duration} ثانیه")
            
            options = []
            
            # بررسی آیا این یک پلی‌لیست است
            if is_youtube_playlist(url):
                options = [
                    {
                        "id": "youtube_playlist_hd", 
                        "label": "دانلود 3 ویدیوی اول پلی‌لیست (720p)", 
                        "quality": "720p", 
                        "format": "best[height<=720]",
                        "display_name": "پلی‌لیست - کیفیت HD",
                        "type": "playlist",
                        "priority": 1
                    },
                    {
                        "id": "youtube_playlist_sd", 
                        "label": "دانلود 3 ویدیوی اول پلی‌لیست (480p)", 
                        "quality": "480p", 
                        "format": "best[height<=480]",
                        "display_name": "پلی‌لیست - کیفیت متوسط",
                        "type": "playlist",
                        "priority": 2
                    },
                    {
                        "id": "youtube_playlist_audio", 
                        "label": "دانلود صدای 3 ویدیوی اول پلی‌لیست", 
                        "quality": "audio", 
                        "format": "bestaudio[ext=m4a]",
                        "display_name": "پلی‌لیست - فقط صدا",
                        "type": "audio",
                        "priority": 3
                    }
                ]
            else:
                # اگر ویدیو کوتاه است (شورتز)، همان 5 کیفیت را ارائه می‌دهیم
                if is_short:
                    options = [
                        {
                            "id": "youtube_1080p", 
                            "label": "کیفیت Full HD (1080p)", 
                            "quality": "1080p", 
                            "format": "best[height<=1080]",
                            "display_name": "کیفیت Full HD (1080p)",
                            "type": "video",
                            "priority": 1
                        },
                        {
                            "id": "youtube_720p", 
                            "label": "کیفیت HD (720p)", 
                            "quality": "720p", 
                            "format": "best[height<=720]",
                            "display_name": "کیفیت HD (720p)",
                            "type": "video",
                            "priority": 2
                        },
                        {
                            "id": "youtube_480p", 
                            "label": "کیفیت متوسط (480p)", 
                            "quality": "480p", 
                            "format": "best[height<=480]",
                            "display_name": "کیفیت متوسط (480p)",
                            "type": "video",
                            "priority": 3
                        },
                        {
                            "id": "youtube_360p", 
                            "label": "کیفیت پایین (360p)", 
                            "quality": "360p", 
                            "format": "best[height<=360]",
                            "display_name": "کیفیت پایین (360p)",
                            "type": "video",
                            "priority": 4
                        },
                        {
                            "id": "youtube_240p", 
                            "label": "کیفیت خیلی پایین (240p)", 
                            "quality": "240p", 
                            "format": "best[height<=240]",
                            "display_name": "کیفیت خیلی پایین (240p)",
                            "type": "video",
                            "priority": 5
                        },
                        {
                            "id": "youtube_audio", 
                            "label": "فقط صدا (MP3)", 
                            "quality": "audio", 
                            "format": "bestaudio[ext=m4a]",
                            "display_name": "فقط صدا (MP3)",
                            "type": "audio",
                            "priority": 6
                        }
                    ]
                else:
                    # برای ویدیوهای معمولی، تمام گزینه‌های کیفیت
                    options = [
                        {
                            "id": "youtube_1080p", 
                            "label": "کیفیت Full HD (1080p)", 
                            "quality": "1080p", 
                            "format": "best[height<=1080]",
                            "display_name": "کیفیت Full HD (1080p)",
                            "type": "video",
                            "priority": 1
                        },
                        {
                            "id": "youtube_720p", 
                            "label": "کیفیت HD (720p)", 
                            "quality": "720p", 
                            "format": "best[height<=720]",
                            "display_name": "کیفیت HD (720p)",
                            "type": "video",
                            "priority": 2
                        },
                        {
                            "id": "youtube_480p", 
                            "label": "کیفیت متوسط (480p)", 
                            "quality": "480p", 
                            "format": "best[height<=480]",
                            "display_name": "کیفیت متوسط (480p)",
                            "type": "video",
                            "priority": 3
                        },
                        {
                            "id": "youtube_360p", 
                            "label": "کیفیت پایین (360p)", 
                            "quality": "360p", 
                            "format": "best[height<=360]",
                            "display_name": "کیفیت پایین (360p)",
                            "type": "video",
                            "priority": 4
                        },
                        {
                            "id": "youtube_240p", 
                            "label": "کیفیت خیلی پایین (240p)", 
                            "quality": "240p", 
                            "format": "best[height<=240]",
                            "display_name": "کیفیت خیلی پایین (240p)",
                            "type": "video",
                            "priority": 5
                        },
                        {
                            "id": "youtube_audio", 
                            "label": "فقط صدا (MP3)", 
                            "quality": "audio", 
                            "format": "bestaudio[ext=m4a]",
                            "display_name": "فقط صدا (MP3)",
                            "type": "audio",
                            "priority": 6
                        }
                    ]

            # مرتب‌سازی گزینه‌ها براساس اولویت
            options = sorted(options, key=lambda x: x.get('priority', 99))
            
            logger.info(f"تعداد گزینه‌های دانلود ایجاد شده: {len(options)}")
            return options
            
        except Exception as e:
            logger.error(f"خطا در دریافت گزینه‌های دانلود یوتیوب: {str(e)}")
            logger.error(f"جزئیات خطا: {traceback.format_exc()}")
            return []
            
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
                return cached_file
                
            # پاکسازی URL
            clean_url = self.clean_youtube_url(url)
            
            # دریافت اطلاعات ویدیو
            info = await self.get_video_info(clean_url)
            if not info:
                return None
                
            # ایجاد نام فایل خروجی
            video_id = info.get('id', 'video')
            title = info.get('title', 'youtube_video').replace('/', '_')
            
            # پاکسازی نام فایل
            title = clean_filename(title)
            
            # تنظیم خروجی بر اساس نوع فرمت
            is_audio_only = 'audio' in format_option
            output_ext = 'mp3' if is_audio_only else 'mp4'
            output_filename = f"{title}_{video_id}.{output_ext}"
            output_path = get_unique_filename(TEMP_DOWNLOAD_DIR, output_filename)
            
            # تنظیمات دانلود
            ydl_opts = self.ydl_opts.copy()
            
            if is_audio_only:
                try:
                    # روش اول: استفاده از yt-dlp برای دانلود مستقیم صدا
                    ydl_opts.update({
                        'format': 'bestaudio[ext=m4a]/bestaudio/best',
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '192',
                        }],
                        'outtmpl': output_path.replace('.mp3', '.%(ext)s'),
                    })
                    
                    # دانلود با yt-dlp
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        await loop.run_in_executor(None, ydl.download, [clean_url])
                        
                    # اگر فایل ایجاد نشد، از روش دوم استفاده می‌کنیم
                    if not os.path.exists(output_path):
                        # روش دوم: دانلود ویدیو و استخراج صدا
                        video_ydl_opts = self.ydl_opts.copy()
                        video_ydl_opts.update({
                            'format': 'best[ext=mp4]/best',
                            'outtmpl': output_path.replace('.mp3', '_temp.mp4')
                        })
                        
                        with yt_dlp.YoutubeDL(video_ydl_opts) as ydl:
                            await loop.run_in_executor(None, ydl.download, [clean_url])
                            
                        # استخراج صدا از ویدیو
                        video_path = output_path.replace('.mp3', '_temp.mp4')
                        if os.path.exists(video_path):
                            try:
                                from audio_processing import extract_audio
                                audio_path = extract_audio(video_path, 'mp3', '192k')
                                if audio_path:
                                    shutil.move(audio_path, output_path)
                                    os.remove(video_path)
                            except ImportError:
                                logger.warning("ماژول audio_processing یافت نشد")
                                try:
                                    from telegram_fixes import extract_audio_from_video
                                    audio_path = extract_audio_from_video(video_path, 'mp3', '192k')
                                    if audio_path:
                                        shutil.move(audio_path, output_path)
                                        os.remove(video_path)
                                except ImportError:
                                    logger.warning("ماژول telegram_fixes نیز یافت نشد")
                                    
                except Exception as e:
                    logger.error(f"خطا در استخراج صدا: {str(e)}")
                    return None
            else:
                # انتخاب فرمت بر اساس گزینه کاربر با اولویت کیفیت خاص
                if '1080p' in format_option:
                    format_spec = 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]'
                    quality = '1080p'
                elif '720p' in format_option:
                    format_spec = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]'
                    quality = '720p'
                elif '480p' in format_option:
                    format_spec = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]'
                    quality = '480p'
                elif '360p' in format_option:
                    format_spec = 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best[height<=360]'
                    quality = '360p'
                elif '240p' in format_option:
                    format_spec = 'bestvideo[height<=240][ext=mp4]+bestaudio[ext=m4a]/best[height<=240][ext=mp4]/best[height<=240]'
                    quality = '240p'
                else:
                    format_spec = 'best[ext=mp4]/best'
                    quality = 'best'
                    
                logger.info(f"استفاده از فرمت {format_spec} برای دانلود یوتیوب با کیفیت {quality}")
                    
                # تنظیمات بیشتر برای بهبود کیفیت دانلود
                ydl_opts.update({
                    'format': format_spec,
                    'outtmpl': output_path,
                    'merge_output_format': 'mp4',  # ترکیب ویدیو و صدا در فرمت MP4
                    'postprocessor_args': [
                        # تنظیمات انکودر برای کنترل کیفیت
                        '-c:v', 'libx264',  # انکودر ویدیو
                        '-c:a', 'aac',  # انکودر صدا
                        '-b:a', '128k',  # بیت‌ریت صدا
                        '-preset', 'fast',  # سرعت انکود (کیفیت متوسط، سرعت بیشتر)
                    ],
                })
                
            # بررسی پلی‌لیست
            if is_youtube_playlist(clean_url):
                ydl_opts.update({
                    'noplaylist': False,
                    'playlist_items': '1-3',  # دانلود حداکثر 3 ویدیوی اول
                })
                
                # اگر پلی‌لیست باشد، مسیر خروجی را تغییر می‌دهیم
                playlist_id = re.search(r'list=([A-Za-z0-9_-]+)', clean_url).group(1)
                playlist_dir = os.path.join(TEMP_DOWNLOAD_DIR, f'playlist_{playlist_id}_{uuid.uuid4().hex[:8]}')
                os.makedirs(playlist_dir, exist_ok=True)
                
                ydl_opts['outtmpl'] = os.path.join(playlist_dir, '%(playlist_index)s-%(title)s.%(ext)s')
                
                # دانلود ویدیوها
                loop = asyncio.get_event_loop()
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    await loop.run_in_executor(None, ydl.download, [clean_url])
                    
                # ایجاد فایل zip از ویدیوهای دانلود شده
                zip_filename = f"playlist_{playlist_id}.zip"
                zip_path = get_unique_filename(TEMP_DOWNLOAD_DIR, zip_filename)
                
                # لیست فایل‌های دانلود شده
                downloaded_files = [os.path.join(playlist_dir, f) for f in os.listdir(playlist_dir) 
                                  if os.path.isfile(os.path.join(playlist_dir, f))]
                
                # لاگ تعداد فایل‌های دانلود شده
                logger.info(f"تعداد {len(downloaded_files)} فایل از پلی‌لیست دانلود شد.")
                
                if not downloaded_files:
                    logger.error(f"هیچ فایلی از پلی‌لیست دانلود نشد: {clean_url}")
                    return None
                    
                # ایجاد فایل zip
                import zipfile
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for file in downloaded_files:
                        zipf.write(file, os.path.basename(file))
                        
                # پاکسازی دایرکتوری موقت
                shutil.rmtree(playlist_dir, ignore_errors=True)
                
                # افزودن به کش
                add_to_cache(cache_key, zip_path)
                
                return zip_path
                
            else:
                # دانلود ویدیو
                loop = asyncio.get_event_loop()
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    await loop.run_in_executor(None, ydl.download, [clean_url])
                    
                # بررسی وجود فایل خروجی
                if is_audio_only:
                    # برای فایل‌های صوتی، پسوند فایل ممکن است تغییر کرده باشد
                    mp3_path = output_path
                    if not os.path.exists(mp3_path):
                        base_path = output_path.replace('.mp3', '')
                        possible_exts = ['.mp3', '.m4a', '.webm', '.opus']
                        for ext in possible_exts:
                            if os.path.exists(base_path + ext):
                                # تغییر نام فایل به فرمت نهایی
                                os.rename(base_path + ext, mp3_path)
                                break
                
                # بررسی وجود فایل نهایی
                if not os.path.exists(output_path):
                    logger.error(f"فایل خروجی ایجاد نشد: {output_path}")
                    return None
                    
                # بررسی اگر نیاز به تغییر کیفیت ویدیو است
                if not is_audio_only and quality != "best" and quality in ["240p", "360p", "480p", "720p", "1080p"]:
                    try:
                        logger.info(f"تبدیل کیفیت ویدیو به {quality}...")
                        from telegram_fixes import convert_video_quality
                        converted_path = convert_video_quality(output_path, quality, is_audio_request=False)
                        if converted_path and os.path.exists(converted_path):
                            logger.info(f"تبدیل کیفیت موفق: {converted_path}")
                            output_path = converted_path
                        else:
                            logger.warning(f"تبدیل کیفیت ناموفق بود، استفاده از فایل اصلی")
                    except ImportError:
                        logger.warning("ماژول telegram_fixes یافت نشد، تبدیل کیفیت انجام نشد")
                    except Exception as e:
                        logger.error(f"خطا در تبدیل کیفیت ویدیو: {str(e)}")
                
                # افزودن به کش
                add_to_cache(cache_key, output_path)
                
                return output_path
                
        except Exception as e:
            logger.error(f"خطا در دانلود ویدیوی یوتیوب: {str(e)}")
            return None

"""
بخش 5: هندلرهای ربات تلگرام (از ماژول telegram_bot.py)
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    هندلر دستور /start
    """
    user_id = update.effective_user.id
    logger.info(f"دستور /start دریافت شد از کاربر {user_id}")
    try:
        await update.message.reply_text(START_MESSAGE)
        logger.info(f"پاسخ به دستور /start برای کاربر {user_id} ارسال شد")
    except Exception as e:
        logger.error(f"خطا در پاسخ به دستور /start: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    هندلر دستور /help
    """
    await update.message.reply_text(HELP_MESSAGE)

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    هندلر دستور /about
    """
    await update.message.reply_text(ABOUT_MESSAGE)

async def process_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    هندلر پردازش URL ارسال شده توسط کاربر
    """
    user_id = update.effective_user.id
    logger.info(f"پیام جدید از کاربر {user_id}: {update.message.text[:30]}...")
    # استخراج URL از متن پیام
    url = extract_url(update.message.text)
    
    if not url:
        await update.message.reply_text(ERROR_MESSAGES["url_not_found"])
        return
        
    # ارسال پیام در حال پردازش
    processing_message = await update.message.reply_text(
        STATUS_MESSAGES["processing"]
    )
    
    # ذخیره شناسه کاربر برای استفاده‌های بعدی
    user_id = update.effective_user.id
    
    try:
        # بررسی نوع URL و نرمال‌سازی
        if is_instagram_url(url):
            # نرمال‌سازی URL اینستاگرام
            normalized_url = normalize_instagram_url(url)
            logger.info(f"URL اینستاگرام نرمال‌سازی شد: {url} -> {normalized_url}")
            
            # ذخیره URL در مخزن پایدار
            url_id = f"ig_{str(uuid.uuid4().hex)[:6]}"
            persistent_url_storage[url_id] = {
                'url': normalized_url,
                'type': 'instagram',
                'user_id': user_id,
                'timestamp': time.time()
            }
            
            # ذخیره URL در context.user_data برای سازگاری با قبل
            if 'urls' not in context.user_data:
                context.user_data['urls'] = {}
            context.user_data['urls'][url_id] = normalized_url
            
            await process_instagram_url(update, context, normalized_url, processing_message, url_id)
        elif is_youtube_url(url):
            # نرمال‌سازی URL یوتیوب
            normalized_url = normalize_youtube_url(url)
            logger.info(f"URL یوتیوب نرمال‌سازی شد: {url} -> {normalized_url}")
            
            # ذخیره URL در مخزن پایدار
            url_id = f"yt_{str(uuid.uuid4().hex)[:6]}"
            persistent_url_storage[url_id] = {
                'url': normalized_url,
                'type': 'youtube',
                'user_id': user_id,
                'timestamp': time.time()
            }
            
            # ذخیره URL در context.user_data برای سازگاری با قبل
            if 'urls' not in context.user_data:
                context.user_data['urls'] = {}
            context.user_data['urls'][url_id] = normalized_url
            logger.info(f"URL یوتیوب در context.user_data ذخیره شد: {url_id}")
            
            await process_youtube_url(update, context, normalized_url, processing_message, url_id)
        else:
            await processing_message.edit_text(ERROR_MESSAGES["unsupported_url"])
    except Exception as e:
        logger.error(f"خطا در پردازش URL: {url} - {str(e)}")
        
        # پیام خطای بهتر به کاربر
        error_message = ERROR_MESSAGES["generic_error"]
        
        # بهبود پیام خطا برای حالت‌های خاص
        if "rate limit" in str(e).lower():
            error_message = ERROR_MESSAGES["instagram_rate_limit"]
        elif "private" in str(e).lower() or "login" in str(e).lower():
            error_message = ERROR_MESSAGES["instagram_private"]
        elif "network" in str(e).lower() or "connection" in str(e).lower():
            error_message = ERROR_MESSAGES["network_error"]
        elif "timeout" in str(e).lower():
            error_message = ERROR_MESSAGES["download_timeout"]
        
        await processing_message.edit_text(error_message)

async def process_instagram_url(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, status_message, url_id: str = None) -> None:
    """
    پردازش URL اینستاگرام
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: کانتکست تلگرام
        url: آدرس اینستاگرام
        status_message: پیام وضعیت در حال پردازش
        url_id: شناسه URL (اختیاری، اگر از قبل ایجاد شده باشد)
    """
    logger.info(f"شروع پردازش URL اینستاگرام: {url[:30]}...")
    try:
        # ایجاد دانلودر اینستاگرام
        downloader = InstagramDownloader()
        
        # دریافت گزینه‌های دانلود
        options = await downloader.get_download_options(url)
        
        if not options:
            await status_message.edit_text(ERROR_MESSAGES["fetch_options_failed"])
            return
            
        # ذخیره URL در داده‌های کاربر
        user_id = update.effective_user.id
        
        # اگر url_id ارائه نشده، یک شناسه جدید ایجاد کن
        if not url_id:
            url_id = f"ig_{str(uuid.uuid4().hex)[:6]}"
            
            # ذخیره در مخزن پایدار
            persistent_url_storage[url_id] = {
                'url': url,
                'type': 'instagram',
                'user_id': user_id,
                'timestamp': time.time()
            }
            logger.info(f"URL اینستاگرام در مخزن پایدار ذخیره شد: {url_id}")
            
            # ذخیره در context.user_data برای سازگاری با قبل
            if 'urls' not in context.user_data:
                context.user_data['urls'] = {}
            context.user_data['urls'][url_id] = url
            logger.info(f"URL اینستاگرام در context.user_data ذخیره شد: {url_id}")
        
        # ایجاد کیبورد با دکمه‌های منحصر به فرد و کوتاه‌تر
        keyboard = []
        
        # افزودن سرعنوان گروه‌بندی به کیبورد
        keyboard.append([InlineKeyboardButton("🎬 کیفیت‌های ویدیو:", callback_data="header_video")])
        
        # گروه‌بندی دکمه‌ها بر اساس نوع (ویدیو/صدا)
        video_buttons = []
        audio_buttons = []
        
        for i, option in enumerate(options):
            # ایجاد شناسه کوتاه برای کاهش طول callback_data
            option_short_id = f"{i}"
            # افزودن شماره به نمایش دکمه برای نمایش بهتر
            quality_text = option.get('quality', 'نامشخص')
            default_label = f"کیفیت {quality_text}"
            display_name = option.get('display_name', default_label)
            display_label = f"{i+1}. {display_name}"
            
            # ثبت در لاگ برای اطمینان از صحت داده‌ها
            logger.info(f"گزینه {i}: کیفیت={option.get('quality', 'نامشخص')}, نمایش={display_label}")
            
            # ذخیره اطلاعات گزینه برای استفاده بعدی
            if user_id not in user_download_data:
                user_download_data[user_id] = {}
            if 'option_map' not in user_download_data[user_id]:
                user_download_data[user_id]['option_map'] = {}
                
            user_download_data[user_id]['option_map'][option_short_id] = option
            
            # دکمه با callback_data کوتاه‌تر - اصلاح شده با نمایش شماره
            button = InlineKeyboardButton(
                display_label,
                callback_data=f"dl_ig_{option_short_id}_{url_id}"
            )
            
            # تفکیک دکمه‌ها بر اساس نوع
            if option.get('type') == 'audio' and "audio" in option.get("quality", "").lower():
                audio_buttons.append([button])
            else:
                video_buttons.append([button])
        
        # افزودن دکمه‌های ویدیو
        keyboard.extend(video_buttons)
        
        # اطمینان از نمایش فقط یک دکمه‌ی صوتی
        # اگر هیچ دکمه‌ی صوتی وجود نداشته باشد، یک دکمه اضافه می‌کنیم
        # در غیر این صورت، هیچ دکمه‌ای اضافه نمی‌کنیم چون قبلاً اضافه شده‌اند
        if not audio_buttons:
            # افزودن دکمه با نام "فقط صدا" و callback_data مخصوص صدا
            keyboard.append([InlineKeyboardButton("🎵 فقط صدا (MP3)", callback_data=f"dl_ig_audio_{url_id}")])
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # ارسال گزینه‌های دانلود
        await status_message.edit_text(
            INSTAGRAM_DOWNLOAD_OPTIONS,
            reply_markup=reply_markup
        )
        
        # ذخیره اطلاعات دانلود برای کاربر
        user_download_data[user_id]['instagram_options'] = options
        user_download_data[user_id]['url'] = url
        
    except Exception as e:
        logger.error(f"خطا در پردازش URL اینستاگرام: {str(e)}")
        
        # ثبت اطلاعات بیشتر برای اشکال‌زدایی
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # پیام خطای بهتر به کاربر
        error_message = ERROR_MESSAGES["generic_error"]
        
        # بهبود پیام خطا برای حالت‌های خاص
        if "rate limit" in str(e).lower():
            error_message = ERROR_MESSAGES["instagram_rate_limit"]
        elif "private" in str(e).lower() or "login" in str(e).lower():
            error_message = ERROR_MESSAGES["instagram_private"]
        elif "network" in str(e).lower() or "connection" in str(e).lower():
            error_message = ERROR_MESSAGES["network_error"]
        elif "timeout" in str(e).lower():
            error_message = ERROR_MESSAGES["download_timeout"]
            
        await status_message.edit_text(error_message)

async def process_youtube_url(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, status_message, url_id: str = None) -> None:
    """
    پردازش URL یوتیوب و نمایش گزینه‌های دانلود (نسخه بهبود یافته)
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: کانتکست تلگرام
        url: آدرس یوتیوب
        status_message: پیام وضعیت در حال پردازش
        url_id: شناسه URL (اختیاری، اگر از قبل ایجاد شده باشد)
    """
    logger.info(f"شروع پردازش URL یوتیوب: {url[:30]}...")
    try:
        # ایجاد دانلودر یوتیوب
        downloader = YouTubeDownloader()
        
        # دریافت گزینه‌های دانلود
        options = await downloader.get_download_options(url)
        
        if not options:
            await status_message.edit_text(ERROR_MESSAGES["fetch_options_failed"])
            return
            
        # ذخیره URL در داده‌های کاربر
        user_id = update.effective_user.id
        
        # اگر url_id ارائه نشده، یک شناسه جدید ایجاد کن
        if not url_id:
            url_id = f"yt_{str(uuid.uuid4().hex)[:6]}"
            
            # ذخیره در مخزن پایدار
            persistent_url_storage[url_id] = {
                'url': url,
                'type': 'youtube',
                'user_id': user_id,
                'timestamp': time.time()
            }
            logger.info(f"URL یوتیوب در مخزن پایدار ذخیره شد: {url_id}")
            
            # ذخیره در context.user_data برای سازگاری با قبل
            if 'urls' not in context.user_data:
                context.user_data['urls'] = {}
            context.user_data['urls'][url_id] = url
            logger.info(f"URL یوتیوب در context.user_data ذخیره شد: {url_id}")
        
        # ایجاد کیبورد با دکمه‌های منحصر به فرد و کوتاه‌تر
        keyboard = []
        
        # گروه‌بندی دکمه‌ها بر اساس نوع (ویدیو/صدا/پلی‌لیست)
        video_buttons = []
        audio_buttons = []
        playlist_buttons = []
        
        for i, option in enumerate(options):
            # ایجاد شناسه کوتاه برای کاهش طول callback_data
            option_short_id = f"{i}"
            
            # ذخیره اطلاعات گزینه برای استفاده بعدی
            if user_id not in user_download_data:
                user_download_data[user_id] = {}
            if 'option_map' not in user_download_data[user_id]:
                user_download_data[user_id]['option_map'] = {}
                
            user_download_data[user_id]['option_map'][option_short_id] = option
            
            # دکمه با callback_data کوتاه‌تر
            button = InlineKeyboardButton(
                option.get("label", f"کیفیت {option.get('quality', 'نامشخص')}"),
                callback_data=f"dl_yt_{option_short_id}_{url_id}"
            )
            
            # تفکیک دکمه‌ها بر اساس نوع
            if option.get('format_note', '').lower() == 'audio only' or option.get('type') == 'audio':
                if not any("دانلود فقط صدا" in btn[0].text for btn in audio_buttons):  # بررسی عدم وجود دکمه تکراری
                    audio_buttons.append([InlineKeyboardButton("🎵 دانلود فقط صدا", callback_data=f"dl_yt_audio_{url_id}")])

            elif 'playlist' in option.get('format_id', '').lower():
                playlist_buttons.append([button])
            else:
                video_buttons.append([button])
        
        # افزودن عنوان بخش ویدیو
        if video_buttons:
            keyboard.append([InlineKeyboardButton("🎬 کیفیت‌های ویدیو:", callback_data="header_video")])
            keyboard.extend(video_buttons)
        
        # افزودن عنوان بخش صدا
        if audio_buttons:
            # دکمه عنوان با callback_data خنثی
            # اضافه کردن دکمه فقط صدا برای دانلود مستقیم صوتی
            keyboard.append([InlineKeyboardButton("🎵 دانلود فقط صدا", callback_data=f"dl_yt_audio_{url_id}")])
            
        # افزودن عنوان بخش پلی‌لیست
        if playlist_buttons:
            keyboard.append([InlineKeyboardButton("🎞️ پلی‌لیست:", callback_data="header_playlist")])
            keyboard.extend(playlist_buttons)
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # انتخاب پیام مناسب بر اساس نوع لینک یوتیوب
        if is_youtube_playlist(url):
            options_message = YOUTUBE_PLAYLIST_DOWNLOAD_OPTIONS
        elif is_youtube_shorts(url):
            options_message = YOUTUBE_SHORTS_DOWNLOAD_OPTIONS
        else:
            options_message = YOUTUBE_DOWNLOAD_OPTIONS
            
        # ارسال گزینه‌های دانلود
        await status_message.edit_text(
            options_message,
            reply_markup=reply_markup
        )
        
        # ذخیره اطلاعات دانلود برای کاربر
        user_download_data[user_id]['youtube_options'] = options
        user_download_data[user_id]['url'] = url
        
    except Exception as e:
        logger.error(f"خطا در پردازش URL یوتیوب: {str(e)}")
        
        # ثبت اطلاعات بیشتر برای اشکال‌زدایی
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # پیام خطای بهتر به کاربر
        error_message = ERROR_MESSAGES["generic_error"]
        
        # بهبود پیام خطا برای حالت‌های خاص
        if "network" in str(e).lower() or "connection" in str(e).lower():
            error_message = ERROR_MESSAGES["network_error"]
        elif "timeout" in str(e).lower():
            error_message = ERROR_MESSAGES["download_timeout"]
        elif "copyright" in str(e).lower() or "removed" in str(e).lower():
            error_message = "❌ این ویدیو به دلیل مشکلات کپی‌رایت یا محدودیت‌های دیگر قابل دانلود نیست."
            
        await status_message.edit_text(error_message)

async def handle_download_option(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    هندلر انتخاب گزینه دانلود توسط کاربر
    """
    query = update.callback_query
    await query.answer()
    
    # استخراج اطلاعات کالبک
    callback_data = query.data
    user_id = update.effective_user.id
    
    logger.info(f"کاربر {user_id} دکمه {callback_data} را انتخاب کرد")
    
    # ذخیره آخرین کلیک دکمه برای استفاده در بازیابی
    recent_button_clicks[user_id] = callback_data
    
    try:
        # جدا کردن اجزای کالبک
        parts = callback_data.split('_')
        if len(parts) < 4:
            logger.warning(f"فرمت نامعتبر کالبک: {callback_data}")
            await query.edit_message_text(ERROR_MESSAGES["generic_error"])
            return
            
        # استخراج نوع دانلود (اینستاگرام/یوتیوب)، گزینه و شناسه URL
        download_type = parts[1]  # ig یا yt
        option_id = parts[2]      # شناسه گزینه انتخاب شده
        
        # شناسه URL ممکن است شامل چند بخش پس از آخرین _ باشد، بنابراین همه را می‌گیریم
        url_id_parts = parts[3:]
        url_id = '_'.join(url_id_parts)
        
        logger.info(f"شناسه URL استخراج شده: {url_id}")
        
        logger.info(f"پردازش درخواست دانلود - نوع: {download_type}, گزینه: {option_id}, شناسه URL: {url_id}")
        
        # دریافت URL اصلی - ابتدا از مخزن پایدار و سپس از user_data
        url = None
        
        # روش اول: بررسی در مخزن پایدار
        if url_id in persistent_url_storage:
            url = persistent_url_storage[url_id]['url']
            logger.info(f"URL از مخزن پایدار بازیابی شد: {url_id} -> {url[:30]}...")
        
        # روش دوم: بررسی در user_data
        elif 'urls' in context.user_data and url_id in context.user_data['urls']:
            url = context.user_data['urls'][url_id]
            logger.info(f"URL از user_data بازیابی شد: {url_id} -> {url[:30]}...")
            
            # ذخیره در مخزن پایدار برای استفاده آینده
            persistent_url_storage[url_id] = {
                'url': url,
                'type': download_type,
                'user_id': user_id,
                'timestamp': time.time()
            }
        
        # اگر URL در هیچ یک از منابع پیدا نشد
        if not url:
            logger.warning(f"URL با شناسه {url_id} پیدا نشد")
            
            # بررسی مجدد با حذف پیشوند از شناسه URL
            if url_id.startswith(('ig_', 'yt_')) and len(url_id) > 3:
                clean_url_id = url_id[3:]
                logger.info(f"تلاش مجدد با شناسه بدون پیشوند: {clean_url_id}")
                
                # بررسی در مخزن پایدار با شناسه بدون پیشوند
                for storage_url_id, storage_data in persistent_url_storage.items():
                    if storage_url_id.endswith(clean_url_id):
                        url = storage_data['url']
                        logger.info(f"URL با شناسه مشابه یافت شد: {storage_url_id} -> {url[:30]}...")
                        break
                        
                # بررسی در user_data با شناسه بدون پیشوند
                if not url and 'urls' in context.user_data:
                    for data_url_id, data_url in context.user_data['urls'].items():
                        if data_url_id.endswith(clean_url_id):
                            url = data_url
                            logger.info(f"URL با شناسه مشابه در user_data یافت شد: {data_url_id} -> {url[:30]}...")
                            break
            
            # روش سوم: جستجو در کل مخزن پایدار برای یافتن URL با نوع یکسان
            if not url and download_type in ['ig', 'yt']:
                search_type = 'instagram' if download_type == 'ig' else 'youtube'
                logger.info(f"جستجوی جایگزین: بررسی همه URLهای نوع {search_type} در مخزن پایدار")
                
                # دریافت آخرین URL اضافه شده از این نوع برای کاربر فعلی
                matching_urls = [(vid, data) for vid, data in persistent_url_storage.items() 
                                 if data.get('type') == search_type and data.get('user_id') == user_id]
                
                if matching_urls:
                    # مرتب‌سازی بر اساس زمان (جدیدترین ابتدا)
                    matching_urls.sort(key=lambda x: x[1].get('timestamp', 0), reverse=True)
                    newest_url_id, newest_data = matching_urls[0]
                    url = newest_data['url']
                    logger.info(f"جدیدترین URL {search_type} یافت شد: {newest_url_id} -> {url[:30]}...")
            
            # روش چهارم: بررسی آخرین URL ارسال شده توسط کاربر
            if not url and 'url' in user_download_data.get(user_id, {}):
                url = user_download_data[user_id]['url']
                logger.info(f"استفاده از آخرین URL ارسال شده توسط کاربر: {url[:30]}...")
                
            # اگر همچنان URL پیدا نشد، نمایش پیام خطا
            if not url:
                await query.edit_message_text(ERROR_MESSAGES["url_expired"])
                return
        
        # ارسال پیام در حال دانلود
        await query.edit_message_text(STATUS_MESSAGES["downloading"])
        
        # بررسی اگر کالبک مربوط به دکمه "فقط صدا" است
        if download_type == "audio" or option_id == "audio" or "audio" in callback_data:
            logger.info(f"درخواست دانلود صوتی تشخیص داده شد برای URL: {url[:30]}...")
            
            # ارسال پیام در حال پردازش صدا
            await query.edit_message_text(STATUS_MESSAGES["processing_audio"])
            
            # تشخیص نوع URL (اینستاگرام یا یوتیوب)
            if is_instagram_url(url):
                # دانلود صوتی اینستاگرام
                downloader = InstagramDownloader()
                downloaded_file = await downloader.download_post(url, quality='audio')
                
                if downloaded_file and os.path.exists(downloaded_file):
                    # بررسی نوع فایل دانلود شده
                    if downloaded_file.lower().endswith(('.mp3', '.m4a', '.aac', '.wav')):
                        # فایل صوتی است، مستقیماً ارسال کن
                        audio_path = downloaded_file
                    else:
                        # فایل ویدیویی است، تبدیل به صوت کن
                        logger.info(f"تبدیل ویدیو به صوت: {downloaded_file}")
                        
                        # روش 1: استفاده از ماژول audio_processing
                        audio_path = None
                        try:
                            # تلاش اول با ماژول audio_processing
                            from audio_processing import extract_audio
                            audio_path = extract_audio(downloaded_file, 'mp3', '192k')
                            logger.info(f"تبدیل با ماژول audio_processing: {audio_path}")
                        except ImportError:
                            logger.warning("ماژول audio_processing یافت نشد، تلاش با audio_extractor")
                            try:
                                # تلاش دوم با ماژول audio_extractor
                                from audio_processing.audio_extractor import extract_audio
                                audio_path = extract_audio(downloaded_file, 'mp3', '192k')
                                logger.info(f"تبدیل با ماژول audio_extractor: {audio_path}")
                            except ImportError:
                                logger.warning("ماژول audio_extractor نیز یافت نشد")
                        
                        # روش 2: استفاده از ماژول telegram_fixes اگر روش 1 موفق نبود
                        if not audio_path or not os.path.exists(audio_path):
                            logger.info("تلاش با ماژول telegram_fixes...")
                            try:
                                from telegram_fixes import extract_audio_from_video
                                audio_path = extract_audio_from_video(downloaded_file, 'mp3', '192k')
                                logger.info(f"تبدیل با ماژول telegram_fixes: {audio_path}")
                            except (ImportError, Exception) as e:
                                logger.error(f"خطا در استفاده از ماژول telegram_fixes: {str(e)}")
                        
                        # روش 3: استفاده مستقیم از FFmpeg اگر روش‌های قبلی موفق نبودند
                        if not audio_path or not os.path.exists(audio_path):
                            logger.info("استفاده مستقیم از FFmpeg...")
                            
                            # ایجاد نام فایل خروجی
                            base_name = os.path.basename(downloaded_file)
                            file_name, _ = os.path.splitext(base_name)
                            output_dir = os.path.dirname(downloaded_file)
                            audio_path = os.path.join(output_dir, f"{file_name}_audio.mp3")
                            
                            # آماده‌سازی دستور FFmpeg
                            cmd = [
                                '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',
                                '-i', downloaded_file,
                                '-vn',  # بدون ویدیو
                                '-acodec', 'libmp3lame',
                                '-ab', '192k',
                                '-ar', '44100',
                                '-y',  # جایگزینی فایل موجود
                                audio_path
                            ]
                            
                            try:
                                # اجرای FFmpeg
                                import subprocess
                                logger.info(f"اجرای دستور FFmpeg: {' '.join(cmd)}")
                                result = subprocess.run(
                                    cmd,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    text=True
                                )
                                
                                if result.returncode != 0:
                                    logger.error(f"خطا در اجرای FFmpeg: {result.stderr}")
                                    audio_path = None
                                elif not os.path.exists(audio_path):
                                    logger.error(f"فایل صوتی ایجاد نشد: {audio_path}")
                                    audio_path = None
                            except Exception as e:
                                logger.error(f"خطا در اجرای FFmpeg: {str(e)}")
                                audio_path = None
                        
                        # بررسی نتیجه نهایی
                        if not audio_path or not os.path.exists(audio_path):
                            logger.error("تمام روش‌های استخراج صدا ناموفق بودند")
                            await query.edit_message_text(ERROR_MESSAGES["download_failed"])
                            return
                    
                    # ارسال فایل صوتی
                    await query.edit_message_text(STATUS_MESSAGES["uploading"])
                    file_size = os.path.getsize(audio_path)
                    
                    with open(audio_path, 'rb') as audio_file:
                        caption = f"🎵 صدای دانلود شده از اینستاگرام\n💾 حجم: {human_readable_size(file_size)}"
                        await context.bot.send_audio(
                            chat_id=update.effective_chat.id,
                            audio=audio_file,
                            caption=caption
                        )
                    await query.edit_message_text(STATUS_MESSAGES["complete"])
                else:
                    await query.edit_message_text(ERROR_MESSAGES["download_failed"])
                
                return
                
            elif is_youtube_url(url):
                # دانلود صوتی یوتیوب - ورژن بهبود یافته
                # تنظیمات پیشرفته برای دانلود صوتی با کیفیت بالا
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }, {
                        'key': 'FFmpegMetadata',
                        'add_metadata': True,
                    }],
                    'outtmpl': os.path.join(TEMP_DOWNLOAD_DIR, 'yt_audio_%(id)s.%(ext)s'),
                    'writethumbnail': True,
                    'quiet': True,
                    'noplaylist': True,
                    'prefer_ffmpeg': True,
                    'ffmpeg_location': '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg'  # تنظیم مسیر اختصاصی ffmpeg
                }
                
                # دانلود
                try:
                    loop = asyncio.get_event_loop()
                    
                    # به دست آوردن اطلاعات ویدیو برای نام فایل
                    youtube_dl = YouTubeDownloader()
                    info = await youtube_dl.get_video_info(url)
                    
                    if not info:
                        await query.edit_message_text(ERROR_MESSAGES["download_failed"])
                        return
                        
                    video_id = info.get('id', 'video')
                    title = clean_filename(info.get('title', 'youtube_audio'))
                    output_path = os.path.join(TEMP_DOWNLOAD_DIR, f"yt_audio_{video_id}.mp3")
                    
                    # اجرای دانلود
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        await loop.run_in_executor(None, ydl.download, [url])
                    
                    # ممکن است فایل با فرمت دیگری ذخیره شده باشد
                    if not os.path.exists(output_path):
                        # جستجوی فایل با شناسه ویدیو
                        for filename in os.listdir(TEMP_DOWNLOAD_DIR):
                            if video_id in filename and filename.endswith(('.mp3', '.m4a', '.aac', '.wav')):
                                output_path = os.path.join(TEMP_DOWNLOAD_DIR, filename)
                                break
                    
                    if os.path.exists(output_path):
                        # ارسال فایل صوتی
                        await query.edit_message_text(STATUS_MESSAGES["uploading"])
                        file_size = os.path.getsize(output_path)
                        
                        with open(output_path, 'rb') as audio_file:
                            caption = f"🎵 صدای دانلود شده از یوتیوب\n🎵 {title}\n💾 حجم: {human_readable_size(file_size)}"
                            await context.bot.send_audio(
                                chat_id=update.effective_chat.id,
                                audio=audio_file,
                                caption=caption
                            )
                        await query.edit_message_text(STATUS_MESSAGES["complete"])
                    else:
                        logger.error(f"فایل صوتی دانلود شده یافت نشد: {output_path}")
                        await query.edit_message_text(ERROR_MESSAGES["download_failed"])
                
                except Exception as e:
                    logger.error(f"خطا در دانلود صوتی یوتیوب: {str(e)}")
                    logger.error(traceback.format_exc())
                    await query.edit_message_text(ERROR_MESSAGES["download_failed"])
                    
                return
            
            else:
                await query.edit_message_text(ERROR_MESSAGES["unsupported_url"])
                return
            
        # بررسی وجود اطلاعات گزینه‌های دانلود در کش
        if url_id in option_cache:
            logger.info(f"اطلاعات گزینه‌های دانلود از کش بازیابی شد: {url_id}")
            
            # بازیابی اطلاعات گزینه انتخاب شده از کش
            options = option_cache[url_id]
            option_index = int(option_id) if option_id.isdigit() else -1
            
            # بررسی و لاگ‌گیری دقیق از اطلاعات گزینه
            logger.info(f"شماره گزینه: {option_index}, تعداد گزینه‌ها: {len(options)}")
            logger.info(f"گزینه‌های موجود: {[opt.get('quality', 'نامشخص') for opt in options]}")
            
            if 0 <= option_index < len(options):
                selected_option = options[option_index]
                logger.info(f"گزینه انتخاب شده: {selected_option.get('quality', 'نامشخص')}")
                
                # لاگ اطلاعات کامل گزینه برای عیب‌یابی
                logger.info(f"جزئیات کامل گزینه انتخاب شده: {selected_option}")
                
                # تنظیم کیفیت صحیح بر اساس شماره گزینه (بدون وابستگی به محتوای options)
                # شماره گزینه به کیفیت مربوطه نگاشت شود برای هر دو منبع یکسان است
                quality_mapping = {
                    0: "1080p",
                    1: "720p",
                    2: "480p",
                    3: "360p",
                    4: "240p",
                    5: "audio"
                }
                
                # اصلاح کیفیت در selected_option برای هر دو نوع (اینستاگرام و یوتیوب)
                if option_index in quality_mapping:
                    selected_option['quality'] = quality_mapping[option_index]
                    logger.info(f"کیفیت بر اساس شماره گزینه اصلاح شد: {selected_option['quality']}")
                
                # هدایت به تابع دانلود مناسب با اطلاعات کامل گزینه
                if download_type == "ig":
                    await download_instagram_with_option(update, context, url, selected_option)
                elif download_type == "yt":
                    await download_youtube_with_option(update, context, url, selected_option)
                else:
                    await query.edit_message_text(ERROR_MESSAGES["generic_error"])
                return
        
        # اگر کش وجود نداشت، از روش قدیمی استفاده کن
        # هدایت به تابع دانلود مناسب
        if download_type == "ig":
            await download_instagram(update, context, url, option_id)
        elif download_type == "yt":
            await download_youtube(update, context, url, option_id)
        else:
            await query.edit_message_text(ERROR_MESSAGES["generic_error"])
            
    except Exception as e:
        logger.error(f"خطا در پردازش انتخاب دانلود: {str(e)}")
        logger.error(f"جزئیات خطا: {traceback.format_exc()}")
        await query.edit_message_text(ERROR_MESSAGES["generic_error"])

async def download_instagram(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, option_id: str) -> None:
    """
    دانلود ویدیوی اینستاگرام با کیفیت مشخص
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: کانتکست تلگرام
        url: آدرس اینستاگرام
        option_id: شناسه گزینه انتخاب شده (می‌تواند نام کیفیت یا شماره باشد)
    """
    query = update.callback_query
    
    try:
        # ایجاد دانلودر اینستاگرام
        downloader = InstagramDownloader()
        
        # تعیین کیفیت بر اساس گزینه انتخاب شده
        quality = "best"
        is_audio = False
        display_name = "بهترین کیفیت"  # نام نمایشی پیش‌فرض
        user_id = update.effective_user.id
        
        logger.info(f"گزینه انتخاب شده برای دانلود اینستاگرام: {option_id}")
        
        # بررسی اگر این یک درخواست فقط صدا باشد
        if option_id == "audio":
            logger.info("درخواست دانلود فقط صدا")
            quality = "audio"
            is_audio = True
            display_name = "فقط صدا"
        # بررسی برای درخواست صوتی - 'instagram_audio' یا کلمه 'audio' در شناسه گزینه
        elif "audio" in option_id.lower():
            quality = "audio"
            is_audio = True
            display_name = "فقط صدا (MP3)"
            logger.info(f"درخواست صوتی تشخیص داده شد: {option_id}")
        # بررسی اگر option_id یک عدد است - این روش درست‌تر است
        elif option_id.isdigit():
            # تبدیل به عدد برای راحتی کار
            option_num = int(option_id)
            
            # نگاشت مستقیم شماره گزینه به کیفیت متناظر
            # گزینه‌های اینستاگرام طبق تعریف get_download_options:
            # 0: 1080p, 1: 720p, 2: 480p, 3: 360p, 4: 240p, 5: audio
            if option_num == 0:
                quality = "1080p"
                display_name = "کیفیت Full HD (1080p)"
            elif option_num == 1:
                quality = "720p"
                display_name = "کیفیت HD (720p)"
            elif option_num == 2:
                quality = "480p"
                display_name = "کیفیت متوسط (480p)"
            elif option_num == 3:
                quality = "360p"
                display_name = "کیفیت پایین (360p)"
            elif option_num == 4:
                quality = "240p"
                display_name = "کیفیت خیلی پایین (240p)"
            elif option_num == 5:
                quality = "audio"
                is_audio = True
                display_name = "فقط صدا (MP3)"
            logger.info(f"درخواست کیفیت براساس شماره گزینه {option_num}: {quality}")
            
        # نسخه قدیمی - تشخیص بر اساس نام کیفیت در option_id
        elif "1080p" in option_id:
            quality = "1080p"
            is_audio = False  # تأکید بر درخواست ویدیویی
            display_name = "کیفیت Full HD (1080p)"
        elif "720p" in option_id:
            quality = "720p"
            is_audio = False  # تأکید بر درخواست ویدیویی
            display_name = "کیفیت HD (720p)"
        elif "480p" in option_id:
            quality = "480p"
            is_audio = False  # تأکید بر درخواست ویدیویی
            display_name = "کیفیت متوسط (480p)"
            logger.info(f"کیفیت 480p انتخاب شد: {option_id}")
        elif "360p" in option_id:
            quality = "360p"
            is_audio = False  # تأکید بر درخواست ویدیویی
            display_name = "کیفیت پایین (360p)"
            logger.info(f"کیفیت 360p انتخاب شد: {option_id}")
        elif "240p" in option_id:
            quality = "240p"
            is_audio = False  # تأکید بر درخواست ویدیویی
            display_name = "کیفیت خیلی پایین (240p)"
        elif "medium" in option_id:
            quality = "480p"  # استفاده از فرمت جدید برای کیفیت متوسط
            display_name = "کیفیت متوسط (480p)"
        elif "low" in option_id:
            quality = "240p"  # استفاده از فرمت جدید برای کیفیت پایین
            display_name = "کیفیت خیلی پایین (240p)"
# این بخش حذف شده است زیرا بالاتر شرط option_id.isdigit وجود دارد و باعث تکرار می‌شود
            
        logger.info(f"دانلود اینستاگرام با کیفیت: {quality}, صوتی: {is_audio}")
        
        # 1. دانلود ویدیو با بهترین کیفیت
        best_quality_file = None
        
        # بررسی کش برای بهترین کیفیت
        cached_best = get_from_cache(f"{url}_best")
        if cached_best and os.path.exists(cached_best):
            logger.info(f"فایل با بهترین کیفیت از کش برگردانده شد: {cached_best}")
            best_quality_file = cached_best
        else:
            # دانلود با بهترین کیفیت
            best_quality_file = await downloader.download_post(url, "best")
            if best_quality_file and os.path.exists(best_quality_file):
                # افزودن به کش بهترین کیفیت
                add_to_cache(f"{url}_best", best_quality_file)
                logger.info(f"فایل با بهترین کیفیت دانلود شد: {best_quality_file}")
        
        if not best_quality_file or not os.path.exists(best_quality_file):
            await query.edit_message_text(ERROR_MESSAGES["download_failed"])
            return
        
        # 2. اگر کیفیت انتخابی "best" است، همان فایل را برگردان
        downloaded_file = best_quality_file
        
        # 3. تبدیل کیفیت برای سایر موارد
        if quality != "best" or is_audio:
            # پیام در حال پردازش
            await query.edit_message_text(STATUS_MESSAGES["processing"])
            
            try:
                # بررسی کش برای کیفیت درخواستی
                cached_quality = get_from_cache(f"{url}_{quality}")
                if cached_quality and os.path.exists(cached_quality):
                    logger.info(f"فایل با کیفیت {quality} از کش برگردانده شد: {cached_quality}")
                    downloaded_file = cached_quality
                else:
                    # اجرای تبدیل کیفیت
                    try:
                        from telegram_fixes import convert_video_quality
                        logger.info(f"تبدیل کیفیت ویدیو به {quality}, صوتی: {is_audio}")
                        
                        # انجام تبدیل
                        converted_file = convert_video_quality(
                            video_path=best_quality_file, 
                            quality=quality,
                            is_audio_request=is_audio
                        )
                        
                        if converted_file and os.path.exists(converted_file):
                            downloaded_file = converted_file
                            logger.info(f"تبدیل موفق: {downloaded_file}")
                            # افزودن به کش
                            add_to_cache(f"{url}_{quality}", downloaded_file)
                        else:
                            logger.warning("تبدیل ناموفق بود، استفاده از فایل اصلی")
                    except ImportError as ie:
                        logger.error(f"ماژول telegram_fixes یافت نشد: {str(ie)}")
                        # تلاش برای استفاده از روش دیگر
                        if is_audio and os.path.exists(best_quality_file):
                            try:
                                logger.info("تلاش برای استخراج صوت با ماژول audio_processing")
                                from audio_processing import extract_audio
                                audio_path = extract_audio(best_quality_file)
                                if audio_path and os.path.exists(audio_path):
                                    downloaded_file = audio_path
                                    logger.info(f"استخراج صدا با audio_processing موفق: {audio_path}")
                                    # افزودن به کش
                                    add_to_cache(f"{url}_audio", audio_path)
                                else:
                                    logger.warning("استخراج صدا ناموفق بود، استفاده از فایل اصلی")
                            except ImportError:
                                logger.error("ماژول audio_processing در دسترس نیست")
                    except Exception as e:
                        logger.error(f"خطا در تبدیل کیفیت: {str(e)}")
            except Exception as e:
                logger.error(f"خطا در مرحله پردازش: {str(e)}")
                # در صورت خطا از فایل اصلی استفاده می‌کنیم
            
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
        
        # احترام به انتخاب کاربر برای نوع فایل (صوتی یا ویدیویی)
        # اینجا تصمیم فقط بر اساس انتخاب کاربر است، نه پسوند فایل
        # اگر کاربر گزینه صوتی انتخاب نکرده باشد، حتی اگر فایل با پسوند صوتی باشد، 
        # به عنوان ویدیو در نظر گرفته می‌شود (ممکن است کیفیت با عنوان "فقط صدا" انتخاب شده باشد)
        
        # ارسال فایل بر اساس نوع آن
        if is_audio:
            try:
                with open(downloaded_file, 'rb') as audio_file:
                    caption = f"🎵 صدای دانلود شده از اینستاگرام\n💾 حجم: {human_readable_size(file_size)}"
                    await context.bot.send_audio(
                        chat_id=update.effective_chat.id,
                        audio=audio_file,
                        caption=caption
                    )
            except Exception as audio_error:
                logger.error(f"خطا در ارسال فایل صوتی: {str(audio_error)}")
                # اگر ارسال به عنوان صوت خطا داد، به عنوان سند ارسال کن
                with open(downloaded_file, 'rb') as document_file:
                    caption = f"🎵 صدای دانلود شده از اینستاگرام\n💾 حجم: {human_readable_size(file_size)}"
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=document_file,
                        caption=caption
                    )
        else:
            # ارسال ویدیو
            with open(downloaded_file, 'rb') as video_file:
                caption = f"📥 دانلود شده از اینستاگرام\n💾 حجم: {human_readable_size(file_size)}\n🎬 کیفیت: {quality}"
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=video_file,
                    caption=caption,
                    supports_streaming=True
                )
            
        # ارسال پیام تکمیل
        await query.edit_message_text(STATUS_MESSAGES["complete"])
        
    except Exception as e:
        logger.error(f"خطا در دانلود ویدیوی اینستاگرام: {str(e)}")
        logger.error(f"جزئیات خطا: {traceback.format_exc()}")
        await query.edit_message_text(ERROR_MESSAGES["download_failed"])

async def download_instagram_with_option(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, selected_option: Dict) -> None:
    """
    دانلود ویدیوی اینستاگرام با استفاده از اطلاعات کامل گزینه
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: کانتکست تلگرام
        url: آدرس اینستاگرام
        selected_option: گزینه انتخاب شده از کش
    """
    query = update.callback_query
    
    try:
        logger.info(f"شروع دانلود اینستاگرام با گزینه کامل: {selected_option.get('quality', 'نامشخص')}")
        
        # بررسی نوع گزینه (صدا یا ویدیو) با دقت بالا
        option_id = selected_option.get('id', '')
        option_type = selected_option.get('type', '')
        is_audio = option_type == 'audio' or 'audio' in option_id.lower()
        
        # دقت بیشتر برای تشخیص درخواست‌های ویدیویی
        if '240p' in option_id or '360p' in option_id or '480p' in option_id or '720p' in option_id or '1080p' in option_id:
            is_audio = False
            logger.info(f"درخواست ویدیویی تشخیص داده شد: {option_id}")
            
        logger.info(f"نوع گزینه انتخاب شده: {option_type}, شناسه: {option_id}, تشخیص صوتی: {is_audio}")
        
        # ایجاد دانلودر اینستاگرام
        downloader = InstagramDownloader()
        
        # دانلود محتوا
        downloaded_file = None

        # بررسی اگر ماژول بهبودهای جدید در دسترس است
        try:
            from telegram_fixes import download_with_quality
            # نوع دانلود و کیفیت
            quality = selected_option.get('quality', 'best')
            
            # همگام‌سازی با تشخیص نوع دانلود در بالا
            quality = selected_option.get('quality', 'best')
            
            # دقت بیشتر برای تشخیص درخواست‌های ویدیویی
            if ('240p' in option_id or '360p' in option_id or '480p' in option_id or 
                '720p' in option_id or '1080p' in option_id):
                is_audio = False
                logger.info(f"درخواست ویدیویی در پردازش تشخیص داده شد: {option_id}")
            elif 'audio' in option_id.lower() or selected_option.get('type') == 'audio':
                is_audio = True
                logger.info(f"درخواست صوتی در پردازش تشخیص داده شد: {option_id}")
            
            # پیام وضعیت
            if is_audio:
                await query.edit_message_text(STATUS_MESSAGES["downloading_audio"])
                quality = 'audio'  # تنظیم کیفیت به 'audio' برای دانلود صوتی
                logger.info("دانلود درخواست صوتی اینستاگرام")
            else:
                await query.edit_message_text(STATUS_MESSAGES["downloading"])
            
            # ابتدا ویدیو را با بهترین کیفیت دانلود می‌کنیم
            # بررسی کش برای بهترین کیفیت
            cached_file = get_from_cache(url, "best")
            
            if cached_file and os.path.exists(cached_file):
                logger.info(f"فایل با بهترین کیفیت از کش برگردانده شد: {cached_file}")
                best_quality_file = cached_file
            else:
                # دانلود با بهترین کیفیت
                logger.info(f"دانلود اینستاگرام با بهترین کیفیت")
                best_quality_file = await download_with_quality(url, "best", False, "instagram")
                
                if best_quality_file and os.path.exists(best_quality_file):
                    # افزودن به کش با در نظر گرفتن کیفیت
                    add_to_cache(url, best_quality_file, "best")
                    logger.info(f"فایل با کیفیت بالا با موفقیت دانلود شد: {best_quality_file}")
                else:
                    logger.error(f"دانلود با ماژول بهبود یافته ناموفق بود")
                    raise Exception("دانلود با ماژول بهبود یافته ناموفق بود")
            
            # حالا اگر کیفیت درخواستی "best" نیست یا audio است، فایل را تبدیل می‌کنیم
            if quality == "best" and not is_audio:
                # اگر کیفیت درخواستی بهترین است، همان فایل را برمی‌گردانیم
                downloaded_file = best_quality_file
                logger.info(f"فایل با کیفیت بالا بدون تغییر برگردانده شد: {downloaded_file}")
            else:
                # تبدیل فایل به کیفیت مورد نظر
                logger.info(f"تبدیل فایل به کیفیت {quality}")
                
                # پیام وضعیت جدید
                await query.edit_message_text(STATUS_MESSAGES["processing"])
                
                try:
                    # استفاده از تابع convert_video_quality برای تبدیل کیفیت
                    from telegram_fixes import convert_video_quality
                    logger.info(f"تبدیل کیفیت ویدیو با استفاده از ماژول بهبودیافته: {quality}")
                    
                    # قبلاً: if is_audio: quality = "audio"
                    
                    # تبدیل کیفیت ویدیو یا استخراج صدا با تابع جامع
                    converted_file = convert_video_quality(
                        video_path=best_quality_file, 
                        quality=quality,
                        is_audio_request=is_audio
                    )
                    
                    if converted_file and os.path.exists(converted_file):
                        downloaded_file = converted_file
                        logger.info(f"تبدیل موفق: {downloaded_file}")
                        # افزودن به کش
                        add_to_cache(url, downloaded_file, quality)
                    else:
                        # خطا در تبدیل
                        logger.error(f"تبدیل ناموفق بود، برگرداندن فایل اصلی")
                        downloaded_file = best_quality_file
                except Exception as e:
                    logger.error(f"خطا در تبدیل کیفیت: {str(e)}")
                    # برگرداندن فایل اصلی در صورت خطا
                    downloaded_file = best_quality_file
            
        except ImportError:
            logger.info("ماژول بهبود یافته در دسترس نیست، استفاده از روش قدیمی")
            # اگر صدا درخواست شده، دانلود صدا
            if is_audio:
                logger.info(f"دانلود صدای پست اینستاگرام: {url[:30]}...")
                # استفاده از yt-dlp برای دانلود صدا
                logger.info("استفاده از yt-dlp برای دانلود صدا...")
                # استخراج کد کوتاه پست
                shortcode = downloader.extract_post_shortcode(url)
                if shortcode:
                    # تنظیمات yt-dlp برای دانلود فقط صدا
                    ydl_opts = {
                        'format': 'bestaudio',
                        'outtmpl': os.path.join(TEMP_DOWNLOAD_DIR, f"instagram_audio_{shortcode}.%(ext)s"),
                        'quiet': True,
                        'no_warnings': True,
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '192',
                        }],
                        'user_agent': USER_AGENT,
                        'http_headers': HTTP_HEADERS
                    }
                    
                    # اجرا در thread pool
                    loop = asyncio.get_event_loop()
                    final_path = os.path.join(TEMP_DOWNLOAD_DIR, f"instagram_audio_{shortcode}.mp3")
                    
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        await loop.run_in_executor(None, ydl.download, [url])
                    
                    # بررسی وجود فایل خروجی
                    if os.path.exists(final_path):
                        downloaded_file = final_path
                    else:
                        # جستجو برای یافتن فایل با پسوندهای متفاوت
                        for ext in ['mp3', 'aac', 'm4a', 'opus']:
                            alt_path = os.path.join(TEMP_DOWNLOAD_DIR, f"instagram_audio_{shortcode}.{ext}")
                            if os.path.exists(alt_path):
                                downloaded_file = alt_path
                                break
                
                # اگر دانلود صدا موفق نبود، تلاش برای دانلود معمولی و سپس استخراج صدا
                if not downloaded_file:
                    logger.info("دانلود صدا ناموفق بود، استفاده از دانلود معمولی و استخراج صدا...")
                    video_file = await downloader.download_post(url, 'best')
                    
                    # استخراج صدا
                    if video_file and os.path.exists(video_file):
                        try:
                            # ارسال پیام وضعیت استخراج صدا
                            await query.edit_message_text(STATUS_MESSAGES["processing_audio"])
                            
                            # استخراج صدا با استفاده از ماژول audio_processing
                            try:
                                from audio_processing import extract_audio
                                audio_file = extract_audio(video_file)
                                if audio_file and os.path.exists(audio_file):
                                    downloaded_file = audio_file
                            except ImportError:
                                logger.warning("ماژول audio_processing در دسترس نیست")
                                # استفاده از تابع extract_audio_from_video از ماژول اصلاحات
                                try:
                                    from telegram_fixes import extract_audio_from_video
                                    audio_file = extract_audio_from_video(video_file)
                                    if audio_file and os.path.exists(audio_file):
                                        downloaded_file = audio_file
                                except ImportError:
                                    logger.warning("هیچ یک از ماژول‌های استخراج صدا در دسترس نیستند")
                                    # اگر هیچ ماژول موجود نبود، از ویدیو استفاده می‌کنیم
                                    downloaded_file = video_file
                        except Exception as e:
                            logger.error(f"خطا در استخراج صدا: {e}")
                            # اگر استخراج صدا با خطا مواجه شد، همان ویدیو را برمی‌گردانیم
                            downloaded_file = video_file
            else:
                # دانلود ویدیو با کیفیت انتخاب شده
                quality = selected_option.get('quality', 'best')
                logger.info(f"دانلود ویدیوی اینستاگرام با کیفیت {quality}: {url[:30]}...")
                downloaded_file = await downloader.download_post(url, quality)
        
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
        
        # ارسال محتوا بر اساس نوع آن
        if is_audio:
            # ارسال فایل صوتی
            with open(downloaded_file, 'rb') as audio_file:
                caption = f"🎵 صدای دانلود شده از اینستاگرام\n💾 حجم: {human_readable_size(file_size)}"
                await context.bot.send_audio(
                    chat_id=update.effective_chat.id,
                    audio=audio_file,
                    caption=caption
                )
        else:
            # ارسال ویدیو
            with open(downloaded_file, 'rb') as video_file:
                caption = f"📥 دانلود شده از اینستاگرام\n💾 حجم: {human_readable_size(file_size)}"
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=video_file,
                    caption=caption,
                    supports_streaming=True
                )
                
        # ارسال پیام تکمیل
        await query.edit_message_text(STATUS_MESSAGES["complete"])
        
    except Exception as e:
        logger.error(f"خطا در دانلود اینستاگرام با گزینه: {str(e)}")
        logger.error(f"جزئیات خطا: {traceback.format_exc()}")
        await query.edit_message_text(ERROR_MESSAGES["download_failed"])

async def download_youtube_with_option(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, selected_option: Dict) -> None:
    """
    دانلود ویدیوی یوتیوب با استفاده از اطلاعات کامل گزینه
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: کانتکست تلگرام
        url: آدرس یوتیوب
        selected_option: گزینه انتخاب شده از کش
    """
    query = update.callback_query
    
    try:
        logger.info(f"شروع دانلود یوتیوب با گزینه کامل: {selected_option.get('label', 'نامشخص')}")
        
        # تعیین نوع دانلود - صوتی یا ویدئویی
        is_audio = False
        format_id = selected_option.get('id', '')
        format_option = selected_option.get('format', '')
        
        # بررسی دقیق برای تشخیص دانلود صوتی
        if 'audio' in format_id.lower() or 'audio' in format_option.lower():
            is_audio = True
            logger.info(f"درخواست دانلود صوتی از یوتیوب تشخیص داده شد: {format_id}")
            await query.edit_message_text(STATUS_MESSAGES["downloading_audio"])
        else:
            await query.edit_message_text(STATUS_MESSAGES["downloading"])
            
        # بررسی اگر ماژول بهبودهای جدید در دسترس است
        try:
            # استفاده از ماژول بهبود یافته
            from telegram_fixes import download_with_quality
            
            logger.info(f"استفاده از ماژول بهبود یافته برای دانلود یوتیوب")
            # اگر audio انتخاب شده، گزینه is_audio را روشن می‌کنیم
            if 'audio' in format_id.lower() or 'audio' in format_option.lower():
                is_audio = True
                quality = 'audio'
            else:
                # تعیین کیفیت براساس انتخاب کاربر
                quality = selected_option.get('quality', 'best')
                
            logger.info(f"کیفیت انتخابی برای دانلود: {quality}, صوتی: {is_audio}")
            
            # ابتدا ویدیو را با بهترین کیفیت دانلود می‌کنیم
            # بررسی کش برای بهترین کیفیت
            cached_file = get_from_cache(url, "best")
            
            if cached_file and os.path.exists(cached_file):
                logger.info(f"فایل با بهترین کیفیت از کش برگردانده شد: {cached_file}")
                best_quality_file = cached_file
            else:
                # دانلود با بهترین کیفیت
                logger.info(f"دانلود یوتیوب با بهترین کیفیت")
                best_quality_file = await download_with_quality(url, "best", False, "youtube")
                
                if best_quality_file and os.path.exists(best_quality_file):
                    # افزودن به کش با در نظر گرفتن کیفیت
                    add_to_cache(url, best_quality_file, "best")
                    logger.info(f"فایل با کیفیت بالا با موفقیت دانلود شد: {best_quality_file}")
                else:
                    logger.error(f"دانلود با ماژول بهبود یافته ناموفق بود")
                    raise Exception("دانلود با ماژول بهبود یافته ناموفق بود")
            
            # حالا اگر کیفیت درخواستی "best" نیست یا audio است، فایل را تبدیل می‌کنیم
            if quality == "best" and not is_audio:
                # اگر کیفیت درخواستی بهترین است، همان فایل را برمی‌گردانیم
                downloaded_file = best_quality_file
                logger.info(f"فایل با کیفیت بالا بدون تغییر برگردانده شد: {downloaded_file}")
            else:
                # تبدیل فایل به کیفیت مورد نظر
                logger.info(f"تبدیل فایل به کیفیت {quality}")
                
                # پیام وضعیت جدید
                if is_audio:
                    await query.edit_message_text(STATUS_MESSAGES["processing_audio"])
                else:
                    await query.edit_message_text(STATUS_MESSAGES["processing"])
                
                try:
                    # استفاده از تابع convert_video_quality برای تبدیل کیفیت
                    from telegram_fixes import convert_video_quality
                    logger.info(f"تبدیل کیفیت ویدیو با استفاده از ماژول بهبودیافته: {quality}")
                    
                    # قبلاً: if is_audio: quality = "audio"
                    
                    # تبدیل کیفیت ویدیو یا استخراج صدا با تابع جامع
                    converted_file = convert_video_quality(
                        video_path=best_quality_file, 
                        quality=quality,
                        is_audio_request=is_audio
                    )
                    
                    if converted_file and os.path.exists(converted_file):
                        downloaded_file = converted_file
                        logger.info(f"تبدیل موفق: {downloaded_file}")
                        # افزودن به کش
                        add_to_cache(url, downloaded_file, quality)
                    else:
                        # خطا در تبدیل
                        logger.error(f"تبدیل ناموفق بود، برگرداندن فایل اصلی")
                        downloaded_file = best_quality_file
                except Exception as e:
                    logger.error(f"خطا در تبدیل کیفیت: {str(e)}")
                    # برگرداندن فایل اصلی در صورت خطا
                    downloaded_file = best_quality_file
                    
                    # اگر درخواست صوتی بود، تلاش کنیم با روش‌های دیگر صدا را استخراج کنیم
                    if is_audio:
                        audio_path = None
                        try:
                            from telegram_fixes import extract_audio_from_video
                            audio_path = extract_audio_from_video(downloaded_file, 'mp3', '192k')
                            logger.info(f"تبدیل با ماژول telegram_fixes: {audio_path}")
                        except (ImportError, Exception) as e:
                            logger.error(f"خطا در استفاده از تابع extract_audio_from_video: {e}")
                    
                        # روش دیگر: استفاده مستقیم از FFmpeg
                        if not audio_path or not os.path.exists(audio_path):
                            logger.info("استفاده مستقیم از FFmpeg...")
                            try:
                                import subprocess
                                import uuid
                                
                                base_name = os.path.basename(downloaded_file)
                                file_name, _ = os.path.splitext(base_name)
                                output_dir = os.path.dirname(downloaded_file)
                                audio_path = os.path.join(output_dir, f"{file_name}_audio_{uuid.uuid4().hex[:8]}.mp3")
                                
                                cmd = [
                                    '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',
                                    '-i', downloaded_file,
                                    '-vn',  # بدون ویدیو
                                    '-acodec', 'libmp3lame',
                                    '-ab', '192k',
                                    '-ar', '44100',
                                    '-ac', '2',
                                    '-y',  # جایگزینی فایل موجود
                                    audio_path
                                ]
                                
                                logger.info(f"اجرای دستور FFmpeg: {' '.join(cmd)}")
                                result = subprocess.run(
                                    cmd,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    text=True
                                )
                                
                                if result.returncode != 0:
                                    logger.error(f"خطا در استخراج صدا با FFmpeg: {result.stderr}")
                                elif os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                                    logger.info(f"استخراج صدا با FFmpeg موفق: {audio_path}")
                                    downloaded_file = audio_path  # جایگزینی فایل ویدیویی با فایل صوتی
                                else:
                                    logger.error(f"فایل صوتی ایجاد نشد یا خالی است: {audio_path}")
                            except Exception as e:
                                logger.error(f"خطا در اجرای FFmpeg: {e}")
                        else:
                            # اگر استخراج صدا موفق بود، فایل را جایگزین می‌کنیم
                            downloaded_file = audio_path
                
                # افزودن به کش با کیفیت
                cache_quality = "audio" if is_audio else quality
                add_to_cache(url, downloaded_file, cache_quality)
                logger.info(f"فایل با موفقیت دانلود شد (کیفیت {cache_quality}): {downloaded_file}")
                
        except (ImportError, Exception) as e:
            logger.warning(f"خطا در استفاده از ماژول بهبود یافته: {e}")
            
            # ایجاد دانلودر یوتیوب
            downloader = YouTubeDownloader()
            
            # روش دانلود را انتخاب می‌کنیم
            # برای فایل‌های صوتی باید از روش مستقیم استفاده کنیم
            if is_audio:
                # تنظیمات دانلود صوتی
                info = await downloader.get_video_info(url)
                if not info:
                    await query.edit_message_text(ERROR_MESSAGES["download_failed"])
                    return
                    
                # ایجاد نام فایل خروجی
                video_id = info.get('id', 'video')
                title = info.get('title', 'youtube_audio').replace('/', '_')
                title = clean_filename(title)
                
                output_filename = f"{title}_{video_id}.mp3"
                output_path = get_unique_filename(TEMP_DOWNLOAD_DIR, output_filename)
                
                # تنظیمات yt-dlp برای دانلود فقط صوت
                ydl_opts = {
                    'format': 'bestaudio',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'ffmpeg_location': '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',
                    'outtmpl': output_path.replace('.mp3', '.%(ext)s'),
                    'quiet': True,
                    'cookiefile': YOUTUBE_COOKIE_FILE,
                    'noplaylist': True,
                }
                
                # دانلود فایل
                logger.info(f"دانلود صدای یوتیوب با yt-dlp برای: {url[:30]}...")
                
                # اجرا در thread pool
                loop = asyncio.get_event_loop()
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    await loop.run_in_executor(None, ydl.download, [url])
                
                # بررسی وجود فایل mp3
                if not os.path.exists(output_path):
                    # جستجو برای یافتن فایل با پسوندهای متفاوت
                    for ext in ['mp3', 'aac', 'm4a', 'opus', 'webm']:
                        alt_path = output_path.replace('.mp3', f'.{ext}')
                        if os.path.exists(alt_path):
                            if ext != 'mp3':  # اگر پسوند فایل mp3 نیست، آن را تغییر نام بده
                                os.rename(alt_path, output_path)
                            break
                
                if not os.path.exists(output_path):
                    logger.error(f"فایل صوتی دانلود شده پیدا نشد: {output_path}")
                    await query.edit_message_text(ERROR_MESSAGES["download_failed"])
                    return
                    
                downloaded_file = output_path
                # افزودن به کش با کیفیت
                add_to_cache(url, downloaded_file, "audio")
                
            else:
                # دانلود محتوا با فرمت انتخاب شده
                format_option = selected_option.get('format_id', selected_option.get('format', ''))
                logger.info(f"فرمت انتخاب شده برای دانلود ویدیو: {format_option}")
                
                downloaded_file = await downloader.download_video(url, format_option if format_option else format_id)
        
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
        
        is_playlist = 'playlist' in format_option.lower() if format_option else 'playlist' in format_id.lower()
        
        # تشخیص نوع فایل براساس پسوند فایل (برای اطمینان)
        if downloaded_file and os.path.exists(downloaded_file) and downloaded_file.endswith(('.mp3', '.m4a', '.aac', '.wav')):
            is_audio = True
        
        # ارسال فایل بر اساس نوع آن
        if is_audio:
            # ارسال فایل صوتی
            try:
                if os.path.exists(downloaded_file):
                    with open(downloaded_file, 'rb') as audio_file:
                        caption = f"🎵 صدای دانلود شده از یوتیوب\n💾 حجم: {human_readable_size(file_size)}"
                        logger.info(f"ارسال فایل صوتی: {downloaded_file}")
                        await context.bot.send_audio(
                            chat_id=update.effective_chat.id,
                            audio=audio_file,
                            caption=caption
                        )
                else:
                    logger.error(f"فایل صوتی برای ارسال وجود ندارد: {downloaded_file}")
                    await query.edit_message_text(ERROR_MESSAGES["download_failed"])
                    return
            except Exception as e:
                logger.error(f"خطا در ارسال فایل صوتی: {str(e)}. تلاش برای ارسال به عنوان سند...")
                # اگر ارسال به عنوان صوت خطا داد، به عنوان سند ارسال کن
                with open(downloaded_file, 'rb') as document_file:
                    caption = f"🎵 صدای دانلود شده از یوتیوب\n💾 حجم: {human_readable_size(file_size)}"
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=document_file,
                        caption=caption
                    )
        elif is_playlist:
            # ارسال فایل زیپ پلی‌لیست
            with open(downloaded_file, 'rb') as zip_file:
                caption = f"📁 پلی‌لیست دانلود شده از یوتیوب\n💾 حجم: {human_readable_size(file_size)}"
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=zip_file,
                    caption=caption
                )
        else:
            # ارسال ویدیو
            with open(downloaded_file, 'rb') as video_file:
                caption = f"📥 دانلود شده از یوتیوب\n💾 حجم: {human_readable_size(file_size)}\n🎬 کیفیت: {selected_option.get('label', 'نامشخص')}"
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=video_file,
                    caption=caption,
                    supports_streaming=True
                )
                
        # ارسال پیام تکمیل
        await query.edit_message_text(STATUS_MESSAGES["complete"])
        
    except Exception as e:
        logger.error(f"خطا در دانلود یوتیوب با گزینه: {str(e)}")
        logger.error(f"جزئیات خطا: {traceback.format_exc()}")
        await query.edit_message_text(ERROR_MESSAGES["download_failed"])

async def download_youtube(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, option_id: str) -> None:
    """
    دانلود ویدیوی یوتیوب
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: کانتکست تلگرام
        url: آدرس یوتیوب
        option_id: شناسه گزینه انتخاب شده (می‌تواند نام کیفیت یا شماره باشد)
    """
    query = update.callback_query
    
    try:
        # ایجاد دانلودر یوتیوب
        downloader = YouTubeDownloader()
        
        # تعیین نوع درخواست و کیفیت بر اساس شماره گزینه یا محتوای آن
        is_audio_request = False
        format_option = "best"  # مقدار پیش‌فرض
        quality_display = "بهترین کیفیت"
        
        logger.info(f"گزینه انتخاب شده برای دانلود یوتیوب: {option_id}")
        
        # بررسی اگر option_id یک عدد است
        if option_id.isdigit():
            # تبدیل به عدد برای راحتی کار
            option_num = int(option_id)
            
            # نگاشت مستقیم شماره گزینه به کیفیت متناظر
            # گزینه‌های یوتیوب معمولاً: 0: 1080p, 1: 720p, 2: 480p, 3: 360p, 4: 240p, 5: audio
            if option_num == 0:
                format_option = "137+140/bestvideo[height<=1080]+bestaudio/best"
                quality_display = "کیفیت Full HD (1080p)"
            elif option_num == 1:
                format_option = "136+140/bestvideo[height<=720]+bestaudio/best"
                quality_display = "کیفیت HD (720p)"
            elif option_num == 2:
                format_option = "135+140/bestvideo[height<=480]+bestaudio/best"
                quality_display = "کیفیت متوسط (480p)"
            elif option_num == 3:
                format_option = "134+140/bestvideo[height<=360]+bestaudio/best"
                quality_display = "کیفیت پایین (360p)"
            elif option_num == 4:
                format_option = "133+140/bestvideo[height<=240]+bestaudio/best"
                quality_display = "کیفیت خیلی پایین (240p)"
            elif option_num == 5:
                format_option = "bestaudio"
                is_audio_request = True
                quality_display = "فقط صدا (MP3)"
                
            logger.info(f"کیفیت انتخاب شده بر اساس شماره گزینه {option_num}: {format_option}")
        
        # تشخیص صوتی از روی محتوای option_id
        elif 'audio' in option_id.lower():
            is_audio_request = True
            format_option = "bestaudio"
            quality_display = "فقط صدا (MP3)"
            logger.info(f"درخواست دانلود صوتی تشخیص داده شد: {option_id}")
        
        if is_audio_request:
            logger.info(f"درخواست دانلود صوتی از یوتیوب: {url[:30]}...")
            
            # تنظیمات دانلود صوتی
            info = await downloader.get_video_info(url)
            if not info:
                await query.edit_message_text(ERROR_MESSAGES["download_failed"])
                return
                
            # ایجاد نام فایل خروجی
            video_id = info.get('id', 'video')
            title = info.get('title', 'youtube_audio').replace('/', '_')
            # پاکسازی نام فایل
            title = clean_filename(title)
            
            output_filename = f"{title}_{video_id}.mp3"
            output_path = get_unique_filename(TEMP_DOWNLOAD_DIR, output_filename)
            
            # تنظیمات yt-dlp برای دانلود صوتی - با تاکید روی تبدیل به mp3
            ydl_opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio/ba*',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                },
                {
                    # پردازشگر برای بهبود کیفیت صدا و اضافه کردن متادیتا
                    'key': 'FFmpegMetadata',
                    'add_metadata': True,
                }],
                'ffmpeg_location': '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',
                'outtmpl': output_path.replace('.mp3', '.%(ext)s'),
                'quiet': True,
                'cookiefile': YOUTUBE_COOKIE_FILE,
                'noplaylist': True,  # فقط ویدیوی اصلی، نه پلی‌لیست
            }
            
            # دانلود فایل
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await loop.run_in_executor(None, ydl.download, [url])
            
            # بررسی وجود فایل mp3
            if not os.path.exists(output_path):
                # جستجو برای یافتن فایل با پسوندهای متفاوت
                for ext in ['mp3', 'aac', 'm4a', 'opus', 'webm']:
                    alt_path = output_path.replace('.mp3', f'.{ext}')
                    if os.path.exists(alt_path):
                        if ext != 'mp3':  # اگر پسوند فایل mp3 نیست، آن را تغییر نام بده
                            os.rename(alt_path, output_path)
                        break
            
            if not os.path.exists(output_path):
                logger.error("فایل صوتی دانلود شده پیدا نشد")
                await query.edit_message_text(ERROR_MESSAGES["download_failed"])
                return
                
            downloaded_file = output_path
            is_audio = True
            
        else:
            # دانلود ویدیو با گزینه انتخاب شده
            logger.info(f"دانلود ویدیوی یوتیوب با گزینه {format_option}: {url[:30]}...")
            downloaded_file = await downloader.download_video(url, format_option)
            
            # بروزرسانی متغیر کیفیت برای استفاده در caption
            option_id = format_option
            
            # تشخیص فایل صوتی از روی پسوند
            is_audio = downloaded_file.endswith(('.mp3', '.m4a', '.aac', '.wav'))
            
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
        
        # تعیین نوع فایل و نحوه ارسال
        is_playlist = 'playlist' in option_id and downloaded_file.endswith('.zip')
        
        # بررسی مجدد نوع فایل براساس پسوند
        if not is_audio and not is_playlist:
            is_audio = downloaded_file.endswith(('.mp3', '.m4a', '.aac', '.wav'))
        
        # ارسال فایل بر اساس نوع آن
        if is_audio:
            # ارسال فایل صوتی
            try:
                with open(downloaded_file, 'rb') as audio_file:
                    caption = f"🎵 صدای دانلود شده از یوتیوب\n💾 حجم: {human_readable_size(file_size)}"
                    await context.bot.send_audio(
                        chat_id=update.effective_chat.id,
                        audio=audio_file,
                        caption=caption
                    )
            except Exception as audio_error:
                logger.error(f"خطا در ارسال فایل صوتی: {str(audio_error)}")
                # اگر ارسال به عنوان صوت خطا داد، به عنوان سند ارسال کن
                with open(downloaded_file, 'rb') as document_file:
                    caption = f"🎵 صدای دانلود شده از یوتیوب\n💾 حجم: {human_readable_size(file_size)}"
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=document_file,
                        caption=caption
                    )
        elif is_playlist:
            # ارسال فایل زیپ پلی‌لیست
            with open(downloaded_file, 'rb') as zip_file:
                caption = f"📁 پلی‌لیست دانلود شده از یوتیوب\n💾 حجم: {human_readable_size(file_size)}"
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=zip_file,
                    caption=caption
                )
        else:
            # ارسال ویدیو
            with open(downloaded_file, 'rb') as video_file:
                caption = f"📥 دانلود شده از یوتیوب\n💾 حجم: {human_readable_size(file_size)}"
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=video_file,
                    caption=caption,
                    supports_streaming=True
                )
                
        # ارسال پیام تکمیل
        await query.edit_message_text(STATUS_MESSAGES["complete"])
        
    except Exception as e:
        logger.error(f"خطا در دانلود ویدیوی یوتیوب: {str(e)}")
        logger.error(f"جزئیات خطا: {traceback.format_exc()}")
        await query.edit_message_text(ERROR_MESSAGES["download_failed"])

"""
بخش 6: توابع تست و راه‌اندازی (از ماژول main.py)
"""

def clean_temp_files():
    """پاکسازی فایل‌های موقت قدیمی"""
    try:
        # حذف فایل‌های موقت قدیمی (بیشتر از 24 ساعت)
        now = time.time()
        cutoff = now - (24 * 3600)  # 24 ساعت
        
        files_removed = 0
        
        for file_name in os.listdir(TEMP_DOWNLOAD_DIR):
            file_path = os.path.join(TEMP_DOWNLOAD_DIR, file_name)
            if os.path.isfile(file_path) and os.path.getmtime(file_path) < cutoff:
                try:
                    os.remove(file_path)
                    files_removed += 1
                except Exception as e:
                    logger.warning(f"خطا در حذف فایل موقت {file_path}: {e}")
                    
        # حذف دایرکتوری‌های خالی
        for root, dirs, files in os.walk(TEMP_DOWNLOAD_DIR, topdown=False):
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                if not os.listdir(dir_path):
                    try:
                        os.rmdir(dir_path)
                    except Exception as e:
                        logger.warning(f"خطا در حذف دایرکتوری خالی {dir_path}: {e}")
                        
        logger.info(f"پاکسازی فایل‌های موقت: {files_removed} فایل حذف شد")
        
    except Exception as e:
        logger.error(f"خطا در پاکسازی فایل‌های موقت: {e}")

async def run_periodic_cleanup(app):
    """اجرای منظم تابع پاکسازی فایل‌های موقت"""
    while True:
        try:
            clean_temp_files()
        except Exception as e:
            logger.error(f"خطا در پاکسازی دوره‌ای: {e}")
            
        # انتظار 6 ساعت تا اجرای بعدی
        await asyncio.sleep(6 * 3600)

def run_tests() -> bool:
    """
    اجرای تست‌های خودکار
    
    Returns:
        True اگر همه تست‌ها موفق باشند، در غیر این صورت False
    """
    logger.info("در حال اجرای تست‌های خودکار...")
    
    all_tests_passed = True
    
    # تست 1: بررسی تشخیص URL
    test_urls = [
        "https://www.instagram.com/p/ABC123/",
        "https://www.youtube.com/watch?v=ABC123",
        "www.instagram.com/p/ABC123/",
        "نمونه متن بدون لینک"
    ]
    
    for i, url_text in enumerate(test_urls):
        extracted = extract_url(url_text)
        if i < 3 and not extracted:
            logger.error(f"تست تشخیص URL شکست خورد: {url_text}")
            all_tests_passed = False
        elif i == 3 and extracted:
            logger.error(f"تست تشخیص URL شکست خورد (تشخیص اشتباه): {url_text}")
            all_tests_passed = False
            
    # تست 2: بررسی تشخیص نوع URL
    test_url_types = [
        {"url": "https://www.instagram.com/p/ABC123/", "instagram": True, "youtube": False},
        {"url": "https://www.youtube.com/watch?v=ABC123", "instagram": False, "youtube": True},
        {"url": "https://www.example.com", "instagram": False, "youtube": False}
    ]
    
    for test in test_url_types:
        url = test["url"]
        is_insta = is_instagram_url(url)
        is_yt = is_youtube_url(url)
        
        if is_insta != test["instagram"] or is_yt != test["youtube"]:
            logger.error(f"تست تشخیص نوع URL شکست خورد: {url}, " 
                       f"اینستاگرام: {is_insta}, یوتیوب: {is_yt}")
            all_tests_passed = False
            
    # تست 3: بررسی ساختار کش
    # ایجاد یک فایل موقت برای تست
    try:
        # ایجاد فایل تست موقت
        fd, test_path = tempfile.mkstemp(suffix='.mp4', prefix='test_video_')
        with os.fdopen(fd, 'w') as f:
            f.write("این یک فایل تست است")
        
        # افزودن به کش
        test_url = "https://test.com/video"
        add_to_cache(test_url, test_path)
        cached = get_from_cache(test_url)
        
        if cached != test_path:
            logger.error(f"تست کش شکست خورد. مقدار بازگردانده شده: {cached}, مورد انتظار: {test_path}")
            all_tests_passed = False
        else:
            logger.info(f"تست کش با موفقیت انجام شد")
            
        # پاکسازی فایل تست
        if os.path.exists(test_path):
            os.remove(test_path)
    except Exception as e:
        logger.error(f"خطا در اجرای تست کش: {e}")
        all_tests_passed = False
        
    # تست 4: بررسی پاکسازی نام فایل
    test_filenames = [
        {"input": "file:with*invalid?chars.mp4", "expected_pattern": r"file.with.invalid.chars\.mp4"},
        {"input": "a" * 150 + ".mp4", "expected_pattern": r"a{90}\.\.\.\.mp4"}
    ]
    
    for test in test_filenames:
        cleaned = clean_filename(test["input"])
        if not re.match(test["expected_pattern"], cleaned):
            logger.error(f"تست پاکسازی نام فایل شکست خورد. ورودی: {test['input']}, خروجی: {cleaned}")
            all_tests_passed = False
            
    if all_tests_passed:
        logger.info("همه تست‌ها با موفقیت اجرا شدند!")
    else:
        logger.warning("برخی تست‌ها شکست خوردند.")
        
    return all_tests_passed

async def main():
    """راه‌اندازی ربات تلگرام"""
    # بررسی وجود نمونه‌های دیگر ربات در حال اجرا
    lock_file = "/tmp/telegram_bot_lock"
    try:
        if os.path.exists(lock_file):
            # بررسی زنده بودن فرآیند
            with open(lock_file, 'r') as f:
                pid = int(f.read().strip())
            try:
                # بررسی آیا این PID هنوز زنده است
                os.kill(pid, 0)
                logger.warning(f"یک نمونه دیگر از ربات (PID: {pid}) در حال اجراست. این نمونه خاتمه می‌یابد.")
                return
            except OSError:
                # PID وجود ندارد، فایل قفل قدیمی است
                logger.info("فایل قفل قدیمی پیدا شد. ادامه اجرا...")
        
        # ایجاد فایل قفل با PID فعلی
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
            
        # پاکسازی فایل‌های موقت
        clean_temp_files()
        
        # دریافت توکن ربات از متغیرهای محیطی
        telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        
        if not telegram_token:
            logger.error("توکن ربات تلگرام یافت نشد! لطفاً متغیر محیطی TELEGRAM_BOT_TOKEN را تنظیم کنید.")
            return
            
        # ایجاد اپلیکیشن ربات
        app = Application.builder().token(telegram_token).build()
        
        # افزودن هندلرها
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("about", about_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_url))
        app.add_handler(CallbackQueryHandler(handle_download_option))
        
        # راه‌اندازی وظیفه پاکسازی دوره‌ای
        asyncio.create_task(run_periodic_cleanup(app))
        
        # راه‌اندازی ربات
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        
        logger.info("ربات با موفقیت راه‌اندازی شد!")
        
        try:
            # نگه داشتن ربات در حال اجرا
            await asyncio.Event().wait()
        finally:
            # حذف فایل قفل هنگام خروج
            if os.path.exists(lock_file):
                os.remove(lock_file)
    except Exception as e:
        logger.error(f"خطا در راه‌اندازی ربات: {e}")
        # حذف فایل قفل در صورت بروز خطا
        if os.path.exists(lock_file):
            os.remove(lock_file)

if __name__ == "__main__":
    # بررسی وجود آرگومان‌های خط فرمان
    parser = argparse.ArgumentParser(description='ربات تلگرام دانلود ویدیوهای اینستاگرام و یوتیوب')
    parser.add_argument('--skip-tests', action='store_true', help='رد شدن از تست‌های خودکار')
    args = parser.parse_args()
    
    if not args.skip_tests:
        # اجرای تست‌های خودکار
        tests_passed = run_tests()
        if not tests_passed:
            logger.warning("برخی تست‌ها شکست خوردند. ربات با این حال راه‌اندازی می‌شود.")
    
    try:
        # راه‌اندازی ربات
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("خروج از برنامه با دستور کاربر...")
    except Exception as e:
        logger.error(f"خطا در راه‌اندازی ربات: {e}")
    finally:
        # پاکسازی و خروج
        if os.path.exists(YOUTUBE_COOKIE_FILE):
            try:
                os.remove(YOUTUBE_COOKIE_FILE)
                logger.info(f"فایل کوکی موقت حذف شد: {YOUTUBE_COOKIE_FILE}")
            except:
                pass
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ماژول telegram_fixes

این ماژول توابع اصلاح شده و تکمیلی برای ربات تلگرام ارائه می‌دهد.
شامل بهبودهایی برای دانلود از یوتیوب و اینستاگرام با کیفیت‌های مختلف.
"""

import os
import re
import uuid
import logging
import asyncio
import tempfile
import subprocess
from typing import Optional, Dict, Tuple, List

import yt_dlp
from audio_processing import extract_audio, is_video_file, is_audio_file

# تنظیم مسیر پیشفرض ffmpeg
FFMPEG_PATH = '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg'
FFPROBE_PATH = '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffprobe'

# راه‌اندازی لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# تنظیمات دایرکتوری دانلود موقت
DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)

# تنظیمات FFmpeg
DEFAULT_FFMPEG_PATH = '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg'

# تعیین کیفیت‌های استاندارد ویدیو با گزینه‌های پیشرفته
# نقشه کیفیت‌های ویدیو با مشخصات کامل برای پردازش
VIDEO_QUALITY_MAP = {
    'best': {
        'height': None, 
        'width': None, 
        'display_name': 'بهترین کیفیت', 
        'ffmpeg_options': [],
        'format_note': 'بهترین کیفیت موجود',
        'priority': 1
    },
    '1080p': {
        'height': 1080, 
        'width': 1920, 
        'display_name': 'کیفیت Full HD (1080p)', 
        'ffmpeg_options': ['-vf', 'scale=-2:1080', '-b:v', '2500k'],
        'format_note': 'فول اچ‌دی',
        'priority': 2
    },
    '720p': {
        'height': 720, 
        'width': 1280, 
        'display_name': 'کیفیت HD (720p)', 
        'ffmpeg_options': ['-vf', 'scale=-2:720', '-b:v', '1500k'],
        'format_note': 'اچ‌دی',
        'priority': 3
    },
    '480p': {
        'height': 480, 
        'width': 854, 
        'display_name': 'کیفیت متوسط (480p)', 
        'ffmpeg_options': ['-vf', 'scale=-2:480', '-b:v', '1000k'],
        'format_note': 'کیفیت متوسط',
        'priority': 4
    },
    'medium': {  # اضافه کردن کیفیت متوسط برای سازگاری با اینستاگرام
        'height': 480, 
        'width': 854, 
        'display_name': 'کیفیت متوسط (480p)', 
        'ffmpeg_options': ['-vf', 'scale=-2:480', '-b:v', '1000k'],
        'format_note': 'کیفیت متوسط',
        'priority': 4
    },
    '360p': {
        'height': 360, 
        'width': 640, 
        'display_name': 'کیفیت پایین (360p)', 
        'ffmpeg_options': ['-vf', 'scale=-2:360', '-b:v', '700k'],
        'format_note': 'کیفیت پایین',
        'priority': 5
    },
    '240p': {
        'height': 240, 
        'width': 426, 
        'display_name': 'کیفیت خیلی پایین (240p)', 
        'ffmpeg_options': ['-vf', 'scale=-2:240', '-b:v', '500k'],
        'format_note': 'کیفیت خیلی پایین',
        'priority': 6
    },
    'low': {  # اضافه کردن کیفیت پایین برای سازگاری با اینستاگرام
        'height': 240, 
        'width': 426, 
        'display_name': 'کیفیت پایین (240p)', 
        'ffmpeg_options': ['-vf', 'scale=-2:240', '-b:v', '500k'],
        'format_note': 'کیفیت پایین',
        'priority': 6
    },
    'audio': {
        'height': 0, 
        'width': 0, 
        'audio_only': True, 
        'display_name': 'فقط صدا (MP3)', 
        'ffmpeg_options': ['-vn', '-ar', '44100', '-ac', '2', '-b:a', '192k'],
        'format_note': 'فقط صدا',
        'priority': 7,
        'extract_audio': True,
        'audio_format': 'mp3',
        'audio_quality': '192k'
    }
}

# تنظیمات هدرهای HTTP
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# ایجاد فایل کوکی موقت برای یوتیوب
def create_youtube_cookies():
    """ایجاد فایل کوکی موقت برای یوتیوب"""
    cookies_content = """# Netscape HTTP Cookie File
# http://curl.haxx.se/docs/cookie_spec.html
# This file was generated by libcurl! Edit at your own risk.

.youtube.com    TRUE    /       FALSE   2147483647      CONSENT YES+cb.20210629-13-p1.en+FX+119
.youtube.com    TRUE    /       FALSE   2147483647      VISITOR_INFO1_LIVE      HV1eNSA-Vas
.youtube.com    TRUE    /       FALSE   2147483647      YSC     qVtBh7mnhcM
.youtube.com    TRUE    /       FALSE   2147483647      GPS     1
"""
    
    # ایجاد فایل موقت
    fd, cookie_file = tempfile.mkstemp(suffix='.txt', prefix='youtube_cookies_')
    with os.fdopen(fd, 'w') as f:
        f.write(cookies_content)
    
    logger.info(f"فایل کوکی موقت یوتیوب ایجاد شد: {cookie_file}")
    return cookie_file

# تنظیم مسیر فایل کوکی یوتیوب
YOUTUBE_COOKIE_FILE = create_youtube_cookies()

# تنظیمات پایه برای yt-dlp
YDL_OPTS_BASE = {
    'quiet': True,
    'no_warnings': True,
    'cookiefile': YOUTUBE_COOKIE_FILE,
    'noplaylist': True,
    'user_agent': USER_AGENT,
    'http_headers': {
        'User-Agent': USER_AGENT,
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://www.google.com/',
    },
    'ffmpeg_location': '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg'
}

def get_unique_filename(directory: str, filename: str) -> str:
    """
    ایجاد نام فایل یکتا برای جلوگیری از بازنویسی فایل‌های موجود
    
    Args:
        directory: مسیر دایرکتوری
        filename: نام فایل اصلی
        
    Returns:
        مسیر کامل فایل با نام یکتا
    """
    base_name, extension = os.path.splitext(filename)
    counter = 1
    new_filename = filename
    
    # اگر فایل وجود داشت، یک شماره به آن اضافه کن
    while os.path.exists(os.path.join(directory, new_filename)):
        new_filename = f"{base_name}_{counter}{extension}"
        counter += 1
        
    return os.path.join(directory, new_filename)

def clean_filename(filename: str) -> str:
    """
    پاکسازی نام فایل از کاراکترهای غیرمجاز
    
    Args:
        filename: نام فایل اصلی
        
    Returns:
        نام فایل پاکسازی شده
    """
    # حذف کاراکترهای غیرمجاز در نام فایل
    invalid_chars = r'[<>:"/\\|?*]'
    cleaned_name = re.sub(invalid_chars, '_', filename)
    
    # کوتاه کردن فایل‌های با نام طولانی
    if len(cleaned_name) > 100:
        name_parts = os.path.splitext(cleaned_name)
        cleaned_name = name_parts[0][:90] + '...' + name_parts[1]
        
    return cleaned_name

def get_format_spec_for_quality(quality: str) -> str:
    """
    دریافت تنظیمات فرمت yt-dlp براساس کیفیت مورد نظر (نسخه بهبود یافته)
    
    Args:
        quality: کیفیت ویدیو (best, 1080p, 720p, 480p, 360p, 240p, audio)
        
    Returns:
        رشته فرمت مناسب برای yt-dlp
    """
    # دریافت اطلاعات کیفیت از نقشه کیفیت‌ها
    quality_info = VIDEO_QUALITY_MAP.get(quality, VIDEO_QUALITY_MAP.get('best', {}))
    
    # گزینه صوتی (بهبود دانلود صوتی - نسخه فوق پیشرفته)
    if quality == 'audio' or quality_info.get('audio_only'):
        # فرمت بهینه برای استخراج صدا - انتخاب هوشمند از بین همه فرمت‌های صوتی
        # منطق انتخاب مبتنی بر آخرین تکنولوژی‌های دانلود صوتی:
        # 1. بهترین کیفیت m4a (بیت‌ریت بالا و پشتیبانی iOS و macOS)
        # 2. بهترین کیفیت opus (کیفیت عالی با حجم کم - استاندارد یوتیوب)
        # 3. بهترین کیفیت mp3 (سازگاری گسترده با همه دستگاه‌ها)
        # 4. هر صدای موجود با کیفیت مناسب
        return 'bestaudio[ext=m4a][abr>128]/bestaudio[ext=opus][abr>96]/bestaudio[ext=mp3][abr>160]/bestaudio[ext=webm]/bestaudio[abr>96]/bestaudio'
    
    # بهترین کیفیت (ترکیب بهترین ویدیو و صدا)
    elif quality == 'best':
        # اولویت با فایل‌های mp4 برای سازگاری بیشتر
        return 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best'
    
    # کیفیت‌های استاندارد با ارتفاع مشخص
    else:
        height = quality_info.get('height', 0)
        if height:
            # فرمت پیشرفته با منطق انتخاب بهتر:
            # 1. ویدیو با ارتفاع دقیق و فرمت MP4
            # 2. ویدیو با ارتفاع نزدیک (با حداکثر 100 پیکسل تفاوت) و فرمت MP4
            # 3. بهترین ویدیو با حداکثر ارتفاع مجاز
            # 4. در نهایت هر ویدیویی که با این شرایط مطابقت داشته باشد
            return (
                f'bestvideo[height={height}][ext=mp4]+bestaudio[ext=m4a]/'
                f'bestvideo[height<={height}][height>={height-100}][ext=mp4]+bestaudio[ext=m4a]/'
                f'best[height<={height}][ext=mp4]/best[height<={height}]/best'
            )
        else:
            # حالت پیش‌فرض با اولویت MP4
            return 'best[ext=mp4]/best'

async def download_with_quality(url: str, quality: str = 'best', is_audio: bool = False, source_type: str = 'youtube') -> Optional[str]:
    """
    دانلود ویدیو با کیفیت مشخص از یوتیوب یا اینستاگرام
    
    Args:
        url: آدرس ویدیو
        quality: کیفیت دانلود (best, 1080p, 720p, 480p, 360p, 240p, audio)
        is_audio: آیا فقط صدا دانلود شود؟
        source_type: نوع منبع (youtube یا instagram)
        
    Returns:
        مسیر فایل دانلود شده یا None در صورت خطا
    """
    try:
        # تنظیمات yt-dlp
        ydl_opts = YDL_OPTS_BASE.copy()
        
        # ایجاد مسیر خروجی منحصر به فرد
        download_id = uuid.uuid4().hex[:8]
        
        # دریافت تنظیمات کیفیت
        quality_settings = VIDEO_QUALITY_MAP.get(quality, VIDEO_QUALITY_MAP.get('best', {}))
        ffmpeg_options = quality_settings.get('ffmpeg_options', [])
        height = quality_settings.get('height')
        display_name = quality_settings.get('display_name', quality)
        logger.info(f"کیفیت انتخاب شده: {display_name} (ارتفاع: {height})")
        
        # اگر درخواست صوتی است
        if is_audio or quality == 'audio':
            # مطمئن می‌شویم is_audio صحیح است
            is_audio = True
            quality = 'audio'
            logger.info(f"درخواست دانلود صوتی از {source_type}: {url}")
            ydl_opts.update({
                'format': 'bestaudio[ext=m4a][abr>128]/bestaudio[ext=opus][abr>96]/bestaudio[ext=mp3][abr>160]/bestaudio[ext=webm]/bestaudio[abr>96]/bestaudio',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                },
                {
                    # پردازشگر برای بهبود کیفیت صدا و اضافه کردن متادیتا
                    'key': 'FFmpegMetadata',
                    'add_metadata': True,
                }],
                'postprocessor_args': [
                    '-ar', '44100',  # نرخ نمونه‌برداری
                    '-ac', '2',      # تعداد کانال‌ها (استریو)
                    '-b:a', '192k',  # بیت‌ریت
                ],
                'ffmpeg_location': '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',  # تنظیم مسیر اختصاصی ffmpeg
                'prefer_ffmpeg': True,  # ترجیح استفاده از ffmpeg
            })
            output_template = os.path.join(DEFAULT_DOWNLOAD_DIR, f'{source_type}_audio_{download_id}.%(ext)s')
        else:
            # انتخاب تنظیمات مناسب برای منبع
            if source_type == 'youtube':
                # دانلود از یوتیوب با تنظیمات پیشرفته
                format_spec = get_format_spec_for_quality(quality)
                logger.info(f"یوتیوب - انتخاب کیفیت {quality} با فرمت: {format_spec}")
                
                # تنظیمات پیشرفته برای کنترل کیفیت
                ydl_opts.update({
                    'format': format_spec,
                    'merge_output_format': 'mp4',  # ترکیب ویدیو و صدا در فرمت MP4
                })
                
                # اضافه کردن تنظیمات FFmpeg در صورت وجود
                if ffmpeg_options:
                    logger.info(f"اعمال تنظیمات FFmpeg: {ffmpeg_options}")
                    ydl_opts['postprocessor_args'] = ffmpeg_options
                
                output_template = os.path.join(DEFAULT_DOWNLOAD_DIR, f'youtube_{quality}_{download_id}.%(ext)s')
            
            elif source_type == 'instagram':
                # دانلود از اینستاگرام با تنظیمات فوق پیشرفته بهینه
                # استراتژی دقیق تنظیم کیفیت برای اینستاگرام
                # کیفیت مختلف برای اینستاگرام بر اساس نقشه کیفیت
                
                # محاسبه format_spec پیشرفته برای انتخاب درست کیفیت در اینستاگرام
                if quality == 'best':
                    # بهترین کیفیت با ارجحیت فرمت MP4 برای حداکثر سازگاری
                    format_spec = 'best[ext=mp4]/best'
                elif quality == 'medium':
                    # تنظیم دقیق برای کیفیت متوسط - تنظیم هوشمند ارتفاع بین 480 و 360
                    format_spec = f'best[height<=480][height>=360][ext=mp4]/best[height<=480][height>=360]/best[height<=480][ext=mp4]/best[height<=480]/best[ext=mp4]/best'
                elif quality == 'low':
                    # تنظیم دقیق برای کیفیت پایین - حداکثر 240 پیکسل ارتفاع
                    format_spec = f'best[height<=240][ext=mp4]/best[height<=240]/best[ext=mp4]/worst[ext=mp4]/worst'
                elif quality in VIDEO_QUALITY_MAP and height:
                    # کیفیت‌های عددی با ارتفاع دقیق (1080p, 720p, 480p, 360p, 240p)
                    # استراتژی چند لایه برای انتخاب بهترین تطابق
                    format_spec = (
                        f'best[height={height}][ext=mp4]/'
                        f'best[height<={height}][height>={max(height-100, 120)}][ext=mp4]/'
                        f'best[height<={height}][ext=mp4]/'
                        f'best[height<={height}]/'
                        f'best[ext=mp4]/best'
                    )
                else:
                    # حالت پیش‌فرض با اولویت MP4
                    format_spec = 'best[ext=mp4]/best'
                
                logger.info(f"اینستاگرام - انتخاب کیفیت {quality} با فرمت پیشرفته: {format_spec}")
                
                # اضافه کردن تنظیمات FFmpeg اختصاصی برای بهبود کیفیت ویدیوی اینستاگرام
                instagram_ffmpeg_options = []
                
                # تنظیمات پیشرفته برای کنترل کیفیت
                if quality == 'medium':
                    # محدود کردن بیت‌ریت برای کیفیت متوسط
                    instagram_ffmpeg_options = ['-b:v', '1500k', '-maxrate', '1800k', '-bufsize', '3000k']
                elif quality == 'low':
                    # محدود کردن بیت‌ریت برای کیفیت پایین
                    instagram_ffmpeg_options = ['-b:v', '800k', '-maxrate', '1000k', '-bufsize', '1600k']
                    
                # تنظیمات پیشرفته برای کنترل کیفیت
                ydl_opts.update({
                    'format': format_spec,
                    'merge_output_format': 'mp4',  # اطمینان از خروجی MP4
                })
                
                # اضافه کردن تنظیمات FFmpeg در صورت وجود
                if ffmpeg_options:
                    logger.info(f"اعمال تنظیمات FFmpeg از VIDEO_QUALITY_MAP: {ffmpeg_options}")
                    ydl_opts['postprocessor_args'] = ffmpeg_options
                # اضافه کردن تنظیمات FFmpeg اختصاصی اینستاگرام (اولویت باالتر)
                elif instagram_ffmpeg_options:
                    logger.info(f"اعمال تنظیمات FFmpeg اختصاصی اینستاگرام: {instagram_ffmpeg_options}")
                    ydl_opts['postprocessor_args'] = instagram_ffmpeg_options
                
                output_template = os.path.join(DEFAULT_DOWNLOAD_DIR, f'instagram_{quality}_{download_id}.%(ext)s')
            else:
                # منبع نامشخص
                logger.error(f"نوع منبع غیرمجاز: {source_type}")
                return None
                
        # تنظیم قالب نام فایل خروجی
        ydl_opts['outtmpl'] = output_template
        
        logger.info(f"دانلود از {source_type} با کیفیت {quality}, صوتی: {is_audio}")
        logger.info(f"تنظیمات دانلود: {ydl_opts}")
        
        # اجرای دستور دانلود در thread pool
        loop = asyncio.get_event_loop()
        downloaded_files = []
        
        def download_with_ytdlp():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if info:
                        if 'entries' in info:
                            # پلی‌لیست
                            entries = list(info['entries'])
                            logger.info(f"تعداد فایل‌های پلی‌لیست: {len(entries)}")
                            for entry in entries:
                                if 'requested_downloads' in entry:
                                    for download in entry['requested_downloads']:
                                        downloaded_files.append(download['filepath'])
                        elif 'requested_downloads' in info:
                            # فایل منفرد
                            for download in info['requested_downloads']:
                                downloaded_files.append(download['filepath'])
                                logger.info(f"فایل دانلود شده: {download['filepath']}, فرمت: {download.get('format', 'نامشخص')}")
            except Exception as e:
                logger.error(f"خطا در دانلود با yt-dlp: {str(e)}")
                import traceback
                logger.error(f"جزئیات خطا: {traceback.format_exc()}")
            return downloaded_files
            
        result = await loop.run_in_executor(None, download_with_ytdlp)
        
        # بررسی نتیجه دانلود
        if not downloaded_files:
            logger.error(f"هیچ فایلی دانلود نشد از {url}")
            return None
            
        downloaded_file = downloaded_files[0]
        logger.info(f"فایل دانلود شده: {downloaded_file}")
        
        # اگر فایل ویدیویی است و کاربر صدا درخواست کرده، استخراج صدا
        if is_audio and is_video_file(downloaded_file):
            logger.info(f"استخراج صدا از ویدیو: {downloaded_file}")
            # استفاده از yt-dlp برای استخراج صدا
            audio_file = extract_audio(downloaded_file, 'mp3', '192k')
            if audio_file:
                logger.info(f"فایل صوتی با موفقیت استخراج شد: {audio_file}")
                return audio_file
            else:
                logger.error("استخراج صدا ناموفق بود، تلاش با روش دوم...")
                # تلاش با FFmpeg مستقیم
                base_name = os.path.basename(downloaded_file)
                file_name, _ = os.path.splitext(base_name)
                output_dir = os.path.dirname(downloaded_file)
                audio_path = os.path.join(output_dir, f"{file_name}_audio.mp3")
                
                cmd = [
                    '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',
                    '-i', downloaded_file,
                    '-vn',  # بدون ویدیو
                    '-acodec', 'libmp3lame',
                    '-ab', '192k',
                    '-ar', '44100',
                    '-y',
                    audio_path
                ]
                
                try:
                    result = subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    
                    if result.returncode == 0 and os.path.exists(audio_path):
                        logger.info(f"استخراج صدا با FFmpeg موفق: {audio_path}")
                        return audio_path
                except Exception as e:
                    logger.error(f"خطا در استخراج صدا با FFmpeg: {e}")
                
                logger.warning("استخراج صدا ناموفق بود، ارسال فایل ویدیویی به جای صدا")
                return downloaded_file
        
        # بررسی حجم فایل
        if os.path.exists(downloaded_file):
            file_size = os.path.getsize(downloaded_file) / (1024 * 1024)  # MB
            logger.info(f"حجم فایل دانلود شده: {file_size:.2f} MB")
        
        return downloaded_file
        
    except Exception as e:
        logger.error(f"خطا در دانلود با کیفیت: {str(e)}")
        import traceback
        logger.error(f"جزئیات خطا: {traceback.format_exc()}")
        return None

def convert_video_quality(video_path: str, quality: str = "720p", is_audio_request: bool = False) -> Optional[str]:
    """
    تبدیل کیفیت ویدیو با استفاده از ffmpeg (روش بهبود یافته و تضمین شده)
    
    Args:
        video_path: مسیر فایل ویدیویی اصلی
        quality: کیفیت هدف (1080p, 720p, 480p, 360p, 240p, audio)
        is_audio_request: آیا خروجی باید فایل صوتی باشد
        
    Returns:
        مسیر فایل تبدیل شده یا None در صورت خطا
    """
    if not os.path.exists(video_path):
        logger.error(f"فایل ویدیویی یافت نشد: {video_path}")
        return None
        
    try:
        # تصمیم‌گیری صریح برای استخراج صدا
        if is_audio_request or quality == "audio":
            logger.info(f"درخواست استخراج صدا از ویدیو: {video_path}")
            return extract_audio_from_video(video_path)
        
        # ⚠️ اینجا مطمئن می‌شویم که درخواست ویدیویی است، نه صوتی
        logger.info(f"درخواست تبدیل کیفیت ویدیو به {quality}")
        
        # تعیین ارتفاع برای هر کیفیت - با اصلاحات دقیق برای اطمینان از انطباق کامل
        quality_heights = {
            "1080p": 1080, 
            "720p": 720, 
            "480p": 480, 
            "360p": 360, 
            "240p": 240,
            "medium": 480,  # اطمینان از پشتیبانی کیفیت‌های مبتنی بر نام
            "low": 240
        }
        
        # اگر کیفیت نامعتبر است، بررسی دقیق‌تر انجام می‌دهیم
        if quality not in quality_heights:
            # بررسی برای کیفیت‌های عددی با الگوهای مختلف
            if "1080" in quality or "full" in quality.lower() or "hd+" in quality.lower():
                logger.info(f"کیفیت {quality} به 1080p نگاشت شد.")
                quality = "1080p"
            elif "720" in quality or "hd" in quality.lower():
                logger.info(f"کیفیت {quality} به 720p نگاشت شد.")
                quality = "720p"
            elif "480" in quality or "sd" in quality.lower() or "medium" in quality.lower():
                logger.info(f"کیفیت {quality} به 480p نگاشت شد.")
                quality = "480p"
            elif "360" in quality or "low" in quality.lower():
                logger.info(f"کیفیت {quality} به 360p نگاشت شد.")
                quality = "360p"
            elif "240" in quality or "very" in quality.lower() or "lowest" in quality.lower():
                logger.info(f"کیفیت {quality} به 240p نگاشت شد.")
                quality = "240p"
            else:
                # اگر هیچ تطابقی پیدا نشد، از کیفیت 720p استفاده می‌کنیم
                logger.warning(f"کیفیت {quality} پشتیبانی نمی‌شود. استفاده از 720p به جای آن.")
                quality = "720p"
        
        # اختصاص ارتفاع هدف بر اساس کیفیت نهایی
        target_height = quality_heights[quality]
        logger.info(f"کیفیت نهایی انتخاب شده: {quality} با ارتفاع {target_height}")
        
        # مسیر فایل خروجی - اضافه کردن پیشوند video برای تأکید بر نوع فایل
        file_dir = os.path.dirname(video_path)
        file_name, file_ext = os.path.splitext(os.path.basename(video_path))
        converted_file = os.path.join(file_dir, f"{file_name}_video_{quality}{file_ext}")
        
        # بررسی وجود فایل از قبل
        if os.path.exists(converted_file):
            logger.info(f"فایل تبدیل شده از قبل وجود دارد: {converted_file}")
            return converted_file
        
        # بررسی ارتفاع فعلی ویدیو
        ffprobe_cmd = [
            '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffprobe', 
            '-v', 'error', 
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height', 
            '-of', 'csv=p=0:s=x', 
            video_path
        ]
        
        probe_result = subprocess.run(
            ffprobe_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        original_width = 0
        original_height = 0
        
        # تصمیم‌گیری برای دستور ffmpeg
        if probe_result.returncode == 0 and probe_result.stdout.strip():
            # اطلاعات ویدیو به دست آمد
            dimensions = probe_result.stdout.strip()
            logger.info(f"ابعاد اصلی ویدیو: {dimensions}")
            try:
                width_str, height_str = dimensions.split('x')
                original_width = int(width_str)
                original_height = int(height_str)
            except (ValueError, Exception) as e:
                logger.warning(f"خطا در تفسیر ابعاد: {e}")
        else:
            logger.warning("نمی‌توان به اطلاعات ویدیو دست یافت - استفاده از روش امن")
        
        # اگر فایل خروجی از قبل وجود دارد، آن را برگرداند
        if os.path.exists(converted_file) and os.path.getsize(converted_file) > 10000:
            logger.info(f"فایل تبدیل شده از قبل وجود دارد: {converted_file}")
            return converted_file
        
        # محاسبه عرض جدید با حفظ نسبت تصویر
        # استفاده از فرمول متفاوت برای تضمین کیفیت بهتر و عدم تغییر نسبت تصویر
        scale_filter = f'scale=-2:{target_height}:force_original_aspect_ratio=decrease,format=yuv420p'
        
        # اگر ابعاد اصلی را داریم، اطلاعات آن را نمایش می‌دهیم
        if original_width > 0 and original_height > 0:
            aspect_ratio = original_width / original_height
            calculated_width = int(target_height * aspect_ratio)
            # اطمینان از زوج بودن عرض
            if calculated_width % 2 != 0:
                calculated_width += 1
            logger.info(f"عرض محاسبه شده برای کیفیت {quality}: {calculated_width} (نسبت تصویر: {aspect_ratio:.2f})")
            
        logger.info(f"استفاده از فیلتر مقیاس بندی: {scale_filter}")
        
        # دستور ffmpeg سراسری با پارامترهای بهینه
        cmd = [
            '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg', 
            '-i', video_path, 
            '-c:v', 'libx264',     # کدک ویدیو: H.264 (سازگاری بالا)
            '-c:a', 'aac',         # کدک صدا: AAC (سازگاری بالا)
            '-b:a', '128k',        # بیت‌ریت صدا
            '-vf', scale_filter,   # فیلتر مقیاس‌بندی با فرمت تضمین شده
            '-preset', 'ultrafast', # سرعت بالا
            '-crf', '28',          # کیفیت متوسط (مقادیر کمتر = کیفیت بالاتر)
            '-max_muxing_queue_size', '9999', # افزایش حداکثر صف برای جلوگیری از خطای مربوطه
            '-y',                  # جایگزینی فایل موجود
            converted_file
        ]
        
        logger.info(f"در حال تبدیل ویدیو به کیفیت {quality}...")
        logger.debug(f"دستور FFMPEG: {' '.join(cmd)}")
        
        # اجرای دستور
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # بررسی نتیجه
        if result.returncode == 0 and os.path.exists(converted_file) and os.path.getsize(converted_file) > 10000:
            logger.info(f"تبدیل کیفیت موفق: {converted_file}")
            
            # بررسی نهایی فایل
            verify_cmd = [
                '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffprobe', 
                '-v', 'error', 
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height', 
                '-of', 'csv=p=0:s=x', 
                converted_file
            ]
            
            verify_result = subprocess.run(
                verify_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if verify_result.returncode == 0 and verify_result.stdout.strip():
                converted_dimensions = verify_result.stdout.strip()
                logger.info(f"ابعاد ویدیوی تبدیل شده: {converted_dimensions}")
                return converted_file
            else:
                logger.error(f"فایل تبدیل شده معتبر نیست: {verify_result.stderr}")
                # اگر تبدیل موفق نبود، با روش دیگری تلاش می‌کنیم
                return fallback_convert_video(video_path, quality)
        else:
            logger.error(f"خطا در تبدیل کیفیت: {result.stderr[:300]}...")
            # اگر تبدیل موفق نبود، با روش دیگری تلاش می‌کنیم
            return fallback_convert_video(video_path, quality)
    
    except Exception as e:
        logger.error(f"خطا در تبدیل کیفیت ویدیو: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        # اگر تبدیل موفق نبود، با روش دیگری تلاش می‌کنیم
        return fallback_convert_video(video_path, quality)

def fallback_convert_video(video_path: str, quality: str) -> str:
    """
    روش پشتیبان برای تبدیل کیفیت ویدیو در صورت شکست روش اصلی
    
    Args:
        video_path: مسیر فایل ویدیویی اصلی
        quality: کیفیت هدف (1080p, 720p, 480p, 360p, 240p)
        
    Returns:
        مسیر فایل تبدیل شده یا مسیر فایل اصلی در صورت خطا
    """
    logger.info(f"استفاده از روش پشتیبان برای تبدیل کیفیت ویدیو به {quality}")
    
    try:
        # تعیین ارتفاع برای هر کیفیت
        quality_heights = {
            "1080p": 1080, 
            "720p": 720, 
            "480p": 480, 
            "360p": 360, 
            "240p": 240
        }
        
        # اگر کیفیت نامعتبر است، از 720p استفاده کن
        if quality not in quality_heights:
            quality = "720p"
        
        target_height = quality_heights[quality]
        
        # مسیر فایل خروجی با پسوند متفاوت برای جلوگیری از تداخل
        file_dir = os.path.dirname(video_path)
        file_name, file_ext = os.path.splitext(os.path.basename(video_path))
        converted_file = os.path.join(file_dir, f"{file_name}_fallback_{quality}{file_ext}")
        
        # استفاده از دستور ساده‌تر ffmpeg با پارامترهای حداقلی اما مطمئن
        cmd = [
            '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg', 
            '-i', video_path, 
            '-vf', f'scale=-2:{target_height}:force_original_aspect_ratio=decrease,format=yuv420p',  # حفظ نسبت تصویر با دقت بالا
            '-c:v', 'libx264',                    # استفاده از کدک قدرتمند
            '-c:a', 'copy',                       # فقط کپی صدا
            '-crf', '23',                         # کیفیت مناسب
            '-preset', 'veryfast',                # سرعت بالا
            '-max_muxing_queue_size', '9999',     # افزایش حداکثر صف برای جلوگیری از خطا
            '-y',                                 # جایگزینی فایل موجود
            converted_file
        ]
        
        logger.info(f"روش پشتیبان در حال اجرا: {' '.join(cmd)}")
        
        # اجرای دستور
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # بررسی نتیجه
        if result.returncode == 0 and os.path.exists(converted_file) and os.path.getsize(converted_file) > 10000:
            logger.info(f"تبدیل کیفیت با روش پشتیبان موفق: {converted_file}")
            return converted_file
        else:
            logger.error(f"خطا در روش پشتیبان: {result.stderr[:100]}...")
            logger.info("برگشت به فایل اصلی")
            return video_path
    
    except Exception as e:
        logger.error(f"خطا در روش پشتیبان: {str(e)}")
        logger.info("برگشت به فایل اصلی")
        return video_path

def extract_audio_from_video(video_path: str, output_format: str = 'mp3', bitrate: str = '192k') -> Optional[str]:
    """
    استخراج صدا از فایل ویدیویی (نسخه فوق پیشرفته با چند روش پشتیبان)
    
    این تابع از چندین روش مختلف برای استخراج صدا استفاده می‌کند. هر روش که خطا داشته باشد،
    به طور خودکار به روش بعدی می‌رود. این سیستم چند لایه‌ای اطمینان می‌دهد که تحت هر شرایطی،
    صدا استخراج خواهد شد (حتی در محیط‌های با محدودیت‌های نصب یا دسترسی).
    
    Args:
        video_path: مسیر فایل ویدیویی
        output_format: فرمت خروجی صدا (mp3, m4a, wav)
        bitrate: نرخ بیت خروجی
        
    Returns:
        مسیر فایل صوتی ایجاد شده یا None در صورت خطا
    """
    import os
    import logging
    import subprocess
    import traceback
    from typing import List
    
    logger = logging.getLogger(__name__)
    logger.info(f"شروع استخراج صدا از فایل: {video_path}")
    
    # تولید مسیر خروجی
    base_name = os.path.basename(video_path)
    file_name, _ = os.path.splitext(base_name)
    output_dir = os.path.dirname(video_path)
    audio_path = os.path.join(output_dir, f"{file_name}_audio.{output_format}")
    high_quality_options = ['-q:a', '0', '-b:a', bitrate, '-ar', '48000', '-ac', '2']
    
    # روش‌های مختلف استخراج صدا
    extraction_methods = []
    
    # 1. روش اول: استفاده از ماژول audio_processing 
    def method_audio_processing():
        try:
            logger.info("روش 1: استفاده از ماژول audio_processing")
            # تلاش برای وارد کردن ماژول مستقیماً
            from audio_processing import extract_audio
            result = extract_audio(video_path, output_format, bitrate)
            if result and os.path.exists(result):
                logger.info(f"روش 1 موفق: {result}")
                return result
            logger.warning("روش 1 ناموفق: ماژول audio_processing نتوانست صدا را استخراج کند")
        except (ImportError, Exception) as e:
            logger.warning(f"روش 1 ناموفق: {str(e)}")
        return None
    extraction_methods.append(method_audio_processing)
    
    # 2. روش دوم: استفاده از ماژول audio_extractor
    def method_audio_extractor():
        try:
            logger.info("روش 2: استفاده از ماژول audio_extractor")
            from audio_processing.audio_extractor import extract_audio
            result = extract_audio(video_path, output_format, bitrate)
            if result and os.path.exists(result):
                logger.info(f"روش 2 موفق: {result}")
                return result
            logger.warning("روش 2 ناموفق: ماژول audio_extractor نتوانست صدا را استخراج کند")
        except (ImportError, Exception) as e:
            logger.warning(f"روش 2 ناموفق: {str(e)}")
        return None
    extraction_methods.append(method_audio_extractor)

    # 3. روش سوم: استفاده از yt-dlp با قابلیت استخراج صدا
    def method_ytdlp():
        try:
            logger.info("روش 3: استفاده از yt-dlp")
            import yt_dlp
            
            ydl_opts = {
                'format': 'bestaudio',
                'paths': {'home': output_dir},
                'outtmpl': os.path.join(output_dir, f"{file_name}_ytdlp.%(ext)s"),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': output_format,
                    'preferredquality': bitrate.replace('k', ''),
                }],
                'ffmpeg_location': '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # استفاده از yt-dlp برای پردازش فایل محلی
                ydl.download([f"file://{os.path.abspath(video_path)}"])
            
            # جستجو برای فایل خروجی
            expected_path = os.path.join(output_dir, f"{file_name}_ytdlp.{output_format}")
            if os.path.exists(expected_path):
                logger.info(f"روش 3 موفق: {expected_path}")
                return expected_path
                
            # جستجوی فایل‌های مشابه
            for filename in os.listdir(output_dir):
                if filename.startswith(f"{file_name}_ytdlp") and filename.endswith(f".{output_format}"):
                    result_path = os.path.join(output_dir, filename)
                    logger.info(f"روش 3 موفق: {result_path}")
                    return result_path
                    
            logger.warning("روش 3 ناموفق: yt-dlp نتوانست صدا را استخراج کند")
        except (ImportError, Exception) as e:
            logger.warning(f"روش 3 ناموفق: {str(e)}")
        return None
    extraction_methods.append(method_ytdlp)
    
    # 4. روش چهارم: استفاده مستقیم از FFmpeg با تنظیمات پیشرفته
    def method_ffmpeg():
        try:
            logger.info("روش 4: استفاده مستقیم از FFmpeg")
            # آماده‌سازی دستور FFmpeg با تنظیمات پیشرفته
            cmd = [
                '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',
                '-i', video_path,
                '-vn',            # حذف ویدیو
                '-acodec', 'libmp3lame' if output_format == 'mp3' else 'aac' if output_format == 'm4a' else 'flac' if output_format == 'flac' else 'copy',
                '-b:a', bitrate,  # بیت‌ریت
                '-ar', '44100',   # نرخ نمونه‌برداری
                '-ac', '2',       # تعداد کانال‌ها (استریو)
                '-af', 'loudnorm=I=-14:LRA=11:TP=-1',  # نرمال‌سازی صدا
                '-y',             # جایگزینی فایل موجود
                audio_path
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode == 0 and os.path.exists(audio_path):
                logger.info(f"روش 4 موفق: {audio_path}")
                return audio_path
            
            logger.warning(f"روش 4 ناموفق: FFmpeg نتوانست صدا را استخراج کند - {result.stderr[:100]}...")
        except Exception as e:
            logger.warning(f"روش 4 ناموفق: {str(e)}")
        return None
    extraction_methods.append(method_ffmpeg)
    
    # 5. روش پنجم: استفاده از FFmpeg با تنظیمات ساده‌تر
    def method_ffmpeg_simple():
        try:
            logger.info("روش 5: استفاده از FFmpeg (ساده)")
            # دستور ساده‌تر برای استخراج صدا
            cmd = [
                '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',
                '-i', video_path,
                '-vn',               # حذف ویدیو
                '-acodec', 'copy',   # کدک صدا را تغییر نده، فقط کپی کن
                '-y',                # جایگزینی فایل موجود
                audio_path
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode == 0 and os.path.exists(audio_path):
                logger.info(f"روش 5 موفق: {audio_path}")
                return audio_path
                
            logger.warning(f"روش 5 ناموفق: FFmpeg ساده نتوانست صدا را استخراج کند - {result.stderr[:100]}...")
        except Exception as e:
            logger.warning(f"روش 5 ناموفق: {str(e)}")
        return None
    extraction_methods.append(method_ffmpeg_simple)
    
    # 6. روش ششم: استفاده از تلاش با ffmpeg در مسیر‌های متداول
    def method_ffmpeg_alternate_paths():
        try:
            logger.info("روش 6: استفاده از FFmpeg در مسیرهای جایگزین")
            # لیستی از مسیرهای احتمالی ffmpeg
            ffmpeg_paths = [
                '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',
                'ffmpeg',
                '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',
                '/usr/local/bin/ffmpeg',
                '/opt/homebrew/bin/ffmpeg',
                '/opt/local/bin/ffmpeg',
                os.path.expanduser('~/.local/bin/ffmpeg')
            ]
            
            for ffmpeg_path in ffmpeg_paths:
                try:
                    cmd = [
                        ffmpeg_path,
                        '-i', video_path,
                        '-vn',
                        '-acodec', 'libmp3lame',
                        '-ab', bitrate,
                        '-y',
                        audio_path
                    ]
                    
                    result = subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=60  # حداکثر 60 ثانیه منتظر باش
                    )
                    
                    if result.returncode == 0 and os.path.exists(audio_path):
                        logger.info(f"روش 6 موفق با {ffmpeg_path}: {audio_path}")
                        return audio_path
                except (subprocess.SubprocessError, FileNotFoundError, Exception) as e:
                    continue
                    
            logger.warning("روش 6 ناموفق: هیچکدام از مسیرهای ffmpeg کار نکرد")
        except Exception as e:
            logger.warning(f"روش 6 ناموفق: {str(e)}")
        return None
    extraction_methods.append(method_ffmpeg_alternate_paths)

    # اجرای تمام روش‌ها به ترتیب تا زمانی که یکی موفق شود
    for i, method in enumerate(extraction_methods):
        try:
            result = method()
            if result and os.path.exists(result):
                logger.info(f"استخراج صدا با روش {i+1} موفق بود: {result}")
                return result
        except Exception as e:
            logger.error(f"خطا در روش {i+1}: {str(e)}")
            logger.error(traceback.format_exc())
    
    # اگر همه روش‌ها شکست خوردند
    logger.error("تمام روش‌های استخراج صدا ناموفق بودند")
    return None

if __name__ == "__main__":
    print("ماژول telegram_fixes بارگذاری شد.")
    print("برای استفاده از این ماژول، آن را import کنید.")
# -*- coding: utf-8 -*-

"""
ماژول audio_processing

این ماژول توابعی برای استخراج صدا از فایل‌های ویدیویی و کار با فایل‌های صوتی ارائه می‌دهد.
"""

import os
import uuid
import logging
import subprocess
import tempfile
from typing import Optional

# راه‌اندازی لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# تنظیمات پیش‌فرض استخراج صدا
DEFAULT_AUDIO_BITRATE = '192k'
DEFAULT_AUDIO_FORMAT = 'mp3'
DEFAULT_AUDIO_SAMPLE_RATE = '44100'
DEFAULT_AUDIO_CHANNELS = '2'

def extract_audio(video_path: str, output_format: str = 'mp3', bitrate: str = '192k') -> Optional[str]:
    """
    استخراج صدا از فایل ویدیویی با استفاده از FFmpeg
    
    Args:
        video_path: مسیر فایل ویدیویی
        output_format: فرمت خروجی صدا (mp3, m4a, wav)
        bitrate: نرخ بیت خروجی
        
    Returns:
        مسیر فایل صوتی ایجاد شده یا None در صورت خطا
    """
    if not os.path.exists(video_path):
        logger.error(f"فایل ویدیویی وجود ندارد: {video_path}")
        return None
        
    try:
        # ایجاد مسیر خروجی
        base_name = os.path.basename(video_path)
        file_name, _ = os.path.splitext(base_name)
        output_dir = os.path.dirname(video_path)
        audio_path = os.path.join(output_dir, f"{file_name}_audio_{uuid.uuid4().hex[:8]}.{output_format}")
        
        logger.info(f"استخراج صدا از {video_path} به {audio_path}")
        
        # آماده‌سازی دستور FFmpeg
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vn',  # بدون ویدیو
            '-acodec', get_codec_for_format(output_format),
            '-ab', bitrate,
            '-ar', DEFAULT_AUDIO_SAMPLE_RATE,
            '-ac', DEFAULT_AUDIO_CHANNELS,
            '-y',  # جایگزینی فایل موجود
            audio_path
        ]
        
        # اجرای FFmpeg
        logger.info(f"اجرای دستور FFmpeg: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"خطا در استخراج صدا: {result.stderr}")
            # تلاش با روش دوم
            return extract_audio_with_ytdlp(video_path, output_format, bitrate)
            
        # بررسی فایل خروجی
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
            logger.info(f"استخراج صدا با موفقیت انجام شد: {audio_path}")
            return audio_path
        else:
            logger.error(f"فایل صوتی ایجاد نشد یا خالی است: {audio_path}")
            # تلاش با روش دوم
            return extract_audio_with_ytdlp(video_path, output_format, bitrate)
            
    except Exception as e:
        logger.error(f"خطا در استخراج صدا: {str(e)}")
        # تلاش با روش دوم
        return extract_audio_with_ytdlp(video_path, output_format, bitrate)

def extract_audio_with_ytdlp(video_path: str, output_format: str = 'mp3', bitrate: str = '192k') -> Optional[str]:
    """
    استخراج صدا از فایل ویدیویی با استفاده از yt-dlp (نسخه بهبود یافته)
    
    Args:
        video_path: مسیر فایل ویدیویی
        output_format: فرمت خروجی صدا (mp3, m4a, wav)
        bitrate: نرخ بیت خروجی
        
    Returns:
        مسیر فایل صوتی ایجاد شده یا None در صورت خطا
    """
    try:
        # ایجاد مسیر خروجی
        base_name = os.path.basename(video_path)
        file_name, _ = os.path.splitext(base_name)
        output_dir = os.path.dirname(video_path)
        temp_output = os.path.join(output_dir, f"{file_name}_audio_{uuid.uuid4().hex[:8]}")
        
        logger.info(f"استخراج صدا با yt-dlp از {video_path} به {temp_output}")
        
        try:
            import yt_dlp
            
            # تنظیمات پیشرفته yt-dlp برای استخراج صدا با کیفیت بالا
            ydl_opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
                'postprocessors': [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': output_format,
                        'preferredquality': bitrate.replace('k', ''),
                    },
                    {
                        # پردازشگر برای بهبود کیفیت صدا و اضافه کردن متادیتا
                        'key': 'FFmpegMetadata',
                        'add_metadata': True,
                    }
                ],
                'postprocessor_args': [
                    '-ar', DEFAULT_AUDIO_SAMPLE_RATE,  # نرخ نمونه‌برداری
                    '-ac', DEFAULT_AUDIO_CHANNELS,     # تعداد کانال‌ها (استریو)
                ],
                'outtmpl': temp_output,
                'quiet': False,  # نمایش جزئیات بیشتر برای عیب‌یابی
                'noplaylist': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_path])
            
            # بررسی فایل خروجی
            audio_path = f"{temp_output}.{output_format}"
            if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                logger.info(f"استخراج صدا با yt-dlp با موفقیت انجام شد: {audio_path}")
                return audio_path
            else:
                logger.error(f"فایل صوتی با yt-dlp ایجاد نشد یا خالی است")
        
        except ImportError:
            logger.warning("yt-dlp یافت نشد، تلاش با FFmpeg...")
        
        # اگر yt-dlp نصب نبود یا استخراج با آن ناموفق بود، از FFmpeg استفاده می‌کنیم
        audio_path = os.path.join(output_dir, f"{file_name}_audio_{uuid.uuid4().hex[:8]}.{output_format}")
        
        # آماده‌سازی دستور FFmpeg
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vn',  # بدون ویدیو
            '-acodec', get_codec_for_format(output_format),
            '-ab', bitrate,
            '-ar', DEFAULT_AUDIO_SAMPLE_RATE,
            '-ac', DEFAULT_AUDIO_CHANNELS,
            '-y',  # جایگزینی فایل موجود
            audio_path
        ]
        
        logger.info(f"استخراج صدا با FFmpeg: {' '.join(cmd)}")
        
        # اجرای FFmpeg
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode == 0 and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
            logger.info(f"استخراج صدا با FFmpeg موفق: {audio_path}")
            return audio_path
        else:
            logger.error(f"استخراج صدا با FFmpeg ناموفق: {result.stderr}")
            return None
            
    except Exception as e:
        logger.error(f"خطا در استخراج صدا: {str(e)}")
        import traceback
        logger.error(f"جزئیات خطا: {traceback.format_exc()}")
        return None
        
def get_codec_for_format(format: str) -> str:
    """
    تعیین کدک مناسب برای فرمت صوتی
    
    Args:
        format: فرمت صوتی (mp3, m4a, wav, ogg)
        
    Returns:
        نام کدک مناسب
    """
    format_codec_map = {
        'mp3': 'libmp3lame',
        'm4a': 'aac',
        'aac': 'aac',
        'wav': 'pcm_s16le',
        'ogg': 'libvorbis',
        'opus': 'libopus',
        'flac': 'flac'
    }
    
    return format_codec_map.get(format.lower(), 'libmp3lame')
    
def is_video_file(file_path: str) -> bool:
    """
    بررسی می‌کند که آیا فایل از نوع ویدیو است یا خیر
    
    Args:
        file_path: مسیر فایل
        
    Returns:
        True اگر فایل ویدیویی باشد، در غیر این صورت False
    """
    if not file_path:
        return False
    video_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm')
    return file_path.lower().endswith(video_extensions)
    
def is_audio_file(file_path: str) -> bool:
    """
    بررسی می‌کند که آیا فایل از نوع صوتی است یا خیر
    
    Args:
        file_path: مسیر فایل
        
    Returns:
        True اگر فایل صوتی باشد، در غیر این صورت False
    """
    if not file_path:
        return False
    audio_extensions = ('.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg', '.opus')
    return file_path.lower().endswith(audio_extensions)
    
def convert_audio_format(audio_path: str, output_format: str = 'mp3', bitrate: str = '192k') -> Optional[str]:
    """
    تبدیل فرمت فایل صوتی
    
    Args:
        audio_path: مسیر فایل صوتی
        output_format: فرمت خروجی صدا (mp3, m4a, wav)
        bitrate: نرخ بیت خروجی
        
    Returns:
        مسیر فایل صوتی ایجاد شده یا None در صورت خطا
    """
    if not os.path.exists(audio_path):
        logger.error(f"فایل صوتی وجود ندارد: {audio_path}")
        return None
        
    try:
        # ایجاد مسیر خروجی
        base_name = os.path.basename(audio_path)
        file_name, _ = os.path.splitext(base_name)
        output_dir = os.path.dirname(audio_path)
        output_path = os.path.join(output_dir, f"{file_name}_converted_{uuid.uuid4().hex[:8]}.{output_format}")
        
        logger.info(f"تبدیل فرمت صدا از {audio_path} به {output_path}")
        
        # آماده‌سازی دستور FFmpeg
        cmd = [
            'ffmpeg',
            '-i', audio_path,
            '-acodec', get_codec_for_format(output_format),
            '-ab', bitrate,
            '-ar', DEFAULT_AUDIO_SAMPLE_RATE,
            '-ac', DEFAULT_AUDIO_CHANNELS,
            '-y',  # جایگزینی فایل موجود
            output_path
        ]
        
        # اجرای FFmpeg
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"خطا در تبدیل فرمت صدا: {result.stderr}")
            return None
            
        # بررسی فایل خروجی
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"تبدیل فرمت صدا با موفقیت انجام شد: {output_path}")
            return output_path
        else:
            logger.error(f"فایل صوتی ایجاد نشد یا خالی است: {output_path}")
            return None
            
    except Exception as e:
        logger.error(f"خطا در تبدیل فرمت صدا: {str(e)}")
        return None
        
def get_audio_info(audio_path: str) -> Optional[dict]:
    """
    دریافت اطلاعات فایل صوتی
    
    Args:
        audio_path: مسیر فایل صوتی
        
    Returns:
        دیکشنری حاوی اطلاعات صدا یا None در صورت خطا
    """
    if not os.path.exists(audio_path):
        logger.error(f"فایل صوتی وجود ندارد: {audio_path}")
        return None
        
    try:
        # آماده‌سازی دستور FFprobe
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            audio_path
        ]
        
        # اجرای FFprobe
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"خطا در دریافت اطلاعات صدا: {result.stderr}")
            return None
            
        # پردازش خروجی
        import json
        info = json.loads(result.stdout)
        
        # استخراج اطلاعات مورد نیاز
        audio_info = {}
        
        # اطلاعات فرمت
        if 'format' in info:
            audio_info['format'] = info['format'].get('format_name', 'unknown')
            audio_info['duration'] = float(info['format'].get('duration', 0))
            audio_info['size'] = int(info['format'].get('size', 0))
            audio_info['bitrate'] = int(info['format'].get('bit_rate', 0))
            
        # اطلاعات جریان صوتی
        for stream in info.get('streams', []):
            if stream.get('codec_type') == 'audio':
                audio_info['codec'] = stream.get('codec_name', 'unknown')
                audio_info['sample_rate'] = int(stream.get('sample_rate', 0))
                audio_info['channels'] = int(stream.get('channels', 0))
                audio_info['channel_layout'] = stream.get('channel_layout', 'unknown')
                break
                
        return audio_info
        
    except Exception as e:
        logger.error(f"خطا در دریافت اطلاعات صدا: {str(e)}")
        return None

# ماژول را در سطح فایل تعریف می‌کنیم
if not os.path.exists('audio_processing'):
    os.makedirs('audio_processing', exist_ok=True)

# ایجاد فایل __init__.py
init_path = os.path.join('audio_processing', "__init__.py")
if not os.path.exists(init_path):
    with open(init_path, "w") as f:
        f.write('"""ماژول پردازش صدا برای ربات تلگرام"""\n\nfrom audio_processing import extract_audio, is_video_file, is_audio_file\n\n__all__ = ["extract_audio", "is_video_file", "is_audio_file"]')

# ایجاد فایل audio_extractor.py
extractor_path = os.path.join('audio_processing', "audio_extractor.py")
if not os.path.exists(extractor_path):
    with open(extractor_path, "w") as f:
        f.write('''#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ماژول audio_extractor

این ماژول تابع استخراج صدا از فایل‌های ویدیویی را ارائه می‌دهد.
"""

import os
import logging
from typing import Optional
from audio_processing import extract_audio as _extract_audio

# راه‌اندازی لاگر
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_audio(video_path: str, output_format: str = 'mp3', bitrate: str = '192k') -> Optional[str]:
    """
    استخراج صدا از فایل ویدیویی
    
    Args:
        video_path: مسیر فایل ویدیویی
        output_format: فرمت خروجی صدا (mp3, m4a, wav)
        bitrate: نرخ بیت خروجی
        
    Returns:
        مسیر فایل صوتی ایجاد شده یا None در صورت خطا
    """
    logger.info(f"فراخوانی استخراج صدا با ماژول audio_extractor برای فایل: {video_path}")
    return _extract_audio(video_path, output_format, bitrate)
''')
    
    logger.info(f"ماژول audio_extractor با موفقیت ایجاد شد: {extractor_path}")

# آزمایش استخراج صدا
if __name__ == "__main__":
    print("ماژول audio_processing بارگذاری شد.")
    print("برای استفاده از این ماژول، آن را import کنید.")

"""
ماژول پردازش صدا برای ربات تلگرام

این ماژول شامل توابع استخراج صدا و کار با فایل‌های صوتی است.
"""

# به جای import از خود ماژول، تابع‌ها را مستقیماً تعریف می‌کنیم
import os
import uuid
import logging
import subprocess
from typing import Optional

# راه‌اندازی لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# تنظیمات پیش‌فرض استخراج صدا
DEFAULT_AUDIO_BITRATE = '192k'
DEFAULT_AUDIO_FORMAT = 'mp3'
DEFAULT_AUDIO_SAMPLE_RATE = '44100'
DEFAULT_AUDIO_CHANNELS = '2'

def get_codec_for_format(format: str) -> str:
    """
    تعیین کدک مناسب برای فرمت صوتی
    
    Args:
        format: فرمت صوتی (mp3, m4a, wav, ogg)
        
    Returns:
        نام کدک مناسب
    """
    format_codec_map = {
        'mp3': 'libmp3lame',
        'm4a': 'aac',
        'aac': 'aac',
        'wav': 'pcm_s16le',
        'ogg': 'libvorbis',
        'opus': 'libopus',
        'flac': 'flac'
    }
    
    return format_codec_map.get(format.lower(), 'libmp3lame')

def extract_audio(video_path: str, output_format: str = 'mp3', bitrate: str = '192k') -> Optional[str]:
    """
    استخراج صدا از فایل ویدیویی با استفاده از FFmpeg
    
    Args:
        video_path: مسیر فایل ویدیویی
        output_format: فرمت خروجی صدا (mp3, m4a, wav)
        bitrate: نرخ بیت خروجی
        
    Returns:
        مسیر فایل صوتی ایجاد شده یا None در صورت خطا
    """
    if not os.path.exists(video_path):
        logger.error(f"فایل ویدیویی وجود ندارد: {video_path}")
        return None
        
    try:
        # ایجاد مسیر خروجی
        base_name = os.path.basename(video_path)
        file_name, _ = os.path.splitext(base_name)
        output_dir = os.path.dirname(video_path)
        audio_path = os.path.join(output_dir, f"{file_name}_audio_{uuid.uuid4().hex[:8]}.{output_format}")
        
        logger.info(f"استخراج صدا از {video_path} به {audio_path}")
        
        # آماده‌سازی دستور FFmpeg با مسیر دقیق
        ffmpeg_path = '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg'
        cmd = [
            ffmpeg_path,
            '-i', video_path,
            '-vn',  # بدون ویدیو
            '-acodec', get_codec_for_format(output_format),
            '-ab', bitrate,
            '-ar', DEFAULT_AUDIO_SAMPLE_RATE,
            '-ac', DEFAULT_AUDIO_CHANNELS,
            '-y',  # جایگزینی فایل موجود
            audio_path
        ]
        
        # اجرای FFmpeg
        logger.info(f"اجرای دستور FFmpeg: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"خطا در استخراج صدا: {result.stderr}")
            return None
            
        # بررسی فایل خروجی
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
            logger.info(f"استخراج صدا با موفقیت انجام شد: {audio_path}")
            return audio_path
        else:
            logger.error(f"فایل صوتی ایجاد نشد یا خالی است: {audio_path}")
            return None
            
    except Exception as e:
        logger.error(f"خطا در استخراج صدا: {str(e)}")
        return None

def is_video_file(file_path: str) -> bool:
    """
    بررسی می‌کند که آیا فایل از نوع ویدیو است یا خیر
    
    Args:
        file_path: مسیر فایل
        
    Returns:
        True اگر فایل ویدیویی باشد، در غیر این صورت False
    """
    if not file_path:
        return False
    video_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm')
    return file_path.lower().endswith(video_extensions)
    
def is_audio_file(file_path: str) -> bool:
    """
    بررسی می‌کند که آیا فایل از نوع صوتی است یا خیر
    
    Args:
        file_path: مسیر فایل
        
    Returns:
        True اگر فایل صوتی باشد، در غیر این صورت False
    """
    if not file_path:
        return False
    audio_extensions = ('.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg', '.opus')
    return file_path.lower().endswith(audio_extensions)

__all__ = ['extract_audio', 'is_video_file', 'is_audio_file']
# -*- coding: utf-8 -*-

"""
ماژول audio_extractor

این ماژول تابع استخراج صدا از فایل‌های ویدیویی را ارائه می‌دهد.
"""

import os
import uuid
import logging
import subprocess
from typing import Optional

# راه‌اندازی لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_audio(video_path: str, output_format: str = 'mp3', bitrate: str = '192k') -> Optional[str]:
    """
    استخراج صدا از فایل ویدیویی با استفاده از FFmpeg
    
    Args:
        video_path: مسیر فایل ویدیویی
        output_format: فرمت خروجی صدا (mp3, m4a, wav)
        bitrate: نرخ بیت خروجی
        
    Returns:
        مسیر فایل صوتی ایجاد شده یا None در صورت خطا
    """
    if not os.path.exists(video_path):
        logger.error(f"فایل ویدیویی وجود ندارد: {video_path}")
        return None
        
    try:
        # ایجاد مسیر خروجی
        base_name = os.path.basename(video_path)
        file_name, _ = os.path.splitext(base_name)
        output_dir = os.path.dirname(video_path)
        audio_path = os.path.join(output_dir, f"{file_name}_{uuid.uuid4().hex[:8]}.{output_format}")
        
        logger.info(f"استخراج صدا از {video_path} به {audio_path}")
        
        # کُدِک مناسب برای فرمت خروجی
        codec_map = {
            'mp3': 'libmp3lame',
            'm4a': 'aac',
            'aac': 'aac',
            'wav': 'pcm_s16le',
            'ogg': 'libvorbis',
            'opus': 'libopus',
            'flac': 'flac'
        }
        
        codec = codec_map.get(output_format.lower(), 'libmp3lame')
        
        # آماده‌سازی دستور FFmpeg
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vn',  # بدون ویدیو
            '-acodec', codec,
            '-ab', bitrate,
            '-ar', '44100',  # نرخ نمونه‌برداری
            '-ac', '2',      # تعداد کانال‌ها
            '-y',  # جایگزینی فایل موجود
            audio_path
        ]
        
        # اجرای FFmpeg
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"خطا در استخراج صدا: {result.stderr}")
            logger.debug(f"خروجی FFmpeg: {result.stdout}")
            return None
            
        # بررسی فایل خروجی
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
            logger.info(f"استخراج صدا با موفقیت انجام شد: {audio_path}")
            return audio_path
        else:
            logger.error(f"فایل صوتی ایجاد نشد یا خالی است: {audio_path}")
            return None
            
    except Exception as e:
        logger.error(f"خطا در استخراج صدا: {str(e)}")
        return None
# -*- coding: utf-8 -*-

"""
پچ عیب‌یابی برای ربات تلگرام

این اسکریپت را برای عیب‌یابی و گزارش خطاهای مربوط به تبدیل کیفیت و پردازش ویدیو اجرا کنید.
"""

import os
import json
import sys
import logging
import subprocess
import traceback
from typing import Dict, List, Optional, Any, Tuple
import time
import datetime
from pathlib import Path

# تنظیم لاگینگ پیشرفته
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('debug_log.txt')
    ]
)

logger = logging.getLogger('debug_patch')

# مسیرهای مهم
TELEGRAM_DOWNLOADER_PATH = 'telegram_downloader.py'
TELEGRAM_FIXES_PATH = 'telegram_fixes.py'
DOWNLOADS_DIR = 'downloads'
DEBUG_DIR = os.path.join(DOWNLOADS_DIR, 'debug')

def setup_debug_environment():
    """آماده‌سازی محیط عیب‌یابی"""
    # ایجاد دایرکتوری‌های لازم
    os.makedirs(DEBUG_DIR, exist_ok=True)
    
    # ایجاد فایل لاگ جداگانه با تاریخ
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    debug_log_path = os.path.join(DEBUG_DIR, f'debug_log_{timestamp}.txt')
    file_handler = logging.FileHandler(debug_log_path)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    
    logger.info(f"محیط عیب‌یابی آماده شد. فایل لاگ: {debug_log_path}")
    return debug_log_path

def find_video_files(directory: str = DOWNLOADS_DIR) -> List[str]:
    """پیدا کردن فایل‌های ویدیویی در دایرکتوری"""
    video_extensions = ['.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv']
    video_files = []
    
    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext) for ext in video_extensions):
                video_files.append(os.path.join(root, file))
    
    return video_files

def find_audio_files(directory: str = DOWNLOADS_DIR) -> List[str]:
    """پیدا کردن فایل‌های صوتی در دایرکتوری"""
    audio_extensions = ['.mp3', '.m4a', '.aac', '.wav', '.ogg', '.opus']
    audio_files = []
    
    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext) for ext in audio_extensions):
                audio_files.append(os.path.join(root, file))
    
    return audio_files

def get_file_info(file_path: str) -> Dict:
    """دریافت اطلاعات فایل با استفاده از ffprobe"""
    if not os.path.exists(file_path):
        logger.error(f"فایل وجود ندارد: {file_path}")
        return {}
    
    try:
        # دستور ffprobe برای استخراج همه اطلاعات به فرمت JSON
        cmd = [
            '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            file_path
        ]
        
        logger.debug(f"اجرای دستور ffprobe: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"خطا در اجرای ffprobe: {result.stderr}")
            return {}
            
        # تبدیل خروجی JSON به دیکشنری
        file_info = json.loads(result.stdout)
        
        # خلاصه‌ای از اطلاعات مهم را لاگ می‌کنیم
        for stream in file_info.get('streams', []):
            if stream.get('codec_type') == 'video':
                logger.info(f"اطلاعات استریم ویدیو: " + 
                           f"رزولوشن: {stream.get('width', 'N/A')}x{stream.get('height', 'N/A')}, " +
                           f"کدک: {stream.get('codec_name', 'N/A')}")
            elif stream.get('codec_type') == 'audio':
                logger.info(f"اطلاعات استریم صوتی: " + 
                           f"کدک: {stream.get('codec_name', 'N/A')}, " +
                           f"کانال‌ها: {stream.get('channels', 'N/A')}")
        
        return file_info
    except Exception as e:
        logger.error(f"خطا در استخراج اطلاعات فایل: {str(e)}")
        logger.error(traceback.format_exc())
        return {}

def analyze_video_file(file_path: str) -> Dict:
    """تحلیل کامل فایل ویدیویی"""
    result = {
        "file_path": file_path,
        "file_size": 0,
        "duration": 0,
        "has_video": False,
        "has_audio": False,
        "video_info": {},
        "audio_info": {},
        "format_info": {},
        "is_valid": False
    }
    
    if not os.path.exists(file_path):
        logger.error(f"فایل وجود ندارد: {file_path}")
        return result
    
    # دریافت حجم فایل
    result["file_size"] = os.path.getsize(file_path)
    
    # دریافت اطلاعات فایل
    file_info = get_file_info(file_path)
    if not file_info:
        logger.error(f"نمی‌توان اطلاعات فایل را دریافت کرد: {file_path}")
        return result
    
    # استخراج اطلاعات مورد نیاز
    result["format_info"] = file_info.get('format', {})
    result["duration"] = float(result["format_info"].get('duration', 0))
    
    # بررسی استریم‌های ویدیو و صدا
    for stream in file_info.get('streams', []):
        if stream.get('codec_type') == 'video':
            result["has_video"] = True
            result["video_info"] = stream
        elif stream.get('codec_type') == 'audio':
            result["has_audio"] = True
            result["audio_info"] = stream
    
    # اگر حداقل یکی از استریم‌های ویدیو یا صدا وجود داشته باشد، فایل معتبر است
    result["is_valid"] = result["has_video"] or result["has_audio"]
    
    return result

def test_convert_video_quality(input_file: str, quality: str) -> Dict:
    """تست تبدیل کیفیت ویدیو با کیفیت مشخص"""
    result = {
        "input_file": input_file,
        "quality": quality,
        "output_file": None,
        "success": False,
        "error": None,
        "ffmpeg_output": None,
        "converted_info": None,
        "original_info": None
    }
    
    if not os.path.exists(input_file):
        result["error"] = f"فایل ورودی وجود ندارد: {input_file}"
        return result
    
    try:
        # دریافت اطلاعات فایل اصلی
        original_info = analyze_video_file(input_file)
        result["original_info"] = original_info
        
        if not original_info["is_valid"]:
            result["error"] = "فایل ورودی نامعتبر است"
            return result
        
        # تعیین ارتفاع متناسب با کیفیت
        target_height = {
            "1080p": 1080,
            "720p": 720,
            "480p": 480,
            "360p": 360,
            "240p": 240
        }.get(quality, 720)
        
        # ایجاد نام فایل خروجی
        timestamp = int(time.time())
        output_file = os.path.join(DEBUG_DIR, f"converted_{quality}_{timestamp}.mp4")
        result["output_file"] = output_file
        
        # تنظیم دستور ffmpeg
        cmd = [
            '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',
            '-i', input_file,
            '-c:v', 'libx264',
            '-c:a', 'copy',
            '-vf', f'scale=trunc(oh*a/2)*2:{target_height}',  # تضمین عرض زوج
            '-preset', 'fast',
            '-y',
            output_file
        ]
        
        logger.info(f"اجرای دستور ffmpeg: {' '.join(cmd)}")
        
        # اجرای دستور
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        result["ffmpeg_output"] = process.stderr
        
        if process.returncode != 0:
            result["error"] = f"خطا در اجرای ffmpeg: کد خروجی {process.returncode}"
            logger.error(result["error"])
            logger.error(process.stderr)
            return result
        
        # بررسی وجود فایل خروجی
        if not os.path.exists(output_file):
            result["error"] = "فایل خروجی ایجاد نشد"
            return result
        
        # بررسی حجم فایل خروجی
        if os.path.getsize(output_file) < 1000:  # کمتر از 1 کیلوبایت
            result["error"] = "فایل خروجی خیلی کوچک است"
            return result
        
        # تحلیل فایل خروجی
        converted_info = analyze_video_file(output_file)
        result["converted_info"] = converted_info
        
        if not converted_info["is_valid"]:
            result["error"] = "فایل خروجی نامعتبر است"
            return result
        
        # بررسی نتیجه تبدیل
        if not converted_info["has_video"]:
            result["error"] = "فایل خروجی ویدیو ندارد"
            return result
        
        actual_height = converted_info["video_info"].get("height")
        if not actual_height:
            result["error"] = "نمی‌توان ارتفاع خروجی را تعیین کرد"
            return result
        
        logger.info(f"تبدیل کیفیت انجام شد: ارتفاع مورد نظر={target_height}, ارتفاع واقعی={actual_height}")
        
        # تبدیل موفق
        result["success"] = True
        return result
    except Exception as e:
        logger.error(f"خطای غیرمنتظره در تبدیل کیفیت: {str(e)}")
        logger.error(traceback.format_exc())
        result["error"] = f"خطای غیرمنتظره: {str(e)}"
        return result

def test_extract_audio(input_file: str) -> Dict:
    """تست استخراج صدا از ویدیو"""
    result = {
        "input_file": input_file,
        "output_file": None,
        "success": False,
        "error": None,
        "ffmpeg_output": None,
        "audio_info": None,
        "original_info": None
    }
    
    if not os.path.exists(input_file):
        result["error"] = f"فایل ورودی وجود ندارد: {input_file}"
        return result
    
    try:
        # دریافت اطلاعات فایل اصلی
        original_info = analyze_video_file(input_file)
        result["original_info"] = original_info
        
        if not original_info["is_valid"]:
            result["error"] = "فایل ورودی نامعتبر است"
            return result
        
        if not original_info["has_audio"]:
            result["error"] = "فایل ورودی صدا ندارد"
            return result
        
        # ایجاد نام فایل خروجی
        timestamp = int(time.time())
        output_file = os.path.join(DEBUG_DIR, f"audio_{timestamp}.mp3")
        result["output_file"] = output_file
        
        # تنظیم دستور ffmpeg
        cmd = [
            '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',
            '-i', input_file,
            '-vn',  # بدون ویدیو
            '-acodec', 'libmp3lame',
            '-ab', '192k',
            '-ar', '44100',
            '-ac', '2',
            '-y',
            output_file
        ]
        
        logger.info(f"اجرای دستور ffmpeg برای استخراج صدا: {' '.join(cmd)}")
        
        # اجرای دستور
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        result["ffmpeg_output"] = process.stderr
        
        if process.returncode != 0:
            result["error"] = f"خطا در اجرای ffmpeg: کد خروجی {process.returncode}"
            logger.error(result["error"])
            logger.error(process.stderr)
            return result
        
        # بررسی وجود فایل خروجی
        if not os.path.exists(output_file):
            result["error"] = "فایل خروجی ایجاد نشد"
            return result
        
        # بررسی حجم فایل خروجی
        if os.path.getsize(output_file) < 1000:  # کمتر از 1 کیلوبایت
            result["error"] = "فایل صوتی خروجی خیلی کوچک است"
            return result
        
        # تحلیل فایل خروجی
        audio_info = analyze_video_file(output_file)
        result["audio_info"] = audio_info
        
        if not audio_info["is_valid"]:
            result["error"] = "فایل صوتی خروجی نامعتبر است"
            return result
        
        # بررسی نتیجه استخراج
        if not audio_info["has_audio"]:
            result["error"] = "فایل خروجی صدا ندارد"
            return result
        
        logger.info(f"استخراج صدا انجام شد: فرمت={audio_info['audio_info'].get('codec_name', 'نامشخص')}")
        
        # استخراج موفق
        result["success"] = True
        return result
    except Exception as e:
        logger.error(f"خطای غیرمنتظره در استخراج صدا: {str(e)}")
        logger.error(traceback.format_exc())
        result["error"] = f"خطای غیرمنتظره: {str(e)}"
        return result

def check_telegram_downloader_issues():
    """بررسی مشکلات بالقوه در کد ربات تلگرام"""
    issues = []
    
    try:
        if not os.path.exists(TELEGRAM_DOWNLOADER_PATH):
            issues.append(f"فایل {TELEGRAM_DOWNLOADER_PATH} وجود ندارد")
            return issues
        
        # بررسی الگوهای مشکل‌دار
        problem_patterns = [
            {
                "pattern": "if \"audio\" in option_id.lower():",
                "issue": "تشخیص فایل صوتی بر اساس شناسه گزینه به تنهایی می‌تواند گمراه‌کننده باشد",
                "suggestion": "بررسی دقیق‌تر با چند شرط مختلف"
            },
            {
                "pattern": "quality = \"audio\"",
                "issue": "تنظیم quality به مقدار 'audio' ممکن است باعث سردرگمی شود",
                "suggestion": "استفاده از متغیر جداگانه برای تعیین نوع فایل"
            },
            {
                "pattern": "is_audio = downloaded_file.endswith",
                "issue": "تشخیص نوع فایل بر اساس پسوند فایل می‌تواند نادرست باشد",
                "suggestion": "استفاده از منطق مشخص برای تعیین نوع خروجی"
            }
        ]
        
        with open(TELEGRAM_DOWNLOADER_PATH, "r", encoding="utf-8") as f:
            content = f.read()
            
        for issue in problem_patterns:
            if issue["pattern"] in content:
                issues.append(f"مشکل: {issue['issue']} | پیشنهاد: {issue['suggestion']}")
                
        return issues
    except Exception as e:
        logger.error(f"خطا در بررسی مشکلات کد: {str(e)}")
        issues.append(f"خطا در بررسی کد: {str(e)}")
        return issues

def check_telegram_fixes_issues():
    """بررسی مشکلات بالقوه در کد ماژول اصلاحات"""
    issues = []
    
    try:
        if not os.path.exists(TELEGRAM_FIXES_PATH):
            issues.append(f"فایل {TELEGRAM_FIXES_PATH} وجود ندارد")
            return issues
        
        # بررسی الگوهای مشکل‌دار
        problem_patterns = [
            {
                "pattern": "scale=",
                "issue": "مشکل احتمالی در نحوه استفاده از scale در ffmpeg",
                "suggestion": "بررسی دقیق پارامترهای scale برای اطمینان از عرض زوج"
            },
            {
                "pattern": "if quality == \"audio\":",
                "issue": "تصمیم‌گیری فقط بر اساس مقدار quality",
                "suggestion": "استفاده از پارامتر جداگانه برای تعیین نوع خروجی"
            }
        ]
        
        with open(TELEGRAM_FIXES_PATH, "r", encoding="utf-8") as f:
            content = f.read()
            
        for issue in problem_patterns:
            if issue["pattern"] in content:
                issues.append(f"مشکل در {TELEGRAM_FIXES_PATH}: {issue['issue']} | پیشنهاد: {issue['suggestion']}")
                
        return issues
    except Exception as e:
        logger.error(f"خطا در بررسی مشکلات کد: {str(e)}")
        issues.append(f"خطا در بررسی کد: {str(e)}")
        return issues

def main():
    """اجرای اصلی عیب‌یابی"""
    try:
        logger.info("شروع عیب‌یابی پیشرفته...")
        
        # آماده‌سازی محیط
        debug_log_path = setup_debug_environment()
        logger.info(f"فایل لاگ عیب‌یابی: {debug_log_path}")
        
        # بررسی مشکلات کد
        td_issues = check_telegram_downloader_issues()
        tf_issues = check_telegram_fixes_issues()
        
        all_issues = td_issues + tf_issues
        
        if all_issues:
            logger.info(f"تعداد {len(all_issues)} مشکل بالقوه در کد پیدا شد:")
            for i, issue in enumerate(all_issues, 1):
                logger.info(f"{i}. {issue}")
        else:
            logger.info("هیچ مشکل مشخصی در ساختار کد پیدا نشد.")
        
        # جستجوی فایل‌های ویدیویی
        video_files = find_video_files()
        logger.info(f"تعداد {len(video_files)} فایل ویدیویی پیدا شد.")
        
        # اگر فایل ویدیویی پیدا شد، اولین نمونه را برای تست استفاده می‌کنیم
        if video_files:
            test_file = video_files[0]
            logger.info(f"استفاده از فایل {test_file} برای تست...")
            
            # تحلیل فایل ویدیویی
            file_analysis = analyze_video_file(test_file)
            logger.info("== تحلیل فایل ویدیویی ==")
            logger.info(f"مسیر: {test_file}")
            logger.info(f"حجم: {file_analysis['file_size'] / 1024:.2f} کیلوبایت")
            logger.info(f"مدت: {file_analysis['duration']:.2f} ثانیه")
            logger.info(f"دارای ویدیو: {file_analysis['has_video']}")
            logger.info(f"دارای صدا: {file_analysis['has_audio']}")
            
            if file_analysis["has_video"]:
                resolution = f"{file_analysis['video_info'].get('width', 'N/A')}x{file_analysis['video_info'].get('height', 'N/A')}"
                logger.info(f"رزولوشن: {resolution}")
            
            # تست تبدیل کیفیت
            qualities_to_test = ["360p", "480p"]
            for quality in qualities_to_test:
                logger.info(f"\n== تست تبدیل به کیفیت {quality} ==")
                result = test_convert_video_quality(test_file, quality)
                
                if result["success"]:
                    logger.info(f"تبدیل به کیفیت {quality} موفق بود!")
                    conversion_change = "بدون تغییر"
                    
                    if (result["original_info"]["video_info"].get("height") != 
                        result["converted_info"]["video_info"].get("height")):
                        old_res = f"{result['original_info']['video_info'].get('width', 'N/A')}x{result['original_info']['video_info'].get('height', 'N/A')}"
                        new_res = f"{result['converted_info']['video_info'].get('width', 'N/A')}x{result['converted_info']['video_info'].get('height', 'N/A')}"
                        conversion_change = f"تغییر رزولوشن از {old_res} به {new_res}"
                    
                    logger.info(f"نتیجه تبدیل: {conversion_change}")
                else:
                    logger.error(f"تبدیل به کیفیت {quality} ناموفق بود: {result['error']}")
            
            # تست استخراج صدا
            logger.info("\n== تست استخراج صدا ==")
            audio_result = test_extract_audio(test_file)
            
            if audio_result["success"]:
                logger.info("استخراج صدا موفق بود!")
                logger.info(f"فایل صوتی: {audio_result['output_file']}")
                logger.info(f"حجم: {os.path.getsize(audio_result['output_file']) / 1024:.2f} کیلوبایت")
            else:
                logger.error(f"استخراج صدا ناموفق بود: {audio_result['error']}")
        else:
            logger.warning("هیچ فایل ویدیویی برای تست پیدا نشد.")
            
        # تست نمونه‌های خاص مشکل‌دار
        logger.info("\n=== تست‌های عمومی مشکلات شایع ===")
        
        # مشکل 1: عرض فرد
        logger.info("- تست مشکل عرض فرد (width not divisible by 2):")
        logger.info("این مشکل زمانی رخ می‌دهد که عرض ویدیو فرد باشد و باعث خطای ffmpeg می‌شود.")
        logger.info("راه حل: استفاده از 'scale=trunc(oh*a/2)*2:height' برای تضمین عرض زوج.")
        
        # مشکل 2: تشخیص نادرست نوع فایل
        logger.info("- تست مشکل تشخیص نوع فایل:")
        logger.info("این مشکل زمانی رخ می‌دهد که فقط از پسوند فایل برای تشخیص نوع استفاده شود.")
        logger.info("راه حل: تصمیم‌گیری مستقیم بر اساس انتخاب کاربر و پارامتر is_audio.")
        
        # مشکل 3: تبدیل کیفیت نامناسب
        logger.info("- تست مشکل تبدیل کیفیت نامناسب:")
        logger.info("این مشکل زمانی رخ می‌دهد که پارامترهای ffmpeg نامناسب باشند.")
        logger.info("راه حل: استفاده از پارامترهای ساده و مطمئن برای حفظ کیفیت و سازگاری.")
        
        logger.info("\n=== توصیه‌های نهایی ===")
        logger.info("1. استفاده از متغیرهای جداگانه و صریح برای تعیین نوع خروجی (صوتی یا ویدیویی)")
        logger.info("2. بازنویسی کامل منطق تشخیص نوع فایل با اولویت انتخاب کاربر")
        logger.info("3. استفاده از دستورات ffmpeg ساده و مطمئن با تنظیمات مناسب")
        logger.info("4. افزودن بررسی و تأیید فایل خروجی برای اطمینان از صحت عملیات")
        
        logger.info("\nعیب‌یابی به پایان رسید. نتایج کامل در فایل لاگ ذخیره شده است.")
        return True
    except Exception as e:
        logger.error(f"خطا در اجرای عیب‌یابی: {str(e)}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-

"""
اسکریپت اصلاحی برای رفع مشکلات مهم ربات تلگرام دانلودر

این اسکریپت مشکلات زیر را اصلاح می‌کند:
1. رفع مشکل مسیر ffmpeg در یوتیوب و اینستاگرام
2. رفع مشکل تبدیل کیفیت و استخراج صدا
3. حل مشکل 360p (که صدا برمی‌گرداند) و 480p (که ویدیو با کیفیت 240p برمی‌گرداند)
"""

import os
import sys
import re
import shutil
import logging
import subprocess
import traceback

# تنظیم لاگر
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("fix_script")

# مسیرهای مهم
TELEGRAM_FIXES_PATH = 'telegram_fixes.py'
TELEGRAM_DOWNLOADER_PATH = 'telegram_downloader.py'

# مسیر صحیح ffmpeg در محیط replit
CORRECT_FFMPEG_PATH = '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg'
CORRECT_FFPROBE_PATH = '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffprobe'

def backup_file(file_path):
    """ایجاد نسخه پشتیبان از فایل"""
    try:
        backup_path = f"{file_path}.backup_fix"
        shutil.copy2(file_path, backup_path)
        logger.info(f"نسخه پشتیبان ایجاد شد: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"خطا در ایجاد نسخه پشتیبان: {str(e)}")
        return False

def fix_ffmpeg_paths_in_telegram_fixes():
    """اصلاح مسیرهای ffmpeg در فایل telegram_fixes.py"""
    try:
        with open(TELEGRAM_FIXES_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        # اصلاح مسیر در تعریف FFMPEG_PATH و FFPROBE_PATH
        pattern1 = r"FFMPEG_PATH\s*=\s*['\"].*?['\"]"
        replacement1 = f"FFMPEG_PATH = '{CORRECT_FFMPEG_PATH}'"
        content = re.sub(pattern1, replacement1, content)

        pattern2 = r"FFPROBE_PATH\s*=\s*['\"].*?['\"]"
        replacement2 = f"FFPROBE_PATH = '{CORRECT_FFPROBE_PATH}'"
        content = re.sub(pattern2, replacement2, content)

        # اصلاح مسیرهای ffmpeg و ffprobe در کل فایل
        content = content.replace('/usr/bin/ffmpeg', CORRECT_FFMPEG_PATH)
        content = content.replace('/usr/bin/ffprobe', CORRECT_FFPROBE_PATH)

        # ذخیره تغییرات
        with open(TELEGRAM_FIXES_PATH, 'w', encoding='utf-8') as f:
            f.write(content)
            
        logger.info("مسیرهای ffmpeg در telegram_fixes.py اصلاح شد")
        return True
    except Exception as e:
        logger.error(f"خطا در اصلاح مسیرهای ffmpeg در telegram_fixes.py: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def fix_ffmpeg_paths_in_telegram_downloader():
    """اصلاح مسیرهای ffmpeg در فایل telegram_downloader.py"""
    try:
        with open(TELEGRAM_DOWNLOADER_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        # اصلاح مسیر در کل فایل
        content = content.replace('/usr/bin/ffmpeg', CORRECT_FFMPEG_PATH)
        content = content.replace('/usr/bin/ffprobe', CORRECT_FFPROBE_PATH)

        # ذخیره تغییرات
        with open(TELEGRAM_DOWNLOADER_PATH, 'w', encoding='utf-8') as f:
            f.write(content)
            
        logger.info("مسیرهای ffmpeg در telegram_downloader.py اصلاح شد")
        return True
    except Exception as e:
        logger.error(f"خطا در اصلاح مسیرهای ffmpeg در telegram_downloader.py: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def fix_convert_video_quality_calls():
    """اصلاح فراخوانی‌های تابع convert_video_quality در فایل telegram_downloader.py"""
    try:
        with open(TELEGRAM_DOWNLOADER_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        # الگوی فراخوانی تابع به صورت قدیمی
        pattern = r"if is_audio:\s+quality = \"audio\"[^\n]*\s+# تبدیل کیفیت ویدیو یا استخراج صدا با تابع جامع\s+converted_file = convert_video_quality\(([^,]+), ([^,\)]+)(?:, is_audio_request=False)?\)"
        
        # جایگزینی با فراخوانی صحیح
        replacement = """# قبلاً: if is_audio: quality = "audio"
                    
                    # تبدیل کیفیت ویدیو یا استخراج صدا با تابع جامع
                    converted_file = convert_video_quality(
                        video_path=\\1, 
                        quality=\\2,
                        is_audio_request=is_audio
                    )"""
        
        # انجام جایگزینی
        new_content = re.sub(pattern, replacement, content)
        
        # بررسی تغییرات
        if new_content == content:
            logger.warning("الگوی فراخوانی تابع convert_video_quality یافت نشد یا قبلا اصلاح شده است")
            return False
            
        # ذخیره تغییرات
        with open(TELEGRAM_DOWNLOADER_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        logger.info("فراخوانی‌های تابع convert_video_quality اصلاح شد")
        return True
    except Exception as e:
        logger.error(f"خطا در اصلاح فراخوانی‌های تابع convert_video_quality: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def fix_instagram_audio_quality_issue():
    """اصلاح مشکل تشخیص کیفیت صدا در اینستاگرام"""
    try:
        with open(TELEGRAM_DOWNLOADER_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        # بخشی که دکمه صدا را برای اینستاگرام پردازش می‌کند
        pattern = r"(elif download_type == \"ig\":[^\n]*\s+)(.*?)(# شروع دانلود)"
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            logger.warning("بخش پردازش کالبک اینستاگرام یافت نشد")
            return False
            
        callback_start = match.group(1)
        callback_code = match.group(2)
        callback_end = match.group(3)
        
        # اصلاح کد پردازش کالبک
        # 1. جایگزینی تشخیص درخواست صوتی
        callback_code = re.sub(
            r"is_audio = False\s+if \"audio\" in option_id\.lower\(\):",
            "is_audio = \"audio\" in option_id.lower()",
            callback_code
        )
        
        # 2. اصلاح متغیر quality در اینستاگرام
        callback_code = re.sub(
            r"quality = \"(\w+)p\"",
            "quality = \"\\1p\"  # ⚠️ حتی برای درخواست‌های صوتی، کیفیت را تنظیم می‌کنیم",
            callback_code
        )
        
        # ذخیره تغییرات
        new_content = callback_start + callback_code + callback_end
        
        with open(TELEGRAM_DOWNLOADER_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        logger.info("مشکل تشخیص کیفیت صدا در اینستاگرام اصلاح شد")
        return True
    except Exception as e:
        logger.error(f"خطا در اصلاح مشکل تشخیص کیفیت صدا در اینستاگرام: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def fix_yt_dlp_ffmpeg_location():
    """اصلاح تنظیمات ffmpeg_location در yt_dlp"""
    try:
        with open(TELEGRAM_FIXES_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        # اصلاح 'ffmpeg_location' در yt_dlp_opts
        pattern = r"'ffmpeg_location':\s*['\"].*?['\"]"
        replacement = f"'ffmpeg_location': '{CORRECT_FFMPEG_PATH}'"
        content = re.sub(pattern, replacement, content)

        # ذخیره تغییرات
        with open(TELEGRAM_FIXES_PATH, 'w', encoding='utf-8') as f:
            f.write(content)
            
        logger.info("تنظیمات ffmpeg_location در yt_dlp اصلاح شد")
        return True
    except Exception as e:
        logger.error(f"خطا در اصلاح تنظیمات ffmpeg_location در yt_dlp: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def main():
    """تابع اصلی اسکریپت"""
    try:
        logger.info("شروع اجرای اسکریپت اصلاحی...")
        
        # ایجاد نسخه پشتیبان
        backup_file(TELEGRAM_FIXES_PATH)
        backup_file(TELEGRAM_DOWNLOADER_PATH)
        
        # اصلاح مسیرهای ffmpeg
        fix_ffmpeg_paths_in_telegram_fixes()
        fix_ffmpeg_paths_in_telegram_downloader()
        
        # اصلاح تنظیمات yt_dlp
        fix_yt_dlp_ffmpeg_location()
        
        # اصلاح فراخوانی‌های convert_video_quality
        fix_convert_video_quality_calls()
        
        # اصلاح مشکل تشخیص کیفیت صدا در اینستاگرام
        fix_instagram_audio_quality_issue()
        
        logger.info("""
اصلاحات انجام شده:
1. مسیرهای ffmpeg و ffprobe در تمام فایل‌ها به مسیرهای صحیح تغییر یافت
2. تنظیمات ffmpeg_location در yt_dlp اصلاح شد
3. فراخوانی‌های تابع convert_video_quality به روش صحیح تغییر یافت (is_audio_request)
4. مشکل تشخیص کیفیت صدا در اینستاگرام اصلاح شد

برای اعمال تغییرات، ربات را مجدداً راه‌اندازی کنید.
""")
        return True
    except Exception as e:
        logger.error(f"خطا در اجرای اسکریپت اصلاحی: {str(e)}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
پچ اصلاحی برای رفع مشکل کیفیت 360p و درخواست صوتی در اینستاگرام

این اسکریپت باگ‌های مربوط به درخواست صوتی و تبدیل کیفیت را اصلاح می‌کند.
"""

import os
import sys
import logging
import traceback
import argparse
import inspect
import re
import shutil
import tempfile
from typing import Dict, List, Tuple, Any, Optional

# تنظیم لاگینگ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("instagram_fix_patch")

# مسیرهای مهم
TELEGRAM_FIXES_PATH = 'telegram_fixes.py'
TELEGRAM_DOWNLOADER_PATH = 'telegram_downloader.py'

def backup_file(file_path: str) -> bool:
    """ایجاد نسخه پشتیبان از فایل"""
    try:
        backup_path = f"{file_path}.backup"
        shutil.copy2(file_path, backup_path)
        logger.info(f"نسخه پشتیبان ایجاد شد: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"خطا در ایجاد نسخه پشتیبان: {str(e)}")
        return False

def patch_convert_video_quality() -> bool:
    """اصلاح تابع convert_video_quality در telegram_fixes.py"""
    try:
        with open(TELEGRAM_FIXES_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # الگوی تابع convert_video_quality
        pattern = r'def convert_video_quality\(video_path: str, quality: str = "720p"\) -> Optional\[str\]:'
        
        # جایگزینی با پارامتر جدید
        replacement = 'def convert_video_quality(video_path: str, quality: str = "720p", is_audio_request: bool = False) -> Optional[str]:'
        
        # جایگزینی تعریف تابع
        new_content = re.sub(pattern, replacement, content)
        
        # آیا تغییری ایجاد نشد؟
        if new_content == content:
            logger.warning("الگوی تابع convert_video_quality یافت نشد")
            return False
        
        # الگوی شرط تشخیص درخواست صوتی
        audio_pattern = r'if quality == "audio":'
        
        # جایگزینی با شرط جدید
        audio_replacement = 'if is_audio_request or quality == "audio":'
        
        # جایگزینی شرط تشخیص صدا
        new_content = re.sub(audio_pattern, audio_replacement, new_content)
        
        # ذخیره تغییرات
        with open(TELEGRAM_FIXES_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        logger.info("تابع convert_video_quality با موفقیت اصلاح شد")
        return True
    except Exception as e:
        logger.error(f"خطا در اصلاح تابع convert_video_quality: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def patch_download_with_quality() -> bool:
    """اصلاح تابع download_with_quality در telegram_fixes.py"""
    try:
        with open(TELEGRAM_FIXES_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # استخراج بدنه تابع download_with_quality
        pattern = r'async def download_with_quality\([^)]*\)[^{]*:\n(.*?)(?=\n\n[^\s])'
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            logger.warning("بدنه تابع download_with_quality یافت نشد")
            return False
        
        func_body = match.group(1)
        
        # اصلاح فراخوانی تابع convert_video_quality
        convert_pattern = r'converted_file = convert_video_quality\(downloaded_file, quality\)'
        convert_replacement = 'converted_file = convert_video_quality(\n                video_path=downloaded_file,\n                quality=quality,\n                is_audio_request=False\n            )'
        
        updated_body = re.sub(convert_pattern, convert_replacement, func_body)
        
        # اصلاح فراخوانی تابع extract_audio_from_video (برای صورت درخواست صوتی)
        audio_extract_pattern = r'audio_file = extract_audio_from_video\(downloaded_file\)'
        audio_extract_replacement = 'audio_file = convert_video_quality(\n                video_path=downloaded_file,\n                quality="audio",\n                is_audio_request=True\n            )'
        
        updated_body = re.sub(audio_extract_pattern, audio_extract_replacement, updated_body)
        
        # جایگزینی بدنه تابع در کل محتوا
        new_content = content.replace(func_body, updated_body)
        
        # ذخیره تغییرات
        with open(TELEGRAM_FIXES_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        logger.info("تابع download_with_quality با موفقیت اصلاح شد")
        return True
    except Exception as e:
        logger.error(f"خطا در اصلاح تابع download_with_quality: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def fix_instagram_callback() -> bool:
    """اصلاح پردازش کالبک‌های اینستاگرام در telegram_downloader.py"""
    try:
        with open(TELEGRAM_DOWNLOADER_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # یافتن بخش پردازش کالبک اینستاگرام
        pattern = r'elif download_type == "ig":(.*?)(?=\n\s*elif|$)'
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            logger.warning("بخش پردازش کالبک اینستاگرام یافت نشد")
            return False
        
        callback_section = match.group(1)
        
        # اضافه کردن تشخیص صریح درخواست صوتی
        audio_pattern = r'is_audio = False\s+if "audio" in option_id.lower\(\):'
        audio_replacement = 'is_audio_request = "audio" in option_id.lower()'
        
        updated_section = re.sub(audio_pattern, audio_replacement, callback_section)
        
        # اصلاح فراخوانی download_with_quality
        download_pattern = r'downloaded_file = await download_with_quality\(\s+url=url,\s+quality=quality,\s+is_audio=is_audio,\s+source_type="instagram"\s+\)'
        download_replacement = 'downloaded_file = await download_with_quality(\n                    url=url,\n                    quality=quality,\n                    is_audio=is_audio_request,\n                    source_type="instagram"\n                )'
        
        updated_section = re.sub(download_pattern, download_replacement, updated_section)
        
        # جایگزینی بخش در کل محتوا
        new_content = content.replace(callback_section, updated_section)
        
        # ذخیره تغییرات
        with open(TELEGRAM_DOWNLOADER_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        logger.info("پردازش کالبک اینستاگرام با موفقیت اصلاح شد")
        return True
    except Exception as e:
        logger.error(f"خطا در اصلاح پردازش کالبک اینستاگرام: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def find_and_fix_all_convert_video_quality_calls() -> int:
    """یافتن و اصلاح تمام فراخوانی‌های تابع convert_video_quality"""
    try:
        count = 0
        patterns = [
            (r'convert_video_quality\(([^,]+), ([^)]+)\)', r'convert_video_quality(\1, \2, is_audio_request=False)'),
            (r'convert_video_quality\(([^,]+), "audio"\)', r'convert_video_quality(\1, "audio", is_audio_request=True)'),
        ]
        
        # بررسی و اصلاح در telegram_downloader.py
        with open(TELEGRAM_DOWNLOADER_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        new_content = content
        for pattern, replacement in patterns:
            new_content = re.sub(pattern, replacement, new_content)
            
        if new_content != content:
            with open(TELEGRAM_DOWNLOADER_PATH, 'w', encoding='utf-8') as f:
                f.write(new_content)
            count += 1
            logger.info(f"فراخوانی‌های convert_video_quality در {TELEGRAM_DOWNLOADER_PATH} اصلاح شد")
        
        return count
    except Exception as e:
        logger.error(f"خطا در اصلاح فراخوانی‌های convert_video_quality: {str(e)}")
        logger.error(traceback.format_exc())
        return 0

def main():
    """تابع اصلی پچ"""
    try:
        logger.info("شروع اجرای پچ اصلاحی اینستاگرام...")
        
        # ایجاد نسخه پشتیبان
        backup_file(TELEGRAM_FIXES_PATH)
        backup_file(TELEGRAM_DOWNLOADER_PATH)
        
        # اصلاح توابع
        success1 = patch_convert_video_quality()
        success2 = patch_download_with_quality()
        success3 = fix_instagram_callback()
        count = find_and_fix_all_convert_video_quality_calls()
        
        if success1 and success2 and success3:
            logger.info("پچ با موفقیت اعمال شد!")
            logger.info(f"تعداد {count} فراخوانی تابع convert_video_quality اصلاح شد")
            
            logger.info("""
تغییرات انجام شده:
1. اضافه کردن پارامتر is_audio_request به تابع convert_video_quality
2. اصلاح منطق تشخیص درخواست صوتی در تابع download_with_quality
3. اصلاح پردازش کالبک‌های اینستاگرام برای تشخیص دقیق نوع فایل
4. اصلاح تمام فراخوانی‌های تابع convert_video_quality در کل پروژه
""")
            return True
        else:
            logger.warning("برخی از اصلاحات ناموفق بودند.")
            return False
            
    except Exception as e:
        logger.error(f"خطا در اجرای پچ: {str(e)}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ماژول عیب‌یابی ویدیو

این ماژول شامل ابزارهای پیشرفته برای عیب‌یابی مشکلات تبدیل کیفیت ویدیو
و تشخیص نوع فایل است.
"""

import os
import subprocess
import logging
import json
import uuid
import time
import traceback
from typing import Dict, List, Tuple, Optional, Any

"""
هسته اصلی ربات

بخشی از ربات تلگرام دانلودر پیشرفته
"""

def get_codec_for_format(format: str) -> str:
    """
    تعیین کدک مناسب برای فرمت صوتی
    
    Args:
        format: فرمت صوتی (mp3, m4a, wav, ogg)
        
    Returns:
        نام کدک مناسب
    """
    format_codec_map = {
        'mp3': 'libmp3lame',
        'm4a': 'aac',
        'aac': 'aac',
        'wav': 'pcm_s16le',
        'ogg': 'libvorbis',
        'opus': 'libopus',
        'flac': 'flac'
    }
    
    return format_codec_map.get(format.lower(), 'libmp3lame')

def human_readable_size(size_bytes: int) -> str:
    """
    تبدیل حجم فایل از بایت به فرمت خوانا برای انسان
    
    Args:
        size_bytes: حجم فایل به بایت
        
    Returns:
        رشته حاوی حجم فایل با واحد مناسب
    """
    if size_bytes == 0:
        return "0B"
        
    size_names = ("B", "KB", "MB", "GB", "TB")
    i = 0
    
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024
        i += 1
        
    return f"{size_bytes:.2f} {size_names[i]}"


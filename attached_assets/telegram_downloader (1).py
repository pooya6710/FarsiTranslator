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

def get_from_cache(url: str) -> Optional[str]:
    """Get file from download cache
    
    Args:
        url: URL of the file
        
    Returns:
        Path to the cached file or None if not found or expired
    """
    # Check if file exists in cache - بررسی وجود فایل در کش
    if url in download_cache:
        timestamp, file_path = download_cache[url]
        if time.time() - timestamp < CACHE_TIMEOUT and os.path.exists(file_path):
            # بررسی وجود فایل در سیستم فایل
            if os.path.exists(file_path):
                # استفاده از logger در سطح ریشه برای هماهنگی با توابع تست
                logging.info(f"فایل از کش برگردانده شد: {file_path}")
                return file_path
            else:
                # حذف از کش اگر فایل وجود نداشته باشد
                del download_cache[url]
    return None

def add_to_cache(url: str, file_path: str):
    """Add file to download cache
    
    Args:
        url: URL of the file
        file_path: Path to the saved file
    """
    # بررسی وجود فایل قبل از افزودن به کش
    if os.path.exists(file_path):
        download_cache[url] = (time.time(), file_path)
        # استفاده از logger در سطح ریشه برای هماهنگی با توابع تست
        logging.info(f"فایل به کش اضافه شد: {file_path}")
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
START_MESSAGE = r"""
🎥 *به ربات دانلودر اینستاگرام و یوتیوب خوش آمدید* 🎬

با این ربات می‌توانید ویدیوهای اینستاگرام و یوتیوب را با کیفیت دلخواه دانلود کنید.

📱 *قابلیت‌ها*:
• دانلود ویدیوهای اینستاگرام (پست‌ها و ریلز)
• دانلود ویدیوهای یوتیوب (عادی، شورتز و پلی‌لیست)
• انتخاب کیفیت مختلف (1080p، 720p، 480p، 360p، 240p)
• دانلود فقط صدای ویدیو

🔍 *نحوه استفاده*:
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
            # بررسی کش
            cached_file = get_from_cache(url)
            if cached_file:
                logger.info(f"فایل از کش برگردانده شد: {cached_file}")
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
            final_path = get_unique_filename(TEMP_DOWNLOAD_DIR, final_filename)
            
            # کپی فایل به مسیر نهایی
            shutil.copy2(video_path, final_path)
            
            # پاکسازی دایرکتوری موقت
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            # افزودن به کش
            add_to_cache(url, final_path)
            
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
                if quality == 'low':
                    # کیفیت پایین - حداکثر 240p با بیت ریت محدود
                    format_spec = 'worstvideo[height<=240][ext=mp4]+worstaudio[ext=m4a]/worst[height<=240][ext=mp4]/worst[ext=mp4]'
                elif quality == 'medium':
                    # کیفیت متوسط - حداکثر 480p
                    format_spec = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]'
                elif quality == 'best':
                    # کیفیت بالا - بدون محدودیت، بهترین کیفیت موجود
                    format_spec = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
                else:
                    # پیش فرض
                    format_spec = 'best[ext=mp4]/best'
                
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
            }
            
            # اجرا در thread pool
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await loop.run_in_executor(None, ydl.download, [url])
            
            # بررسی موفقیت دانلود
            if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
                # افزودن به کش
                add_to_cache(url, final_path)
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
                # افزودن به کش
                add_to_cache(url, final_path)
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
                
            # گزینه‌های دانلود ثابت برای اینستاگرام
            options = [
                {"id": "instagram_high", "label": "کیفیت بالا (1080p)", "quality": "best", "type": "video"},
                {"id": "instagram_medium", "label": "کیفیت متوسط (480p)", "quality": "medium", "type": "video"},
                {"id": "instagram_low", "label": "کیفیت پایین (240p)", "quality": "low", "type": "video"},
                {"id": "instagram_audio", "label": "فقط صدا (MP3)", "quality": "audio", "type": "audio"}
            ]
            
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
        دریافت گزینه‌های دانلود برای ویدیوی یوتیوب
        
        Args:
            url: آدرس ویدیوی یوتیوب
            
        Returns:
            لیستی از گزینه‌های دانلود
        """
        try:
            # دریافت اطلاعات ویدیو
            info = await self.get_video_info(url)
            if not info:
                return []
                
            formats = []
            
            # بررسی آیا این یک پلی‌لیست است
            if is_youtube_playlist(url):
                formats = [
                    {"id": "youtube_playlist_hd", "label": "دانلود 3 ویدیوی اول پلی‌لیست (720p)", "format": "best[height<=720]"},
                    {"id": "youtube_playlist_sd", "label": "دانلود 3 ویدیوی اول پلی‌لیست (480p)", "format": "best[height<=480]"},
                    {"id": "youtube_playlist_audio", "label": "دانلود صدای 3 ویدیوی اول پلی‌لیست", "format": "bestaudio[ext=m4a]"}
                ]
            else:
                # گزینه‌های کیفیت ویدیو
                formats = [
                    {"id": "youtube_1080p", "label": "کیفیت بالا (1080p)", "format": "best[height<=1080]"},
                    {"id": "youtube_720p", "label": "کیفیت خوب (720p)", "format": "best[height<=720]"},
                    {"id": "youtube_480p", "label": "کیفیت متوسط (480p)", "format": "best[height<=480]"},
                    {"id": "youtube_360p", "label": "کیفیت پایین (360p)", "format": "best[height<=360]"},
                    {"id": "youtube_240p", "label": "کیفیت خیلی پایین (240p)", "format": "best[height<=240]"},
                    {"id": "youtube_audio", "label": "فقط صدا (MP3)", "format": "bestaudio[ext=m4a]"}
                ]
                
            return formats
            
        except Exception as e:
            logger.error(f"خطا در دریافت گزینه‌های دانلود یوتیوب: {str(e)}")
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
                ydl_opts.update({
                    'format': 'bestaudio[ext=m4a]',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'outtmpl': output_path.replace('.mp3', '.%(ext)s'),
                })
            else:
                # انتخاب فرمت بر اساس گزینه کاربر با اولویت کیفیت خاص
                if '1080p' in format_option:
                    format_spec = 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]'
                elif '720p' in format_option:
                    format_spec = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]'
                elif '480p' in format_option:
                    format_spec = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]'
                elif '360p' in format_option:
                    format_spec = 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best[height<=360]'
                elif '240p' in format_option:
                    format_spec = 'bestvideo[height<=240][ext=mp4]+bestaudio[ext=m4a]/best[height<=240][ext=mp4]/best[height<=240]'
                else:
                    format_spec = 'best[ext=mp4]/best'
                    
                logger.info(f"استفاده از فرمت {format_spec} برای دانلود یوتیوب با گزینه {format_option}")
                    
                ydl_opts.update({
                    'format': format_spec,
                    'outtmpl': output_path,
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
    await update.message.reply_text(
        START_MESSAGE,
        parse_mode='Markdown'
    )

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
            
            # ذخیره اطلاعات گزینه برای استفاده بعدی
            if user_id not in user_download_data:
                user_download_data[user_id] = {}
            if 'option_map' not in user_download_data[user_id]:
                user_download_data[user_id]['option_map'] = {}
                
            user_download_data[user_id]['option_map'][option_short_id] = option
            
            # دکمه با callback_data کوتاه‌تر
            button = InlineKeyboardButton(
                option.get("display_name", f"کیفیت {option.get('quality', 'نامشخص')}"),
                callback_data=f"dl_ig_{option_short_id}_{url_id}"
            )
            
            # تفکیک دکمه‌ها بر اساس نوع
            if option.get('type') == 'audio':
                audio_buttons.append([button])
            else:
                video_buttons.append([button])
        
        # افزودن دکمه‌های ویدیو
        keyboard.extend(video_buttons)
        
        # اگر گزینه صوتی وجود دارد، اضافه کن
        if audio_buttons:
            # دکمه عنوان با callback_data معتبر
            keyboard.append([InlineKeyboardButton("🎵 فقط صدا", callback_data=f"dl_ig_audio_{url_id}")])
            keyboard.extend(audio_buttons)
            
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
    پردازش URL یوتیوب
    
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
                audio_buttons.append([button])
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
            # دکمه عنوان با callback_data معتبر
            keyboard.append([InlineKeyboardButton("🎵 فقط صدا", callback_data=f"dl_yt_audio_{url_id}")])
            keyboard.extend(audio_buttons)
            
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
        if download_type == "audio" or option_id == "audio":
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
                        from audio_processing.audio_extractor import extract_audio
                        logger.info(f"تبدیل ویدیو به صوت: {downloaded_file}")
                        audio_path = extract_audio(downloaded_file, 'mp3', '192k')
                        if not audio_path:
                            logger.error("خطا در تبدیل ویدیو به صوت")
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
                # دانلود صوتی یوتیوب
                # تنظیمات خاص برای دانلود فقط صوت
                ydl_opts = {
                    'format': 'bestaudio',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'outtmpl': os.path.join(TEMP_DOWNLOAD_DIR, 'yt_audio_%(id)s.%(ext)s'),
                    'quiet': True,
                    'noplaylist': True,
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
            
            if 0 <= option_index < len(options):
                selected_option = options[option_index]
                logger.info(f"گزینه انتخاب شده: {selected_option.get('quality', 'نامشخص')}")
                
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
    دانلود ویدیوی اینستاگرام
    """
    query = update.callback_query
    
    try:
        # ایجاد دانلودر اینستاگرام
        downloader = InstagramDownloader()
        
        # تعیین کیفیت بر اساس گزینه انتخاب شده
        quality = "best"
        is_audio = False
        
        # بررسی نوع دانلود
        if isinstance(option_id, str):
            if "medium" in option_id:
                quality = "medium"
            elif "low" in option_id:
                quality = "low"
            elif "audio" in option_id:
                quality = "audio"
                is_audio = True
        else:
            # اگر به عنوان یک عدد ارسال شده باشد
            if option_id == "1":
                quality = "medium"
            elif option_id == "2":
                quality = "low"
            elif option_id == "3":
                quality = "audio"
                is_audio = True
            
        logger.info(f"دانلود اینستاگرام با کیفیت: {quality}, صوتی: {is_audio}")
            
        # دانلود ویدیو/صدا
        downloaded_file = await downloader.download_post(url, quality)
        
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
        
        # تعیین نوع فایل بر اساس پسوند
        is_audio = is_audio or downloaded_file.endswith(('.mp3', '.m4a', '.aac', '.wav'))
        
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
        
        # بررسی نوع گزینه (صدا یا ویدیو)
        is_audio = selected_option.get('type') == 'audio'
        
        # ایجاد دانلودر اینستاگرام
        downloader = InstagramDownloader()
        
        # دانلود محتوا
        downloaded_file = None

        # بررسی اگر ماژول بهبودهای جدید در دسترس است
        try:
            from telegram_fixes import download_with_quality
            # نوع دانلود و کیفیت
            quality = selected_option.get('quality', 'best')
            
            # بررسی دقیق نوع دانلود (صوتی یا ویدیویی)
            option_id = selected_option.get('id', '')
            is_audio = (selected_option.get('type') == 'audio') or ('audio' in option_id.lower() if option_id else False)
            
            # پیام وضعیت
            if is_audio:
                await query.edit_message_text(STATUS_MESSAGES["downloading_audio"])
                quality = 'audio'  # تنظیم کیفیت به 'audio' برای دانلود صوتی
                logger.info("دانلود درخواست صوتی اینستاگرام")
            else:
                await query.edit_message_text(STATUS_MESSAGES["downloading"])
                
            # دانلود با استفاده از ماژول جدید
            logger.info(f"دانلود اینستاگرام با ماژول بهبود یافته: {quality}, صوتی={is_audio}")
            downloaded_file = await download_with_quality(url, quality, is_audio, "instagram")
            
            if downloaded_file and os.path.exists(downloaded_file):
                # افزودن به کش با نوع مناسب
                cache_key = url + ("_audio" if is_audio else "")
                add_to_cache(cache_key, downloaded_file)
                logger.info(f"فایل با موفقیت دانلود شد: {downloaded_file}")
            else:
                logger.error(f"دانلود با ماژول بهبود یافته ناموفق بود")
                raise Exception("دانلود با ماژول بهبود یافته ناموفق بود")
            
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
            
            # دانلود با استفاده از ماژول جدید
            downloaded_file = await download_with_quality(url, quality, is_audio, "youtube")
            
            if downloaded_file and os.path.exists(downloaded_file):
                # افزودن به کش
                cache_key = url + ("_audio" if is_audio else "")
                add_to_cache(cache_key, downloaded_file)
                logger.info(f"فایل با موفقیت دانلود شد: {downloaded_file}")
            else:
                logger.error(f"دانلود با ماژول بهبود یافته ناموفق بود")
                raise Exception("دانلود با ماژول بهبود یافته ناموفق بود")
                
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
                # افزودن به کش
                add_to_cache(url + "_audio", downloaded_file)
                
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
    """
    query = update.callback_query
    
    try:
        # ایجاد دانلودر یوتیوب
        downloader = YouTubeDownloader()
        
        # تعیین اگر فایل صوتی درخواست شده است
        is_audio_request = ('audio' in option_id.lower()) if isinstance(option_id, str) else False
        
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
            
            # تنظیمات yt-dlp برای دانلود صوتی
            ydl_opts = {
                'format': 'bestaudio',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': output_path.replace('.mp3', '.%(ext)s'),
                'quiet': True,
                'cookiefile': YOUTUBE_COOKIE_FILE,
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
            logger.info(f"دانلود ویدیوی یوتیوب با گزینه {option_id}: {url[:30]}...")
            downloaded_file = await downloader.download_video(url, option_id)
            
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

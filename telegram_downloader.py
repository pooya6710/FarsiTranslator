#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
دانلودر تلگرام هوشمند و پیشرفته ویدیوهای اینستاگرام و یوتیوب

این اسکریپت یک ربات تلگرام با قابلیت‌های پیشرفته برای دانلود ویدیوهای اینستاگرام و یوتیوب ایجاد می‌کند.
قابلیت‌های اصلی:
- دانلود سریع با بهینه‌سازی چند نخی
- پشتیبانی از کیفیت‌های مختلف ویدیو (240p تا 1080p)
- استخراج صدا از ویدیو (MP3)
- رابط کاربری زیبا و کاربرپسند
- دانلود چندین ویدیو به صورت همزمان
- مدیریت هوشمند کش برای عملکرد سریع‌تر

نحوه استفاده:
1. مطمئن شوید که همه وابستگی‌های مورد نیاز را نصب کرده‌اید:
   pip install python-telegram-bot yt-dlp instaloader requests

2. متغیر محیطی TELEGRAM_BOT_TOKEN را تنظیم کنید.

3. اسکریپت را اجرا کنید:
   python telegram_downloader.py

این برنامه در ابتدا تست‌های خودکار را اجرا می‌کند و سپس ربات را راه‌اندازی می‌کند.
برای راه‌اندازی بدون اجرای تست‌ها، از آرگومان --skip-tests استفاده کنید:
   python telegram_downloader.py --skip-tests

نسخه ۲.۲.۰ - بهینه‌سازی شده با امکانات جدید
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
from concurrent.futures import ThreadPoolExecutor, as_completed

# تنظیمات لاگینگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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
    try:
        # برای python-telegram-bot نسخه 13.x
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ParseMode, ChatAction
        from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters
        from telegram.ext import CallbackContext
        
        # تنظیم فیلتر‌های نسخه 13.x
        class filters:
            TEXT = Filters.text & ~Filters.command
            COMMAND = Filters.command
        
        # تعریف متغیرهای ساختگی برای سازگاری با کد
        Application = None
        
        # ساختگی برای سازگاری با هر دو نسخه
        class ContextTypes:
            DEFAULT_TYPE = CallbackContext
        
        # حالت نسخه 13
        PTB_VERSION = 13
        logger.info("استفاده از python-telegram-bot نسخه 13.x")
    except ImportError:
        # برای python-telegram-bot نسخه 20.x و بالاتر
        from telegram.ext import (
            Application, CommandHandler, MessageHandler, 
            CallbackQueryHandler, ContextTypes, filters
        )
        from telegram.constants import ParseMode, ChatAction
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
        
        # حالت نسخه 20
        PTB_VERSION = 20
        logger.info("استفاده از python-telegram-bot نسخه 20.x و بالاتر")
        
    import instaloader
except ImportError as e:
    print(f"خطا در وارد کردن کتابخانه‌های مورد نیاز: {e}")
    print("لطفاً اطمینان حاصل کنید که تمام وابستگی‌ها را نصب کرده‌اید:")
    print("pip install python-telegram-bot==13.15 yt-dlp instaloader requests")
    exit(1)

# تنظیمات لاگینگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
persistent_url_storage = {}

# ذخیره‌سازی اطلاعات دانلود برای هر کاربر
# این دیکشنری داده‌های کاربران را برای دانلود ذخیره می‌کند
user_download_data = {}

# ذخیره‌سازی اطلاعات گزینه‌های دانلود برای هر URL
# این مخزن برای جلوگیری از مشکل از دست رفتن گزینه‌های دانلود استفاده می‌شود
option_cache = {}

# دیکشنری برای ذخیره آخرین دکمه‌های فشرده شده توسط کاربران
# این برای کمک به حل مشکل "لینک منقضی شده" استفاده می‌شود
recent_button_clicks = {}

# بارگذاری ماژول‌های اصلاحی اینستاگرام
INSTAGRAM_FIX_PATCH_AVAILABLE = False
INSTAGRAM_DIRECT_DOWNLOADER_AVAILABLE = False

# ابتدا بررسی ماژول جدید مستقیم دانلود
try:
    from instagram_direct_downloader import download_instagram_content
    INSTAGRAM_DIRECT_DOWNLOADER_AVAILABLE = True
    INSTAGRAM_FIX_PATCH_AVAILABLE = True  # برای حفظ سازگاری با کد فعلی
    logger.info("ماژول دانلود مستقیم instagram_direct_downloader با موفقیت اعمال شد")
except ImportError:
    logger.warning("ماژول instagram_direct_downloader یافت نشد، تلاش با روش‌های دیگر...")
except Exception as e:
    logger.error(f"خطا در بارگیری ماژول instagram_direct_downloader: {e}")

"""
بخش 1: تنظیمات و ثابت‌ها
"""

# تنظیمات دایرکتوری دانلود
TEMP_DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
logger.info(f"مسیر دانلود موقت: {TEMP_DOWNLOAD_DIR}")

# متن‌های پاسخ ربات
START_MESSAGE = """
<b>🎬 به ربات هوشمند دانلودر اینستاگرام و یوتیوب خوش آمدید 🎬</b>

با این ربات می‌توانید ویدیوهای اینستاگرام و یوتیوب را با بهترین کیفیت و سرعت دانلود کنید.

<b>📱 قابلیت‌های ویژه:</b>
• <b>دانلود فوق سریع</b> با بهینه‌سازی چند نخی
• دانلود ویدیوهای <b>اینستاگرام</b> (پست‌ها و ریلز)
• دانلود ویدیوهای <b>یوتیوب</b> (عادی، شورتز و پلی‌لیست)
• انتخاب کیفیت‌های متنوع <b>(1080p، 720p، 480p، 360p، 240p)</b>
• <b>استخراج صدا</b> با کیفیت بالا (MP3)
• <b>دانلود موازی و همزمان</b> چندین لینک
• <b>رابط کاربری زیبا</b> و کاربرپسند

<b>🔍 نحوه استفاده:</b>
• <b>ارسال لینک:</b> کافیست لینک ویدیو را برای ربات ارسال کنید
• <b>دانلود گروهی:</b> برای دانلود چندین لینک از دستور /bulkdownload استفاده کنید

<b>🛠️ نسخه ۲.۲.۰ - سریع‌تر، زیباتر، کاربردی‌تر</b>

👨‍💻 برای دیدن راهنمای کامل: /help
"""

HELP_MESSAGE = """<b>📚 راهنمای استفاده از ربات دانلودر</b>

<b>👨‍💻 روش استفاده:</b>
1️⃣ <b>ارسال لینک</b> ویدیو از اینستاگرام یا یوتیوب
2️⃣ <b>انتخاب کیفیت</b> دلخواه از میان گزینه‌های ارائه شده
3️⃣ <b>دریافت ویدیو</b> با کیفیت انتخاب شده در کمترین زمان ممکن

<b>📱 لینک‌های پشتیبانی شده:</b>
• <b>یوتیوب:</b> ویدیو عادی، شورتز و پلی‌لیست
• <b>اینستاگرام:</b> پست‌ها، ریل‌ها و استوری‌ها

<b>🎬 کیفیت‌های قابل انتخاب:</b>
• <b>1080p (Full HD)</b> - کیفیت عالی
• <b>720p (HD)</b> - کیفیت بالا
• <b>480p</b> - کیفیت متوسط
• <b>360p</b> - کیفیت پایین
• <b>240p</b> - کیفیت خیلی پایین
• <b>MP3</b> - فقط صدا

<b>📥 دانلود گروهی:</b>
برای دانلود چندین لینک به صورت همزمان از دستور <code>/bulkdownload</code> استفاده کنید:

<code>/bulkdownload 720p
https://youtube.com/watch?v=VIDEO1
https://instagram.com/p/POST1
https://youtube.com/shorts/VIDEO2</code>

<b>📊 مدیریت دانلودها:</b>
• <code>/status_BATCH_ID</code> - بررسی وضعیت یک دسته دانلود
• <code>/mydownloads</code> - مشاهده لیست همه دانلودهای شما

<b>⚠️ محدودیت‌ها:</b>
• حداکثر حجم فایل: <b>50 مگابایت</b>
• حداکثر تعداد دانلود همزمان: <b>3</b>

<i>برای اطلاعات بیشتر: /about</i>"""

ABOUT_MESSAGE = """<b>📱 درباره ربات هوشمند دانلودر مدیا</b>

این ربات به شما امکان دانلود ویدیوهای <b>اینستاگرام</b> و <b>یوتیوب</b> را با بهترین کیفیت و سرعت می‌دهد.

<b>✨ قابلیت‌های ویژه:</b>
• <b>دانلود سریع</b> با بهینه‌سازی چندنخی
• دانلود ویدیوهای <b>اینستاگرام</b> (پست‌ها و ریل‌ها)
• دانلود ویدیوهای <b>یوتیوب</b> (عادی، شورتز و پلی‌لیست)
• انتخاب <b>کیفیت‌های متنوع</b> (1080p، 720p، 480p، 360p، 240p)
• استخراج <b>صدا با کیفیت بالا</b> (MP3)
• <b>دانلود موازی</b> و همزمان چندین لینک
• <b>رابط کاربری زیبا</b> و کاربرپسند

<b>🛠️ تکنولوژی‌های پیشرفته:</b>
• Python 3.11 با AsyncIO
• python-telegram-bot - نسخه ۲۰
• yt-dlp - با پردازش بهینه‌شده
• instaloader - با پشتیبانی از پست‌های جدید
• FFmpeg - رندرینگ سریع و کم‌حجم
• پردازش چندنخی برای دانلود همزمان

<b>📌 نسخه:</b> 2.2.0

<b>🔄 آخرین بروزرسانی:</b> فروردین ۱۴۰۴

<i>توسعه داده شده توسط تیم DataPixelStudio</i>"""

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
        
    # تبدیل لینک‌های اشتراک‌گذاری به فرمت استاندارد
    if '/share/reel/' in url:
        shortcode = url.split('/share/reel/')[-1].split('?')[0].split('/')[0]
        return f"https://www.instagram.com/reel/{shortcode}/"
    elif '/share/p/' in url:
        shortcode = url.split('/share/p/')[-1].split('?')[0].split('/')[0] 
        return f"https://www.instagram.com/p/{shortcode}/"
        
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
            
            # الویت با دانلود مستقیم با ماژول جدید است (حتی برای آزمایش)
            logger.info(f"شروع تلاش‌های دانلود برای اینستاگرام URL: {url}, کیفیت: {quality}")
            downloaded_file = None
            
            # آزمایش 1: استفاده مستقیم از ماژول دانلود مستقیم
            try:
                from instagram_direct_downloader import download_instagram_content
                logger.info(f"تلاش اول: استفاده از ماژول instagram_direct_downloader")
                
                # ایجاد مسیر خروجی منحصر به فرد
                output_dir = os.path.join(TEMP_DOWNLOAD_DIR, f"instagram_direct_{shortcode}_{str(uuid.uuid4().hex)[:8]}")
                os.makedirs(output_dir, exist_ok=True)
                
                # استفاده مستقیم از تابع (بدون async)
                logger.info(f"فراخوانی مستقیم download_instagram_content با مسیر: {output_dir}")
                direct_result = download_instagram_content(url, output_dir, quality)
                logger.info(f"نتیجه فراخوانی مستقیم: {direct_result}")
                
                if direct_result and os.path.exists(direct_result) and os.path.getsize(direct_result) > 1024:  # 1KB
                    downloaded_file = direct_result
                    logger.info(f"دانلود مستقیم با instagram_direct_downloader موفق بود: {downloaded_file}")
                else:
                    logger.warning("دانلود مستقیم ناموفق بود یا فایل خالی است")
            except Exception as direct_error:
                logger.error(f"خطا در استفاده مستقیم از دانلود مستقیم: {direct_error}")
            
            # اگر روش اول ناموفق بود، از async استفاده می‌کنیم
            if not downloaded_file:
                try:
                    logger.info("تلاش دوم: استفاده از دانلود مستقیم با async")
                    loop = asyncio.get_event_loop()
                    
                    # ایجاد مسیر خروجی جدید
                    output_dir = os.path.join(TEMP_DOWNLOAD_DIR, f"instagram_async_{shortcode}_{str(uuid.uuid4().hex)[:8]}")
                    os.makedirs(output_dir, exist_ok=True)
                    
                    # استفاده از run_in_executor
                    async_result = await loop.run_in_executor(
                        None,
                        lambda: download_instagram_content(url, output_dir, quality)
                    )
                    logger.info(f"نتیجه دانلود async: {async_result}")
                    
                    if async_result and os.path.exists(async_result) and os.path.getsize(async_result) > 1024:
                        downloaded_file = async_result
                        logger.info(f"دانلود async با instagram_direct_downloader موفق بود: {downloaded_file}")
                    else:
                        logger.warning("دانلود async نیز ناموفق بود یا فایل خالی است")
                except Exception as async_error:
                    logger.error(f"خطا در استفاده از دانلود async: {async_error}")
                    
                    if downloaded_file and os.path.exists(downloaded_file) and os.path.getsize(downloaded_file) > 0:
                        logger.info(f"دانلود اینستاگرام با پچ اختصاصی موفقیت‌آمیز بود: {downloaded_file}")
                        # افزودن به کش با کیفیت
                        cache_key = f"{url}_{quality}"
                        add_to_cache(cache_key, downloaded_file)
                        return downloaded_file
                    else:
                        logger.warning("دانلود با پچ اختصاصی ناموفق بود، استفاده از روش‌های دیگر")
                except Exception as patch_error:
                    logger.error(f"خطا در دانلود با پچ اختصاصی: {patch_error}")
            
            # تغییر ترتیب روش‌های دانلود - ابتدا با yt-dlp که نیاز به لاگین ندارد
            # روش اول: استفاده از yt-dlp (بدون نیاز به لاگین)
            logger.info(f"تلاش برای دانلود با روش اول (yt-dlp): {url}")
            result = await self._download_with_ytdlp(url, shortcode, quality)
            if result:
                return result
                
            # روش دوم: استفاده از درخواست مستقیم
            logger.info(f"تلاش برای دانلود با روش دوم (درخواست مستقیم): {url}")
            result = await self._download_with_direct_request(url, shortcode, quality)
            if result:
                return result
                
            # روش سوم: استفاده از instaloader (ممکن است نیاز به لاگین داشته باشد)
            logger.info(f"تلاش برای دانلود با روش سوم (instaloader): {url}")
            result = await self._download_with_instaloader(url, shortcode, quality)
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
        """روش دانلود با استفاده از yt-dlp با بهینه‌سازی برای اینستاگرام"""
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
                # استفاده از تنظیمات بهبود یافته برای اینستاگرام - با فرمت جدید و بهینه
                # اینستاگرام گاهی محدودیت‌های خاصی روی API اعمال می‌کند، پس باید انعطاف‌پذیر باشیم
                if quality == '240p':
                    # کیفیت خیلی پایین - 240p
                    format_spec = 'worstvideo+bestaudio/worst[height>=240]/worst'
                elif quality == '360p':
                    # کیفیت پایین - 360p - با اولویت بندی جدید
                    format_spec = 'best[height<=360]/bestvideo[height<=360]+bestaudio/best'
                elif quality == '480p':
                    # کیفیت متوسط - 480p - با اولویت بندی جدید
                    format_spec = 'best[height<=480]/bestvideo[height<=480]+bestaudio/best'
                elif quality == '720p':
                    # کیفیت HD - 720p - با اولویت بندی جدید 
                    format_spec = 'best[height<=720]/bestvideo[height<=720]+bestaudio/best'
                elif quality == '1080p':
                    # کیفیت Full HD - 1080p - با حالت‌های متنوع جایگزین
                    format_spec = 'best[height<=1080]/bestvideo[height<=1080]+bestaudio/best'
                else:
                    # پیش فرض - بهترین کیفیت موجود - ساده‌ترین حالت
                    format_spec = 'best'
                
                # هیچ پردازش اضافی در این مرحله نیاز نیست
                postprocessors = []
                
            logger.info(f"استفاده از فرمت جدید {format_spec} برای دانلود اینستاگرام با کیفیت {quality}")
            
            # تنظیمات دانلود بهینه شده برای اینستاگرام
            ydl_opts = {
                'format': format_spec,
                'outtmpl': final_path if not is_audio_download else final_path.replace('.mp3', '.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                # یک User-Agent جدید و معتبر برای دور زدن محدودیت‌های اینستاگرام
                'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
                'socket_timeout': 30,
                'retries': 15,  # افزایش تعداد تلاش‌ها
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Origin': 'https://www.instagram.com',
                    'Referer': 'https://www.instagram.com/',
                    'DNT': '1',  # Do Not Track
                    'Connection': 'keep-alive'
                },
                'postprocessors': postprocessors,
                'writeinfojson': False,
                'writethumbnail': False,
                'noplaylist': True,
                'extractor_retries': 5,  # افزایش تعداد تلاش‌ها برای استخراج اطلاعات
                'skip_download_archive': True,  # عدم بررسی آرشیو دانلود
                'ffmpeg_location': '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',
                'prefer_ffmpeg': True,
                # استفاده از کوکی‌های رندوم برای جلوگیری از محدودیت نرخ درخواست
                'cookiefile': None,
                'cookiesfrombrowser': None,
                # تنظیمات پیشرفته‌تر
                'sleep_interval': 1,  # فاصله زمانی بین درخواست‌ها
                'max_sleep_interval': 5,  # حداکثر فاصله زمانی
                'force_generic_extractor': False,  # استفاده از استخراج‌کننده تخصصی
            }
            
            # اجرا در thread pool با کنترل خطا
            loop = asyncio.get_event_loop()
            download_success = False
            
            # روش 1: استفاده اصلی با تنظیمات بهینه
            try:
                logger.info(f"شروع دانلود اینستاگرام با yt-dlp و تنظیمات پیشرفته: {url[:30]}")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    await loop.run_in_executor(None, ydl.download, [url])
                    
                # بررسی موفقیت دانلود
                if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
                    download_success = True
                    logger.info(f"دانلود با روش اصلی موفق: {os.path.getsize(final_path)} بایت")
            except Exception as e:
                logger.warning(f"خطا در دانلود اینستاگرام با yt-dlp: {e}, تلاش با روش جایگزین...")
            
            # روش 2: استفاده از تنظیمات جایگزین با User-Agent متفاوت
            if not download_success:
                try:
                    logger.info("تلاش با روش جایگزین اول: User-Agent دیگر")
                    fallback_ydl_opts = ydl_opts.copy()
                    fallback_ydl_opts['format'] = 'best'  # ساده‌ترین فرمت
                    # تغییر User-Agent
                    fallback_ydl_opts['user_agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    fallback_ydl_opts['http_headers']['User-Agent'] = fallback_ydl_opts['user_agent']
                    
                    with yt_dlp.YoutubeDL(fallback_ydl_opts) as ydl:
                        await loop.run_in_executor(None, ydl.download, [url])
                    
                    # بررسی موفقیت دانلود با روش جایگزین
                    if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
                        download_success = True
                        logger.info(f"دانلود با روش جایگزین اول موفق: {os.path.getsize(final_path)} بایت")
                except Exception as fallback_error:
                    logger.warning(f"خطا در روش جایگزین اول: {fallback_error}")
            
            # روش 3: استفاده از حالت اندروید با تنظیمات مینیمال
            if not download_success:
                try:
                    logger.info("تلاش با روش جایگزین دوم: حالت اندروید")
                    android_ydl_opts = {
                        'format': 'best',
                        'outtmpl': final_path,
                        'quiet': True,
                        'user_agent': 'Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
                        'http_headers': {
                            'User-Agent': 'Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
                            'Accept': '*/*',
                            'Origin': 'https://www.instagram.com',
                            'Referer': 'https://www.instagram.com/',
                        },
                        'ffmpeg_location': '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',
                    }
                    
                    with yt_dlp.YoutubeDL(android_ydl_opts) as ydl:
                        await loop.run_in_executor(None, ydl.download, [url])
                    
                    # بررسی موفقیت دانلود با روش جایگزین
                    if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
                        download_success = True
                        logger.info(f"دانلود با روش جایگزین دوم موفق: {os.path.getsize(final_path)} بایت")
                except Exception as android_error:
                    logger.warning(f"خطا در روش جایگزین دوم: {android_error}")
                        
            # پردازش فایل دانلود شده برای تبدیل کیفیت اگر موفق بودیم
            if download_success or (os.path.exists(final_path) and os.path.getsize(final_path) > 0):
                # اگر کیفیت خاصی درخواست شده و فایل ویدیویی است، تبدیل کیفیت کنیم
                if not is_audio_download and quality != 'best':
                    try:
                        from telegram_fixes import convert_video_quality
                        logger.info(f"تبدیل کیفیت ویدیو به {quality}...")
                        converted_path = convert_video_quality(final_path, quality, is_audio_request=False)
                        if converted_path and os.path.exists(converted_path):
                            logger.info(f"تبدیل کیفیت ویدیو به {quality} موفقیت‌آمیز بود: {converted_path}")
                            # جایگزینی فایل نهایی
                            final_path = converted_path
                    except Exception as e:
                        logger.error(f"خطا در تبدیل کیفیت ویدیو: {str(e)}")
                
                # بررسی فایل صوتی 
                if is_audio_download:
                    # بررسی اگر نیاز به تبدیل به صوت است
                    if not final_path.lower().endswith(('.mp3', '.m4a', '.aac', '.wav')):
                        try:
                            from audio_processing import extract_audio
                            logger.info(f"تبدیل ویدیو به صوت: {final_path}")
                            audio_path = extract_audio(final_path, 'mp3', '192k')
                            if audio_path and os.path.exists(audio_path):
                                final_path = audio_path
                                logger.info(f"تبدیل ویدیو به صوت موفق: {audio_path}")
                        except Exception as audio_error:
                            logger.error(f"خطا در تبدیل به صوت: {audio_error}")
                
                # افزودن به کش با کیفیت
                cache_key = f"{url}_{quality}"
                add_to_cache(cache_key, final_path)
                logger.info(f"دانلود اینستاگرام موفق بود: {final_path}, کیفیت: {quality}, حجم: {os.path.getsize(final_path)}")
                return final_path
            else:
                logger.warning(f"فایل دانلود شده با همه روش‌ها خالی یا ناقص است")
                return None
                
        except Exception as e:
            logger.error(f"خطا در دانلود با yt-dlp: {str(e)}")
            return None
            
    async def _download_with_direct_request(self, url: str, shortcode: str, quality: str) -> Optional[str]:
        """روش دانلود با استفاده از درخواست مستقیم - نسخه بهبود یافته"""
        try:
            # ابتدا باید URL مستقیم ویدیو را پیدا کنیم
            video_url = None
            
            # روش 1: استفاده از yt-dlp برای استخراج URL مستقیم (بدون دانلود)
            try:
                logger.info(f"تلاش برای استخراج URL مستقیم با yt-dlp: {url}")
                ydl_opts = {
                    'format': 'best',
                    'quiet': True,
                    'no_warnings': True,
                    'skip_download': True,  # فقط اطلاعات را استخراج کن، دانلود نکن
                    'dump_single_json': True,
                    'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
                        'Accept': '*/*',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Origin': 'https://www.instagram.com',
                        'Referer': 'https://www.instagram.com/',
                    }
                }
                
                # استفاده از فانکشن extract_info برای دریافت اطلاعات بدون دانلود
                loop = asyncio.get_event_loop()
                
                def get_video_info():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        return ydl.extract_info(url, download=False)
                
                info = await loop.run_in_executor(None, get_video_info)
                
                # بررسی اطلاعات استخراج شده
                if info and 'url' in info:
                    video_url = info['url']
                    logger.info(f"URL مستقیم با yt-dlp پیدا شد")
                elif info and 'formats' in info and info['formats']:
                    # انتخاب بهترین فرمت
                    best_format = None
                    for fmt in info['formats']:
                        if fmt.get('vcodec', 'none') != 'none' and fmt.get('acodec', 'none') != 'none':
                            if best_format is None or fmt.get('height', 0) > best_format.get('height', 0):
                                best_format = fmt
                    
                    if best_format and 'url' in best_format:
                        video_url = best_format['url']
                        logger.info(f"URL مستقیم از فرمت‌های موجود انتخاب شد: {best_format.get('format_id', 'نامشخص')}")
            except Exception as e_ytdlp:
                logger.warning(f"خطا در استخراج URL مستقیم با yt-dlp: {e_ytdlp}")
            
            # روش 2: استفاده از instaloader اگر yt-dlp موفق نبود
            if not video_url:
                try:
                    logger.info(f"تلاش برای استخراج URL مستقیم با instaloader: {shortcode}")
                    post = instaloader.Post.from_shortcode(self.loader.context, shortcode)
                    if hasattr(post, 'video_url') and post.video_url:
                        video_url = post.video_url
                        logger.info("URL مستقیم با instaloader پیدا شد")
                    else:
                        logger.warning("URL ویدیو با instaloader یافت نشد")
                except Exception as e_insta:
                    logger.warning(f"خطا در یافتن URL مستقیم با instaloader: {e_insta}")
            
            # روش 3: پارس کردن صفحه
            if not video_url:
                try:
                    logger.info(f"تلاش برای استخراج URL مستقیم با پارس کردن صفحه: {url}")
                    # استفاده از User-Agent های مختلف برای بالا بردن شانس موفقیت
                    user_agents = [
                        'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
                        'Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    ]
                    
                    success = False
                    for ua in user_agents:
                        if success:
                            break
                            
                        headers = {
                            'User-Agent': ua,
                            'Accept': 'text/html,application/xhtml+xml,application/xml',
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Referer': 'https://www.instagram.com/',
                            'Cache-Control': 'no-cache',
                            'Pragma': 'no-cache'
                        }
                        
                        # افزودن کوکی های تصادفی برای دور زدن محدودیت
                        cookies = {
                            'ig_cb': '1',
                            'ig_did': str(uuid.uuid4()),
                            'mid': str(uuid.uuid4())[:16],
                            'csrftoken': str(uuid.uuid4())
                        }
                        
                        response = requests.get(url, headers=headers, cookies=cookies, timeout=15)
                        
                        # پترن های مختلف برای یافتن URL ویدیو
                        video_patterns = [
                            r'"video_url":"([^"]+)"',
                            r'property="og:video" content="([^"]+)"',
                            r'<video[^>]+src="([^"]+)"',
                            r'"contentUrl":\s*"([^"]+)"'
                        ]
                        
                        for pattern in video_patterns:
                            match = re.search(pattern, response.text)
                            if match:
                                video_url = match.group(1).replace('\\u0026', '&')
                                logger.info(f"URL مستقیم با پترن {pattern} یافت شد")
                                success = True
                                break
                                
                except Exception as e_parse:
                    logger.warning(f"خطا در یافتن URL مستقیم با پارس کردن صفحه: {e_parse}")
            
            # اگر URL مستقیم پیدا نشد
            if not video_url:
                logger.error("هیچ URL مستقیمی برای دانلود پیدا نشد")
                return None
                
            # تنظیم مسیر خروجی
            final_filename = f"instagram_direct_{shortcode}.mp4"
            final_path = get_unique_filename(TEMP_DOWNLOAD_DIR, final_filename)
            
            # تنظیم هدرهای مختلف برای دانلود
            user_agents = [
                'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
                'Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36'
            ]
            
            # استفاده از user agent متفاوت برای دور زدن محدودیت
            selected_ua = random.choice(user_agents)
            
            custom_headers = {
                'User-Agent': selected_ua,
                'Accept': '*/*',
                'Accept-Encoding': 'identity;q=1, *;q=0',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': url,
                'Range': 'bytes=0-',
                'Origin': 'https://www.instagram.com',
                'Connection': 'keep-alive'
            }
            
            # دانلود ویدیو با مدیریت خطا و تلاش مجدد
            loop = asyncio.get_event_loop()
            max_retries = 3
            retry_delay = 2
            success = False
            
            for attempt in range(max_retries):
                try:
                    # تابع دانلود با قابلیت نمایش پیشرفت
                    def download_file():
                        try:
                            logger.info(f"دانلود فایل... تلاش {attempt+1}/{max_retries}")
                            response = requests.get(video_url, headers=custom_headers, stream=True, timeout=30)
                            response.raise_for_status()
                            
                            file_size = int(response.headers.get('content-length', 0))
                            downloaded = 0
                            
                            with open(final_path, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=8192):
                                    if chunk:
                                        f.write(chunk)
                                        downloaded += len(chunk)
                            
                            return os.path.getsize(final_path) > 0
                        except Exception as e:
                            logger.warning(f"خطا در دانلود فایل (تلاش {attempt+1}): {e}")
                            return False
                    
                    success = await loop.run_in_executor(None, download_file)
                    
                    if success:
                        logger.info(f"دانلود موفق در تلاش {attempt+1}")
                        break
                    else:
                        logger.warning(f"تلاش {attempt+1} ناموفق، منتظر {retry_delay} ثانیه...")
                        await asyncio.sleep(retry_delay)
                        # افزایش تاخیر برای تلاش بعدی
                        retry_delay *= 2
                except Exception as download_error:
                    logger.warning(f"خطا در اجرای تابع دانلود: {download_error}")
                    await asyncio.sleep(retry_delay)
                    # افزایش تاخیر برای تلاش بعدی
                    retry_delay *= 2
            
            # بررسی نتیجه نهایی
            if success:
                # پردازش نهایی فایل بر اساس کیفیت درخواستی
                if quality != "best" and quality != "audio":
                    # تغییر کیفیت ویدیو اگر درخواست شده
                    try:
                        from telegram_fixes import convert_video_quality
                        logger.info(f"تبدیل کیفیت ویدیو دانلود شده به {quality}...")
                        converted_path = convert_video_quality(final_path, quality, is_audio_request=False)
                        if converted_path and os.path.exists(converted_path):
                            final_path = converted_path
                    except Exception as conv_error:
                        logger.error(f"خطا در تبدیل کیفیت ویدیو: {conv_error}")
                elif quality == "audio":
                    # استخراج صدا اگر درخواست شده
                    try:
                        from audio_processing import extract_audio
                        logger.info("استخراج صدا از ویدیو...")
                        audio_path = extract_audio(final_path, 'mp3', '192k')
                        if audio_path and os.path.exists(audio_path):
                            final_path = audio_path
                    except Exception as audio_error:
                        logger.error(f"خطا در استخراج صدا: {audio_error}")
                
                # افزودن به کش با کیفیت
                cache_key = f"{url}_{quality}"
                add_to_cache(cache_key, final_path)
                logger.info(f"دانلود با درخواست مستقیم موفق بود: {final_path}")
                return final_path
            else:
                logger.warning("دانلود مستقیم ناموفق بود پس از چندین تلاش")
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
            # بررسی دقیق‌تر برای تشخیص درخواست‌های صوتی
            # فقط زمانی صوتی در نظر گرفته می‌شود که دقیقاً 'audio' یا 'bestaudio' در کل format_option باشد
            # این باعث می‌شود که کیفیت‌های ویدیویی که شامل کلمه audio هستند (مانند bestaudio) در بخش‌های دیگر، اشتباهاً صوتی تشخیص داده نشوند
            is_audio_only = format_option == 'bestaudio' or format_option == 'audio'
            logger.info(f"آیا درخواست فقط صوتی است؟ {is_audio_only} (format_option: {format_option})")
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
                    
                    # دانلود با yt-dlp - بدون استفاده از loop
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        try:
                            # روش مستقیم
                            ydl.download([clean_url])
                        except Exception as e1:
                            logger.error(f"خطا در دانلود صوتی با روش اول: {e1}")
                            # روش با ترد جدا
                            try:
                                import threading
                                download_thread = threading.Thread(target=ydl.download, args=([clean_url],))
                                download_thread.start()
                                download_thread.join(timeout=30) # انتظار حداکثر 30 ثانیه
                            except Exception as e2:
                                logger.error(f"خطا در دانلود صوتی با روش دوم: {e2}")
                        
                    # اگر فایل ایجاد نشد، از روش دوم استفاده می‌کنیم
                    if not os.path.exists(output_path):
                        # روش دوم: دانلود ویدیو و استخراج صدا
                        video_ydl_opts = self.ydl_opts.copy()
                        video_ydl_opts.update({
                            'format': 'best[ext=mp4]/best',
                            'outtmpl': output_path.replace('.mp3', '_temp.mp4')
                        })
                        
                        with yt_dlp.YoutubeDL(video_ydl_opts) as ydl:
                            try:
                                # روش مستقیم
                                ydl.download([clean_url])
                            except Exception as e1:
                                logger.error(f"خطا در دانلود ویدیو با روش اول: {e1}")
                                # روش با ترد جداگانه
                                try:
                                    import threading
                                    download_thread = threading.Thread(target=ydl.download, args=([clean_url],))
                                    download_thread.start()
                                    download_thread.join(timeout=30)  # انتظار حداکثر 30 ثانیه
                                except Exception as e2:
                                    logger.error(f"خطا در دانلود ویدیو با روش دوم: {e2}")
                            
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
                # انتخاب فرمت بر اساس گزینه کاربر با تضمین دریافت ویدیو - بهینه‌سازی شده
                # تبدیل format_option به رشته اگر رشته نباشد
                format_option = str(format_option) if format_option else "best"
                
                # ابتدا مقدار پیش‌فرض برای quality تنظیم می‌کنیم
                quality = "best"  
                
                if '1080p' in format_option or '1080' in format_option:
                    format_spec = 'best[height<=1080]/bestvideo[height<=1080]+bestaudio/best'
                    quality = '1080p'
                elif '720p' in format_option or '720' in format_option:
                    format_spec = 'best[height<=720]/bestvideo[height<=720]+bestaudio/best'
                    quality = '720p'
                elif '480p' in format_option or '480' in format_option:
                    format_spec = 'best[height<=480]/bestvideo[height<=480]+bestaudio/best'
                    quality = '480p'
                elif '360p' in format_option or '360' in format_option:
                    format_spec = 'best[height<=360]/bestvideo[height<=360]+bestaudio/best'
                    quality = '360p'
                elif '240p' in format_option or '240' in format_option:
                    format_spec = 'best[height<=240]/bestvideo[height<=240]+bestaudio/best'
                    quality = '240p'
                else:
                    format_spec = 'best/bestvideo+bestaudio/bestvideo/bestaudio'
                    quality = 'best'
                    
                logger.info(f"استفاده از فرمت جدید {format_spec} برای دانلود اینستاگرام با کیفیت {quality}")
                    
                logger.info(f"استفاده از فرمت {format_spec} برای دانلود یوتیوب با کیفیت {quality}")
                    
                # تنظیمات فوق‌العاده بهینه‌سازی شده برای افزایش چندبرابری سرعت دانلود
                ydl_opts.update({
                    'format': format_spec,
                    'outtmpl': output_path,
                    'merge_output_format': 'mp4',  # ترکیب ویدیو و صدا در فرمت MP4
                    'concurrent_fragment_downloads': 20,  # افزایش دانلود همزمان قطعات (20 قطعه) 
                    'buffersize': 1024 * 1024 * 50,  # افزایش بافر به 50 مگابایت
                    'http_chunk_size': 1024 * 1024 * 25,  # افزایش اندازه قطعات دانلود (25 مگابایت)
                    'fragment_retries': 10,  # افزایش تلاش مجدد در صورت شکست دانلود قطعه
                    'retry_sleep_functions': {'fragment': lambda x: 0.5},  # کاهش زمان انتظار بین تلاش‌های مجدد
                    'live_from_start': True,
                    'socket_timeout': 30,  # افزایش مهلت انتظار اتصال
                    'retries': 10,  # افزایش تعداد تلاش‌های مجدد کلی
                    'file_access_retries': 10,  # تلاش مجدد در صورت مشکل در دسترسی به فایل
                    'extractor_retries': 5,  # تلاش‌های مجدد عمل استخراج
                    'throttledratelimit': 0,  # حذف محدودیت سرعت
                    'verbose': False,
                    'progress_hooks': [],
                    'noplaylist': True,
                    'sleep_interval': 0,  # حذف تأخیر بین درخواست‌ها
                    'max_sleep_interval': 0,  # حذف حداکثر تأخیر
                    'postprocessor_args': [
                        # تنظیمات فوق‌سریع انکودر
                        '-c:v', 'libx264',
                        '-c:a', 'aac',
                        '-b:a', '128k',
                        '-preset', 'ultrafast',
                        '-crf', '28',  # کیفیت پایین‌تر برای سرعت بیشتر
                        '-threads', '8',  # استفاده از 8 هسته پردازشی
                        '-tune', 'fastdecode',  # تنظیم برای دیکود سریع
                        '-flags', '+cgop',  # فعال‌سازی Group of Pictures بسته
                        '-movflags', '+faststart',  # بهینه‌سازی برای پخش سریع‌تر
                        '-g', '30',  # هر 30 فریم یک keyframe
                    ],
                    'noprogress': True,  # عدم نمایش نوار پیشرفت
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
                # دانلود ویدیو - بدون استفاده از loop
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    try:
                        # روش مستقیم
                        ydl.download([clean_url])
                    except Exception as e1:
                        logger.error(f"خطا در دانلود ویدیو با روش اول: {e1}")
                        # روش با ترد جداگانه
                        try:
                            import threading
                            download_thread = threading.Thread(target=ydl.download, args=([clean_url],))
                            download_thread.start()
                            download_thread.join(timeout=30)  # انتظار حداکثر 30 ثانیه
                        except Exception as e2:
                            logger.error(f"خطا در دانلود ویدیو با روش دوم: {e2}")
                    
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
بخش 5: سیستم آمار و عملکرد
"""

# اضافه کردن ماژول‌های آمار و عملکرد
try:
    from stats_manager import StatsManager, stats_command, handle_stats_buttons, Timer
    from performance_optimizer import init_performance_optimizations, MemoryMonitor, NetworkOptimizer, FFmpegOptimizer
    from database_models import init_db
    
    # راه‌اندازی بهینه‌سازی‌های عملکرد
    init_performance_optimizations()
    
    # راه‌اندازی پایگاه داده
    init_db()
    
    # تنظیم متغیرهای مدیریت آمار
    STATS_ENABLED = True
    download_timer = Timer()
    
    logger.info("سیستم آمار و عملکرد با موفقیت راه‌اندازی شد")
except ImportError as e:
    logger.warning(f"خطا در بارگذاری ماژول‌های آمار و عملکرد: {e}")
    STATS_ENABLED = False

"""
بخش 6: هندلرهای ربات تلگرام (از ماژول telegram_bot.py)
"""

async def start(update: Update, context) -> None:
    """
    هندلر دستور /start
    """
    user_id = update.effective_user.id
    logger.info(f"دستور /start دریافت شد از کاربر {user_id}")
    try:
        # بارگذاری ماژول‌های بهینه‌سازی اگر موجود باشند
        try:
            from enhanced_telegram_handler import apply_all_enhancements
            await apply_all_enhancements()
        except ImportError:
            logger.info("ماژول enhanced_telegram_handler در دسترس نیست")
            
        # تلاش برای بهینه‌سازی yt-dlp
        try:
            from youtube_downloader_optimizer import optimize_youtube_downloader
            optimize_youtube_downloader()
        except ImportError:
            logger.info("ماژول youtube_downloader_optimizer در دسترس نیست")
            
        # تلاش برای بهینه‌سازی کش
        try:
            from cache_optimizer import optimize_cache
            optimize_cache()
        except ImportError:
            logger.info("ماژول cache_optimizer در دسترس نیست")
        
        # ایجاد دکمه‌های راهنما
        keyboard = [
            [
                InlineKeyboardButton("📚 راهنمای استفاده", callback_data="help"),
                InlineKeyboardButton("ℹ️ درباره ربات", callback_data="about")
            ],
            [
                InlineKeyboardButton("📥 دانلودهای من", callback_data="mydownloads")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # ارسال پیام خوش‌آمدگویی با فرمت HTML و دکمه‌ها
        await update.message.reply_text(
            START_MESSAGE,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        logger.info(f"پاسخ به دستور /start برای کاربر {user_id} ارسال شد")
    except Exception as e:
        logger.error(f"خطا در پاسخ به دستور /start: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")

async def help_command(update: Update, context) -> None:
    """
    هندلر دستور /help
    """
    # ایجاد دکمه‌های راهنما
    keyboard = [
        [
            InlineKeyboardButton("🎬 کیفیت‌های ویدیو", callback_data="help_video"),
            InlineKeyboardButton("🎵 دانلود صوتی", callback_data="help_audio")
        ],
        [
            InlineKeyboardButton("📱 دانلود گروهی", callback_data="help_bulk"),
            InlineKeyboardButton("ℹ️ درباره ربات", callback_data="about")
        ],
        [
            InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="back_to_start")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام راهنما با فرمت HTML و دکمه‌ها
    await update.message.reply_text(
        HELP_MESSAGE,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def about_command(update: Update, context) -> None:
    """
    هندلر دستور /about
    """
    # ایجاد دکمه بازگشت به منوی اصلی
    keyboard = [
        [
            InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="back_to_start")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام درباره با فرمت HTML و دکمه بازگشت
    await update.message.reply_text(
        ABOUT_MESSAGE,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def process_url(update: Update, context) -> None:
    """
    هندلر پردازش URL ارسال شده توسط کاربر
    """
    user_id = update.effective_user.id
    logger.info(f"پیام جدید از کاربر {user_id}: {update.message.text[:30]}...")
    
    # ثبت کاربر در سیستم آمار اگر فعال باشد
    if STATS_ENABLED:
        try:
            StatsManager.ensure_user_exists(update)
        except Exception as e:
            logger.error(f"خطا در ثبت کاربر در سیستم آمار: {e}")
    
    # استخراج URL از متن پیام
    url = extract_url(update.message.text)
    
    if not url:
        # اگر URL در پیام یافت نشود، هیچ واکنشی نشان نمی‌دهیم
        logger.info(f"پیام بدون لینک از کاربر {user_id} دریافت شد - بدون پاسخ")
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

async def process_instagram_url(update: Update, context, url: str, status_message, url_id: str = None) -> None:
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
            if option.get('type') == 'audio' or "audio" in option.get("quality", "").lower():
                audio_buttons.append([button])
            else:
                video_buttons.append([button])
        
        # افزودن دکمه‌های ویدیو
        keyboard.extend(video_buttons)
        
        # افزودن دکمه‌های صوتی
        if audio_buttons:
            keyboard.extend(audio_buttons)
        else:
            # اگر هیچ دکمه صوتی وجود نداشته باشد، یک دکمه اضافه می‌کنیم
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

async def process_youtube_url(update: Update, context, url: str, status_message, url_id: str = None) -> None:
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

async def handle_download_option(update: Update, context) -> None:
    """
    هندلر انتخاب گزینه دانلود توسط کاربر
    """
    query = update.callback_query
    await query.answer()
    
    # استخراج اطلاعات کالبک
    callback_data = query.data
    user_id = update.effective_user.id
    
    # اطمینان از اینکه این هندلر فقط کالبک‌های دانلود را پردازش می‌کند
    if not callback_data.startswith("dl_"):
        logger.warning(f"کالبک غیر دانلود {callback_data} به هندلر دانلود ارسال شد - در حال رد کردن")
        return
    
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
        if download_type == "audio" or option_id == "audio" or "audio" in callback_data or (download_type == "ig" and option_id == "audio"):
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

async def download_instagram(update: Update, context, url: str, option_id: str) -> None:
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

async def download_instagram_with_option(update: Update, context, url: str, selected_option: Dict) -> None:
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

async def download_youtube_with_option(update: Update, context, url: str, selected_option: Dict) -> None:
    """
    دانلود ویدیوی یوتیوب با استفاده از اطلاعات کامل گزینه
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: کانتکست تلگرام
        url: آدرس یوتیوب
        selected_option: گزینه انتخاب شده از کش
    """
    query = update.callback_query
    user_id = update.effective_user.id
    user_download_data[user_id] = {'url': url, 'download_time': time.time()}
    
    # شروع زمان‌سنج برای ثبت آمار
    if STATS_ENABLED:
        download_timer.start()
    
    try:
        logger.info(f"شروع دانلود یوتیوب با گزینه کامل: {selected_option.get('label', 'نامشخص')}")
        
        # تعیین نوع دانلود - صوتی یا ویدئویی
        is_audio = False
        format_id = selected_option.get('id', '')
        format_option = selected_option.get('format', '')
        quality = selected_option.get('quality', 'best')  # تنظیم متغیر quality
        
        logger.info(f"اطلاعات گزینه انتخاب شده - format_id: {format_id}, format_option: {format_option}, quality: {quality}")
        
        # بررسی دقیق برای تشخیص دانلود صوتی
        if 'audio' in format_id.lower() or 'audio' in format_option.lower():
            is_audio = True
            quality = "audio"  # تنظیم کیفیت برای درخواست صوتی
            logger.info(f"درخواست دانلود صوتی از یوتیوب تشخیص داده شد: {format_id}, quality تنظیم شد به: {quality}")
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

async def download_youtube(update: Update, context, url: str, option_id: str) -> None:
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
            
            # نگاشت مستقیم شماره گزینه به کیفیت متناظر با تضمین دریافت ویدیو
            # گزینه‌های یوتیوب معمولاً: 0: 1080p, 1: 720p, 2: 480p, 3: 360p, 4: 240p, 5: audio
            if option_num == 0:
                # روش ایمن‌تر با تضمین کیفیت 1080p و جلوگیری از نمایش صوتی فقط
                format_option = "bestvideo[height=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height=1080]+bestaudio/best[height=1080][ext=mp4]/best[height=1080]/best"
                quality = "1080p"
                quality_display = "کیفیت Full HD (1080p)"
                is_audio_request = False  # تأکید بر اینکه درخواست ویدیویی است، نه صوتی
            elif option_num == 1:
                format_option = "bestvideo[height=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height=720]+bestaudio/best[height=720][ext=mp4]/best[height=720]/best"
                quality = "720p"
                quality_display = "کیفیت HD (720p)"
                is_audio_request = False  # تأکید بر اینکه درخواست ویدیویی است، نه صوتی
            elif option_num == 2:
                format_option = "bestvideo[height=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height=480]+bestaudio/best[height=480][ext=mp4]/best[height=480]/best"
                quality = "480p"
                quality_display = "کیفیت متوسط (480p)"
                is_audio_request = False  # تأکید بر اینکه درخواست ویدیویی است، نه صوتی
            elif option_num == 3:
                format_option = "bestvideo[height=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height=360]+bestaudio/best[height=360][ext=mp4]/best[height=360]/best"
                quality = "360p"
                quality_display = "کیفیت پایین (360p)"
                is_audio_request = False  # تأکید بر اینکه درخواست ویدیویی است، نه صوتی
            elif option_num == 4:
                format_option = "bestvideo[height=240][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height=240]+bestaudio/best[height=240][ext=mp4]/best[height=240]/best"
                quality = "240p"
                quality_display = "کیفیت خیلی پایین (240p)"
                is_audio_request = False  # تأکید بر اینکه درخواست ویدیویی است، نه صوتی
            elif option_num == 5:
                format_option = "bestaudio/best"
                is_audio_request = True
                quality = "audio"
                quality_display = "فقط صدا (MP3)"
                
            logger.info(f"کیفیت انتخاب شده بر اساس شماره گزینه {option_num}: {format_option}")
        
        # تشخیص صوتی از روی محتوای option_id
        elif 'audio' in option_id.lower():
            is_audio_request = True
            format_option = "bestaudio/best"
            quality = "audio"
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
            
            # دانلود فایل - اصلاح متغیر loop
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # استفاده از روش ایمن برای دانلود بدون نیاز به loop
                try:
                    # روش 1: دانلود مستقیم
                    ydl.download([url])
                except Exception as e:
                    logger.error(f"خطا در دانلود با روش اول: {e}")
                    # روش 2: بدون استفاده از loop
                    try:
                        # ایجاد یک ترد جداگانه برای دانلود
                        import threading
                        download_thread = threading.Thread(target=ydl.download, args=([url],))
                        download_thread.start()
                        download_thread.join(timeout=30)  # انتظار حداکثر 30 ثانیه
                    except Exception as e2:
                        logger.error(f"خطا در دانلود با روش دوم: {e2}")
            
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
            
            # مقدار is_audio را همیشه به False تنظیم می‌کنیم برای درخواست‌های ویدیویی
            # زیرا وقتی اینجا هستیم یعنی کاربر ویدیو درخواست کرده، نه صدا
            is_audio = False
            
            # اگر فایل با موفقیت دانلود شد، بررسی کنیم آیا نیاز به تبدیل کیفیت است
            if downloaded_file and os.path.exists(downloaded_file) and quality and quality != "best" and not is_audio:
                try:
                    logger.info(f"تلاش برای تبدیل کیفیت ویدیوی دانلود شده به {quality}...")
                    # استفاده از ماژول بهبود یافته برای تبدیل کیفیت
                    try:
                        from telegram_fixes import convert_video_quality
                        converted_file = convert_video_quality(
                            video_path=downloaded_file, 
                            quality=quality,
                            is_audio_request=is_audio
                        )
                        
                        if converted_file and os.path.exists(converted_file):
                            logger.info(f"تبدیل کیفیت موفق: {converted_file}")
                            downloaded_file = converted_file
                        else:
                            logger.warning(f"تبدیل کیفیت ناموفق بود، استفاده از فایل اصلی")
                    except ImportError:
                        logger.warning("ماژول telegram_fixes یافت نشد، تبدیل کیفیت انجام نشد")
                    except Exception as e:
                        logger.error(f"خطا در تبدیل کیفیت ویدیو: {str(e)}")
                except Exception as e:
                    logger.error(f"خطا در تبدیل کیفیت ویدیو در تابع download_youtube: {str(e)}")
                    # فایل اصلی را برمی‌گردانیم
            
            # بررسی اضافی برای اطمینان از صحت فرمت ویدیو
            if downloaded_file and downloaded_file.endswith(('.mp3', '.m4a', '.aac', '.wav')) and not downloaded_file.endswith(('.mp4', '.webm', '.mkv')):
                # اگر فایل صوتی باشد، آن را به MP4 تبدیل می‌کنیم (فایل صوتی با تصویر ثابت)
                logger.warning(f"فایل دانلود شده صوتی است، تبدیل به ویدیو: {downloaded_file}")
                
                # نام فایل ویدیویی جدید
                video_path = downloaded_file.rsplit(".", 1)[0] + "_video.mp4"
                
                # تبدیل به ویدیو با استفاده از ffmpeg
                cmd = [
                    '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',
                    '-i', downloaded_file,
                    '-c:a', 'copy',
                    '-f', 'lavfi',
                    '-i', 'color=c=black:s=1280x720',
                    '-shortest',
                    '-vf', "drawtext=text='یوتیوب':fontcolor=white:fontsize=30:x=(w-text_w)/2:y=(h-text_h)/2",
                    '-c:v', 'libx264',
                    '-tune', 'stillimage',
                    '-pix_fmt', 'yuv420p',
                    '-shortest',
                    '-y',
                    video_path
                ]
                
                try:
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    if result.returncode == 0 and os.path.exists(video_path):
                        downloaded_file = video_path
                        is_audio = False
                        logger.info(f"تبدیل صوت به ویدیو موفق: {video_path}")
                    else:
                        logger.error(f"خطا در تبدیل صوت به ویدیو: {result.stderr}")
                except Exception as e:
                    logger.error(f"خطا در اجرای FFmpeg برای تبدیل صوت به ویدیو: {e}")
                    # اگر تبدیل با خطا مواجه شد، از همان فایل صوتی استفاده می‌کنیم
                    is_audio = True
            
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
        
        # بررسی مجدد نوع فایل براساس پسوند - فقط برای مواردی که is_audio از قبل True نیست
        # و فقط برای فایل‌هایی که ویدیویی نیستند
        if not is_audio and not is_playlist and downloaded_file and not downloaded_file.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
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
        
        # ثبت آمار دانلود در صورت فعال بودن سیستم آمار
        if STATS_ENABLED:
            try:
                # توقف زمان‌سنج
                download_timer.stop()
                download_time = download_timer.get_elapsed()
                
                # تبدیل حجم فایل از بایت به مگابایت
                file_size_mb = file_size / (1024 * 1024) if file_size else None
                
                # ثبت در پایگاه داده
                try:
                    from stats_manager import StatsManager
                    StatsManager.record_download(
                        user_id=update.effective_user.id,
                        url=url,
                        source_type="youtube",
                        quality=quality if 'quality' in locals() else 'best',
                        is_audio=is_audio if 'is_audio' in locals() else False,
                        file_size=file_size_mb if file_size_mb is not None else 0.0,
                        download_time=download_time if download_time is not None else 0.0,
                        success=True
                    )
                except ImportError:
                    logger.warning("ماژول StatsManager یافت نشد")
                logger.info(f"آمار دانلود با موفقیت ثبت شد: {url[:30]}...")
            except Exception as stats_error:
                logger.error(f"خطا در ثبت آمار دانلود: {stats_error}")
        
    except Exception as e:
        logger.error(f"خطا در دانلود ویدیوی یوتیوب: {str(e)}")
        logger.error(f"جزئیات خطا: {traceback.format_exc()}")
        
        # ثبت خطا در آمار
        if STATS_ENABLED:
            try:
                # توقف زمان‌سنج
                download_timer.stop()
                download_time = download_timer.get_elapsed()
                
                # ثبت در پایگاه داده
                try:
                    from stats_manager import StatsManager
                    StatsManager.record_download(
                        user_id=update.effective_user.id,
                        url=url,
                        source_type="youtube",
                        quality=quality if 'quality' in locals() else 'best',
                        is_audio=is_audio if 'is_audio' in locals() else False,
                        file_size=0.0,
                        download_time=download_time if download_time is not None else 0.0,
                        success=False,
                        error=str(e)[:255]  # محدود کردن طول پیام خطا
                    )
                except ImportError:
                    logger.warning("ماژول StatsManager یافت نشد")
            except Exception as stats_error:
                logger.error(f"خطا در ثبت آمار خطای دانلود: {stats_error}")
                
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
        # همیشه فایل قفل قبلی را پاک می‌کنیم تا از خطاهای قفل اجتناب شود
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
                logger.info("فایل قفل قبلی حذف شد")
            except:
                logger.warning("خطا در حذف فایل قفل قبلی")
        
        # ایجاد فایل قفل جدید
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
            logger.info(f"فایل قفل جدید با PID {os.getpid()} ایجاد شد")
            
        # پاکسازی فایل‌های موقت
        clean_temp_files()
        
        # دریافت توکن ربات از متغیرهای محیطی
        telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        
        if not telegram_token:
            logger.error("توکن ربات تلگرام یافت نشد! لطفاً متغیر محیطی TELEGRAM_BOT_TOKEN را تنظیم کنید.")
            return
            
        # ایجاد اپلیکیشن ربات 
        # بررسی نسخه کتابخانه و ایجاد اپلیکشن مطابق با آن
        try:
            # نسخه 20.x
            try:
                from telegram.ext import ApplicationBuilder
                app = ApplicationBuilder().token(telegram_token).build()
                logger.info("اپلیکیشن ربات با نسخه PTB 20.x ایجاد شد")
            except (AttributeError, ImportError):
                # نسخه 13.x
                from telegram.ext import Updater
                updater = Updater(token=telegram_token)
                app = updater.dispatcher
                logger.info("اپلیکیشن ربات با نسخه PTB 13.x ایجاد شد")
        except Exception as e:
            logger.error(f"خطا در ایجاد اپلیکیشن ربات: {e}")
            raise
        
        # افزودن هندلرها
        # ایجاد نسخه sync از توابع async
        # برای نسخه 13.x، ما باید یک نسخه sync از هر تابع async ایجاد کنیم

        # تابع sync برای start
        def start_sync(update, context):
            """نسخه sync از start برای سازگاری با PTB 13.x"""
            logger.info(f"دستور /start دریافت شد از کاربر {update.effective_user.id}")
            try:
                # بارگذاری ماژول‌های بهینه‌سازی اگر موجود باشند
                try:
                    from enhanced_telegram_handler import configure_ui_enhancements
                    configure_ui_enhancements(app)
                except ImportError:
                    logger.info("ماژول enhanced_telegram_handler در دسترس نیست")
                    
                # تلاش برای بهینه‌سازی yt-dlp
                try:
                    from youtube_downloader_optimizer import optimize_youtube_downloader
                    optimize_youtube_downloader()
                except ImportError:
                    logger.info("ماژول youtube_downloader_optimizer در دسترس نیست")
                    
                # ایجاد دکمه‌های راهنما
                keyboard = [
                    [
                        InlineKeyboardButton("📚 راهنمای استفاده", callback_data="help"),
                        InlineKeyboardButton("ℹ️ درباره ربات", callback_data="about")
                    ],
                    [
                        InlineKeyboardButton("📥 دانلودهای من", callback_data="mydownloads")
                    ]
                ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # ارسال پیام خوش‌آمدگویی با فرمت HTML و دکمه‌ها
                update.message.reply_text(
                    START_MESSAGE,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                logger.info(f"پاسخ به دستور /start برای کاربر {update.effective_user.id} ارسال شد")
            except Exception as e:
                logger.error(f"خطا در پاسخ به دستور /start: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")

        # تابع sync برای help_command
        def help_command_sync(update, context):
            """نسخه sync از help_command برای سازگاری با PTB 13.x"""
            # ایجاد دکمه‌های راهنما
            keyboard = [
                [
                    InlineKeyboardButton("🎬 کیفیت‌های ویدیو", callback_data="help_video"),
                    InlineKeyboardButton("🎵 دانلود صوتی", callback_data="help_audio")
                ],
                [
                    InlineKeyboardButton("📱 دانلود گروهی", callback_data="help_bulk"),
                    InlineKeyboardButton("ℹ️ درباره ربات", callback_data="about")
                ],
                [
                    InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="back_to_start")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # ارسال پیام راهنما با فرمت HTML و دکمه‌ها
            update.message.reply_text(
                HELP_MESSAGE,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )

        # تابع sync برای about_command
        def about_command_sync(update, context):
            """نسخه sync از about_command برای سازگاری با PTB 13.x"""
            # ایجاد دکمه بازگشت
            keyboard = [
                [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="back_to_start")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # ارسال پیام درباره با فرمت HTML و دکمه‌ها
            update.message.reply_text(
                ABOUT_MESSAGE,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )

        # تابع sync برای process_url
        def process_url_sync(update, context):
            """نسخه sync از process_url برای سازگاری با PTB 13.x"""
            user_id = update.effective_user.id
            logger.info(f"پیام جدید از کاربر {user_id}: {update.message.text[:30]}...")
            
            # ثبت کاربر در سیستم آمار اگر فعال باشد
            if STATS_ENABLED:
                try:
                    StatsManager.ensure_user_exists(update)
                except Exception as e:
                    logger.error(f"خطا در ثبت کاربر در سیستم آمار: {e}")
            
            # استخراج URL از متن پیام
            url = extract_url(update.message.text)
            
            if not url:
                # اگر URL در پیام یافت نشود، هیچ واکنشی نشان نمی‌دهیم
                logger.info(f"پیام بدون لینک از کاربر {user_id} دریافت شد - بدون پاسخ")
                return
                
            # ارسال پیام در حال پردازش
            processing_message = update.message.reply_text(
                STATUS_MESSAGES["processing"]
            )
            
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
                    
                    # فراخوانی نسخه sync از process_instagram_url
                    process_instagram_url_sync(update, context, normalized_url, processing_message, url_id)
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
                    
                    # فراخوانی نسخه sync از process_youtube_url
                    process_youtube_url_sync(update, context, normalized_url, processing_message, url_id)
                else:
                    processing_message.edit_text(ERROR_MESSAGES["unsupported_url"])
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
                
                processing_message.edit_text(error_message)
                
        # در اینجا توابع process_instagram_url_sync و process_youtube_url_sync را می‌نویسیم
        
        # نسخه sync از process_instagram_url
        def process_instagram_url_sync(update, context, url, status_message, url_id=None):
            """نسخه sync از process_instagram_url برای سازگاری با PTB 13.x"""
            logger.info(f"شروع پردازش URL اینستاگرام (sync): {url[:30]}...")
            try:
                # ایجاد دانلودر اینستاگرام
                downloader = InstagramDownloader()
                
                # تبدیل awaitable به نتیجه با استفاده از یک ترفند ساده
                # برای نسخه sync، ما رویکرد متفاوتی برای دریافت گزینه‌ها استفاده می‌کنیم
                options = []
                
                # گزینه‌های پیش‌فرض برای اینستاگرام
                options = [
                    {"quality": "1080p", "display_name": "کیفیت بالا (1080p)", "type": "video"},
                    {"quality": "720p", "display_name": "کیفیت متوسط (720p)", "type": "video"},
                    {"quality": "480p", "display_name": "کیفیت پایین (480p)", "type": "video"},
                    {"quality": "360p", "display_name": "کیفیت کم (360p)", "type": "video"},
                    {"quality": "240p", "display_name": "کیفیت خیلی کم (240p)", "type": "video"},
                    {"quality": "audio", "display_name": "فقط صدا (MP3)", "type": "audio"}
                ]
                
                if not options:
                    status_message.edit_text(ERROR_MESSAGES["fetch_options_failed"])
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
                    
                    # مطمئن شویم متغیرهای مورد نیاز وجود دارند
                    if 'user_download_data' not in globals():
                        global user_download_data
                        user_download_data = {}
                        
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
                    if option.get('type') == 'audio' or "audio" in option.get("quality", "").lower():
                        audio_buttons.append([button])
                    else:
                        video_buttons.append([button])
                
                # افزودن دکمه‌های ویدیو
                keyboard.extend(video_buttons)
                
                # افزودن دکمه‌های صوتی
                if audio_buttons:
                    keyboard.extend(audio_buttons)
                else:
                    # اگر هیچ دکمه صوتی وجود نداشته باشد، یک دکمه اضافه می‌کنیم
                    keyboard.append([InlineKeyboardButton("🎵 فقط صدا (MP3)", callback_data=f"dl_ig_audio_{url_id}")])
                    
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # ارسال گزینه‌های دانلود
                status_message.edit_text(
                    INSTAGRAM_DOWNLOAD_OPTIONS,
                    reply_markup=reply_markup
                )
                
                # ذخیره اطلاعات دانلود برای کاربر
                user_download_data[user_id]['instagram_options'] = options
                user_download_data[user_id]['url'] = url
                
            except Exception as e:
                logger.error(f"خطا در پردازش URL اینستاگرام (sync): {str(e)}")
                
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
                    
                status_message.edit_text(error_message)

        # نسخه sync از process_youtube_url
        def process_youtube_url_sync(update, context, url, status_message, url_id=None):
            """نسخه sync از process_youtube_url برای سازگاری با PTB 13.x"""
            logger.info(f"شروع پردازش URL یوتیوب (sync): {url[:30]}...")
            try:
                # ایجاد دانلودر یوتیوب
                downloader = YouTubeDownloader()
                
                # تبدیل awaitable به نتیجه با استفاده از یک ترفند ساده
                # برای نسخه sync، ما رویکرد متفاوتی برای دریافت گزینه‌ها استفاده می‌کنیم
                options = []
                
                # گزینه‌های پیش‌فرض برای یوتیوب
                options = [
                    {"quality": "1080p", "label": "1. کیفیت عالی (1080p)", "format_id": "137+140"},
                    {"quality": "720p", "label": "2. کیفیت بالا (720p)", "format_id": "136+140"},
                    {"quality": "480p", "label": "3. کیفیت متوسط (480p)", "format_id": "135+140"},
                    {"quality": "360p", "label": "4. کیفیت پایین (360p)", "format_id": "134+140"},
                    {"quality": "240p", "label": "5. کیفیت خیلی پایین (240p)", "format_id": "133+140"},
                    {"quality": "audio", "label": "6. فقط صدا (MP3)", "format_id": "140", "format_note": "audio only"}
                ]
                
                if not options:
                    status_message.edit_text(ERROR_MESSAGES["fetch_options_failed"])
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
                
                # مطمئن شویم متغیرهای مورد نیاز وجود دارند
                if 'user_download_data' not in globals():
                    global user_download_data
                    user_download_data = {}
                
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
                status_message.edit_text(
                    options_message,
                    reply_markup=reply_markup
                )
                
                # ذخیره اطلاعات دانلود برای کاربر
                user_download_data[user_id]['youtube_options'] = options
                user_download_data[user_id]['url'] = url
                
            except Exception as e:
                logger.error(f"خطا در پردازش URL یوتیوب (sync): {str(e)}")
                
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
                    
                status_message.edit_text(error_message)
            
        # ثبت هندلرهای اصلی با نسخه sync
        app.add_handler(CommandHandler("start", start_sync))
        app.add_handler(CommandHandler("help", help_command_sync))
        app.add_handler(CommandHandler("about", about_command_sync))
        
        # اضافه کردن هندلر دستور آمار (فقط برای مدیران)
        if STATS_ENABLED:
            try:
                # وارد کردن ماژول آمار
                from stats_manager import stats_command, handle_stats_buttons
                
                app.add_handler(CommandHandler("stats", stats_command))
                # هندلر کالبک دکمه‌های آمار
                app.add_handler(CallbackQueryHandler(handle_stats_buttons, pattern="^(stats_chart|daily_chart|refresh_stats)$"))
                logger.info("هندلرهای آمار با موفقیت اضافه شدند")
            except Exception as e:
                logger.error(f"خطا در افزودن هندلرهای آمار: {e}")
                
        # استفاده از نسخه sync برای تابع process_url
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_url_sync))
        
        # نسخه sync از handle_download_option
        def handle_download_option_sync(update, context):
            """نسخه sync از handle_download_option برای سازگاری با PTB 13.x"""
            query = update.callback_query
            query.answer()
            
            # استخراج اطلاعات کالبک
            callback_data = query.data
            user_id = update.effective_user.id
            
            # اطمینان از اینکه این هندلر فقط کالبک‌های دانلود را پردازش می‌کند
            if not callback_data.startswith("dl_"):
                logger.warning(f"کالبک غیر دانلود {callback_data} به هندلر دانلود ارسال شد - در حال رد کردن")
                return
            
            logger.info(f"کاربر {user_id} دکمه {callback_data} را انتخاب کرد")
            
            # ذخیره آخرین کلیک دکمه برای استفاده در بازیابی
            recent_button_clicks[user_id] = callback_data
            
            try:
                # جدا کردن اجزای کالبک
                parts = callback_data.split('_')
                if len(parts) < 4:
                    logger.warning(f"فرمت نامعتبر کالبک: {callback_data}")
                    query.edit_message_text(ERROR_MESSAGES["generic_error"])
                    return
                    
                # استخراج نوع دانلود (اینستاگرام/یوتیوب)، گزینه و شناسه URL
                download_type = parts[1]  # ig یا yt
                option_id = parts[2]      # شناسه گزینه انتخاب شده
                url_id = '_'.join(parts[3:])  # شناسه URL (ممکن است شامل '_' باشد)
                
                # بررسی اینکه URL موجود است
                if url_id in persistent_url_storage:
                    url = persistent_url_storage[url_id]['url']
                    # ساخت پیام وضعیت
                    status_message = query.edit_message_text(
                        STATUS_MESSAGES["processing"],
                        reply_markup=None
                    )
                    
                    if download_type == "ig":
                        if option_id == "audio":
                            # درخواست مستقیم برای فقط صدا
                            # اینجا برای سادگی از همان ساختار کیفیت استفاده می‌کنیم
                            selected_option = {
                                "quality": "audio",
                                "display_name": "فقط صدا (MP3)",
                                "type": "audio"
                            }
                            download_instagram_with_option_sync(update, context, url, selected_option, status_message)
                        else:
                            # بررسی وجود گزینه‌های دانلود در cache
                            if user_id in user_download_data and 'option_map' in user_download_data[user_id] and option_id in user_download_data[user_id]['option_map']:
                                selected_option = user_download_data[user_id]['option_map'][option_id]
                                download_instagram_with_option_sync(update, context, url, selected_option, status_message)
                            else:
                                logger.warning(f"گزینه انتخابی {option_id} در کش برای کاربر {user_id} یافت نشد")
                                # اگر گزینه در کش نباشد، یک رویکرد بازیابی خطا داریم
                                # سعی می‌کنیم با شماره شناسایی کنیم
                                quality_map = {
                                    "0": "1080p", "1": "720p", "2": "480p", "3": "360p", 
                                    "4": "240p", "5": "audio"
                                }
                                if option_id in quality_map:
                                    quality = quality_map[option_id]
                                    download_instagram_sync(update, context, url, quality, status_message)
                                else:
                                    query.edit_message_text(ERROR_MESSAGES["url_expired"])
                    
                    elif download_type == "yt":
                        if option_id == "audio":
                            # درخواست مستقیم برای فقط صدا
                            download_youtube_sync(update, context, url, "audio", status_message)
                        else:
                            # بررسی وجود گزینه‌های دانلود در cache
                            if user_id in user_download_data and 'option_map' in user_download_data[user_id] and option_id in user_download_data[user_id]['option_map']:
                                selected_option = user_download_data[user_id]['option_map'][option_id]
                                download_youtube_with_option_sync(update, context, url, selected_option, status_message)
                            else:
                                logger.warning(f"گزینه انتخابی {option_id} در کش برای کاربر {user_id} یافت نشد")
                                # اگر گزینه در کش نباشد، یک رویکرد بازیابی خطا داریم
                                # سعی می‌کنیم با شماره شناسایی کنیم
                                quality_map = {
                                    "0": "1080p", "1": "720p", "2": "480p", "3": "360p", 
                                    "4": "240p", "5": "audio"
                                }
                                if option_id in quality_map:
                                    quality = quality_map[option_id]
                                    download_youtube_sync(update, context, url, quality, status_message)
                                else:
                                    query.edit_message_text(ERROR_MESSAGES["url_expired"])
                else:
                    logger.warning(f"URL ID {url_id} در مخزن یافت نشد")
                    
                    # سعی در بازیابی URL از منابع دیگر
                    matching_urls = [(vid, data) for vid, data in persistent_url_storage.items() 
                                    if data.get('user_id') == user_id]
                    
                    if matching_urls:
                        # انتخاب آخرین URL ذخیره شده برای کاربر
                        latest_url_id, latest_data = sorted(
                            matching_urls, 
                            key=lambda x: x[1].get('timestamp', 0), 
                            reverse=True
                        )[0]
                        
                        # ارسال پیام به کاربر و تلاش مجدد با آخرین URL
                        query.edit_message_text(
                            f"⚠️ لینک قبلی شما منقضی شده است. در حال تلاش با آخرین لینک...",
                            reply_markup=None
                        )
                        logger.info(f"تلاش مجدد با آخرین URL کاربر: {latest_url_id}")
                        
                        # بازسازی قسمت‌های callback_data با URL ID جدید
                        new_callback_data = f"dl_{download_type}_{option_id}_{latest_url_id}"
                        # ذخیره در cache برای استفاده بعدی
                        recent_button_clicks[user_id] = new_callback_data
                        
                        # فراخوانی مجدد هندلر با داده‌های جدید
                        query.data = new_callback_data
                        handle_download_option_sync(update, context)
                    else:
                        query.edit_message_text(ERROR_MESSAGES["url_expired"])
                
            except Exception as e:
                logger.error(f"خطا در پردازش کالبک دانلود: {str(e)}")
                logger.error(traceback.format_exc())
                query.edit_message_text(ERROR_MESSAGES["generic_error"])
        
        # ساده‌سازی توابع دانلود برای نسخه sync
        def download_instagram_sync(update, context, url, quality, status_message):
            """نسخه sync از download_instagram"""
            try:
                # ساخت نسخه ساده‌تر از گزینه‌های انتخاب شده
                selected_option = {
                    "quality": quality,
                    "type": "audio" if quality == "audio" else "video"
                }
                download_instagram_with_option_sync(update, context, url, selected_option, status_message)
            except Exception as e:
                logger.error(f"خطا در دانلود اینستاگرام: {e}")
                status_message.edit_text(ERROR_MESSAGES["generic_error"])
        
        def download_instagram_with_option_sync(update, context, url, selected_option, status_message=None, url_id=None):
            """نسخه sync از download_instagram_with_option"""
            user_id = update.effective_user.id
            # مقداردهی اولیه متغیرهای مهم
            download_time = 0
            logger.info(f"شروع دانلود اینستاگرام برای کاربر {user_id} با کیفیت {selected_option.get('quality', 'نامشخص')}")
            
            try:
                # اگر پیام وضعیت ارائه نشده باشد، آن را ایجاد کن
                if status_message is None:
                    status_message = update.callback_query.edit_message_text(
                        STATUS_MESSAGES["processing"],
                        reply_markup=None
                    )
                
                # نوع دانلود را تعیین کن
                is_audio = selected_option.get('type') == 'audio' or selected_option.get('quality') == 'audio'
                
                if is_audio:
                    status_message.edit_text(STATUS_MESSAGES["downloading_audio"])
                else:
                    status_message.edit_text(STATUS_MESSAGES["downloading"])
                
                # انتخاب کیفیت مناسب
                quality = selected_option.get('quality', 'best')
                
                # دانلود را انجام بده
                instagram_dl = InstagramDownloader()
                
                # بررسی کش قبل از دانلود
                # مقداردهی اولیه file_path
                file_path = None
                
                cache_key = f"{url}_{quality}"
                if cache_key in option_cache:
                    file_path = option_cache[cache_key].get('file_path')
                    if file_path and os.path.exists(file_path):
                        logger.info(f"فایل از کش دریافت شد: {file_path}")
                    else:
                        # اگر فایل در کش نیست یا دیگر وجود ندارد، دانلود کن
                        file_path = None
                
                if not file_path:
                    # ایجاد و شروع تایمر برای اندازه‌گیری زمان دانلود
                    download_timer = time.time()
                
                    # روش بهبود یافته: ابتدا با بهترین کیفیت دانلود و سپس در صورت نیاز تبدیل کیفیت
                    try:
                        # ابتدا با بهترین کیفیت دانلود می‌کنیم
                        logger.info(f"شروع دانلود ویدیوی اینستاگرام با بهترین کیفیت برای تبدیل به {quality}")
                        try:
                            best_file_path = asyncio.get_event_loop().run_until_complete(
                                instagram_dl._download_with_ytdlp(url, "", "best"))
                        except RuntimeError:
                            # اگر event loop در حال اجراست، از روش دیگری استفاده می‌کنیم
                            new_loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(new_loop)
                            best_file_path = new_loop.run_until_complete(
                                instagram_dl._download_with_ytdlp(url, "", "best"))
                            new_loop.close()
                        
                        if best_file_path and os.path.exists(best_file_path) and os.path.getsize(best_file_path) > 0:
                            logger.info(f"ویدیو با بهترین کیفیت دانلود شد: {best_file_path}")
                            
                            # اگر خواسته صوتی باشد
                            if is_audio:
                                from audio_processing import extract_audio
                                file_path = extract_audio(best_file_path)
                                logger.info(f"صدا استخراج شد: {file_path}")
                            # اگر best خواسته باشد، همان فایل اصلی را برگردان
                            elif quality == 'best':
                                file_path = best_file_path
                                logger.info(f"کیفیت اصلی انتخاب شده، تبدیل لازم نیست")
                            # اجبار به تبدیل کیفیت حتی برای 1080p
                            elif quality == '1080p':
                                status_message.edit_text(f"⏳ ویدیو دانلود شد، در حال تبدیل به کیفیت {quality}...")
                                from telegram_fixes import convert_video_quality
                                file_path = convert_video_quality(best_file_path, quality)
                                logger.info(f"ویدیو با موفقیت به کیفیت {quality} تبدیل شد: {file_path}")
                            else:
                                # تبدیل به کیفیت درخواست شده
                                status_message.edit_text(f"⏳ ویدیو دانلود شد، در حال تبدیل به کیفیت {quality}...")
                                
                                # تبدیل به کیفیت درخواست شده با ffmpeg
                                if quality.endswith('p'):
                                    target_height = int(quality.replace('p', ''))
                                else:
                                    # اگر فرمت کیفیت نامعتبر باشد، از مقدار پیش‌فرض استفاده کن
                                    target_height = {'720': 720, '480': 480, '360': 360, '240': 240}.get(quality, 720)
                                
                                from telegram_fixes import convert_video_quality
                                converted_path = convert_video_quality(best_file_path, target_height)
                                
                                if converted_path and os.path.exists(converted_path):
                                    file_path = converted_path
                                    logger.info(f"ویدیو با موفقیت به کیفیت {quality} تبدیل شد: {file_path}")
                                else:
                                    logger.warning(f"تبدیل کیفیت ناموفق بود، استفاده از فایل اصلی")
                                    file_path = best_file_path
                        else:
                            logger.warning(f"دانلود با بهترین کیفیت ناموفق بود، تلاش مستقیم با کیفیت {quality}")
                            # تلاش دانلود مستقیم با کیفیت درخواستی
                            try:
                                file_path = asyncio.get_event_loop().run_until_complete(
                                    instagram_dl._download_with_ytdlp(url, "", quality))
                            except RuntimeError:
                                new_loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(new_loop)
                                file_path = new_loop.run_until_complete(
                                    instagram_dl._download_with_ytdlp(url, "", quality))
                                new_loop.close()
                    except Exception as e:
                        logger.error(f"خطا در روش بهبود یافته: {e}, تلاش با روش قدیمی")
                        # روش قدیمی به عنوان پشتیبان
                        try:
                            file_path = asyncio.get_event_loop().run_until_complete(
                                instagram_dl._download_with_ytdlp(url, "", quality))
                        except RuntimeError:
                            new_loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(new_loop)
                            file_path = new_loop.run_until_complete(
                                instagram_dl._download_with_ytdlp(url, "", quality))
                            new_loop.close()
                    
                    download_time = time.time() - download_timer
                    logger.info(f"دانلود با کیفیت {quality} در {download_time:.2f} ثانیه کامل شد")
                    
                    # افزودن به کش
                    option_cache[cache_key] = {
                        'file_path': file_path,
                        'timestamp': time.time()
                    }
                
                if not file_path or not os.path.exists(file_path):
                    logger.error(f"خطا: مسیر فایل نامعتبر است - {file_path}")
                    status_message.edit_text(ERROR_MESSAGES["download_failed"])
                    return
                
                # مدیریت فایل‌های صوتی
                if is_audio:
                    status_message.edit_text(STATUS_MESSAGES["processing_audio"])
                    
                    # استخراج صدا
                    audio_file = extract_audio(file_path)
                    
                    if not audio_file:
                        logger.error("خطا در استخراج صدا")
                        status_message.edit_text(ERROR_MESSAGES["download_failed"])
                        return
                        
                    # آپلود صدا به تلگرام
                    status_message.edit_text(STATUS_MESSAGES["uploading"])
                    
                    with open(audio_file, 'rb') as audio:
                        update.effective_chat.send_audio(
                            audio=audio,
                            title=os.path.basename(audio_file),
                            caption=f"🎵 فایل صوتی از اینستاگرام\n🔗 {url}",
                            performer="Instagram Audio"
                        )
                        
                    status_message.edit_text(STATUS_MESSAGES["complete"])
                    
                    # افزودن به آمار
                    if STATS_ENABLED:
                        try:
                            StatsManager.add_download_record(update.effective_user, "instagram", "audio", os.path.getsize(audio_file))
                        except Exception as e:
                            logger.error(f"خطا در ثبت آمار: {e}")
                else:
                    # آپلود ویدیو به تلگرام
                    status_message.edit_text(STATUS_MESSAGES["uploading"])
                    
                    # بررسی حجم فایل
                    file_size = os.path.getsize(file_path)
                    if file_size > MAX_TELEGRAM_FILE_SIZE:
                        logger.warning(f"فایل خیلی بزرگ است ({file_size} بایت)، در حال کاهش کیفیت...")
                        status_message.edit_text(f"⚠️ فایل بسیار بزرگ است ({human_readable_size(file_size)}). در حال پردازش کیفیت پایین‌تر...")
                        
                        # تلاش برای تبدیل به کیفیت پایین‌تر
                        try:
                            lower_quality_file = convert_to_lower_quality(file_path)
                            if lower_quality_file and os.path.exists(lower_quality_file):
                                file_path = lower_quality_file
                                logger.info(f"فایل با موفقیت به کیفیت پایین‌تر تبدیل شد: {file_path}")
                            else:
                                logger.error("تبدیل به کیفیت پایین‌تر ناموفق بود")
                                status_message.edit_text(ERROR_MESSAGES["file_too_large"])
                                return
                        except Exception as e:
                            logger.error(f"خطا در تبدیل به کیفیت پایین‌تر: {e}")
                            status_message.edit_text(ERROR_MESSAGES["file_too_large"])
                            return
                    
                    # آپلود فایل
                    try:
                        with open(file_path, 'rb') as video:
                            update.effective_chat.send_video(
                                video=video,
                                caption=f"🎬 ویدیوی اینستاگرام | کیفیت: {quality}\n🔗 {url}",
                                supports_streaming=True
                            )
                            
                        status_message.edit_text(STATUS_MESSAGES["complete"])
                        
                        # افزودن به آمار
                        if STATS_ENABLED:
                            try:
                                StatsManager.add_download_record(update.effective_user, "instagram", quality, os.path.getsize(file_path))
                            except Exception as e:
                                logger.error(f"خطا در ثبت آمار: {e}")
                    except Exception as e:
                        logger.error(f"خطا در آپلود ویدیو: {e}")
                        status_message.edit_text(ERROR_MESSAGES["telegram_upload"])
                        return
                
                # اضافه کردن دکمه "دانلود مجدد" به پیام کامل شده
                keyboard = [
                    [InlineKeyboardButton("⬇️ دانلود با کیفیت دیگر", callback_data=f"redownload_{url}")],
                    [InlineKeyboardButton("🔍 دانلود لینک جدید", callback_data="new_download")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                status_message.edit_text(
                    f"✅ دانلود با موفقیت انجام شد!\n\n" +
                    f"📌 نوع: {'صوتی' if is_audio else 'ویدیویی'}\n" +
                    (f"🎬 کیفیت: {quality}\n" if not is_audio else "") +
                    f"⏱ زمان پردازش: {int(download_time)} ثانیه",
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"خطا در دانلود اینستاگرام با گزینه: {e}")
                logger.error(traceback.format_exc())
                if status_message:
                    status_message.edit_text(ERROR_MESSAGES["generic_error"])
        
        def download_youtube_sync(update, context, url, quality, status_message):
            """نسخه sync از download_youtube"""
            try:
                # ساخت نسخه ساده‌تر از گزینه‌های انتخاب شده
                selected_option = {
                    "quality": quality,
                    "label": f"کیفیت {quality}",
                    "format_id": "best" if quality != "audio" else "bestaudio",
                    "format_note": "audio only" if quality == "audio" else "video"
                }
                download_youtube_with_option_sync(update, context, url, selected_option, status_message)
            except Exception as e:
                logger.error(f"خطا در دانلود یوتیوب: {e}")
                status_message.edit_text(ERROR_MESSAGES["generic_error"])
        
        def download_youtube_with_option_sync(update, context, url, selected_option, status_message=None):
            """نسخه sync از download_youtube_with_option"""
            user_id = update.effective_user.id
            quality = selected_option.get('quality', 'best')
            logger.info(f"شروع دانلود یوتیوب برای کاربر {user_id} با کیفیت {quality}")
            
            try:
                # اگر پیام وضعیت ارائه نشده باشد، آن را ایجاد کن
                if status_message is None:
                    status_message = update.callback_query.edit_message_text(
                        STATUS_MESSAGES["processing"],
                        reply_markup=None
                    )
                
                # نوع دانلود را تعیین کن
                is_audio = selected_option.get('format_note', '').lower() == 'audio only' or quality == 'audio'
                
                if is_audio:
                    status_message.edit_text(STATUS_MESSAGES["downloading_audio"])
                else:
                    status_message.edit_text(STATUS_MESSAGES["downloading"])
                
                # دانلود را انجام بده
                youtube_dl = YouTubeDownloader()
                
                # بررسی کش قبل از دانلود
                cache_key = f"{url}_{quality}"
                file_path = None
                if cache_key in option_cache:
                    file_path = option_cache[cache_key].get('file_path')
                    if file_path and os.path.exists(file_path):
                        logger.info(f"فایل از کش دریافت شد: {file_path}")
                    else:
                        # اگر فایل در کش نیست یا دیگر وجود ندارد، دانلود کن
                        file_path = None
                
                if not file_path:
                    # ایجاد و شروع تایمر برای اندازه‌گیری زمان دانلود
                    download_timer = time.time()
                
                    # انتخاب روش دانلود بر اساس نوع
                    if is_audio:
                        # دانلود فقط صدا
                        ydl_opts = {
                            'format': 'bestaudio/best',
                            'outtmpl': os.path.join(TEMP_DOWNLOAD_DIR, 'youtube', 'yt_audio_%(id)s.%(ext)s'),
                            'postprocessors': [{
                                'key': 'FFmpegExtractAudio',
                                'preferredcodec': 'mp3',
                                'preferredquality': '192',
                            }],
                            'cookies': YOUTUBE_COOKIE_FILE,
                            'quiet': True,
                            'no_warnings': True
                        }
                        
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            info = ydl.extract_info(url, download=True)
                            video_id = info.get('id', '')
                            file_path = os.path.join(TEMP_DOWNLOAD_DIR, 'youtube', f'yt_audio_{video_id}.mp3')
                    else:
                        # دانلود ویدیو - اینجا از format_id استفاده می‌کنیم
                        format_id = selected_option.get('format_id', '')
                        
                        ydl_opts = {
                            'format': format_id if format_id else f'best[height<={quality[:-1]}]',
                            'outtmpl': os.path.join(TEMP_DOWNLOAD_DIR, 'youtube', '%(title)s-%(id)s_video_%(resolution)s.%(ext)s'),
                            'cookies': YOUTUBE_COOKIE_FILE,
                            'quiet': True,
                            'no_warnings': True
                        }
                        
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            info = ydl.extract_info(url, download=True)
                            file_path = ydl.prepare_filename(info)
                            # بررسی وجود فایل با پسوندهای مختلف در صورتی که ydl پسوند را تغییر داده باشد
                            if not os.path.exists(file_path):
                                for ext in ['mp4', 'webm', 'mkv']:
                                    test_path = os.path.splitext(file_path)[0] + f'.{ext}'
                                    if os.path.exists(test_path):
                                        file_path = test_path
                                        break
                    
                    download_time = time.time() - download_timer
                    logger.info(f"دانلود با کیفیت {quality} در {download_time:.2f} ثانیه کامل شد")
                    
                    # افزودن به کش
                    option_cache[cache_key] = {
                        'file_path': file_path,
                        'timestamp': time.time()
                    }
                else:
                    download_time = 0.1  # مقدار دلخواه برای زمان دانلود از کش
                
                if not file_path or not os.path.exists(file_path):
                    logger.error(f"خطا: مسیر فایل نامعتبر است - {file_path}")
                    status_message.edit_text(ERROR_MESSAGES["download_failed"])
                    return
                
                # بررسی حجم فایل
                file_size = os.path.getsize(file_path)
                if file_size > MAX_TELEGRAM_FILE_SIZE and not is_audio:
                    logger.warning(f"فایل خیلی بزرگ است ({file_size} بایت)، در حال کاهش کیفیت...")
                    status_message.edit_text(f"⚠️ فایل بسیار بزرگ است ({human_readable_size(file_size)}). در حال پردازش کیفیت پایین‌تر...")
                    
                    # تلاش برای تبدیل به کیفیت پایین‌تر
                    try:
                        lower_quality_file = convert_to_lower_quality(file_path)
                        if lower_quality_file and os.path.exists(lower_quality_file):
                            file_path = lower_quality_file
                            logger.info(f"فایل با موفقیت به کیفیت پایین‌تر تبدیل شد: {file_path}")
                        else:
                            logger.error("تبدیل به کیفیت پایین‌تر ناموفق بود")
                            status_message.edit_text(ERROR_MESSAGES["file_too_large"])
                            return
                    except Exception as e:
                        logger.error(f"خطا در تبدیل به کیفیت پایین‌تر: {e}")
                        status_message.edit_text(ERROR_MESSAGES["file_too_large"])
                        return
                
                # آپلود فایل به تلگرام
                status_message.edit_text(STATUS_MESSAGES["uploading"])
                
                try:
                    if is_audio:
                        # آپلود به عنوان فایل صوتی
                        with open(file_path, 'rb') as audio:
                            update.effective_chat.send_audio(
                                audio=audio,
                                title=os.path.basename(file_path),
                                caption=f"🎵 فایل صوتی از یوتیوب\n🔗 {url}",
                                performer="YouTube Audio"
                            )
                    else:
                        # آپلود به عنوان ویدیو
                        with open(file_path, 'rb') as video:
                            update.effective_chat.send_video(
                                video=video,
                                caption=f"🎬 ویدیوی یوتیوب | کیفیت: {quality}\n🔗 {url}",
                                supports_streaming=True
                            )
                    
                    # افزودن به آمار
                    if STATS_ENABLED:
                        try:
                            StatsManager.add_download_record(update.effective_user, "youtube", "audio" if is_audio else quality, file_size)
                        except Exception as e:
                            logger.error(f"خطا در ثبت آمار: {e}")
                            
                    # اضافه کردن دکمه "دانلود مجدد" به پیام کامل شده
                    keyboard = [
                        [InlineKeyboardButton("⬇️ دانلود با کیفیت دیگر", callback_data=f"redownload_{url}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    status_message.edit_text(
                        f"✅ دانلود با موفقیت انجام شد!\n\n" +
                        f"📌 نوع: {'صوتی' if is_audio else 'ویدیویی'}\n" +
                        (f"🎬 کیفیت: {quality}\n" if not is_audio else "") +
                        f"⏱ زمان پردازش: {int(download_time)} ثانیه",
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"خطا در آپلود فایل: {e}")
                    status_message.edit_text(ERROR_MESSAGES["telegram_upload"])
            except Exception as e:
                logger.error(f"خطا در دانلود یوتیوب با گزینه: {e}")
                logger.error(traceback.format_exc())
                if status_message:
                    status_message.edit_text(ERROR_MESSAGES["generic_error"])
            
        # ثبت هندلرهای کالبک دکمه‌ها
        from telegram_handlers import handle_menu_button
        
        # هندلر کالبک دکمه‌های دانلود (برای دکمه‌های دانلود فایل)
        # این هندلر باید اول ثبت شود زیرا اولویت بیشتری دارد
        app.add_handler(CallbackQueryHandler(handle_download_option_sync, pattern="^dl_"))
        
        # هندلر کالبک دکمه‌های منو (برای دکمه‌های بازگشت و راهنما)
        app.add_handler(CallbackQueryHandler(handle_menu_button, pattern="^(back_to_start|help|about|help_video|help_audio|help_bulk|mydownloads)$"))
        
        # افزودن هندلرهای دانلود موازی
        try:
            from bulk_download_handler import register_handlers
            register_handlers(app)
            logger.info("هندلرهای دانلود موازی با موفقیت اضافه شدند")
        except ImportError as e:
            logger.warning(f"ماژول دانلود موازی یافت نشد: {e}")
        except Exception as e:
            logger.error(f"خطا در افزودن هندلرهای دانلود موازی: {e}")
        
        # راه‌اندازی وظیفه پاکسازی دوره‌ای
        asyncio.create_task(run_periodic_cleanup(app))
        
        # راه‌اندازی ربات مطابق با نسخه کتابخانه
        try:
            # برای نسخه 20.x
            await app.initialize()
            await app.start()
            await app.updater.start_polling()
            logger.info("ربات با API نسخه 20.x راه‌اندازی شد")
        except AttributeError:
            # برای نسخه 13.x
            try:
                updater.start_polling()
                logger.info("ربات با API نسخه 13.x راه‌اندازی شد")
            except Exception as e:
                logger.error(f"خطا در راه‌اندازی polling: {e}")
                raise
        
        logger.info("ربات با موفقیت راه‌اندازی شد!")
        
        try:
            # نگه داشتن ربات در حال اجرا بر اساس نسخه
            # برای نسخه 13.x نیازی به این کد نیست زیرا updater.idle() در خود کتابخانه انجام می‌شود
            try:
                # برای نسخه 20.x
                await asyncio.Event().wait()
            except AttributeError:
                # برای نسخه 13.x (idle را به صورت مستقیم صدا می‌زنیم)
                try:
                    updater.idle()
                except Exception as e:
                    logger.error(f"خطا در اجرای idle: {e}")
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
import random

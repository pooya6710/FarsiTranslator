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
    cookie_file = os.path.join(tempfile.gettempdir(), "youtube_cookies.txt")
    with open(cookie_file, "w", encoding="utf-8") as f:
        f.write(cookies_content)
    
    return cookie_file

"""
بخش 2: تشخیص URL و پردازش آن
"""

def extract_urls(text: str) -> List[str]:
    """استخراج URL از متن پیام"""
    # الگوی URL برای تشخیص لینک‌های اینستاگرام و یوتیوب
    url_pattern = r'(https?://(?:www\.)?(?:instagram\.com|youtube\.com|youtu\.be)[\w/\.\-\?=&%+]*)'
    
    # استخراج همه URL ها
    urls = re.findall(url_pattern, text)
    
    # حذف پارامترهای اضافی برای لینک‌های اینستاگرام
    cleaned_urls = []
    for url in urls:
        # پاکسازی لینک‌های اینستاگرام
        if 'instagram.com' in url:
            # حذف پارامترهای اضافی مانند ?igshid و غیره
            url = re.sub(r'\?.*$', '', url)
        cleaned_urls.append(url)
    
    return cleaned_urls

def identify_url_type(url: str) -> str:
    """شناسایی نوع URL (اینستاگرام یا یوتیوب)"""
    parsed_url = urlparse(url)
    
    # بررسی دامنه URL
    domain = parsed_url.netloc.lower()
    path = parsed_url.path.lower()
    
    if 'instagram.com' in domain:
        # تشخیص انواع لینک‌های اینستاگرام
        if '/reel/' in path or '/reels/' in path:
            return 'instagram_reel'
        elif '/p/' in path:
            return 'instagram_post'
        else:
            return 'instagram_unknown'
            
    elif 'youtube.com' in domain or 'youtu.be' in domain:
        # تشخیص انواع لینک‌های یوتیوب
        if 'youtube.com/shorts' in url:
            return 'youtube_shorts'
        elif 'youtube.com/playlist' in url or 'list=' in url:
            return 'youtube_playlist'
        elif 'youtube.com/watch' in url or 'youtu.be/' in url:
            return 'youtube_video'
        else:
            return 'youtube_unknown'
            
    # اگر هیچ کدام از موارد بالا نبود
    return 'unknown'

"""
بخش 3: پردازش دانلود اینستاگرام
"""

async def process_instagram_url(url: str, message_id: int, chat_id: int) -> None:
    """پردازش URL اینستاگرام و ارائه گزینه‌های دانلود"""
    # ایجاد کلید منحصر به فرد برای ذخیره‌سازی URL
    unique_key = f"{chat_id}_{message_id}"
    
    # ذخیره URL در مخزن پایدار
    persistent_url_storage[unique_key] = url
    
    # شناسایی نوع URL
    url_type = identify_url_type(url)
    
    # ایجاد گزینه‌های دانلود برای پست اینستاگرام
    keyboard = [
        [
            InlineKeyboardButton("🎬 دانلود ویدیو با کیفیت بالا", callback_data=f"instagram_hd_{unique_key}"),
        ],
        [
            InlineKeyboardButton("🎬 دانلود ویدیو با کیفیت معمولی", callback_data=f"instagram_sd_{unique_key}"),
        ],
        [
            InlineKeyboardButton("🎵 دانلود فقط صدا", callback_data=f"instagram_audio_{unique_key}"),
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    return reply_markup, INSTAGRAM_DOWNLOAD_OPTIONS

async def download_instagram_video(url: str, quality: str = 'hd') -> Optional[str]:
    """دانلود ویدیو از اینستاگرام با استفاده از instaloader"""
    # ایجاد نام فایل موقت
    output_dir = os.path.join(TEMP_DOWNLOAD_DIR, str(uuid.uuid4()))
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # بررسی کش
        cached_file = get_from_cache(f"{url}_{quality}")
        if cached_file:
            return cached_file
        
        # استخراج شناسه پست از URL
        shortcode = None
        
        if '/p/' in url:
            shortcode = url.split('/p/')[1].split('/')[0]
        elif '/reel/' in url:
            shortcode = url.split('/reel/')[1].split('/')[0]
        
        if not shortcode:
            logger.error(f"شناسه پست از URL استخراج نشد: {url}")
            return None
        
        # تنظیم instaloader
        L = instaloader.Instaloader(
            download_videos=True,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            filename_pattern='{profile}_{shortcode}'
        )
        
        # دانلود پست
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=output_dir)
        
        # پیدا کردن فایل ویدیویی دانلود شده
        video_files = [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith('.mp4')]
        
        if not video_files:
            logger.error(f"هیچ فایل ویدیویی دانلود نشد: {url}")
            return None
        
        # انتخاب فایل ویدیویی با بیشترین حجم (کیفیت بالاتر)
        video_file = max(video_files, key=os.path.getsize)
        
        # اگر کیفیت SD درخواست شده و حجم فایل بیش از حد مجاز است
        if quality == 'sd' and os.path.getsize(video_file) > MAX_TELEGRAM_FILE_SIZE:
            # تبدیل به کیفیت پایین‌تر
            compressed_file = os.path.join(output_dir, "compressed_video.mp4")
            ffmpeg_cmd = [
                'ffmpeg', '-i', video_file, 
                '-vf', 'scale=640:-2', 
                '-c:v', 'libx264', '-crf', '28', 
                '-c:a', 'aac', '-b:a', '128k', 
                compressed_file
            ]
            
            subprocess.run(ffmpeg_cmd, check=True)
            
            if os.path.exists(compressed_file):
                video_file = compressed_file
        
        # افزودن به کش
        result_file = os.path.join(TEMP_DOWNLOAD_DIR, f"instagram_{shortcode}_{quality}.mp4")
        shutil.copy2(video_file, result_file)
        add_to_cache(f"{url}_{quality}", result_file)
        
        # پاکسازی فایل‌های موقت
        shutil.rmtree(output_dir, ignore_errors=True)
        
        return result_file
    
    except instaloader.exceptions.InstaloaderException as e:
        logger.error(f"خطا در دانلود اینستاگرام: {str(e)}")
        # پاکسازی فایل‌های موقت
        shutil.rmtree(output_dir, ignore_errors=True)
        return None
    except Exception as e:
        logger.error(f"خطای عمومی: {str(e)}")
        # پاکسازی فایل‌های موقت
        shutil.rmtree(output_dir, ignore_errors=True)
        return None

"""
بخش 4: پردازش دانلود یوتیوب
"""

async def process_youtube_url(url: str, message_id: int, chat_id: int) -> Tuple[InlineKeyboardMarkup, str]:
    """پردازش URL یوتیوب و ارائه گزینه‌های دانلود"""
    # ایجاد کلید منحصر به فرد برای ذخیره‌سازی URL
    unique_key = f"{chat_id}_{message_id}"
    
    # ذخیره URL در مخزن پایدار
    persistent_url_storage[unique_key] = url
    
    # شناسایی نوع URL
    url_type = identify_url_type(url)
    
    # ایجاد گزینه‌های دانلود بر اساس نوع URL
    if url_type == 'youtube_shorts':
        keyboard = [
            [
                InlineKeyboardButton("🎬 دانلود ویدیو با کیفیت بالا", callback_data=f"youtube_1080_{unique_key}"),
            ],
            [
                InlineKeyboardButton("🎬 دانلود ویدیو با کیفیت متوسط", callback_data=f"youtube_720_{unique_key}"),
            ],
            [
                InlineKeyboardButton("🎬 دانلود ویدیو با کیفیت پایین", callback_data=f"youtube_480_{unique_key}"),
            ],
            [
                InlineKeyboardButton("🎵 دانلود فقط صدا", callback_data=f"youtube_audio_{unique_key}"),
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        return reply_markup, YOUTUBE_SHORTS_DOWNLOAD_OPTIONS
        
    elif url_type == 'youtube_playlist':
        keyboard = [
            [
                InlineKeyboardButton("🎬 دانلود اولین ویدیو (1080p)", callback_data=f"youtube_playlist_1080_{unique_key}"),
            ],
            [
                InlineKeyboardButton("🎬 دانلود اولین ویدیو (720p)", callback_data=f"youtube_playlist_720_{unique_key}"),
            ],
            [
                InlineKeyboardButton("🎬 دانلود اولین ویدیو (480p)", callback_data=f"youtube_playlist_480_{unique_key}"),
            ],
            [
                InlineKeyboardButton("🎵 دانلود صدای اولین ویدیو", callback_data=f"youtube_playlist_audio_{unique_key}"),
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        return reply_markup, YOUTUBE_PLAYLIST_DOWNLOAD_OPTIONS
        
    else:  # youtube_video یا موارد دیگر
        keyboard = [
            [
                InlineKeyboardButton("🎬 دانلود با کیفیت 1080p", callback_data=f"youtube_1080_{unique_key}"),
            ],
            [
                InlineKeyboardButton("🎬 دانلود با کیفیت 720p", callback_data=f"youtube_720_{unique_key}"),
            ],
            [
                InlineKeyboardButton("🎬 دانلود با کیفیت 480p", callback_data=f"youtube_480_{unique_key}"),
            ],
            [
                InlineKeyboardButton("🎬 دانلود با کیفیت 360p", callback_data=f"youtube_360_{unique_key}"),
            ],
            [
                InlineKeyboardButton("🎬 دانلود با کیفیت 240p", callback_data=f"youtube_240_{unique_key}"),
            ],
            [
                InlineKeyboardButton("🎵 دانلود فقط صدا", callback_data=f"youtube_audio_{unique_key}"),
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        return reply_markup, YOUTUBE_DOWNLOAD_OPTIONS

async def download_youtube_video(url: str, quality: str = '720') -> Optional[str]:
    """دانلود ویدیو از یوتیوب با استفاده از yt-dlp"""
    # ایجاد نام فایل موقت
    output_dir = os.path.join(TEMP_DOWNLOAD_DIR, str(uuid.uuid4()))
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # بررسی کش
        cached_file = get_from_cache(f"{url}_{quality}")
        if cached_file:
            return cached_file
        
        # ایجاد فایل کوکی برای یوتیوب
        cookie_file = create_youtube_cookies()
        
        # فایل خروجی
        output_file = os.path.join(output_dir, "youtube_video.%(ext)s")
        
        # تنظیم گزینه‌های yt-dlp بر اساس کیفیت
        if quality == 'audio':
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': output_file,
                'cookiefile': cookie_file,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': True,
                'nocheckcertificate': True,
                'prefer_insecure': True,
                'user_agent': USER_AGENT,
                'noplaylist': True
            }
        else:
            # تعیین فرمت ویدیویی بر اساس کیفیت درخواستی
            format_spec = f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}]/best'
            
            ydl_opts = {
                'format': format_spec,
                'outtmpl': output_file,
                'cookiefile': cookie_file,
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': True,
                'nocheckcertificate': True,
                'prefer_insecure': True,
                'user_agent': USER_AGENT,
                'noplaylist': True,
                'merge_output_format': 'mp4'
            }
        
        # دانلود ویدیو
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # پیدا کردن فایل دانلود شده
        downloaded_files = os.listdir(output_dir)
        
        if not downloaded_files:
            logger.error(f"هیچ فایلی دانلود نشد: {url}")
            return None
        
        downloaded_file = os.path.join(output_dir, downloaded_files[0])
        
        # افزودن به کش
        file_extension = os.path.splitext(downloaded_file)[1]
        video_id = url.split('v=')[-1].split('&')[0] if 'v=' in url else url.split('/')[-1]
        result_file = os.path.join(TEMP_DOWNLOAD_DIR, f"youtube_{video_id}_{quality}{file_extension}")
        shutil.copy2(downloaded_file, result_file)
        add_to_cache(f"{url}_{quality}", result_file)
        
        # پاکسازی فایل‌های موقت
        shutil.rmtree(output_dir, ignore_errors=True)
        os.remove(cookie_file) if os.path.exists(cookie_file) else None
        
        return result_file
    
    except Exception as e:
        logger.error(f"خطا در دانلود یوتیوب: {str(e)}")
        # پاکسازی فایل‌های موقت
        shutil.rmtree(output_dir, ignore_errors=True)
        return None

async def download_youtube_playlist_first_video(url: str, quality: str = '720') -> Optional[str]:
    """دانلود اولین ویدیو از پلی‌لیست یوتیوب"""
    # ایجاد نام فایل موقت
    output_dir = os.path.join(TEMP_DOWNLOAD_DIR, str(uuid.uuid4()))
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # بررسی کش
        cached_file = get_from_cache(f"{url}_playlist_{quality}")
        if cached_file:
            return cached_file
        
        # ایجاد فایل کوکی برای یوتیوب
        cookie_file = create_youtube_cookies()
        
        # اول، استخراج لینک اولین ویدیو از پلی‌لیست
        with yt_dlp.YoutubeDL({'quiet': True, 'flat_playlist': True, 'cookiefile': cookie_file}) as ydl:
            info = ydl.extract_info(url, download=False)
            entries = info.get('entries', [])
            
            if not entries:
                logger.error(f"هیچ ویدیویی در پلی‌لیست یافت نشد: {url}")
                return None
                
            # گرفتن اطلاعات اولین ویدیو
            first_video_url = entries[0]['url']
        
        # حالا دانلود اولین ویدیو
        return await download_youtube_video(first_video_url, quality)
    
    except Exception as e:
        logger.error(f"خطا در دانلود پلی‌لیست یوتیوب: {str(e)}")
        # پاکسازی فایل‌های موقت
        shutil.rmtree(output_dir, ignore_errors=True)
        return None

"""
بخش 5: رابط تلگرام
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دستور شروع، خوش‌آمدگویی به کاربر"""
    await update.message.reply_text(
        START_MESSAGE,
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دستور راهنما"""
    await update.message.reply_text(HELP_MESSAGE)

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دستور درباره"""
    await update.message.reply_text(ABOUT_MESSAGE)

async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پردازش پیام دریافتی از کاربر"""
    message = update.message
    chat_id = message.chat_id
    message_id = message.message_id
    text = message.text
    
    # استخراج URL از پیام
    urls = extract_urls(text)
    
    if not urls:
        await message.reply_text(ERROR_MESSAGES["url_not_found"])
        return
    
    # استفاده از اولین URL
    url = urls[0]
    
    # شناسایی نوع URL
    url_type = identify_url_type(url)
    
    # پاسخ اولیه به کاربر
    processing_message = await message.reply_text(STATUS_MESSAGES["processing"])
    
    try:
        # پردازش URL بر اساس نوع آن
        if url_type.startswith('instagram'):
            reply_markup, options_text = await process_instagram_url(url, message_id, chat_id)
            await processing_message.edit_text(options_text, reply_markup=reply_markup)
        
        elif url_type.startswith('youtube'):
            reply_markup, options_text = await process_youtube_url(url, message_id, chat_id)
            await processing_message.edit_text(options_text, reply_markup=reply_markup)
        
        else:
            await processing_message.edit_text(ERROR_MESSAGES["unsupported_url"])
    
    except Exception as e:
        logger.error(f"خطا در پردازش پیام: {str(e)}")
        await processing_message.edit_text(ERROR_MESSAGES["generic_error"])

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پردازش دکمه‌های فشرده شده توسط کاربر"""
    # دریافت اطلاعات دکمه و کاربر
    query = update.callback_query
    chat_id = query.message.chat_id
    message_id = query.message.message_id
    
    # ثبت کلیک دکمه اخیر
    recent_button_clicks[(chat_id, message_id)] = query.data
    
    # پردازش داده‌های دکمه
    callback_data = query.data
    
    # پاسخ اولیه به فشردن دکمه
    await query.answer("در حال پردازش درخواست شما...")
    
    try:
        # استخراج کلید URL از داده‌های دکمه
        url_key = callback_data.split('_')[-1]
        
        # بازیابی URL از مخزن پایدار
        if url_key not in persistent_url_storage:
            await query.message.edit_text(ERROR_MESSAGES["url_expired"])
            return
            
        url = persistent_url_storage[url_key]
        
        # تشخیص نوع درخواست
        if callback_data.startswith('instagram_hd_'):
            # دانلود ویدیوی اینستاگرام با کیفیت بالا
            await query.message.edit_text(STATUS_MESSAGES["downloading"])
            
            video_file = await download_instagram_video(url, 'hd')
            
            if not video_file:
                await query.message.edit_text(ERROR_MESSAGES["download_failed"])
                return
                
            # ارسال ویدیو
            await query.message.edit_text(STATUS_MESSAGES["uploading"])
            
            try:
                with open(video_file, 'rb') as f:
                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=f,
                        caption=f"📷 [Instagram]({url}) | کیفیت: HD",
                        parse_mode='Markdown'
                    )
                await query.message.edit_text(STATUS_MESSAGES["complete"])
            except Exception as e:
                logger.error(f"خطا در ارسال ویدیو: {str(e)}")
                if "File too large" in str(e):
                    await query.message.edit_text(ERROR_MESSAGES["file_too_large"])
                else:
                    await query.message.edit_text(ERROR_MESSAGES["telegram_upload"])
        
        elif callback_data.startswith('instagram_sd_'):
            # دانلود ویدیوی اینستاگرام با کیفیت معمولی
            await query.message.edit_text(STATUS_MESSAGES["downloading"])
            
            video_file = await download_instagram_video(url, 'sd')
            
            if not video_file:
                await query.message.edit_text(ERROR_MESSAGES["download_failed"])
                return
                
            # ارسال ویدیو
            await query.message.edit_text(STATUS_MESSAGES["uploading"])
            
            try:
                with open(video_file, 'rb') as f:
                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=f,
                        caption=f"📷 [Instagram]({url}) | کیفیت: SD",
                        parse_mode='Markdown'
                    )
                await query.message.edit_text(STATUS_MESSAGES["complete"])
            except Exception as e:
                logger.error(f"خطا در ارسال ویدیو: {str(e)}")
                if "File too large" in str(e):
                    await query.message.edit_text(ERROR_MESSAGES["file_too_large"])
                else:
                    await query.message.edit_text(ERROR_MESSAGES["telegram_upload"])
        
        elif callback_data.startswith('instagram_audio_'):
            # دانلود فقط صدای ویدیوی اینستاگرام
            await query.message.edit_text(STATUS_MESSAGES["downloading_audio"])
            
            # ابتدا ویدیو را دانلود می‌کنیم
            video_file = await download_instagram_video(url, 'sd')
            
            if not video_file:
                await query.message.edit_text(ERROR_MESSAGES["download_failed"])
                return
            
            # سپس صدا را استخراج می‌کنیم
            await query.message.edit_text(STATUS_MESSAGES["processing_audio"])
            
            audio_file = extract_audio(video_file, 'mp3', '192k')
            
            if not audio_file:
                await query.message.edit_text(ERROR_MESSAGES["download_failed"])
                return
            
            # ارسال فایل صوتی
            await query.message.edit_text(STATUS_MESSAGES["uploading"])
            
            try:
                with open(audio_file, 'rb') as f:
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=f,
                        caption=f"🎵 [Instagram Audio]({url})",
                        parse_mode='Markdown'
                    )
                await query.message.edit_text(STATUS_MESSAGES["complete"])
            except Exception as e:
                logger.error(f"خطا در ارسال فایل صوتی: {str(e)}")
                await query.message.edit_text(ERROR_MESSAGES["telegram_upload"])
        
        elif callback_data.startswith('youtube_'):
            # پردازش دانلود یوتیوب
            
            # استخراج کیفیت از داده‌های دکمه
            if 'youtube_audio_' in callback_data:
                quality = 'audio'
            elif 'youtube_playlist_' in callback_data:
                # استخراج کیفیت از دکمه‌های پلی‌لیست
                quality = callback_data.split('_')[2]
                await query.message.edit_text(STATUS_MESSAGES["downloading"])
                
                video_file = await download_youtube_playlist_first_video(url, quality)
                
                if not video_file:
                    await query.message.edit_text(ERROR_MESSAGES["download_failed"])
                    return
                
                # اگر درخواست صوتی باشد
                if quality == 'audio':
                    await query.message.edit_text(STATUS_MESSAGES["uploading"])
                    
                    try:
                        with open(video_file, 'rb') as f:
                            await context.bot.send_audio(
                                chat_id=chat_id,
                                audio=f,
                                caption=f"🎵 [YouTube Playlist Audio]({url})",
                                parse_mode='Markdown'
                            )
                        await query.message.edit_text(STATUS_MESSAGES["complete"])
                    except Exception as e:
                        logger.error(f"خطا در ارسال فایل صوتی: {str(e)}")
                        await query.message.edit_text(ERROR_MESSAGES["telegram_upload"])
                else:
                    # ارسال ویدیو
                    await query.message.edit_text(STATUS_MESSAGES["uploading"])
                    
                    try:
                        with open(video_file, 'rb') as f:
                            await context.bot.send_video(
                                chat_id=chat_id,
                                video=f,
                                caption=f"📺 [YouTube Playlist]({url}) | کیفیت: {quality}p",
                                parse_mode='Markdown'
                            )
                        await query.message.edit_text(STATUS_MESSAGES["complete"])
                    except Exception as e:
                        logger.error(f"خطا در ارسال ویدیو: {str(e)}")
                        if "File too large" in str(e):
                            await query.message.edit_text(ERROR_MESSAGES["file_too_large"])
                        else:
                            await query.message.edit_text(ERROR_MESSAGES["telegram_upload"])
                
                return
            else:
                quality = callback_data.split('_')[1]
            
            # دانلود ویدیوی یوتیوب
            await query.message.edit_text(STATUS_MESSAGES["downloading"])
            
            video_file = await download_youtube_video(url, quality)
            
            if not video_file:
                await query.message.edit_text(ERROR_MESSAGES["download_failed"])
                return
            
            # اگر درخواست صوتی باشد
            if quality == 'audio':
                await query.message.edit_text(STATUS_MESSAGES["uploading"])
                
                try:
                    with open(video_file, 'rb') as f:
                        await context.bot.send_audio(
                            chat_id=chat_id,
                            audio=f,
                            caption=f"🎵 [YouTube Audio]({url})",
                            parse_mode='Markdown'
                        )
                    await query.message.edit_text(STATUS_MESSAGES["complete"])
                except Exception as e:
                    logger.error(f"خطا در ارسال فایل صوتی: {str(e)}")
                    await query.message.edit_text(ERROR_MESSAGES["telegram_upload"])
            else:
                # ارسال ویدیو
                await query.message.edit_text(STATUS_MESSAGES["uploading"])
                
                try:
                    with open(video_file, 'rb') as f:
                        await context.bot.send_video(
                            chat_id=chat_id,
                            video=f,
                            caption=f"📺 [YouTube]({url}) | کیفیت: {quality}p",
                            parse_mode='Markdown'
                        )
                    await query.message.edit_text(STATUS_MESSAGES["complete"])
                except Exception as e:
                    logger.error(f"خطا در ارسال ویدیو: {str(e)}")
                    if "File too large" in str(e):
                        await query.message.edit_text(ERROR_MESSAGES["file_too_large"])
                    else:
                        await query.message.edit_text(ERROR_MESSAGES["telegram_upload"])
        
        else:
            await query.message.edit_text(ERROR_MESSAGES["generic_error"])
    
    except Exception as e:
        logger.error(f"خطا در پردازش دکمه: {str(e)}\n{traceback.format_exc()}")
        await query.message.edit_text(ERROR_MESSAGES["generic_error"])

"""
بخش 6: پاکسازی فایل‌های موقت
"""

async def cleanup_temp_files() -> None:
    """پاکسازی فایل‌های موقت قدیمی"""
    try:
        # بررسی همه فایل‌ها در دایرکتوری دانلود
        now = time.time()
        for filename in os.listdir(TEMP_DOWNLOAD_DIR):
            file_path = os.path.join(TEMP_DOWNLOAD_DIR, filename)
            
            # اگر فایل است (نه دایرکتوری) و قدیمی است
            if os.path.isfile(file_path) and now - os.path.getmtime(file_path) > CACHE_TIMEOUT:
                os.remove(file_path)
                logger.info(f"فایل موقت قدیمی پاک شد: {file_path}")
    except Exception as e:
        logger.error(f"خطا در پاکسازی فایل‌های موقت: {str(e)}")

"""
بخش 7: تست‌ها
"""

def run_tests():
    """اجرای تست‌های خودکار"""
    print("اجرای تست‌های خودکار...")
    
    # تست تشخیص URL
    test_urls = [
        "https://www.instagram.com/p/ABC123/",
        "https://www.instagram.com/reel/DEF456/",
        "https://www.youtube.com/watch?v=GHI789",
        "https://youtu.be/JKL012",
        "https://www.youtube.com/shorts/MNO345",
        "https://www.youtube.com/playlist?list=PLQ678",
    ]
    
    for url in test_urls:
        url_type = identify_url_type(url)
        print(f"URL: {url} -> نوع: {url_type}")
    
    # تست استخراج URL
    test_texts = [
        "لینک اینستاگرام من: https://www.instagram.com/p/ABC123/ بفرمایید",
        "یوتیوب: https://www.youtube.com/watch?v=GHI789 و اینستاگرام: https://www.instagram.com/reel/DEF456/",
        "این متن هیچ لینکی ندارد"
    ]
    
    for text in test_texts:
        urls = extract_urls(text)
        print(f"متن: {text[:30]}... -> URLها: {urls}")
    
    print("تست‌ها با موفقیت انجام شد.")

"""
بخش 8: تابع اصلی
"""

def main() -> None:
    """تابع اصلی برنامه"""
    # پارس آرگومان‌های خط فرمان
    parser = argparse.ArgumentParser(description="ربات تلگرام برای دانلود ویدیوهای اینستاگرام و یوتیوب")
    parser.add_argument("--skip-tests", action="store_true", help="رد کردن اجرای تست‌ها")
    args = parser.parse_args()
    
    # اجرای تست‌ها (اگر درخواست نشده باشد که رد شوند)
    if not args.skip_tests:
        run_tests()
    
    # دریافت توکن ربات از متغیرهای محیطی
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    
    if not token:
        print("خطا: متغیر محیطی TELEGRAM_BOT_TOKEN تنظیم نشده است.")
        print("لطفاً با دستور زیر آن را تنظیم کنید:")
        print("export TELEGRAM_BOT_TOKEN=<your_token_here>")
        exit(1)
    
    # ایجاد و راه‌اندازی برنامه تلگرام
    application = Application.builder().token(token).build()
    
    # ثبت هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_message))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # اجرای زمانبندی برای پاکسازی فایل‌های موقت
    asyncio.create_task(cleanup_temp_files())
    
    # شروع پردازش درخواست‌ها
    print("ربات در حال اجراست...")
    application.run_polling()

if __name__ == "__main__":
    main()

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
def get_ffmpeg_path():
    """تشخیص خودکار مسیر ffmpeg براساس محیط اجرا"""
    # مسیر اصلی در Replit
    replit_path = '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg'
    if os.path.exists(replit_path):
        return replit_path
    
    # در محیط Railway یا سایر محیط‌های لینوکس
    try:
        ffmpeg_path = subprocess.check_output(['which', 'ffmpeg']).decode('utf-8').strip()
        if ffmpeg_path:
            return ffmpeg_path
    except:
        pass
    
    return 'ffmpeg'  # استفاده از ffmpeg موجود در مسیر سیستم

def get_ffprobe_path():
    """تشخیص خودکار مسیر ffprobe براساس محیط اجرا"""
    # مسیر اصلی در Replit
    replit_path = '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffprobe'
    if os.path.exists(replit_path):
        return replit_path
    
    # در محیط Railway یا سایر محیط‌های لینوکس
    try:
        ffprobe_path = subprocess.check_output(['which', 'ffprobe']).decode('utf-8').strip()
        if ffprobe_path:
            return ffprobe_path
    except:
        pass
    
    return 'ffprobe'  # استفاده از ffprobe موجود در مسیر سیستم

FFMPEG_PATH = get_ffmpeg_path()
FFPROBE_PATH = get_ffprobe_path()

# لاگ کردن مسیرهای تشخیص داده شده
logging.info(f"مسیر ffmpeg: {FFMPEG_PATH}")
logging.info(f"مسیر ffprobe: {FFPROBE_PATH}")

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
DEFAULT_FFMPEG_PATH = FFMPEG_PATH  # استفاده از مسیر تشخیص داده شده

# تعیین کیفیت‌های استاندارد ویدیو با گزینه‌های پیشرفته و بهینه‌سازی شده برای تناسب حجم با کیفیت
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
        'ffmpeg_options': ['-vf', 'scale=-2:1080', '-b:v', '6000k'],
        'format_note': 'فول اچ‌دی',
        'priority': 2
    },
    '720p': {
        'height': 720, 
        'width': 1280, 
        'display_name': 'کیفیت HD (720p)', 
        'ffmpeg_options': ['-vf', 'scale=-2:720', '-b:v', '3500k'],
        'format_note': 'اچ‌دی',
        'priority': 3
    },
    '480p': {
        'height': 480, 
        'width': 854, 
        'display_name': 'کیفیت متوسط (480p)', 
        'ffmpeg_options': ['-vf', 'scale=-2:480', '-b:v', '2000k'],
        'format_note': 'کیفیت متوسط',
        'priority': 4
    },
    'medium': {  # اضافه کردن کیفیت متوسط برای سازگاری با اینستاگرام
        'height': 480, 
        'width': 854, 
        'display_name': 'کیفیت متوسط (480p)', 
        'ffmpeg_options': ['-vf', 'scale=-2:480', '-b:v', '2000k'],
        'format_note': 'کیفیت متوسط',
        'priority': 4
    },
    '360p': {
        'height': 360, 
        'width': 640, 
        'display_name': 'کیفیت پایین (360p)', 
        'ffmpeg_options': ['-vf', 'scale=-2:360', '-b:v', '1200k'],
        'format_note': 'کیفیت پایین',
        'priority': 5
    },
    '240p': {
        'height': 240, 
        'width': 426, 
        'display_name': 'کیفیت خیلی پایین (240p)', 
        'ffmpeg_options': ['-vf', 'scale=-2:240', '-b:v', '700k'],
        'format_note': 'کیفیت خیلی پایین',
        'priority': 6
    },
    'low': {  # اضافه کردن کیفیت پایین برای سازگاری با اینستاگرام
        'height': 240, 
        'width': 426, 
        'display_name': 'کیفیت پایین (240p)', 
        'ffmpeg_options': ['-vf', 'scale=-2:240', '-b:v', '700k'],
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
    'ffmpeg_location': FFMPEG_PATH  # استفاده از مسیر تشخیص داده شده
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
                f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/'
                f'best[height={height}][ext=mp4]/best[height<={height}][ext=mp4]/best'
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
                'ffmpeg_location': FFMPEG_PATH,  # تنظیم مسیر تشخیص داده شده خودکار
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
                    'format_sort': ['res', 'ext:mp4:m4a'],
                    'video_multistreams': True,
                    'prefer_native_hls': True,
                    'hls_prefer_native': True,
                    'prefer_ffmpeg': True,
                    'noplaylist': True
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
                    # استراتژی چند لایه برای انتخاب بهترین تطابق با تمرکز دقیق بر کیفیت درخواستی
                    if height == 720:  # تنظیمات ویژه برای 720p
                        format_spec = (
                            f'best[height=720][ext=mp4]/'
                            f'best[height<=720][height>=600][ext=mp4]/'
                            f'best[height<=720][ext=mp4]/'
                            f'worst[height>=720][ext=mp4]/'
                            f'best[height<=720]/'
                            f'best[ext=mp4]/best'
                        )
                    else:
                        format_spec = (
                            f'best[height={height}][ext=mp4]/'
                            f'best[height<={height}][height>={max(height-50, 120)}][ext=mp4]/'
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
                    instagram_ffmpeg_options = ['-b:v', '2000k', '-maxrate', '2500k', '-bufsize', '4000k']
                elif quality == 'low':
                    # محدود کردن بیت‌ریت برای کیفیت پایین
                    instagram_ffmpeg_options = ['-b:v', '700k', '-maxrate', '900k', '-bufsize', '1600k']
                    
                # تنظیمات پیشرفته برای کنترل کیفیت
                ydl_opts.update({
                    'format': format_spec,
                    'merge_output_format': 'mp4',  # اطمینان از خروجی MP4
                    # تنظیمات اضافی برای تضمین دریافت ویدیو
                    'format_sort': ['res', 'ext:mp4:m4a'],
                    'video_multistreams': True,
                    'prefer_native_hls': True
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
                    FFMPEG_PATH,  # استفاده از مسیر تشخیص داده شده خودکار
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
    تبدیل کیفیت ویدیو با استفاده از ffmpeg (روش فوق پیشرفته با چندین بهینه‌سازی)
    
    Args:
        video_path: مسیر فایل ویدیویی اصلی
        quality: کیفیت هدف (1080p, 720p, 480p, 360p, 240p, audio)
        is_audio_request: آیا خروجی باید فایل صوتی باشد
        
    Returns:
        مسیر فایل تبدیل شده یا None در صورت خطا
    """
    # اطمینان از اینکه مسیر فایل معتبر است
    import os
    import subprocess
    import logging
    
    logger = logging.getLogger(__name__)
    
    if not video_path or not os.path.exists(video_path):
        logger.error(f"مسیر فایل ویدیویی نامعتبر است: {video_path}")
        return None
        
    # اطمینان از اینکه کیفیت معتبر است
    if not quality:
        quality = "720p"  # کیفیت پیش‌فرض
    import logging
    import time
    import multiprocessing
    from concurrent.futures import ThreadPoolExecutor

    logger = logging.getLogger(__name__)
    
    # بررسی وجود فایل ورودی
    if not os.path.exists(video_path):
        logger.error(f"فایل ویدیویی یافت نشد: {video_path}")
        return None
        
    try:
        # زمان‌سنجی برای ارزیابی بهبود سرعت
        start_time = time.time()
        
        # تصمیم‌گیری صریح برای استخراج صدا با اجرای چند هسته‌ای
        if is_audio_request or quality == "audio":
            logger.info(f"درخواست استخراج صدا از ویدیو با روش چند هسته‌ای: {video_path}")
            
            with ThreadPoolExecutor(max_workers=2) as executor:
                future = executor.submit(extract_audio_from_video, video_path)
                result = future.result()
                
            conversion_time = time.time() - start_time
            logger.info(f"زمان استخراج صدا: {conversion_time:.2f} ثانیه")
            return result
        
        # ⚠️ اطمینان از درخواست ویدیویی
        logger.info(f"درخواست تبدیل کیفیت ویدیو به {quality} با روش بهینه‌سازی شده")
        
        # تعیین ارتفاع برای هر کیفیت با پشتیبانی از انواع فرمت‌ها
        quality_heights = {
            "1080p": 1080, 
            "720p": 720, 
            "480p": 480, 
            "360p": 360, 
            "240p": 240,
            "medium": 480,
            "low": 240,
            # افزودن پشتیبانی حداکثری از انواع فرمت‌ها
            "1080": 1080,
            "720": 720,
            "480": 480,
            "360": 360,
            "240": 240,
            "hd": 720,
            "fullhd": 1080
        }
        
        # استفاده از پردازش چند هسته‌ای برای چند برابر کردن سرعت
        # تنظیم تعداد هسته‌ها برای کارایی بیشتر
        cpu_count = multiprocessing.cpu_count()
        thread_count = min(cpu_count, 8)  # حداکثر 8 هسته
        
        logger.info(f"استفاده از {thread_count} هسته پردازشی برای تبدیل ویدیو")
        
        # فورس کردن تبدیل کیفیت با مکانیزم پیشرفته
        force_conversion = True
        
        # تبدیل quality به رشته اگر عدد باشد
        if isinstance(quality, (int, float)):
            logger.info(f"تبدیل کیفیت عددی {quality} به رشته")
            quality = f"{int(quality)}p"
            
        # رشته کردن کیفیت برای اطمینان
        quality = str(quality)
        
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
                force_conversion = True  # فورس تبدیل کیفیت برای 360p
            elif "240" in quality or "very" in quality.lower() or "lowest" in quality.lower():
                logger.info(f"کیفیت {quality} به 240p نگاشت شد.")
                quality = "240p"
                force_conversion = True  # فورس تبدیل کیفیت برای 240p
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
        
        # بررسی وجود فایل از قبل (فقط در صورتی که فورس تبدیل نباشد)
        if not force_conversion and os.path.exists(converted_file):
            logger.info(f"فایل تبدیل شده از قبل وجود دارد: {converted_file}")
            return converted_file
            
        # اگر فورس تبدیل باشد و فایل از قبل وجود داشته باشد، آن را حذف می‌کنیم
        if force_conversion and os.path.exists(converted_file):
            logger.info(f"حذف فایل قبلی برای تبدیل اجباری: {converted_file}")
            try:
                os.remove(converted_file)
            except Exception as e:
                logger.warning(f"خطا در حذف فایل قبلی: {e}")
        
        # لیست روش‌های مختلف برای تبدیل فایل
        conversion_methods = [
            method_ffmpeg_advanced,
            method_ffmpeg_simple,
            method_ffmpeg_native,
            method_fallback
        ]
        
        # متغیر برای ذخیره خطاها به منظور گزارش
        all_errors = []
        
        # تلاش هر یک از روش‌ها به ترتیب
        for method_index, conversion_method in enumerate(conversion_methods):
            try:
                logger.info(f"تلاش تبدیل کیفیت با روش {method_index + 1}: {conversion_method.__name__}")
                result_file = conversion_method(video_path, quality, target_height, converted_file)
                
                if result_file and os.path.exists(result_file) and os.path.getsize(result_file) > 10000:
                    logger.info(f"روش {method_index + 1} ({conversion_method.__name__}) موفق: {result_file}")
                    return result_file
                else:
                    logger.warning(f"روش {method_index + 1} ({conversion_method.__name__}) ناموفق بود")
                    all_errors.append(f"روش {method_index + 1} ناموفق")
            except Exception as e:
                error_msg = f"خطا در روش {method_index + 1} ({conversion_method.__name__}): {str(e)}"
                logger.error(error_msg)
                all_errors.append(error_msg)
                import traceback
                logger.error(traceback.format_exc())
                continue
        
        # اگر به اینجا رسیدیم، همه روش‌ها ناموفق بوده‌اند
        logger.error(f"همه روش‌های تبدیل کیفیت ناموفق بودند: {', '.join(all_errors)}")
        return video_path  # برگرداندن فایل اصلی
    
    except Exception as e:
        logger.error(f"خطا در تبدیل کیفیت ویدیو: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        # در صورت خطای کلی، فایل اصلی را برمی‌گردانیم
        return video_path

def method_ffmpeg_advanced(video_path: str, quality: str, target_height: int, output_path: str) -> Optional[str]:
    """روش پیشرفته با استفاده از ffmpeg با تنظیمات بهینه برای کیفیت و سرعت"""
    
    logger.info(f"روش پیشرفته ffmpeg برای تبدیل به کیفیت {quality}")
    
    # بررسی ارتفاع فعلی ویدیو
    ffprobe_cmd = [
        FFPROBE_PATH,  # استفاده از مسیر تشخیص داده شده
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
    
    # محاسبه عرض جدید با حفظ نسبت تصویر
    # برای کیفیت‌های 360p و 240p، از روش ساده‌تر استفاده می‌کنیم
    if quality in ["360p", "240p"]:
        scale_filter = f"scale=-2:{target_height}"
    else:
        scale_filter = f'scale=-2:{target_height}:force_original_aspect_ratio=decrease,format=yuv420p'
    
    # بیت‌ریت هوشمندانه برای هر کیفیت - تنظیم شده برای اطمینان از تناسب حجم با کیفیت
    video_bitrates = {
        "1080p": "6000k",  # بیت‌ریت بالا برای 1080p (کاهش نسبت به قبل برای حجم منطقی‌تر)
        "720p": "3500k",   # بیت‌ریت متوسط رو به بالا برای 720p (کاهش برای حل مشکل)
        "480p": "2000k",   # بیت‌ریت متوسط
        "360p": "1200k",   # بیت‌ریت متوسط رو به پایین
        "240p": "700k"     # بیت‌ریت کم
    }
    
    video_bitrate = video_bitrates.get(quality, "3000k")  # بیت‌ریت پیش‌فرض کمتر
    
    # دستور ffmpeg فوق‌بهینه با پارامترهای تنظیم شده برای سرعت چندبرابری
    cmd = [
        FFMPEG_PATH, 
        '-hwaccel', 'auto',    # استفاده خودکار از شتاب‌دهنده سخت‌افزاری اگر موجود باشد
        '-i', video_path,
        '-c:v', 'libx264',     # کدک ویدیو
        '-c:a', 'aac',         # کدک صدا
        '-b:a', '96k',         # کاهش بیت‌ریت صدا برای سرعت بیشتر
        '-ac', '2',            # استریو (بهینه‌ترین حالت)
        '-ar', '44100',        # نرخ نمونه‌برداری استاندارد
        '-b:v', video_bitrate, # بیت‌ریت ویدیو
        '-vf', scale_filter,   # فیلتر مقیاس‌بندی 
        '-preset', 'ultrafast', # سریع‌ترین حالت انکود
        '-tune', 'zerolatency', # بهینه‌سازی برای تأخیر صفر
        '-crf', '30',          # کیفیت پایین‌تر برای سرعت بسیار بیشتر
        '-g', '48',            # فاصله بین I-frames (افزایش برای سرعت بیشتر)
        '-sc_threshold', '0',  # غیرفعال کردن تغییر صحنه برای سرعت بیشتر
        '-max_muxing_queue_size', '9999',
        '-movflags', '+faststart',
        '-threads', '8',       # افزایش تعداد هسته‌های پردازشی
        '-tile-columns', '6',  # بهینه‌سازی برای پردازش موازی
        '-frame-parallel', '1', # پردازش فریم‌های موازی
        '-deadline', 'realtime', # حداکثر سرعت
        '-cpu-used', '8',      # استفاده حداکثری از CPU
        '-static-thresh', '0', # حد آستانه استاتیک
        '-drop-threshold', '30', # امکان از دست دادن برخی فریم‌ها
        '-rc_lookahead', '0',  # حذف کامل look-ahead برای سرعت بیشتر
        '-lag-in-frames', '0', # حذف تاخیر در فریم‌ها
        '-row-mt', '1',        # چند رشته‌ای در سطح ردیف
        '-use_timeline', '0',  # عدم استفاده از timeline
        '-vsync', '0',        # حذف همگام‌سازی فریم
        '-f', 'mp4',           # فرمت خروجی
        '-y',                  # جایگزینی فایل موجود
        '-loglevel', 'error',  # فقط نمایش خطاها
        output_path
    ]
    
    logger.info(f"در حال تبدیل ویدیو به کیفیت {quality} با روش پیشرفته...")
    logger.debug(f"دستور FFMPEG: {' '.join(cmd)}")
    
    # اجرای دستور
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # بررسی نتیجه
    if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
        logger.info(f"تبدیل کیفیت به روش پیشرفته موفق: {output_path}")
        return output_path
    else:
        logger.error(f"خطا در تبدیل کیفیت به روش پیشرفته: {result.stderr[:300]}...")
        return None

def method_ffmpeg_simple(video_path: str, quality: str, target_height: int, output_path: str) -> Optional[str]:
    """روش ساده با استفاده از ffmpeg با تنظیمات ساده‌تر (احتمال سازگاری بالاتر)"""
    
    # مسیر فایل خروجی متفاوت برای جلوگیری از تداخل
    file_dir = os.path.dirname(output_path)
    file_name, file_ext = os.path.splitext(os.path.basename(output_path))
    # اضافه کردن پسوند simple برای تمایز از روش اصلی
    simple_output_path = os.path.join(file_dir, f"{file_name}_simple{file_ext}")
    
    logger.info(f"روش ساده ffmpeg برای تبدیل به کیفیت {quality}")
    
    # بیت‌ریت هوشمندانه برای هر کیفیت - تنظیم شده برای اطمینان از تناسب حجم با کیفیت
    video_bitrates = {
        "1080p": "6000k",  # بیت‌ریت بالا برای 1080p (کاهش نسبت به قبل برای حجم منطقی‌تر)
        "720p": "3500k",   # بیت‌ریت متوسط رو به بالا برای 720p (کاهش برای حل مشکل)
        "480p": "2000k",   # بیت‌ریت متوسط
        "360p": "1200k",   # بیت‌ریت متوسط رو به پایین
        "240p": "700k"     # بیت‌ریت کم
    }
    
    video_bitrate = video_bitrates.get(quality, "3000k")  # بیت‌ریت پیش‌فرض کمتر
    
    # دستور ffmpeg ساده‌تر با تنظیمات بهینه شده برای سرعت
    cmd = [
        FFMPEG_PATH, 
        '-i', video_path,
        '-vf', f'scale=-2:{target_height}',  # فیلتر مقیاس‌بندی بسیار ساده
        '-c:v', 'libx264',             # کدک ویدیو (سازگاری بالا)
        '-b:v', video_bitrate,         # بیت‌ریت ویدیو
        '-c:a', 'copy',                # فقط کپی صدا
        '-pix_fmt', 'yuv420p',         # فرمت پیکسل استاندارد
        '-preset', 'ultrafast',        # سرعت فوق‌العاده بالا
        '-tune', 'fastdecode',         # بهینه‌سازی برای دیکود سریع
        '-threads', '4',               # استفاده از 4 هسته پردازشی
        '-deadline', 'realtime',       # حالت سریع برای انکود
        '-rc_lookahead', '10',         # کاهش look-ahead برای سرعت بیشتر
        '-bufsize', '10M',             # اندازه بافر برای سرعت بالاتر
        '-maxrate', video_bitrate,     # حداکثر بیت‌ریت
        '-y',                          # جایگزینی فایل موجود
        simple_output_path
    ]
    
    logger.info(f"در حال تبدیل ویدیو به کیفیت {quality} با روش ساده...")
    logger.debug(f"دستور FFMPEG: {' '.join(cmd)}")
    
    # اجرای دستور
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # بررسی نتیجه
    if result.returncode == 0 and os.path.exists(simple_output_path) and os.path.getsize(simple_output_path) > 10000:
        logger.info(f"تبدیل کیفیت به روش ساده موفق: {simple_output_path}")
        
        # کپی به مسیر اصلی
        try:
            import shutil
            shutil.copy2(simple_output_path, output_path)
            logger.info(f"فایل از {simple_output_path} به {output_path} کپی شد")
            
            # حذف فایل موقت
            try:
                os.remove(simple_output_path)
            except:
                pass
                
            return output_path
        except Exception as e:
            logger.error(f"خطا در کپی فایل: {e}")
            return simple_output_path
    else:
        logger.error(f"خطا در تبدیل کیفیت به روش ساده: {result.stderr[:300]}...")
        return None

def method_ffmpeg_native(video_path: str, quality: str, target_height: int, output_path: str) -> Optional[str]:
    """روش با استفاده از فقط کدگذاری صوتی و تصویری با سازگاری بیشتر"""
    
    # مسیر فایل خروجی متفاوت برای جلوگیری از تداخل
    file_dir = os.path.dirname(output_path)
    file_name, file_ext = os.path.splitext(os.path.basename(output_path))
    # اضافه کردن پسوند native برای تمایز از روش‌های دیگر
    native_output_path = os.path.join(file_dir, f"{file_name}_native{file_ext}")
    
    logger.info(f"روش بومی ffmpeg برای تبدیل به کیفیت {quality}")
    
    # ایجاد دستوری ساده و بومی برای تبدیل ویدیو
    cmd = [
        FFMPEG_PATH, 
        '-i', video_path,
        '-vf', f'scale=-2:{target_height}',
        '-c:v', 'libx264',
        '-crf', '30' if quality in ["360p", "240p"] else '28',  # کیفیت پایین‌تر برای ویدیوهای کوچک‌تر
        '-preset', 'ultrafast',
        '-c:a', 'aac',
        '-b:a', '96k' if quality in ["360p", "240p"] else '128k',
        '-ar', '44100',
        '-ac', '2',
        '-y',
        native_output_path
    ]
    
    logger.info(f"در حال تبدیل ویدیو به کیفیت {quality} با روش بومی...")
    
    # اجرای دستور
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # بررسی نتیجه
    if result.returncode == 0 and os.path.exists(native_output_path) and os.path.getsize(native_output_path) > 10000:
        logger.info(f"تبدیل کیفیت به روش بومی موفق: {native_output_path}")
        
        # کپی به مسیر اصلی
        try:
            import shutil
            shutil.copy2(native_output_path, output_path)
            logger.info(f"فایل از {native_output_path} به {output_path} کپی شد")
            
            # حذف فایل موقت
            try:
                os.remove(native_output_path)
            except:
                pass
                
            return output_path
        except Exception as e:
            logger.error(f"خطا در کپی فایل: {e}")
            return native_output_path
    else:
        logger.error(f"خطا در تبدیل کیفیت به روش بومی: {result.stderr[:300]}...")
        return None

def method_fallback(video_path: str, quality: str, target_height: int, output_path: str) -> Optional[str]:
    """روش پشتیبان نهایی با استفاده از دستورات بسیار ساده"""
    
    # مسیر فایل خروجی متفاوت برای جلوگیری از تداخل
    file_dir = os.path.dirname(output_path)
    file_name, file_ext = os.path.splitext(os.path.basename(output_path))
    # اضافه کردن پسوند fallback برای تمایز از روش‌های دیگر
    fallback_output_path = os.path.join(file_dir, f"{file_name}_fallback{file_ext}")
    
    logger.info(f"روش پشتیبان نهایی برای تبدیل به کیفیت {quality}")
    
    # ساده‌ترین دستور ممکن برای تبدیل ویدیو
    cmd = [
        FFMPEG_PATH, 
        '-i', video_path,
        '-s', f'?x{target_height}',  # تنظیم مستقیم اندازه
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-c:a', 'copy',  # فقط کپی صدا
        '-y',
        fallback_output_path
    ]
    
    logger.info(f"در حال تبدیل ویدیو به کیفیت {quality} با روش پشتیبان نهایی...")
    
    # اجرای دستور
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # بررسی نتیجه
    if result.returncode == 0 and os.path.exists(fallback_output_path) and os.path.getsize(fallback_output_path) > 10000:
        logger.info(f"تبدیل کیفیت به روش پشتیبان نهایی موفق: {fallback_output_path}")
        
        # کپی به مسیر اصلی
        try:
            import shutil
            shutil.copy2(fallback_output_path, output_path)
            logger.info(f"فایل از {fallback_output_path} به {output_path} کپی شد")
            
            # حذف فایل موقت
            try:
                os.remove(fallback_output_path)
            except:
                pass
                
            return output_path
        except Exception as e:
            logger.error(f"خطا در کپی فایل: {e}")
            return fallback_output_path
    else:
        logger.error(f"خطا در تبدیل کیفیت به روش پشتیبان نهایی: {result.stderr[:300]}...")
        
        # در آخرین تلاش، فایل اصلی را بر می‌گردانیم
        logger.info(f"همه روش‌ها ناموفق بودند. استفاده از فایل اصلی: {video_path}")
        return video_path

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
        
        # بیت‌ریت هوشمندانه برای هر کیفیت - تنظیم شده برای اطمینان از تناسب حجم با کیفیت
        video_bitrates = {
            "1080p": "6000k",  # بیت‌ریت بالا برای 1080p (کاهش نسبت به قبل برای حجم منطقی‌تر)
            "720p": "3500k",   # بیت‌ریت متوسط رو به بالا برای 720p (کاهش برای حل مشکل)
            "480p": "2000k",   # بیت‌ریت متوسط
            "360p": "1200k",   # بیت‌ریت متوسط رو به پایین
            "240p": "700k"     # بیت‌ریت کم
        }
        
        video_bitrate = video_bitrates.get(quality, "3000k")  # بیت‌ریت پیش‌فرض بالاتر
        
        # فیلتر مقیاس‌بندی ساده‌تر برای کیفیت‌های پایین
        if quality in ["360p", "240p"]:
            # استفاده از روش ساده‌تر برای کیفیت‌های پایین
            scale_filter = f"scale=-2:{target_height}"
        else:
            # روش عادی برای سایر کیفیت‌ها
            scale_filter = f'scale=-2:{target_height}:force_original_aspect_ratio=decrease,format=yuv420p'
        
        # استفاده از دستور ساده‌تر ffmpeg با پارامترهای حداقلی اما مطمئن
        cmd = [
            FFMPEG_PATH, 
            '-i', video_path, 
            '-vf', scale_filter,           # فیلتر مقیاس بندی ساده‌تر
            '-c:v', 'libx264',             # استفاده از کدک قدرتمند
            '-b:v', video_bitrate,         # بیت‌ریت ویدیو برای کنترل کیفیت و حجم
            '-c:a', 'copy',                # فقط کپی صدا
            '-crf', '28',                  # کیفیت مناسب (برای کیفیت‌های پایین‌تر)
            '-preset', 'ultrafast',        # سرعت خیلی بالا
            '-max_muxing_queue_size', '9999', # افزایش حداکثر صف برای جلوگیری از خطا
            '-y',                          # جایگزینی فایل موجود
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
                'ffmpeg_location': FFMPEG_PATH,
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
                FFMPEG_PATH,
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
                FFMPEG_PATH,
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
                FFMPEG_PATH,
                'ffmpeg',
                FFMPEG_PATH,
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

# تابع تبدیل به کیفیت پایین‌تر
def convert_to_lower_quality(video_path: str) -> Optional[str]:
    """
    تبدیل ویدیو به کیفیت پایین‌تر برای کاهش حجم
    
    Args:
        video_path: مسیر فایل ویدیویی اصلی
        
    Returns:
        مسیر فایل تبدیل شده یا None در صورت خطا
    """
    try:
        import os
        import subprocess
        import logging
        
        logger = logging.getLogger(__name__)
        
        # تنظیم مسیر خروجی
        file_dir = os.path.dirname(video_path)
        file_name, file_ext = os.path.splitext(os.path.basename(video_path))
        output_path = os.path.join(file_dir, f"{file_name}_lower_quality{file_ext}")
        
        # مسیر ffmpeg
        FFMPEG_PATH = '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg'
        
        # دستور ffmpeg برای کاهش کیفیت
        cmd = [
            FFMPEG_PATH,
            '-i', video_path,
            '-vf', 'scale=-2:360',  # کاهش به کیفیت 360p
            '-b:v', '800k',  # کاهش بیت‌ریت ویدیو
            '-b:a', '96k',   # کاهش بیت‌ریت صدا
            '-ac', '2',      # استریو
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-movflags', '+faststart',
            '-y',
            output_path
        ]
        
        # اجرای دستور
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10240:  # حداقل 10KB
            logger.info(f"تبدیل موفق به کیفیت پایین‌تر: {output_path}")
            return output_path
        else:
            logger.error("خطا: فایل خروجی ایجاد نشد یا خالی است")
            return None
    except Exception as e:
        logging.error(f"خطا در تبدیل به کیفیت پایین‌تر: {e}")
        return None

if __name__ == "__main__":
    print("ماژول telegram_fixes بارگذاری شد.")
    print("برای استفاده از این ماژول، آن را import کنید.")
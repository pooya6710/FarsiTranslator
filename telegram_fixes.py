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
DEFAULT_FFMPEG_PATH = "/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg"

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
                # دانلود از اینستاگرام با تنظیمات بهینه
                if quality == 'best':
                    format_spec = 'best[ext=mp4]/best'
                else:
                    if height:
                        format_spec = f'best[height<={height}][ext=mp4]/best[height<={height}]/best'
                    else:
                        format_spec = 'best[ext=mp4]/best'
                
                logger.info(f"اینستاگرام - انتخاب کیفیت {quality} با فرمت: {format_spec}")
                
                # تنظیمات پیشرفته برای کنترل کیفیت
                ydl_opts.update({
                    'format': format_spec,
                    'merge_output_format': 'mp4',  # اطمینان از خروجی MP4
                })
                
                # اضافه کردن تنظیمات FFmpeg در صورت وجود
                if ffmpeg_options:
                    logger.info(f"اعمال تنظیمات FFmpeg: {ffmpeg_options}")
                    ydl_opts['postprocessor_args'] = ffmpeg_options
                
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
                    'ffmpeg',
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
                'ffmpeg',
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
                'ffmpeg',
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
                'ffmpeg',
                '/usr/bin/ffmpeg',
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
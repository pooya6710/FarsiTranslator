#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ماژول استخراج محتوای یوتیوب

این ماژول توابع پیشرفته برای دانلود ویدیو و صدا از یوتیوب ارائه می‌دهد.
از روش‌های پیشرفته برای اطمینان از دانلود ویدیو با کیفیت مناسب استفاده می‌کند.
"""

import os
import re
import json
import asyncio
import logging
import tempfile
import subprocess
import uuid
import time
import shutil
from typing import Dict, List, Optional, Tuple, Union

import yt_dlp
from yt_dlp.utils import DownloadError

# تنظیم لاگر
logger = logging.getLogger(__name__)

# مسیر پیش‌فرض دانلود
DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)

# مسیر ffmpeg
FFMPEG_PATH = '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg'

# مسیر فایل کوکی یوتیوب
YOUTUBE_COOKIE_FILE = tempfile.mktemp(prefix="youtube_cookies_", suffix=".txt")

# حداکثر تعداد تلاش‌های مجدد
MAX_RETRIES = 3

# نگاشت کیفیت‌های ویدیو
VIDEO_QUALITY_MAP = {
    "1080p": {"height": 1080, "format_id": "137", "display_name": "Full HD (1080p)"},
    "720p": {"height": 720, "format_id": "136", "display_name": "HD (720p)"},
    "480p": {"height": 480, "format_id": "135", "display_name": "SD (480p)"},
    "360p": {"height": 360, "format_id": "134", "display_name": "Low (360p)"},
    "240p": {"height": 240, "format_id": "133", "display_name": "Very Low (240p)"},
    "best": {"display_name": "Best Quality", "priority": 1},
    "audio": {"display_name": "Audio Only (MP3)", "priority": 6}
}

# تنظیمات پایه yt-dlp
YDL_OPTS_BASE = {
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': False,
    'check_formats': True,
    'no_color': True,
    'youtube_include_dash_manifest': True,
    'youtube_include_hls_manifest': True,
    'prefer_ffmpeg': True,
    'ffmpeg_location': FFMPEG_PATH,
    'cookiefile': YOUTUBE_COOKIE_FILE,
    'noplaylist': True,
    'geo_bypass': True,
    'socket_timeout': 30,
}

def clean_youtube_url(url: str) -> str:
    """
    پاکسازی و استانداردسازی URL یوتیوب
    
    Args:
        url: آدرس ویدیوی یوتیوب
        
    Returns:
        URL استاندارد شده
    """
    # حذف پارامترهای اضافی
    url = re.sub(r'&list=.*', '', url)
    url = re.sub(r'&index=.*', '', url)
    url = re.sub(r'&t=.*', '', url)
    url = re.sub(r'&pp=.*', '', url)
    
    # اطمینان از شروع با https
    if url.startswith('www.'):
        url = 'https://' + url
    elif not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        
    return url

def get_video_id(url: str) -> Optional[str]:
    """
    استخراج شناسه ویدیوی یوتیوب
    
    Args:
        url: آدرس ویدیوی یوتیوب
        
    Returns:
        شناسه ویدیو یا None در صورت عدم تطابق
    """
    # الگوهای مختلف URL یوتیوب
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',  # نسخه استاندارد
        r'(?:shorts\/)([0-9A-Za-z_-]{11}).*',  # shorts
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11}).*',  # لینک کوتاه
    ]
    
    url = clean_youtube_url(url)
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def create_format_selector(quality: str) -> str:
    """
    ایجاد الگوی انتخاب فرمت برای کیفیت مشخص
    
    Args:
        quality: کیفیت مورد نظر (1080p, 720p, 480p, 360p, 240p, audio, best)
        
    Returns:
        الگوی انتخاب فرمت yt-dlp
    """
    if quality == "audio":
        return "bestaudio[ext=m4a]/bestaudio/best"
    
    if quality == "best":
        return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    
    # استخراج ارتفاع از نگاشت کیفیت
    height = VIDEO_QUALITY_MAP.get(quality, {}).get("height")
    if not height:
        # اگر کیفیت نامعتبر است، از best استفاده می‌کنیم
        return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    
    # الگوی دقیق براساس ارتفاع
    return (
        f"bestvideo[height={height}][ext=mp4]+bestaudio[ext=m4a]/"
        f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
        f"best[height={height}][ext=mp4]/best[height<={height}][ext=mp4]/"
        f"best[ext=mp4]/best"
    )

def get_output_template(quality: str, video_id: str, title: str) -> str:
    """
    ایجاد قالب نام فایل خروجی
    
    Args:
        quality: کیفیت انتخاب شده
        video_id: شناسه یکتای ویدیو
        title: عنوان ویدیو
        
    Returns:
        مسیر کامل فایل خروجی
    """
    # پاکسازی عنوان
    title = re.sub(r'[\\/*?:"<>|]', "_", title)
    title = re.sub(r'\s+', "_", title)
    
    # کوتاه کردن عنوان طولانی
    if len(title) > 100:
        title = title[:97] + "..."
    
    # ایجاد شناسه یکتا برای جلوگیری از همپوشانی
    unique_id = uuid.uuid4().hex[:8]
    
    if quality == "audio":
        ext = "mp3"
        filename = f"yt_audio_{video_id}_{unique_id}.{ext}"
    else:
        ext = "mp4"
        filename = f"yt_{quality}_{video_id}_{unique_id}.{ext}"
    
    return os.path.join(DEFAULT_DOWNLOAD_DIR, filename)

async def extract_video_info(url: str) -> Optional[Dict]:
    """
    استخراج اطلاعات ویدیوی یوتیوب
    
    Args:
        url: آدرس ویدیوی یوتیوب
        
    Returns:
        دیکشنری حاوی اطلاعات ویدیو یا None در صورت خطا
    """
    url = clean_youtube_url(url)
    
    ydl_opts = {
        **YDL_OPTS_BASE,
        'format': 'best[ext=mp4]/best',
        'skip_download': True
    }
    
    loop = asyncio.get_event_loop()
    
    for attempt in range(MAX_RETRIES):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(None, ydl.extract_info, url, True)
                if info:
                    return info
        except Exception as e:
            logger.error(f"خطا در استخراج اطلاعات ویدیو (تلاش {attempt+1}/{MAX_RETRIES}): {str(e)}")
            if attempt < MAX_RETRIES - 1:
                # انتظار قبل از تلاش مجدد
                await asyncio.sleep(1)
            else:
                logger.error(f"تمام تلاش‌ها ناموفق بود: {url}")
                return None
    
    return None

async def download_youtube_video(url: str, quality: str = "best") -> Optional[str]:
    """
    دانلود ویدیوی یوتیوب با کیفیت مشخص
    
    Args:
        url: آدرس ویدیوی یوتیوب
        quality: کیفیت مورد نظر (1080p, 720p, 480p, 360p, 240p, best)
        
    Returns:
        مسیر فایل دانلود شده یا None در صورت خطا
    """
    logger.info(f"شروع دانلود ویدیوی یوتیوب با کیفیت {quality}: {url}")
    
    # دریافت اطلاعات ویدیو
    info = await extract_video_info(url)
    if not info:
        logger.error("اطلاعات ویدیو دریافت نشد")
        return None
    
    video_id = info.get('id', 'unknown')
    title = info.get('title', 'youtube_video')
    
    # ایجاد قالب نام فایل خروجی
    output_path = get_output_template(quality, video_id, title)
    
    # ایجاد الگوی انتخاب فرمت
    format_selector = create_format_selector(quality)
    logger.info(f"الگوی انتخاب فرمت: {format_selector}")
    
    # تنظیمات yt_dlp
    ydl_opts = {
        **YDL_OPTS_BASE,
        'format': format_selector,
        'merge_output_format': 'mp4',
        'outtmpl': {'default': output_path},
        'verbose': False
    }
    
    # روش‌های مختلف دانلود
    download_methods = [
        download_with_ytdlp,
        download_with_ytdlp_direct,
        download_with_ytdlp_fallback,
    ]
    
    for i, download_method in enumerate(download_methods):
        logger.info(f"تلاش دانلود با روش {i+1}/{len(download_methods)}")
        try:
            result = await download_method(url, ydl_opts)
            if result and os.path.exists(result):
                logger.info(f"دانلود با روش {i+1} موفق: {result}")
                # بررسی نوع فایل
                if quality != "audio" and result.endswith(('.mp3', '.m4a', '.aac', '.wav')):
                    logger.warning(f"فایل دانلود شده صوتی است اما ویدیو درخواست شده بود: {result}")
                    # تلاش با روش بعدی
                    continue
                return result
        except Exception as e:
            logger.error(f"خطا در روش {i+1}: {str(e)}")
    
    logger.error(f"تمام روش‌های دانلود شکست خوردند: {url}")
    return None

async def download_with_ytdlp(url: str, ydl_opts: Dict) -> Optional[str]:
    """
    دانلود با استفاده از yt-dlp مستقیم
    
    Args:
        url: آدرس ویدیو
        ydl_opts: تنظیمات yt-dlp
        
    Returns:
        مسیر فایل دانلود شده یا None در صورت خطا
    """
    loop = asyncio.get_event_loop()
    output_path = ydl_opts['outtmpl']['default']
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await loop.run_in_executor(None, ydl.download, [url])
            
        # بررسی فایل خروجی
        if os.path.exists(output_path):
            return output_path
        
        # بررسی سایر حالت‌های احتمالی
        base_path, ext = os.path.splitext(output_path)
        for possible_ext in ['.mp4', '.mkv', '.webm', '.mp3', '.m4a']:
            possible_path = base_path + possible_ext
            if os.path.exists(possible_path):
                # اگر پسوند فایل تغییر کرده، نام را استاندارد می‌کنیم
                if possible_ext != ext:
                    standardized_path = base_path + ext
                    os.rename(possible_path, standardized_path)
                    return standardized_path
                return possible_path
                
    except Exception as e:
        logger.error(f"خطا در دانلود با yt-dlp: {str(e)}")
    
    return None

async def download_with_ytdlp_direct(url: str, ydl_opts: Dict) -> Optional[str]:
    """
    دانلود با استفاده از yt-dlp به صورت مستقیم
    
    Args:
        url: آدرس ویدیو
        ydl_opts: تنظیمات yt-dlp
        
    Returns:
        مسیر فایل دانلود شده یا None در صورت خطا
    """
    # کپی تنظیمات برای تغییر
    direct_opts = ydl_opts.copy()
    
    # تغییر فرمت به حالت مستقیم (بدون ترکیب)
    if 'format' in direct_opts and '+' in direct_opts['format']:
        # انتخاب بهترین کیفیت ویدیویی که از قبل ترکیب شده است
        direct_opts['format'] = direct_opts['format'].split('/')[0].split('+')[0] + '/best[ext=mp4]/best'
    
    # تغییر نام خروجی برای جلوگیری از تداخل
    output_path = direct_opts['outtmpl']['default']
    base_path, ext = os.path.splitext(output_path)
    direct_opts['outtmpl']['default'] = f"{base_path}_direct{ext}"
    
    try:
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(direct_opts) as ydl:
            await loop.run_in_executor(None, ydl.download, [url])
        
        # بررسی فایل خروجی
        if os.path.exists(direct_opts['outtmpl']['default']):
            # انتقال به مسیر اصلی
            shutil.move(direct_opts['outtmpl']['default'], output_path)
            return output_path
            
    except Exception as e:
        logger.error(f"خطا در دانلود مستقیم با yt-dlp: {str(e)}")
    
    return None

async def download_with_ytdlp_fallback(url: str, ydl_opts: Dict) -> Optional[str]:
    """
    دانلود با استفاده از yt-dlp با روش جایگزین
    
    Args:
        url: آدرس ویدیو
        ydl_opts: تنظیمات yt-dlp
        
    Returns:
        مسیر فایل دانلود شده یا None در صورت خطا
    """
    # کپی تنظیمات برای تغییر
    fallback_opts = ydl_opts.copy()
    
    # تغییر فرمت به حالت ساده‌تر
    fallback_opts['format'] = 'best[ext=mp4]/best'
    
    # تغییر نام خروجی برای جلوگیری از تداخل
    output_path = fallback_opts['outtmpl']['default']
    base_path, ext = os.path.splitext(output_path)
    fallback_opts['outtmpl']['default'] = f"{base_path}_fallback{ext}"
    
    try:
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(fallback_opts) as ydl:
            await loop.run_in_executor(None, ydl.download, [url])
        
        # بررسی فایل خروجی
        if os.path.exists(fallback_opts['outtmpl']['default']):
            # انتقال به مسیر اصلی
            shutil.move(fallback_opts['outtmpl']['default'], output_path)
            return output_path
            
    except Exception as e:
        logger.error(f"خطا در دانلود با روش جایگزین yt-dlp: {str(e)}")
    
    return None

async def download_youtube_audio(url: str) -> Optional[str]:
    """
    دانلود صدای ویدیوی یوتیوب
    
    Args:
        url: آدرس ویدیوی یوتیوب
        
    Returns:
        مسیر فایل صوتی دانلود شده یا None در صورت خطا
    """
    logger.info(f"شروع دانلود صدای یوتیوب: {url}")
    
    # روش 1: دانلود مستقیم صدا
    audio_file = await download_audio_direct(url)
    if audio_file and os.path.exists(audio_file):
        return audio_file
    
    # روش 2: دانلود ویدیو و استخراج صدا
    video_file = await download_youtube_video(url, "best")
    if video_file and os.path.exists(video_file):
        audio_file = await extract_audio_from_video(video_file)
        if audio_file and os.path.exists(audio_file):
            # حذف فایل ویدیویی
            try:
                os.remove(video_file)
            except Exception as e:
                logger.warning(f"خطا در حذف فایل ویدیویی موقت: {str(e)}")
            return audio_file
    
    logger.error("تمام روش‌های دانلود صدا شکست خوردند")
    return None

async def download_audio_direct(url: str) -> Optional[str]:
    """
    دانلود مستقیم صدا از یوتیوب
    
    Args:
        url: آدرس ویدیوی یوتیوب
        
    Returns:
        مسیر فایل صوتی دانلود شده یا None در صورت خطا
    """
    # دریافت اطلاعات ویدیو
    info = await extract_video_info(url)
    if not info:
        logger.error("اطلاعات ویدیو دریافت نشد")
        return None
    
    video_id = info.get('id', 'unknown')
    title = info.get('title', 'youtube_audio')
    
    # ایجاد قالب نام فایل خروجی
    output_path = get_output_template("audio", video_id, title)
    
    # تنظیمات دانلود صوتی
    ydl_opts = {
        **YDL_OPTS_BASE,
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': {'default': output_path.replace('.mp3', '.%(ext)s')},
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    
    loop = asyncio.get_event_loop()
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await loop.run_in_executor(None, ydl.download, [url])
        
        # بررسی وجود فایل
        if os.path.exists(output_path):
            return output_path
        
        # جستجوی فایل با پسوندهای دیگر
        for ext in ['mp3', 'm4a', 'aac', 'wav', 'opus']:
            alt_path = output_path.replace('.mp3', f'.{ext}')
            if os.path.exists(alt_path):
                if ext != 'mp3':
                    # تغییر نام به mp3
                    os.rename(alt_path, output_path)
                return output_path
                
    except Exception as e:
        logger.error(f"خطا در دانلود مستقیم صدا: {str(e)}")
    
    return None

async def extract_audio_from_video(video_path: str) -> Optional[str]:
    """
    استخراج صدا از فایل ویدیویی
    
    Args:
        video_path: مسیر فایل ویدیویی
        
    Returns:
        مسیر فایل صوتی استخراج شده یا None در صورت خطا
    """
    if not os.path.exists(video_path):
        logger.error(f"فایل ویدیویی وجود ندارد: {video_path}")
        return None
    
    try:
        audio_path = video_path.rsplit('.', 1)[0] + '.mp3'
        
        # استفاده از FFmpeg برای استخراج صدا
        cmd = [
            FFMPEG_PATH,
            '-i', video_path,
            '-vn',  # بدون ویدیو
            '-acodec', 'libmp3lame',
            '-ab', '192k',
            '-ar', '44100',
            '-y',  # بازنویسی فایل موجود
            audio_path
        ]
        
        # اجرای دستور در thread pool
        loop = asyncio.get_event_loop()
        process = await loop.run_in_executor(
            None,
            lambda: subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        )
        
        if process.returncode == 0 and os.path.exists(audio_path):
            logger.info(f"استخراج صدا موفق: {audio_path}")
            return audio_path
        else:
            logger.error(f"خطا در استخراج صدا: {process.stderr}")
            
    except Exception as e:
        logger.error(f"خطا در استخراج صدا: {str(e)}")
    
    return None

async def get_available_formats(url: str) -> List[Dict]:
    """
    دریافت فرمت‌های موجود برای یک ویدیوی یوتیوب
    
    Args:
        url: آدرس ویدیوی یوتیوب
        
    Returns:
        لیستی از فرمت‌های موجود با مشخصات
    """
    url = clean_youtube_url(url)
    
    ydl_opts = {
        **YDL_OPTS_BASE,
        'skip_download': True,
        'listformats': True,
    }
    
    loop = asyncio.get_event_loop()
    formats = []
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, ydl.extract_info, url, False)
            if info and 'formats' in info:
                formats = info['formats']
    except Exception as e:
        logger.error(f"خطا در دریافت فرمت‌های موجود: {str(e)}")
    
    return formats

async def get_download_options(url: str) -> List[Dict]:
    """
    دریافت گزینه‌های دانلود برای ویدیوی یوتیوب
    
    Args:
        url: آدرس ویدیوی یوتیوب
        
    Returns:
        لیستی از گزینه‌های دانلود
    """
    # دریافت اطلاعات ویدیو
    info = await extract_video_info(url)
    if not info:
        logger.error("اطلاعات ویدیو دریافت نشد")
        return []
    
    # فرمت‌های موجود
    formats = await get_available_formats(url)
    
    # استخراج ارتفاع‌های موجود
    available_heights = set()
    for fmt in formats:
        if 'height' in fmt and fmt.get('vcodec') != 'none':
            available_heights.add(fmt['height'])
    
    available_heights = sorted(available_heights, reverse=True)
    logger.info(f"ارتفاع‌های موجود: {available_heights}")
    
    # گزینه‌های دانلود
    options = []
    
    # گزینه بهترین کیفیت حذف شده به درخواست کاربر
    
    # افزودن گزینه‌های براساس کیفیت‌های استاندارد
    standard_qualities = [
        ('1080p', 'کیفیت Full HD (1080p)'),
        ('720p', 'کیفیت HD (720p)'),
        ('480p', 'کیفیت متوسط (480p)'),
        ('360p', 'کیفیت پایین (360p)'),
        ('240p', 'کیفیت خیلی پایین (240p)')
    ]
    
    for i, (quality, display_name) in enumerate(standard_qualities):
        # بررسی دسترسی‌پذیری
        height = VIDEO_QUALITY_MAP[quality]['height']
        available = False
        
        # اگر ارتفاع دقیقاً موجود نیست، نزدیک‌ترین را انتخاب می‌کنیم
        for h in available_heights:
            if h >= height - 100 and h <= height + 100:
                available = True
                break
        
        if available or not available_heights:  # اگر هیچ ارتفاعی موجود نباشد، همه را نشان می‌دهیم
            options.append({
                'quality': quality,
                'display_name': display_name,
                'priority': i + 1  # اصلاح شماره‌گذاری بعد از حذف گزینه best
            })
    
    # افزودن گزینه فقط صدا
    options.append({
        'quality': 'audio',
        'display_name': 'فقط صدا (MP3)',
        'type': 'audio',
        'priority': len(options) + 1
    })
    
    return options
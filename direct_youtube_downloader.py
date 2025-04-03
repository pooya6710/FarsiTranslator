#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
اسکریپت دانلود مستقیم ویدیوی یوتیوب به عنوان ویدیو (نه صدا)

این اسکریپت یک روش مستقیم و قابل اعتماد برای دانلود ویدیوهای یوتیوب ارائه می‌دهد.
تمرکز اصلی بر دانلود ویدیو (نه فقط صدا) با کیفیت درخواست شده است.
"""

import os
import sys
import re
import argparse
import subprocess
import logging
from typing import Optional

import yt_dlp

# تنظیم لاگر
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# مسیر پیش‌فرض دانلود
DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)

# مسیر ffmpeg
FFMPEG_PATH = '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg'

def download_video(url: str, quality: str = "720p", output_dir: str = DEFAULT_DOWNLOAD_DIR) -> Optional[str]:
    """
    دانلود ویدیوی یوتیوب به عنوان یک فایل ویدیویی (نه صوتی) با کیفیت مشخص
    
    Args:
        url: آدرس ویدیوی یوتیوب
        quality: کیفیت مورد نظر (1080p, 720p, 480p, 360p, 240p)
        output_dir: مسیر ذخیره‌سازی
        
    Returns:
        مسیر فایل دانلود شده یا None در صورت خطا
    """
    logger.info(f"شروع دانلود ویدیو با کیفیت {quality}: {url}")
    
    # نقشه کیفیت به ارتفاع
    quality_map = {
        "1080p": 1080,
        "720p": 720,
        "480p": 480,
        "360p": 360,
        "240p": 240,
    }
    
    # تبدیل کیفیت به ارتفاع
    height = quality_map.get(quality, 720)
    
    # ساخت الگوی فرمت مناسب
    # ترفند مهم: استفاده از علامت '/' به عنوان جایگزین برای تضمین دریافت ویدیو
    format_spec = (
        f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
        f"best[height<={height}][ext=mp4]/"
        f"best[ext=mp4]/"
        f"best"
    )
    
    # شناسه برای ویدیو
    video_id = extract_video_id(url)
    output_filename = f"direct_yt_{quality}_{video_id}.mp4"
    output_path = os.path.join(output_dir, output_filename)
    
    # تنظیمات yt-dlp
    ydl_opts = {
        'format': format_spec,
        'outtmpl': {'default': output_path},
        'quiet': True,
        'no_warnings': True,
        'ffmpeg_location': FFMPEG_PATH,
        'merge_output_format': 'mp4',
        # ویژگی مهم: غیرفعال کردن پس‌پردازش‌های خودکار
        'postprocessors': [],
        # تنظیمات اضافی
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'geo_bypass': True,
        'noprogress': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"دانلود با فرمت: {format_spec}")
            ydl.download([url])
            
        # بررسی فایل خروجی
        if os.path.exists(output_path):
            logger.info(f"دانلود موفق: {output_path}")
            # بررسی نوع فایل - مطمئن شویم که واقعاً ویدیو است
            if is_video_file(output_path):
                return output_path
            else:
                logger.error(f"فایل دانلود شده ویدیو نیست: {output_path}")
        else:
            logger.error(f"فایل خروجی ایجاد نشد: {output_path}")
    
    except Exception as e:
        logger.error(f"خطا در دانلود ویدیو: {str(e)}")
    
    return None

def download_audio(url: str, output_dir: str = DEFAULT_DOWNLOAD_DIR) -> Optional[str]:
    """
    دانلود فقط صدای ویدیوی یوتیوب
    
    Args:
        url: آدرس ویدیوی یوتیوب
        output_dir: مسیر ذخیره‌سازی
        
    Returns:
        مسیر فایل دانلود شده یا None در صورت خطا
    """
    logger.info(f"شروع دانلود صدا: {url}")
    
    # شناسه برای صدا
    video_id = extract_video_id(url)
    output_filename = f"direct_yt_audio_{video_id}.mp3"
    output_path = os.path.join(output_dir, output_filename)
    
    # تنظیمات yt-dlp
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': {'default': output_path.replace('.mp3', '.%(ext)s')},
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'ffmpeg_location': FFMPEG_PATH,
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        # بررسی فایل خروجی
        if os.path.exists(output_path):
            logger.info(f"دانلود صدا موفق: {output_path}")
            return output_path
            
        # جستجوی فایل با پسوندهای دیگر
        for ext in ['mp3', 'm4a', 'aac', 'wav', 'opus']:
            alt_path = output_path.replace('.mp3', f'.{ext}')
            if os.path.exists(alt_path):
                logger.info(f"فایل صوتی با پسوند دیگر یافت شد: {alt_path}")
                if ext != 'mp3':
                    # تغییر نام به mp3
                    os.rename(alt_path, output_path)
                return output_path
                
        logger.error(f"فایل صوتی ایجاد نشد: {output_path}")
    
    except Exception as e:
        logger.error(f"خطا در دانلود صدا: {str(e)}")
    
    return None

def extract_video_id(url: str) -> str:
    """
    استخراج شناسه ویدیوی یوتیوب
    
    Args:
        url: آدرس ویدیوی یوتیوب
        
    Returns:
        شناسه ویدیو
    """
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:shorts\/)([0-9A-Za-z_-]{11}).*',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11}).*',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    # اگر شناسه پیدا نشد، یک شناسه تصادفی تولید می‌کنیم
    import uuid
    return uuid.uuid4().hex[:11]

def is_video_file(file_path: str) -> bool:
    """
    بررسی می‌کند که آیا فایل از نوع ویدیو است
    
    Args:
        file_path: مسیر فایل
        
    Returns:
        True اگر فایل ویدیویی است، در غیر این صورت False
    """
    if not os.path.exists(file_path):
        return False
        
    # بررسی پسوند فایل
    if not file_path.lower().endswith(('.mp4', '.mkv', '.webm', '.avi', '.mov')):
        return False
        
    # بررسی سایز فایل
    if os.path.getsize(file_path) < 10000:  # کمتر از 10KB خیلی کوچک است
        return False
        
    # بررسی محتوای فایل با ffprobe
    try:
        cmd = [
            FFMPEG_PATH.replace('ffmpeg', 'ffprobe'),
            '-v', 'error',
            '-select_streams', 'v:0',  # انتخاب اولین جریان ویدیویی
            '-show_entries', 'stream=codec_type',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return 'video' in result.stdout.strip()
    
    except Exception as e:
        logger.error(f"خطا در بررسی نوع فایل: {str(e)}")
        # اگر نتوانیم محتوا را بررسی کنیم، به پسوند اعتماد می‌کنیم
        return True

def main():
    """
    اجرای اصلی اسکریپت
    """
    parser = argparse.ArgumentParser(description='دانلود ویدیوی یوتیوب به عنوان ویدیو (نه صدا)')
    parser.add_argument('url', help='آدرس ویدیوی یوتیوب')
    parser.add_argument('--quality', '-q', choices=['1080p', '720p', '480p', '360p', '240p', 'audio'], 
                        default='720p', help='کیفیت مورد نظر (پیش‌فرض: 720p)')
    parser.add_argument('--output-dir', '-o', default=DEFAULT_DOWNLOAD_DIR, 
                        help='مسیر ذخیره‌سازی')
    
    args = parser.parse_args()
    
    # ایجاد مسیر خروجی
    os.makedirs(args.output_dir, exist_ok=True)
    
    # دانلود براساس کیفیت
    if args.quality == 'audio':
        result = download_audio(args.url, args.output_dir)
    else:
        result = download_video(args.url, args.quality, args.output_dir)
    
    # گزارش نتیجه
    if result:
        print(f"دانلود موفق: {result}")
        sys.exit(0)
    else:
        print("دانلود ناموفق")
        sys.exit(1)

if __name__ == "__main__":
    main()
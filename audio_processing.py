#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ماژول پردازش صوتی برای استخراج صدا از فایل‌های ویدیویی

این ماژول توابعی برای تشخیص نوع فایل و استخراج صدا از فایل‌های ویدیویی ارائه می‌دهد.
از ffmpeg به عنوان موتور پردازش استفاده می‌کند.
"""

import os
import subprocess
import logging
from typing import Optional

# تنظیمات لاگینگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def is_video_file(file_path: str) -> bool:
    """بررسی اینکه آیا فایل مورد نظر ویدیو است یا خیر
    
    Args:
        file_path: مسیر فایل
        
    Returns:
        True اگر فایل ویدیویی باشد، False در غیر این صورت
    """
    # پسوندهای رایج فایل‌های ویدیویی
    video_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm')
    return file_path.lower().endswith(video_extensions)

def is_audio_file(file_path: str) -> bool:
    """بررسی اینکه آیا فایل مورد نظر صوتی است یا خیر
    
    Args:
        file_path: مسیر فایل
        
    Returns:
        True اگر فایل صوتی باشد، False در غیر این صورت
    """
    # پسوندهای رایج فایل‌های صوتی
    audio_extensions = ('.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg', '.opus')
    return file_path.lower().endswith(audio_extensions)

def extract_audio(video_path: str, output_format: str = 'mp3', bitrate: str = '192k') -> Optional[str]:
    """استخراج صدا از فایل ویدیویی
    
    Args:
        video_path: مسیر فایل ویدیویی
        output_format: فرمت خروجی صدا (mp3, m4a, aac, etc.)
        bitrate: نرخ بیت خروجی
        
    Returns:
        مسیر فایل صوتی استخراج شده یا None در صورت خطا
    """
    if not os.path.exists(video_path):
        logger.error(f"فایل ویدیویی وجود ندارد: {video_path}")
        return None
        
    if not is_video_file(video_path):
        logger.error(f"فایل مورد نظر ویدیویی نیست: {video_path}")
        return None
    
    try:
        # ایجاد مسیر فایل خروجی
        output_dir = os.path.dirname(video_path)
        base_filename = os.path.basename(video_path).rsplit('.', 1)[0]
        audio_path = os.path.join(output_dir, f"{base_filename}_audio.{output_format}")
        
        # تنظیم دستور ffmpeg
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vn',  # بدون ویدیو
            '-acodec', 'libmp3lame' if output_format == 'mp3' else 'aac',
            '-ab', bitrate,
            '-ar', '44100',  # نرخ نمونه‌برداری
            '-y',  # بازنویسی فایل خروجی در صورت وجود
            audio_path
        ]
        
        # اجرای دستور
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()
        
        # بررسی نتیجه
        if process.returncode != 0:
            logger.error(f"خطا در استخراج صدا: {stderr.decode('utf-8', errors='ignore')}")
            return None
            
        # بررسی وجود فایل خروجی
        if not os.path.exists(audio_path):
            logger.error(f"فایل صوتی ایجاد نشد: {audio_path}")
            return None
            
        logger.info(f"صدا با موفقیت استخراج شد: {audio_path}")
        return audio_path
        
    except Exception as e:
        logger.error(f"خطا در استخراج صدا: {str(e)}")
        return None

def get_audio_metadata(audio_path: str) -> dict:
    """دریافت متادیتای فایل صوتی
    
    Args:
        audio_path: مسیر فایل صوتی
        
    Returns:
        دیکشنری حاوی متادیتای فایل صوتی
    """
    if not os.path.exists(audio_path):
        logger.error(f"فایل صوتی وجود ندارد: {audio_path}")
        return {}
        
    if not is_audio_file(audio_path):
        logger.error(f"فایل مورد نظر صوتی نیست: {audio_path}")
        return {}
    
    try:
        # دستور ffprobe برای دریافت متادیتا
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            audio_path
        ]
        
        # اجرای دستور
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()
        
        # بررسی نتیجه
        if process.returncode != 0:
            logger.error(f"خطا در دریافت متادیتا: {stderr.decode('utf-8', errors='ignore')}")
            return {}
            
        # تبدیل خروجی به دیکشنری
        import json
        metadata = json.loads(stdout.decode('utf-8', errors='ignore'))
        
        return metadata
        
    except Exception as e:
        logger.error(f"خطا در دریافت متادیتا: {str(e)}")
        return {}

def convert_audio_format(audio_path: str, output_format: str = 'mp3', bitrate: str = '192k') -> Optional[str]:
    """تبدیل فرمت فایل صوتی
    
    Args:
        audio_path: مسیر فایل صوتی
        output_format: فرمت خروجی صدا (mp3, m4a, aac, etc.)
        bitrate: نرخ بیت خروجی
        
    Returns:
        مسیر فایل صوتی تبدیل شده یا None در صورت خطا
    """
    if not os.path.exists(audio_path):
        logger.error(f"فایل صوتی وجود ندارد: {audio_path}")
        return None
        
    if not is_audio_file(audio_path):
        logger.error(f"فایل مورد نظر صوتی نیست: {audio_path}")
        return None
    
    try:
        # ایجاد مسیر فایل خروجی
        output_dir = os.path.dirname(audio_path)
        base_filename = os.path.basename(audio_path).rsplit('.', 1)[0]
        output_path = os.path.join(output_dir, f"{base_filename}_converted.{output_format}")
        
        # تنظیم دستور ffmpeg
        cmd = [
            'ffmpeg',
            '-i', audio_path,
            '-acodec', 'libmp3lame' if output_format == 'mp3' else 'aac',
            '-ab', bitrate,
            '-ar', '44100',  # نرخ نمونه‌برداری
            '-y',  # بازنویسی فایل خروجی در صورت وجود
            output_path
        ]
        
        # اجرای دستور
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()
        
        # بررسی نتیجه
        if process.returncode != 0:
            logger.error(f"خطا در تبدیل فرمت صوتی: {stderr.decode('utf-8', errors='ignore')}")
            return None
            
        # بررسی وجود فایل خروجی
        if not os.path.exists(output_path):
            logger.error(f"فایل صوتی تبدیل شده ایجاد نشد: {output_path}")
            return None
            
        logger.info(f"فرمت صوتی با موفقیت تبدیل شد: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"خطا در تبدیل فرمت صوتی: {str(e)}")
        return None

if __name__ == "__main__":
    # آزمایش موارد پایه
    print("ماژول پردازش صوتی")
    print("برای استفاده به عنوان ماژول، آن را import کنید")

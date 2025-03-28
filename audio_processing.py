#!/usr/bin/env python3
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
        audio_path = os.path.join(output_dir, f"{file_name}_{uuid.uuid4().hex[:8]}.{output_format}")
        
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
        output_path = os.path.join(output_dir, f"{file_name}_{uuid.uuid4().hex[:8]}.{output_format}")
        
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

def create_audio_extractor_module():
    """
    ایجاد ماژول audio_extractor.py برای سازگاری با نسخه‌های قبلی
    """
    try:
        module_dir = os.path.dirname(os.path.abspath(__file__))
        extractor_dir = os.path.join(module_dir, "audio_processing")
        
        # ایجاد دایرکتوری اگر وجود ندارد
        os.makedirs(extractor_dir, exist_ok=True)
        
        # ایجاد فایل __init__.py
        init_path = os.path.join(extractor_dir, "__init__.py")
        with open(init_path, "w") as f:
            f.write('"""ماژول پردازش صدا برای ربات تلگرام"""\n')
        
        # ایجاد فایل audio_extractor.py
        extractor_path = os.path.join(extractor_dir, "audio_extractor.py")
        with open(extractor_path, "w") as f:
            f.write('''#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ماژول audio_extractor

این ماژول تابع استخراج صدا از فایل‌های ویدیویی را ارائه می‌دهد.
"""

from audio_processing import extract_audio as _extract_audio

# تابعی که همان تابع اصلی را فراخوانی می‌کند
def extract_audio(video_path, output_format='mp3', bitrate='192k'):
    """
    استخراج صدا از فایل ویدیویی
    
    Args:
        video_path: مسیر فایل ویدیویی
        output_format: فرمت خروجی صدا (mp3, m4a, wav)
        bitrate: نرخ بیت خروجی
        
    Returns:
        مسیر فایل صوتی ایجاد شده یا None در صورت خطا
    """
    return _extract_audio(video_path, output_format, bitrate)
''')
        
        logger.info(f"ماژول audio_extractor با موفقیت ایجاد شد: {extractor_path}")
        return True
        
    except Exception as e:
        logger.error(f"خطا در ایجاد ماژول audio_extractor: {str(e)}")
        return False

# اجرای تابع ایجاد ماژول
create_audio_extractor_module()

if __name__ == "__main__":
    print("ماژول audio_processing بارگذاری شد.")
    print("برای استفاده از این ماژول، آن را import کنید.")
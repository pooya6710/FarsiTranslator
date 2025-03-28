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
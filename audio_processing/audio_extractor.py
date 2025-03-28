#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ماژول audio_extractor

این ماژول تابع استخراج صدا از فایل‌های ویدیویی را ارائه می‌دهد.
"""

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
        
        # کُدِک مناسب برای فرمت خروجی
        codec_map = {
            'mp3': 'libmp3lame',
            'm4a': 'aac',
            'aac': 'aac',
            'wav': 'pcm_s16le',
            'ogg': 'libvorbis',
            'opus': 'libopus',
            'flac': 'flac'
        }
        
        codec = codec_map.get(output_format.lower(), 'libmp3lame')
        
        # آماده‌سازی دستور FFmpeg
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vn',  # بدون ویدیو
            '-acodec', codec,
            '-ab', bitrate,
            '-ar', '44100',  # نرخ نمونه‌برداری
            '-ac', '2',      # تعداد کانال‌ها
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
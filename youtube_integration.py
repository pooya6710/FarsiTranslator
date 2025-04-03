#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ماژول ادغام یوتیوب با ربات تلگرام

این ماژول رابط بین ماژول youtube_extractor و ربات تلگرام است.
"""

import os
import sys
import asyncio
import logging
from typing import Dict, List, Optional, Union

# تنظیم لاگر
logger = logging.getLogger(__name__)

# افزودن مسیر پروژه به sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# واردسازی ماژول‌های پروژه
import youtube_extractor
import direct_youtube_downloader

class YoutubeHandler:
    """کلاس مدیریت دانلود از یوتیوب"""
    
    def __init__(self, download_dir: str = None):
        """
        مقداردهی اولیه
        
        Args:
            download_dir: مسیر دایرکتوری دانلود
        """
        if download_dir is None:
            self.download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
        else:
            self.download_dir = download_dir
            
        # ایجاد دایرکتوری دانلود اگر وجود ندارد
        os.makedirs(self.download_dir, exist_ok=True)
        
        logger.info(f"مدیریت دانلود یوتیوب راه‌اندازی شد. مسیر دانلود: {self.download_dir}")
    
    async def get_video_info(self, url: str) -> Optional[Dict]:
        """
        دریافت اطلاعات ویدیوی یوتیوب
        
        Args:
            url: آدرس ویدیوی یوتیوب
            
        Returns:
            دیکشنری حاوی اطلاعات ویدیو یا None در صورت خطا
        """
        return await youtube_extractor.extract_video_info(url)
    
    async def get_download_options(self, url: str) -> List[Dict]:
        """
        دریافت گزینه‌های دانلود ویدیوی یوتیوب
        
        Args:
            url: آدرس ویدیوی یوتیوب
            
        Returns:
            لیست گزینه‌های دانلود قابل ارائه به کاربر
        """
        # استفاده از ماژول youtube_extractor برای دریافت گزینه‌ها
        options = await youtube_extractor.get_download_options(url)
        logger.info(f"تعداد گزینه‌های دانلود: {len(options)}")
        return options
    
    async def download_video(self, url: str, quality: str = "best") -> Optional[str]:
        """
        دانلود ویدیوی یوتیوب
        
        Args:
            url: آدرس ویدیوی یوتیوب
            quality: کیفیت مورد نظر
            
        Returns:
            مسیر فایل دانلود شده یا None در صورت خطا
        """
        logger.info(f"شروع دانلود ویدیو با کیفیت {quality}: {url}")
        
        # برای اطمینان از دریافت ویدیو (نه صدا)، از روش‌های مختلف استفاده می‌کنیم
        
        # روش 1: استفاده از ماژول youtube_extractor
        try:
            result = await youtube_extractor.download_youtube_video(url, quality)
            if self._verify_video_file(result):
                logger.info(f"دانلود با روش 1 (youtube_extractor) موفق: {result}")
                return result
        except Exception as e:
            logger.error(f"خطا در دانلود با روش 1: {str(e)}")
        
        # روش 2: استفاده از ماژول direct_youtube_downloader
        try:
            # این ماژول async نیست، پس باید در thread pool اجرا شود
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: direct_youtube_downloader.download_video(url, quality, self.download_dir)
            )
            if self._verify_video_file(result):
                logger.info(f"دانلود با روش 2 (direct_youtube_downloader) موفق: {result}")
                return result
        except Exception as e:
            logger.error(f"خطا در دانلود با روش 2: {str(e)}")
        
        # روش 3: استفاده از ویژگی force_video
        try:
            video_id = youtube_extractor.get_video_id(url) or "unknown"
            output_path = os.path.join(self.download_dir, f"yt_force_{quality}_{video_id}.mp4")
            await self._download_with_force_video(url, quality, output_path)
            if self._verify_video_file(output_path):
                logger.info(f"دانلود با روش 3 (force_video) موفق: {output_path}")
                return output_path
        except Exception as e:
            logger.error(f"خطا در دانلود با روش 3: {str(e)}")
        
        logger.error(f"تمام روش‌های دانلود ویدیو شکست خوردند: {url}")
        return None
    
    async def download_audio(self, url: str) -> Optional[str]:
        """
        دانلود صدای ویدیوی یوتیوب
        
        Args:
            url: آدرس ویدیوی یوتیوب
            
        Returns:
            مسیر فایل دانلود شده یا None در صورت خطا
        """
        logger.info(f"شروع دانلود صدا: {url}")
        
        # روش 1: استفاده از ماژول youtube_extractor
        try:
            result = await youtube_extractor.download_youtube_audio(url)
            if result and os.path.exists(result):
                logger.info(f"دانلود صدا با روش 1 (youtube_extractor) موفق: {result}")
                return result
        except Exception as e:
            logger.error(f"خطا در دانلود صدا با روش 1: {str(e)}")
        
        # روش 2: استفاده از ماژول direct_youtube_downloader
        try:
            # این ماژول async نیست، پس باید در thread pool اجرا شود
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: direct_youtube_downloader.download_audio(url, self.download_dir)
            )
            if result and os.path.exists(result):
                logger.info(f"دانلود صدا با روش 2 (direct_youtube_downloader) موفق: {result}")
                return result
        except Exception as e:
            logger.error(f"خطا در دانلود صدا با روش 2: {str(e)}")
        
        # روش 3: دانلود ویدیو و استخراج صدا
        try:
            video_file = await self.download_video(url, "best")
            if video_file and os.path.exists(video_file):
                audio_file = await youtube_extractor.extract_audio_from_video(video_file)
                if audio_file and os.path.exists(audio_file):
                    logger.info(f"دانلود صدا با روش 3 (استخراج از ویدیو) موفق: {audio_file}")
                    return audio_file
        except Exception as e:
            logger.error(f"خطا در دانلود صدا با روش 3: {str(e)}")
        
        logger.error(f"تمام روش‌های دانلود صدا شکست خوردند: {url}")
        return None
    
    def _verify_video_file(self, file_path: Optional[str]) -> bool:
        """
        بررسی می‌کند که فایل یک ویدیوی معتبر است
        
        Args:
            file_path: مسیر فایل
            
        Returns:
            True اگر فایل یک ویدیوی معتبر است، در غیر این صورت False
        """
        if not file_path or not os.path.exists(file_path):
            return False
        
        # بررسی پسوند فایل
        if not file_path.lower().endswith(('.mp4', '.mkv', '.webm', '.avi', '.mov')):
            return False
        
        # بررسی سایز فایل
        file_size = os.path.getsize(file_path)
        if file_size < 10000:  # کمتر از 10KB
            return False
        
        return True
    
    async def _download_with_force_video(self, url: str, quality: str, output_path: str) -> Optional[str]:
        """
        دانلود ویدیو با اجبار به دریافت ویدیو (نه صدا)
        
        Args:
            url: آدرس ویدیوی یوتیوب
            quality: کیفیت مورد نظر
            output_path: مسیر ذخیره‌سازی
            
        Returns:
            مسیر فایل دانلود شده یا None در صورت خطا
        """
        import yt_dlp
        
        # ارتفاع متناظر با کیفیت
        height_map = {
            "1080p": 1080,
            "720p": 720, 
            "480p": 480,
            "360p": 360,
            "240p": 240,
            "best": 0  # بدون محدودیت ارتفاع
        }
        
        height = height_map.get(quality, 720)
        
        # فرمت خاص برای تضمین دریافت ویدیو
        if height > 0:
            format_spec = (
                f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
                f"bestvideo[height<={height}]+bestaudio/"
                f"best[height<={height}][ext=mp4]/"
                f"best[ext=mp4]/"
                f"best"
            )
        else:
            format_spec = (
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
                "bestvideo+bestaudio/"
                "best[ext=mp4]/"
                "best"
            )
        
        # تنظیمات yt-dlp
        ydl_opts = {
            'format': format_spec,
            'outtmpl': {'default': output_path},
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': False,
            'nocheckcertificate': True,
            'noplaylist': True,
            'ffmpeg_location': youtube_extractor.FFMPEG_PATH,
            'merge_output_format': 'mp4',
            'postprocessors': [],  # بدون پس‌پردازش‌های اضافی
        }
        
        try:
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await loop.run_in_executor(None, ydl.download, [url])
            
            if os.path.exists(output_path):
                return output_path
        except Exception as e:
            logger.error(f"خطا در دانلود با force_video: {str(e)}")
        
        return None
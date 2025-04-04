#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
بهینه‌سازی دانلودر یوتیوب

این ماژول عملکرد دانلود ویدیوهای یوتیوب را به‌طور قابل توجهی بهبود می‌بخشد.
"""

import os
import logging
import threading
import subprocess
import yt_dlp
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple, Any, Callable

# تنظیم لاگر
logger = logging.getLogger(__name__)

class YouTubeDownloaderOptimizer:
    """کلاس بهینه‌سازی دانلودر یوتیوب"""
    
    def __init__(self):
        """مقداردهی اولیه بهینه‌ساز"""
        # تنظیمات اصلی
        self.concurrent_downloads = min(os.cpu_count() or 4, 8)  # حداکثر 8 دانلود همزمان
        self.fragment_threads = min(os.cpu_count() or 4, 16)  # حداکثر 16 نخ برای هر دانلود
        
        # کش بهینه‌سازی شده
        self.format_cache = {}  # کش فرمت‌های ویدیو برای جلوگیری از درخواست‌های تکراری
        
        # پارامترهای فراداده
        self.metadata_params = {
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {'youtube': {'player_client': ['android']}},
        }
        
        # قفل برای دسترسی همزمان به کش
        self.cache_lock = threading.Lock()
        
        # ایجاد تنظیمات بهینه برای yt-dlp
        self._configure_ytdlp()
        
        logger.info("بهینه‌ساز دانلودر یوتیوب راه‌اندازی شد")
    
    def _configure_ytdlp(self) -> None:
        """تنظیم yt-dlp برای بهترین عملکرد"""
        # روی‌نویسی تنظیمات پیش‌فرض yt-dlp
        yt_dlp.utils.std_headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-User': '?1',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
        })
        
        # تنظیم مسیر ffmpeg
        self._set_ffmpeg_path()
        
        # غیرفعال کردن disabled_aria
        os.environ['YDL_NO_disabled_downloader'] = '1'
        os.environ['YTDLP_NO_disabled_aria'] = '1'
        
        logger.debug("تنظیمات yt-dlp با موفقیت بهینه‌سازی شد")
    
    def _set_ffmpeg_path(self) -> None:
        """تنظیم مسیر ffmpeg"""
        # مسیر‌های احتمالی ffmpeg
        ffmpeg_paths = [
            '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',  # Replit
            '/usr/bin/ffmpeg',  # لینوکس
            'ffmpeg'  # مسیر سیستم
        ]
        
        # یافتن اولین مسیر معتبر
        for path in ffmpeg_paths:
            if os.path.exists(path) or self._command_exists(path):
                yt_dlp.utils.preferredcodec = path
                break
    
    def _command_exists(self, cmd: str) -> bool:
        """بررسی وجود دستور در سیستم"""
        try:
            subprocess.check_output(['which', cmd], stderr=subprocess.STDOUT)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def get_optimized_options(self, quality: str = 'best') -> Dict[str, Any]:
        """
        دریافت تنظیمات بهینه‌سازی شده برای کیفیت مشخص
        
        Args:
            quality: کیفیت ویدیو ('best', '1080p', '720p', '480p', '360p', '240p', 'audio')
            
        Returns:
            تنظیمات بهینه‌سازی شده
        """
        # تنظیمات پایه با بهینه‌سازی‌های عملکرد
        options = {
            'format_sort': [
                'res:1080',
                'ext:mp4:m4a',
                'codec:h264:aac', 
                'size'
            ],
            'concurrent_fragment_downloads': self.fragment_threads,
            'buffersize': 50 * 1024 * 1024,  # 50 مگابایت بافر
            'http_chunk_size': 10 * 1024 * 1024,  # 10 مگابایت اندازه قطعه
            'fragment_retries': 10,
            'retries': 10,
            'file_access_retries': 5,
            'extractor_retries': 5,
            'throttledratelimit': 0,  # بدون محدودیت سرعت
            'socket_timeout': 30,
            'retry_sleep_functions': {'fragment': lambda n: 0.5},  # تأخیر کم بین تلاش‌های مجدد
            'quiet': True,
            'no_warnings': True,
            'noprogress': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'sleep_interval': 0,
            'max_sleep_interval': 0,
            'live_from_start': True,
        }
        
        # تنظیم فرمت بر اساس کیفیت درخواستی
        if quality == 'audio':
            options['format'] = 'bestaudio[ext=m4a]/bestaudio'
            options['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        elif quality == '1080p':
            options['format'] = 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best'
        elif quality == '720p':
            options['format'] = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best'
        elif quality == '480p':
            options['format'] = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]/best'
        elif quality == '360p':
            options['format'] = 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360]/best'
        elif quality == '240p':
            options['format'] = 'bestvideo[height<=240][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=240]+bestaudio/best[height<=240]/best'
        else:  # بهترین کیفیت
            options['format'] = 'bestvideo+bestaudio/best'
        
        # تنظیمات پیشرفته برای ترکیب ویدیو و صدا
        if quality != 'audio':
            options['merge_output_format'] = 'mp4'
            options['postprocessor_args'] = {
                'ffmpeg': [
                    '-c:v', 'libx264',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-preset', 'ultrafast',
                    '-threads', str(max(1, os.cpu_count() or 2)),
                    '-movflags', '+faststart',
                ]
            }
        
        return options
    
    def patch_ytdlp_downloader(self) -> None:
        """
        اعمال وصله روی دانلودر yt-dlp برای بهبود عملکرد
        """
        try:
            # وصله‌های متنوع برای افزایش سرعت
            # وصله ۱: بهبود کلاس HttpFD برای دانلود سریع‌تر با چندین اتصال
            original_http_fd = yt_dlp.downloader.http.HttpFD
            
            class FastHttpFD(original_http_fd):
                def _start(self, *args, **kwargs):
                    # استفاده از تنظیمات بهینه
                    self.params['buffersize'] = 50 * 1024 * 1024  # 50MB buffer
                    self.params['http_chunk_size'] = 10 * 1024 * 1024  # 10MB chunks
                    return super()._start(*args, **kwargs)
            
            # جایگزینی کلاس اصلی با نسخه بهینه
            yt_dlp.downloader.http.HttpFD = FastHttpFD
            
            logger.info("وصله‌های بهینه‌سازی با موفقیت روی yt-dlp اعمال شد")
            return True
        except Exception as e:
            logger.error(f"خطا در اعمال وصله روی yt-dlp: {e}")
            return False
    
    def optimize_ffmpeg(self) -> None:
        """
        بهینه‌سازی تنظیمات ffmpeg برای ترکیب سریع‌تر ویدیو و صدا
        """
        try:
            # وصله تنظیمات پیش‌فرض ffmpeg در yt-dlp
            if hasattr(yt_dlp.postprocessor.ffmpeg, 'FFmpegPostProcessor'):
                original_init = yt_dlp.postprocessor.ffmpeg.FFmpegPostProcessor.__init__
                
                def optimized_init(self, *args, **kwargs):
                    original_init(self, *args, **kwargs)
                    # افزودن پرچم‌های بهینه‌سازی سرعت به دستورات ffmpeg
                    self._pparams.get('postprocessor_args', {}).setdefault('ffmpeg', [
                        '-c:v', 'libx264',
                        '-preset', 'ultrafast',
                        '-threads', str(max(1, os.cpu_count() or 2)),
                        '-movflags', '+faststart',
                    ])
                
                yt_dlp.postprocessor.ffmpeg.FFmpegPostProcessor.__init__ = optimized_init
                logger.info("تنظیمات ffmpeg با موفقیت بهینه‌سازی شد")
            else:
                logger.warning("کلاس FFmpegPostProcessor در yt-dlp یافت نشد")
        except Exception as e:
            logger.error(f"خطا در بهینه‌سازی ffmpeg: {e}")
    
    def apply_all_optimizations(self) -> bool:
        """
        اعمال تمام بهینه‌سازی‌های ممکن روی سیستم دانلود
        
        Returns:
            موفقیت‌آمیز بودن بهینه‌سازی
        """
        try:
            # پیکربندی yt-dlp
            self._configure_ytdlp()
            
            # اعمال وصله‌ها
            self.patch_ytdlp_downloader()
            
            # بهینه‌سازی ffmpeg
            self.optimize_ffmpeg()
            
            # تنظیم متغیرهای محیطی
            os.environ['YDL_NO_disabled_downloader'] = '1'  # غیرفعال کردن disabled_aria
            os.environ['YTDLP_DOWNLOADER'] = 'native'  # استفاده از دانلودر داخلی
            os.environ['NO_EXTERNAL_DOWNLOADER'] = '1'  # عدم استفاده از دانلودرهای خارجی
            
            logger.info("تمام بهینه‌سازی‌ها با موفقیت اعمال شدند")
            return True
        except Exception as e:
            logger.error(f"خطا در اعمال بهینه‌سازی‌ها: {e}")
            return False

# تابع بهینه‌سازی راحت برای استفاده در سایر ماژول‌ها
def optimize_youtube_downloader() -> bool:
    """
    اعمال تمام بهینه‌سازی‌های ممکن روی دانلودر یوتیوب
    
    Returns:
        bool: موفقیت‌آمیز بودن بهینه‌سازی
    """
    optimizer = YouTubeDownloaderOptimizer()
    return optimizer.apply_all_optimizations()

if __name__ == "__main__":
    # تنظیم لاگر
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # اجرای بهینه‌سازی
    success = optimize_youtube_downloader()
    print(f"نتیجه بهینه‌سازی: {'موفق' if success else 'ناموفق'}")
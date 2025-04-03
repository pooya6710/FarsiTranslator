#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ماژول بهینه‌سازی عملکرد

این ماژول توابع و کلاس‌های مختلف برای بهینه‌سازی عملکرد ربات را ارائه می‌دهد.
"""

import os
import time
import logging
import asyncio
import gc
import tempfile
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple, Any, Optional, Callable
from functools import wraps
import json
import multiprocessing
from multiprocessing import Process, Queue, cpu_count

# تنظیمات لاگر
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# تنظیمات کلی
MAX_WORKERS = max(2, cpu_count() - 1)  # تعداد هسته‌های پردازنده منهای یکی
MAX_MEMORY_USAGE_MB = 500  # حداکثر استفاده از حافظه به مگابایت
CLEANUP_INTERVAL = 3600  # فاصله زمانی پاکسازی خودکار به ثانیه (هر ساعت)
CACHE_MAX_SIZE = 100  # حداکثر تعداد آیتم‌های کش
CACHE_MAX_AGE = 86400  # حداکثر عمر آیتم‌های کش به ثانیه (24 ساعت)
TEMP_DIR = os.path.join(tempfile.gettempdir(), "telegram_bot_tmp")
os.makedirs(TEMP_DIR, exist_ok=True)

# پول اجرایی برای پردازش موازی
thread_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)
logger.info(f"پول اجرایی با {MAX_WORKERS} thread راه‌اندازی شد")

def measure_time(func):
    """دکوراتور برای اندازه‌گیری زمان اجرای یک تابع"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        elapsed_time = time.time() - start_time
        logger.info(f"زمان اجرای {func.__name__}: {elapsed_time:.2f} ثانیه")
        return result
    return wrapper

def run_in_thread_pool(func):
    """دکوراتور برای اجرای یک تابع در پول thread ها"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(thread_pool, lambda: func(*args, **kwargs))
    return wrapper

class MemoryCache:
    """کش حافظه با پاکسازی خودکار"""
    
    def __init__(self, max_size=CACHE_MAX_SIZE, max_age=CACHE_MAX_AGE):
        self.cache = {}
        self.timestamps = {}
        self.max_size = max_size
        self.max_age = max_age
        self.lock = threading.RLock()
        
        # شروع thread پاکسازی
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
    
    def get(self, key):
        """دریافت مقدار از کش"""
        with self.lock:
            if key in self.cache:
                current_time = time.time()
                age = current_time - self.timestamps.get(key, 0)
                if age <= self.max_age:
                    # بروزرسانی timestamp
                    self.timestamps[key] = current_time
                    return self.cache[key]
                else:
                    # حذف آیتم منقضی شده
                    del self.cache[key]
                    del self.timestamps[key]
        return None
    
    def set(self, key, value):
        """ذخیره مقدار در کش"""
        with self.lock:
            # حذف قدیمی‌ترین آیتم‌ها اگر کش پر است
            if len(self.cache) >= self.max_size:
                self._remove_oldest_items(1)
            
            # ذخیره مقدار جدید
            self.cache[key] = value
            self.timestamps[key] = time.time()
    
    def clear(self):
        """پاکسازی کل کش"""
        with self.lock:
            self.cache.clear()
            self.timestamps.clear()
    
    def _remove_oldest_items(self, count=1):
        """حذف قدیمی‌ترین آیتم‌ها"""
        if not self.timestamps:
            return
            
        # مرتب‌سازی آیتم‌ها بر اساس زمان
        sorted_keys = sorted(self.timestamps.items(), key=lambda x: x[1])
        
        # حذف قدیمی‌ترین‌ها
        for key, _ in sorted_keys[:count]:
            if key in self.cache:
                del self.cache[key]
            if key in self.timestamps:
                del self.timestamps[key]
    
    def _cleanup_expired(self):
        """پاکسازی آیتم‌های منقضی شده"""
        with self.lock:
            current_time = time.time()
            expired_keys = [key for key, timestamp in self.timestamps.items() 
                          if current_time - timestamp > self.max_age]
            
            for key in expired_keys:
                if key in self.cache:
                    del self.cache[key]
                if key in self.timestamps:
                    del self.timestamps[key]
            
            return len(expired_keys)
    
    def _cleanup_loop(self):
        """حلقه پاکسازی خودکار که در thread جداگانه اجرا می‌شود"""
        while True:
            time.sleep(CLEANUP_INTERVAL)
            try:
                count = self._cleanup_expired()
                logger.info(f"پاکسازی خودکار کش: {count} آیتم حذف شد")
            except Exception as e:
                logger.error(f"خطا در پاکسازی کش: {e}")

# ایجاد نمونه‌های کش
url_cache = MemoryCache()  # کش برای URL ها
download_cache = MemoryCache()  # کش برای فایل‌های دانلود شده
options_cache = MemoryCache()  # کش برای گزینه‌های دانلود

class MemoryMonitor:
    """کلاس نظارت بر مصرف حافظه"""
    
    @staticmethod
    def get_memory_usage_mb():
        """دریافت میزان مصرف حافظه به مگابایت"""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            return memory_info.rss / 1024 / 1024  # تبدیل به مگابایت
        except ImportError:
            # اگر psutil نصب نشده باشد، از gc استفاده می‌کنیم
            gc.collect()
            return 0
    
    @staticmethod
    def optimize_memory():
        """بهینه‌سازی مصرف حافظه در صورت نیاز"""
        memory_usage = MemoryMonitor.get_memory_usage_mb()
        
        if memory_usage > MAX_MEMORY_USAGE_MB:
            # پاکسازی حافظه
            gc.collect()
            
            # پاکسازی فایل‌های موقت
            try:
                for filename in os.listdir(TEMP_DIR):
                    file_path = os.path.join(TEMP_DIR, filename)
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                    except Exception as e:
                        logger.error(f"خطا در حذف فایل موقت {file_path}: {e}")
            except Exception as e:
                logger.error(f"خطا در پاکسازی دایرکتوری موقت: {e}")
            
            # پاکسازی بخشی از کش‌ها
            url_cache._remove_oldest_items(10)
            download_cache._remove_oldest_items(10)
            options_cache._remove_oldest_items(10)
            
            new_usage = MemoryMonitor.get_memory_usage_mb()
            logger.info(f"بهینه‌سازی حافظه: {memory_usage:.1f}MB -> {new_usage:.1f}MB")
            
            return True
        return False

class NetworkOptimizer:
    """کلاس بهینه‌سازی شبکه"""
    
    @staticmethod
    def optimize_yt_dlp_settings(settings):
        """بهینه‌سازی تنظیمات yt-dlp برای بهبود سرعت دانلود"""
        optimized = settings.copy()
        
        # اضافه کردن تنظیمات بهینه‌سازی شده
        optimized.update({
            'fragment_retries': 10,  # تلاش مجدد در صورت خطا در دانلود قطعه
            'retries': 5,  # تعداد تلاش مجدد در صورت خطا
            'file_access_retries': 5,  # تلاش مجدد در صورت خطا در دسترسی به فایل
            'buffersize': 1024 * 16,  # افزایش سایز بافر
            'http_chunk_size': 10485760,  # تنظیم اندازه قطعه HTTP (10MB)
            'concurrent_fragment_downloads': min(cpu_count() * 2, 10),  # دانلود همزمان قطعات
            'socket_timeout': 30,  # تنظیم timeout سوکت
            'verbose': False,  # غیرفعال کردن گزارش‌های verbose
            'quiet': True,  # کاهش لاگ‌ها
            'progress_hooks': [],  # حذف hook های اضافی
        })
        
        return optimized
    
    @staticmethod
    def get_optimal_chunk_size():
        """محاسبه اندازه بهینه قطعه برای دانلود"""
        # تنظیم اندازه قطعه بر اساس تعداد پردازنده و حافظه
        base_size = 1024 * 1024  # 1MB
        
        # افزایش اندازه قطعه بر اساس تعداد پردازنده‌ها
        cpu_factor = min(cpu_count(), 8) / 4
        
        # محاسبه اندازه نهایی
        return int(base_size * cpu_factor)

class FFmpegOptimizer:
    """کلاس بهینه‌سازی FFmpeg"""
    
    @staticmethod
    def get_optimal_settings(quality=None, is_audio=False, input_file=None):
        """دریافت تنظیمات بهینه FFmpeg بر اساس سیستم و نوع پردازش"""
        settings = []
        
        # تنظیمات عمومی برای همه حالت‌ها
        settings.extend(['-hide_banner', '-y'])
        
        # تنظیمات مختص پلتفرم
        if input_file and os.path.exists(input_file):
            try:
                # آنالیز فایل ورودی
                import subprocess
                result = subprocess.run(
                    ['/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffprobe', '-v', 'quiet', '-print_format', 'json', 
                    '-show_format', '-show_streams', input_file],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                
                if result.returncode == 0:
                    info = json.loads(result.stdout)
                    
                    # بررسی اطلاعات استریم
                    streams = info.get('streams', [])
                    video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
                    audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)
                    
                    if is_audio and audio_stream:
                        # تنظیمات خاص برای استخراج صدا
                        settings.extend([
                            '-vn',  # حذف ویدیو
                            '-acodec', 'libmp3lame',  # کدک MP3
                            '-ar', '44100',  # نرخ نمونه‌برداری
                            '-ac', '2',  # تعداد کانال‌ها (استریو)
                            '-b:a', '192k',  # بیت‌ریت
                        ])
                    elif not is_audio and video_stream:
                        # تنظیمات بهینه برای کدگذاری ویدیو
                        settings.extend([
                            '-c:v', 'libx264',  # کدک ویدیو
                            '-preset', 'fast',  # تنظیم سرعت/کیفیت
                            '-crf', '23',  # کیفیت ثابت (بالاتر = فشرده‌تر)
                            '-c:a', 'aac',  # کدک صدا
                            '-b:a', '128k',  # بیت‌ریت صدا
                        ])
                        
                        # اضافه کردن تنظیمات مختص کیفیت
                        if quality == '1080p':
                            settings.extend(['-vf', 'scale=-2:1080'])
                        elif quality == '720p':
                            settings.extend(['-vf', 'scale=-2:720'])
                        elif quality == '480p':
                            settings.extend(['-vf', 'scale=-2:480'])
                        elif quality == '360p':
                            settings.extend(['-vf', 'scale=-2:360'])
                        elif quality == '240p':
                            settings.extend(['-vf', 'scale=-2:240'])
            except Exception as e:
                logger.error(f"خطا در آنالیز فایل ورودی: {e}")
        
        # تنظیمات بهینه‌سازی عملکرد CPU
        settings.extend(['-threads', str(min(cpu_count(), 4))])
        
        return settings

class AsyncTaskManager:
    """مدیریت تسک‌های آسنکرون"""
    
    def __init__(self, max_concurrent=10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.tasks = set()
    
    async def run(self, coro):
        """اضافه کردن و اجرای یک وظیفه آسنکرون با نظارت"""
        async with self.semaphore:
            task = asyncio.create_task(coro)
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
            return await task

# نمونه مدیر تسک جهانی
task_manager = AsyncTaskManager()

def init_performance_optimizations():
    """راه‌اندازی بهینه‌سازی‌های عملکرد"""
    # اطمینان از وجود پوشه‌های لازم
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    # شروع نظارت بر حافظه
    threading.Thread(target=memory_monitor_loop, daemon=True).start()
    
    logger.info("بهینه‌سازی‌های عملکرد با موفقیت راه‌اندازی شدند")
    return True

def memory_monitor_loop():
    """حلقه نظارت بر حافظه که در یک thread جداگانه اجرا می‌شود"""
    while True:
        try:
            memory_usage = MemoryMonitor.get_memory_usage_mb()
            if memory_usage > MAX_MEMORY_USAGE_MB * 0.8:  # 80% از حداکثر
                logger.warning(f"مصرف حافظه بالا: {memory_usage:.1f}MB")
                MemoryMonitor.optimize_memory()
            
            # پاکسازی دوره‌ای فایل‌های موقت
            cleanup_temp_files()
            
        except Exception as e:
            logger.error(f"خطا در حلقه نظارت بر حافظه: {e}")
        
        time.sleep(300)  # بررسی هر 5 دقیقه

def cleanup_temp_files(max_age=86400):  # حداکثر 1 روز
    """پاکسازی فایل‌های موقت قدیمی"""
    try:
        now = time.time()
        removed_count = 0
        
        for filename in os.listdir(TEMP_DIR):
            file_path = os.path.join(TEMP_DIR, filename)
            try:
                if os.path.isfile(file_path):
                    file_age = now - os.path.getmtime(file_path)
                    if file_age > max_age:
                        os.unlink(file_path)
                        removed_count += 1
            except Exception as e:
                logger.error(f"خطا در حذف فایل موقت {file_path}: {e}")
        
        if removed_count > 0:
            logger.info(f"پاکسازی فایل‌های موقت: {removed_count} فایل حذف شد")
        
        return removed_count
    except Exception as e:
        logger.error(f"خطا در پاکسازی فایل‌های موقت: {e}")
        return 0

# راه‌اندازی بهینه‌سازی‌های عملکرد در صورت اجرای مستقیم این فایل
if __name__ == "__main__":
    init_performance_optimizations()
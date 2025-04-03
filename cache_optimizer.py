"""
بهینه‌سازی حافظه کش ربات تلگرام

این اسکریپت برای مدیریت بهتر حافظه کش و فایل‌های دانلود شده طراحی شده است.
"""

import os
import glob
import time
import logging
import shutil
from typing import List, Tuple
from pathlib import Path

# تنظیم لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# مسیر دایرکتوری دانلودها
DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
CACHE_EXPIRE_DAYS = 3  # تعداد روزهای نگهداری فایل‌ها در کش
MAX_CACHE_SIZE_MB = 1000  # حداکثر حجم کش (مگابایت)

def get_file_info(file_path: str) -> Tuple[float, float]:
    """
    دریافت اطلاعات فایل: زمان آخرین دسترسی و اندازه
    
    Args:
        file_path: مسیر فایل
        
    Returns:
        tuple: (زمان آخرین دسترسی، اندازه فایل به مگابایت)
    """
    stat_info = os.stat(file_path)
    return (stat_info.st_atime, stat_info.st_size / (1024 * 1024))

def find_expired_files() -> List[str]:
    """
    یافتن فایل‌هایی که از تاریخ انقضا گذشته‌اند
    
    Returns:
        list: لیست مسیرهای فایل‌های منقضی شده
    """
    expired_files = []
    now = time.time()
    expire_seconds = CACHE_EXPIRE_DAYS * 24 * 60 * 60
    
    try:
        if not os.path.exists(DOWNLOADS_DIR):
            return []
            
        for file_path in glob.glob(os.path.join(DOWNLOADS_DIR, "**/*"), recursive=True):
            if not os.path.isfile(file_path):
                continue
                
            atime, _ = get_file_info(file_path)
            if now - atime > expire_seconds:
                expired_files.append(file_path)
    except Exception as e:
        logger.error(f"خطا در یافتن فایل‌های منقضی: {e}")
        
    return expired_files

def check_cache_size() -> Tuple[float, List[Tuple[str, float, float]]]:
    """
    بررسی اندازه کل کش و لیست فایل‌ها با اطلاعات آن‌ها
    
    Returns:
        tuple: (اندازه کل کش، لیست فایل‌ها با اطلاعات آن‌ها)
    """
    total_size = 0
    files_info = []
    
    try:
        if not os.path.exists(DOWNLOADS_DIR):
            return (0, [])
            
        for file_path in glob.glob(os.path.join(DOWNLOADS_DIR, "**/*"), recursive=True):
            if not os.path.isfile(file_path):
                continue
                
            atime, size_mb = get_file_info(file_path)
            total_size += size_mb
            files_info.append((file_path, atime, size_mb))
    except Exception as e:
        logger.error(f"خطا در بررسی اندازه کش: {e}")
        
    return (total_size, files_info)

def clean_expired_files() -> int:
    """
    پاکسازی فایل‌های منقضی شده
    
    Returns:
        int: تعداد فایل‌های پاک شده
    """
    expired_files = find_expired_files()
    count = 0
    
    for file_path in expired_files:
        try:
            os.remove(file_path)
            count += 1
            logger.info(f"فایل منقضی حذف شد: {file_path}")
        except Exception as e:
            logger.error(f"خطا در حذف فایل {file_path}: {e}")
            
    return count

def optimize_cache_size() -> int:
    """
    بهینه‌سازی اندازه کش با حذف قدیمی‌ترین فایل‌ها
    در صورتی که اندازه کش از حد مجاز بیشتر باشد
    
    Returns:
        int: تعداد فایل‌های پاک شده
    """
    total_size, files_info = check_cache_size()
    count = 0
    
    if total_size <= MAX_CACHE_SIZE_MB:
        return 0
        
    # مرتب‌سازی بر اساس زمان آخرین دسترسی (قدیمی‌ترین فایل‌ها اول)
    files_info.sort(key=lambda x: x[1])
    
    for file_path, _, size_mb in files_info:
        try:
            os.remove(file_path)
            count += 1
            total_size -= size_mb
            logger.info(f"فایل از کش حذف شد برای آزادسازی فضا: {file_path}")
            
            if total_size <= MAX_CACHE_SIZE_MB:
                break
        except Exception as e:
            logger.error(f"خطا در حذف فایل {file_path}: {e}")
            
    return count

def remove_empty_directories() -> int:
    """
    حذف دایرکتوری‌های خالی در پوشه دانلودها
    
    Returns:
        int: تعداد دایرکتوری‌های پاک شده
    """
    count = 0
    
    try:
        if not os.path.exists(DOWNLOADS_DIR):
            return 0
            
        for dirpath, dirnames, filenames in os.walk(DOWNLOADS_DIR, topdown=False):
            if dirpath == DOWNLOADS_DIR:
                continue
                
            if not dirnames and not filenames:
                os.rmdir(dirpath)
                count += 1
                logger.info(f"دایرکتوری خالی حذف شد: {dirpath}")
    except Exception as e:
        logger.error(f"خطا در حذف دایرکتوری‌های خالی: {e}")
        
    return count

def cleanup_temp_files() -> int:
    """
    پاکسازی فایل‌های موقت yt-dlp و دیگر فایل‌های موقت
    
    Returns:
        int: تعداد فایل‌های پاک شده
    """
    count = 0
    temp_patterns = [
        "/tmp/youtube_cookies_*.txt",
        "/tmp/ytdlp_temp/*",
        "/tmp/*.part",
        "/tmp/*.ytdl",
        "/tmp/*.webm.part",
        "/tmp/*.mp4.part"
    ]
    
    for pattern in temp_patterns:
        for file_path in glob.glob(pattern):
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    count += 1
            except Exception as e:
                logger.error(f"خطا در حذف فایل موقت {file_path}: {e}")
                
    return count

def run_optimization():
    """
    اجرای تمام عملیات بهینه‌سازی
    """
    logger.info("شروع بهینه‌سازی کش...")
    
    # ایجاد دایرکتوری دانلودها اگر وجود ندارد
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    
    # پاکسازی فایل‌های منقضی
    expired_count = clean_expired_files()
    logger.info(f"{expired_count} فایل منقضی شده پاکسازی شد.")
    
    # بهینه‌سازی اندازه کش
    size_count = optimize_cache_size()
    logger.info(f"{size_count} فایل برای کاهش اندازه کش پاکسازی شد.")
    
    # حذف دایرکتوری‌های خالی
    dir_count = remove_empty_directories()
    logger.info(f"{dir_count} دایرکتوری خالی حذف شد.")
    
    # پاکسازی فایل‌های موقت
    temp_count = cleanup_temp_files()
    logger.info(f"{temp_count} فایل موقت پاکسازی شد.")
    
    total_size, _ = check_cache_size()
    logger.info(f"اندازه نهایی کش: {total_size:.2f} مگابایت")
    
    logger.info("بهینه‌سازی کش با موفقیت انجام شد.")

if __name__ == "__main__":
    run_optimization()
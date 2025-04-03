#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
بهینه‌سازی کش دانلودها

این ماژول سیستم کش دانلود‌ها را بهبود می‌بخشد و مدیریت فایل‌های موقت را بهینه می‌کند.
"""

import os
import shutil
import logging
import datetime
import json
from typing import Dict, List, Optional, Tuple
import time

# تنظیم لاگر
logger = logging.getLogger(__name__)

# مسیر دایرکتوری دانلود
DOWNLOADS_DIR = os.environ.get('DOWNLOAD_DIR', 'downloads')
# مسیر دایرکتوری دیباگ
DEBUG_DIR = os.path.join(DOWNLOADS_DIR, 'debug')
# زمان پاکسازی کش (به روز)
CACHE_CLEANUP_DAYS = 2
# حداکثر اندازه کش (به گیگابایت)
MAX_CACHE_SIZE_GB = 5
# حداقل فضای خالی مورد نیاز (به گیگابایت)
MIN_FREE_SPACE_GB = 1

# اطمینان از وجود دایرکتوری دیباگ
os.makedirs(DEBUG_DIR, exist_ok=True)

def get_cache_size() -> Tuple[float, int]:
    """
    محاسبه حجم کل و تعداد فایل‌های کش
    
    Returns:
        tuple: (اندازه به گیگابایت, تعداد فایل‌ها)
    """
    total_size = 0
    file_count = 0
    
    for dirpath, _, filenames in os.walk(DOWNLOADS_DIR):
        for f in filenames:
            # رد کردن فایل‌های دیباگ
            if 'debug' in dirpath:
                continue
                
            fp = os.path.join(dirpath, f)
            if os.path.exists(fp) and os.path.isfile(fp):
                total_size += os.path.getsize(fp)
                file_count += 1
                
    # تبدیل به گیگابایت
    total_size_gb = total_size / (1024 * 1024 * 1024)
    return total_size_gb, file_count

def get_free_space_gb() -> float:
    """
    محاسبه فضای خالی دیسک به گیگابایت
    
    Returns:
        float: فضای خالی به گیگابایت
    """
    if hasattr(os, 'statvfs'):  # فقط در سیستم‌های یونیکس
        statvfs = os.statvfs(DOWNLOADS_DIR)
        free_space = statvfs.f_frsize * statvfs.f_bavail
        return free_space / (1024 * 1024 * 1024)
    else:
        # برای ویندوز یا سیستم‌های دیگر، مقدار پیش‌فرض برگردانده می‌شود
        return 10.0

def get_file_age_days(file_path: str) -> float:
    """
    محاسبه عمر فایل به روز
    
    Args:
        file_path: مسیر فایل
        
    Returns:
        float: عمر فایل به روز
    """
    if not os.path.exists(file_path):
        return 0
        
    mtime = os.path.getmtime(file_path)
    age_seconds = time.time() - mtime
    return age_seconds / (24 * 3600)  # تبدیل به روز

def cleanup_cache(force: bool = False) -> int:
    """
    پاکسازی فایل‌های قدیمی از کش
    
    Args:
        force: اجبار به پاکسازی بدون در نظر گرفتن زمان آخرین پاکسازی
        
    Returns:
        int: تعداد فایل‌های پاک شده
    """
    # زمان آخرین پاکسازی را بررسی می‌کنیم
    last_cleanup_file = os.path.join(DEBUG_DIR, 'last_cleanup.txt')
    
    # اگر اجباری نیست، بررسی زمان آخرین پاکسازی
    if not force and os.path.exists(last_cleanup_file):
        try:
            with open(last_cleanup_file, 'r') as f:
                last_cleanup_str = f.read().strip()
                last_cleanup = float(last_cleanup_str)
                hours_since_cleanup = (time.time() - last_cleanup) / 3600
                
                if hours_since_cleanup < 24:  # فقط یک بار در روز پاکسازی
                    logger.info(f"پاکسازی اخیراً انجام شده است ({hours_since_cleanup:.2f} ساعت قبل)")
                    
                    # نوشتن گزارش وضعیت کش
                    write_cache_status_report()
                    
                    return 0
        except (ValueError, IOError):
            # اگر فایل معتبر نیست، ادامه می‌دهیم
            pass
    
    # محاسبه اندازه کش
    cache_size_gb, file_count = get_cache_size()
    free_space_gb = get_free_space_gb()
    
    logger.info(f"اندازه فعلی کش: {cache_size_gb:.2f} GB ({file_count} فایل)")
    logger.info(f"فضای خالی: {free_space_gb:.2f} GB")
    
    # بررسی نیاز به پاکسازی
    need_cleanup = (cache_size_gb > MAX_CACHE_SIZE_GB or 
                   free_space_gb < MIN_FREE_SPACE_GB or 
                   force)
    
    if not need_cleanup:
        logger.info("نیازی به پاکسازی کش نیست")
        
        # بروزرسانی زمان آخرین پاکسازی
        with open(last_cleanup_file, 'w') as f:
            f.write(str(time.time()))
            
        # نوشتن گزارش وضعیت کش
        write_cache_status_report()
        
        return 0
    
    # جمع‌آوری فایل‌ها برای پاکسازی
    files_to_delete = []
    
    for dirpath, dirnames, filenames in os.walk(DOWNLOADS_DIR):
        # رد کردن دایرکتوری دیباگ
        if 'debug' in dirpath:
            continue
            
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            
            # بررسی عمر فایل
            age_days = get_file_age_days(file_path)
            
            if age_days > CACHE_CLEANUP_DAYS:
                files_to_delete.append((file_path, age_days))
    
    # مرتب‌سازی بر اساس عمر (قدیمی‌ترین‌ها اول)
    files_to_delete.sort(key=lambda x: x[1], reverse=True)
    
    # حذف فایل‌ها
    deleted_count = 0
    deleted_size = 0
    
    for file_path, age in files_to_delete:
        try:
            file_size = os.path.getsize(file_path)
            os.remove(file_path)
            deleted_count += 1
            deleted_size += file_size
            
            logger.debug(f"فایل حذف شد: {file_path} (عمر: {age:.1f} روز)")
            
            # بررسی کافی بودن پاکسازی
            if deleted_count % 10 == 0:
                cache_size_gb, _ = get_cache_size()
                free_space_gb = get_free_space_gb()
                
                if (cache_size_gb < MAX_CACHE_SIZE_GB * 0.8 and 
                    free_space_gb > MIN_FREE_SPACE_GB * 1.2):
                    break
        except OSError as e:
            logger.warning(f"خطا در حذف فایل {file_path}: {e}")
    
    # بروزرسانی زمان آخرین پاکسازی
    with open(last_cleanup_file, 'w') as f:
        f.write(str(time.time()))
    
    deleted_mb = deleted_size / (1024 * 1024)
    logger.info(f"پاکسازی کش انجام شد: {deleted_count} فایل ({deleted_mb:.2f} MB) حذف شد")
    
    # نوشتن گزارش وضعیت کش
    write_cache_status_report()
    
    return deleted_count

def write_cache_status_report() -> str:
    """
    نوشتن گزارش وضعیت کش در فایل متنی
    
    Returns:
        str: مسیر فایل گزارش
    """
    # ایجاد نام فایل با تاریخ و زمان
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    debug_file = os.path.join(DEBUG_DIR, f"debug_log_{now}.txt")
    
    cache_size_gb, file_count = get_cache_size()
    free_space_gb = get_free_space_gb()
    
    with open(debug_file, 'w', encoding='utf-8') as f:
        f.write("===== گزارش وضعیت کش =====\n")
        f.write(f"تاریخ و زمان: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"اندازه کش: {cache_size_gb:.2f} GB\n")
        f.write(f"تعداد فایل‌ها: {file_count}\n")
        f.write(f"فضای خالی: {free_space_gb:.2f} GB\n")
        f.write(f"حداکثر اندازه مجاز کش: {MAX_CACHE_SIZE_GB} GB\n")
        f.write(f"حداقل فضای خالی مورد نیاز: {MIN_FREE_SPACE_GB} GB\n")
        f.write("\n--- ۱۰ فایل بزرگ کش ---\n")
        
        # یافتن ۱۰ فایل بزرگ کش
        files_info = []
        for dirpath, _, filenames in os.walk(DOWNLOADS_DIR):
            if 'debug' in dirpath:
                continue
                
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    file_size = os.path.getsize(file_path)
                    files_info.append((file_path, file_size))
        
        # مرتب‌سازی بر اساس اندازه (بزرگترین‌ها اول)
        files_info.sort(key=lambda x: x[1], reverse=True)
        
        # نوشتن ۱۰ فایل بزرگ
        for i, (file_path, file_size) in enumerate(files_info[:10]):
            file_size_mb = file_size / (1024 * 1024)
            file_age = get_file_age_days(file_path)
            f.write(f"{i+1}. {file_path} - {file_size_mb:.2f} MB (عمر: {file_age:.1f} روز)\n")
    
    logger.info(f"گزارش وضعیت کش نوشته شد: {debug_file}")
    return debug_file

def optimize_cache() -> bool:
    """
    بهینه‌سازی کامل کش
    
    Returns:
        bool: موفقیت‌آمیز بودن بهینه‌سازی
    """
    try:
        # پاکسازی فایل‌های قدیمی
        deleted_count = cleanup_cache(force=False)
        
        # بهینه‌سازی ساختار دایرکتوری
        organize_download_directory()
        
        logger.info(f"بهینه‌سازی کش با موفقیت انجام شد. {deleted_count} فایل حذف شد.")
        return True
    except Exception as e:
        logger.error(f"خطا در بهینه‌سازی کش: {e}")
        return False

def organize_download_directory() -> None:
    """
    سازماندهی دایرکتوری دانلود بر اساس نوع فایل
    """
    # دایرکتوری‌های مقصد
    video_dir = os.path.join(DOWNLOADS_DIR, 'videos')
    audio_dir = os.path.join(DOWNLOADS_DIR, 'audio')
    instagram_dir = os.path.join(DOWNLOADS_DIR, 'instagram')
    youtube_dir = os.path.join(DOWNLOADS_DIR, 'youtube')
    
    # ایجاد دایرکتوری‌ها
    for dir_path in [video_dir, audio_dir, instagram_dir, youtube_dir]:
        os.makedirs(dir_path, exist_ok=True)
    
    # فایل‌های دایرکتوری اصلی را بررسی می‌کنیم
    for filename in os.listdir(DOWNLOADS_DIR):
        file_path = os.path.join(DOWNLOADS_DIR, filename)
        
        # فقط فایل‌ها را بررسی می‌کنیم (نه دایرکتوری‌ها)
        if not os.path.isfile(file_path):
            continue
            
        # رد کردن فایل‌های دیباگ
        if filename.startswith('debug_') or '.txt' in filename:
            continue
        
        # تعیین نوع فایل و مقصد
        destination = None
        
        if 'instagram' in filename.lower():
            destination = instagram_dir
        elif 'youtube' in filename.lower() or 'yt_' in filename.lower():
            destination = youtube_dir
        elif filename.endswith(('.mp4', '.avi', '.mkv', '.webm', '.mov')):
            destination = video_dir
        elif filename.endswith(('.mp3', '.m4a', '.wav', '.aac', '.opus')):
            destination = audio_dir
            
        # انتقال فایل به دایرکتوری مناسب
        if destination:
            dest_path = os.path.join(destination, filename)
            # اگر فایل از قبل وجود داشت، آن را بازنویسی می‌کنیم
            if os.path.exists(dest_path):
                try:
                    os.remove(dest_path)
                except OSError:
                    continue
                    
            try:
                shutil.move(file_path, dest_path)
                logger.debug(f"فایل منتقل شد: {filename} -> {destination}")
            except OSError as e:
                logger.warning(f"خطا در انتقال فایل {filename}: {e}")

if __name__ == "__main__":
    # تنظیم لاگر
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # اجرای بهینه‌سازی
    optimize_cache()
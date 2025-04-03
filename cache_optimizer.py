"""
بهینه‌سازی حافظه کش و مدیریت فایل‌های موقت

این ماژول روش‌های پیشرفته‌ای برای بهینه‌سازی حافظه کش و مدیریت فایل‌های موقت ارائه می‌دهد.
"""

import os
import time
import shutil
import logging
import tempfile
import threading
from typing import Dict, List, Tuple, Optional, Set, Any
from datetime import datetime, timedelta
import asyncio

# تنظیم لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# تنظیمات پیش‌فرض
DEFAULT_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
DEFAULT_MAX_CACHE_SIZE_MB = 1024 * 5  # 5 گیگابایت
DEFAULT_MAX_FILE_AGE_DAYS = 5  # 5 روز
DEFAULT_CLEANUP_INTERVAL_HOURS = 6  # هر 6 ساعت

# الگوهای فایل‌های موقت
TEMP_FILE_PATTERNS = [
    ".temp", ".tmp", ".part", ".partial",
    "ytdl", "cache", "ffmpeg", "downloaded"
]

# فایل قفل
LOCK_FILE = os.path.join(tempfile.gettempdir(), "cache_optimizer_lock")

# آمار کش
cache_stats = {
    "start_size": 0,  # حجم اولیه
    "current_size": 0,  # حجم فعلی
    "cleaned_files": 0,  # تعداد فایل‌های پاکسازی شده
    "cleaned_size": 0,  # حجم آزادشده
    "last_cleanup": None,  # زمان آخرین پاکسازی
    "cleanup_count": 0  # تعداد دفعات پاکسازی
}

# قفل برای همگام‌سازی
cache_lock = threading.Lock()

class CacheOptimizer:
    """کلاس بهینه‌سازی حافظه کش"""
    
    def __init__(self, 
                cache_dir: str = DEFAULT_CACHE_DIR,
                max_cache_size_mb: int = DEFAULT_MAX_CACHE_SIZE_MB,
                max_file_age_days: int = DEFAULT_MAX_FILE_AGE_DAYS,
                cleanup_interval_hours: int = DEFAULT_CLEANUP_INTERVAL_HOURS):
        """
        مقداردهی اولیه کلاس
        
        Args:
            cache_dir: مسیر دایرکتوری کش
            max_cache_size_mb: حداکثر حجم کش به مگابایت
            max_file_age_days: حداکثر سن فایل‌ها به روز
            cleanup_interval_hours: فاصله زمانی پاکسازی به ساعت
        """
        self.cache_dir = cache_dir
        self.max_cache_size_mb = max_cache_size_mb
        self.max_file_age_days = max_file_age_days
        self.cleanup_interval_hours = cleanup_interval_hours
        
        # ایجاد دایرکتوری کش اگر وجود ندارد
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # زیرپوشه‌های کش
        self.debug_dir = os.path.join(self.cache_dir, "debug")
        os.makedirs(self.debug_dir, exist_ok=True)
    
    def get_cache_size(self) -> int:
        """
        محاسبه حجم فعلی کش به بایت
        
        Returns:
            حجم کش به بایت
        """
        total_size = 0
        
        for dirpath, _, filenames in os.walk(self.cache_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)
                    
        return total_size
    
    def format_size(self, size_bytes: int) -> str:
        """
        تبدیل حجم به واحد خوانا
        
        Args:
            size_bytes: حجم به بایت
            
        Returns:
            رشته حجم با واحد مناسب
        """
        # تبدیل به واحدهای خوانا
        for unit in ['بایت', 'کیلوبایت', 'مگابایت', 'گیگابایت', 'ترابایت']:
            if size_bytes < 1024.0:
                if unit == 'بایت':
                    return f"{size_bytes} {unit}"
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
            
        return f"{size_bytes:.2f} پتابایت"
    
    def is_temp_file(self, filename: str) -> bool:
        """
        بررسی می‌کند که آیا فایل موقتی است
        
        Args:
            filename: نام فایل
            
        Returns:
            True اگر فایل موقتی است، False در غیر این صورت
        """
        for pattern in TEMP_FILE_PATTERNS:
            if pattern in filename:
                return True
                
        # بررسی پسوندهای موقت
        temp_extensions = ['.part', '.temp', '.tmp', '.download']
        for ext in temp_extensions:
            if filename.endswith(ext):
                return True
                
        return False
    
    def get_file_age_days(self, filepath: str) -> float:
        """
        محاسبه سن فایل به روز
        
        Args:
            filepath: مسیر فایل
            
        Returns:
            سن فایل به روز
        """
        try:
            mtime = os.path.getmtime(filepath)
            age_seconds = time.time() - mtime
            return age_seconds / (86400)  # تبدیل ثانیه به روز
        except OSError:
            # در صورت خطا، فرض می‌کنیم فایل قدیمی است
            return float('inf')
    
    def should_delete_file(self, filepath: str) -> Tuple[bool, str]:
        """
        بررسی می‌کند که آیا فایل باید حذف شود
        
        Args:
            filepath: مسیر فایل
            
        Returns:
            (should_delete, reason): آیا فایل باید حذف شود و دلیل آن
        """
        try:
            filename = os.path.basename(filepath)
            
            # حذف فایل‌های با حجم صفر
            if os.path.getsize(filepath) == 0:
                return True, "فایل خالی"
                
            # حذف فایل‌های موقت
            if self.is_temp_file(filename):
                age_days = self.get_file_age_days(filepath)
                if age_days > 1:  # فایل‌های موقت قدیمی‌تر از 1 روز
                    return True, "فایل موقت قدیمی"
                    
            # حذف فایل‌های قدیمی
            age_days = self.get_file_age_days(filepath)
            if age_days > self.max_file_age_days:
                return True, f"فایل قدیمی (بیش از {self.max_file_age_days} روز)"
                
            return False, ""
        except OSError:
            # در صورت خطا در دسترسی به فایل، آن را برای حذف علامت‌گذاری می‌کنیم
            return True, "خطا در دسترسی به فایل"
    
    def cleanup_cache(self, force: bool = False) -> Dict[str, Any]:
        """
        پاکسازی کش
        
        Args:
            force: اجبار به پاکسازی بدون توجه به زمان آخرین پاکسازی
            
        Returns:
            آمار پاکسازی
        """
        global cache_stats
        
        with cache_lock:
            # بررسی زمان آخرین پاکسازی
            if not force and cache_stats["last_cleanup"]:
                last_cleanup = datetime.fromisoformat(cache_stats["last_cleanup"])
                time_since_cleanup = datetime.now() - last_cleanup
                
                if time_since_cleanup < timedelta(hours=self.cleanup_interval_hours):
                    logger.info(f"پاکسازی اخیراً انجام شده است ({time_since_cleanup.total_seconds() / 3600:.2f} ساعت قبل)")
                    return cache_stats
            
            # ثبت حجم اولیه
            initial_size = self.get_cache_size()
            initial_size_mb = initial_size / (1024 * 1024)
            logger.info(f"شروع پاکسازی کش. حجم فعلی: {self.format_size(initial_size)} ({initial_size_mb:.2f} MB)")
            
            # به‌روزرسانی آمار
            cache_stats["start_size"] = initial_size
            cache_stats["last_cleanup"] = datetime.now().isoformat()
            cache_stats["cleanup_count"] += 1
            
            # پاکسازی فایل‌های موقت و قدیمی
            deleted_files = 0
            deleted_size = 0
            
            # مرحله 1: پاکسازی فایل‌های موقت و قدیمی
            for dirpath, _, filenames in os.walk(self.cache_dir):
                for filename in filenames:
                    if "debug" in dirpath:
                        # پردازش متفاوت برای پوشه debug
                        continue
                        
                    filepath = os.path.join(dirpath, filename)
                    
                    should_delete, reason = self.should_delete_file(filepath)
                    if should_delete:
                        try:
                            file_size = os.path.getsize(filepath)
                            os.remove(filepath)
                            logger.debug(f"فایل حذف شد: {filepath} - دلیل: {reason}")
                            deleted_files += 1
                            deleted_size += file_size
                        except OSError as e:
                            logger.warning(f"خطا در حذف فایل {filepath}: {e}")
            
            # مرحله 2: اگر کش هنوز بیش‌تر از حد مجاز است، فایل‌های قدیمی‌تر را حذف می‌کنیم
            if (initial_size - deleted_size) / (1024 * 1024) > self.max_cache_size_mb:
                # جمع‌آوری تمام فایل‌ها با سن آن‌ها
                files_with_age = []
                
                for dirpath, _, filenames in os.walk(self.cache_dir):
                    if "debug" in dirpath:
                        continue
                        
                    for filename in filenames:
                        filepath = os.path.join(dirpath, filename)
                        try:
                            age_days = self.get_file_age_days(filepath)
                            size = os.path.getsize(filepath)
                            files_with_age.append((filepath, age_days, size))
                        except OSError:
                            continue
                
                # مرتب‌سازی فایل‌ها بر اساس سن (قدیمی‌ترین اول)
                files_with_age.sort(key=lambda x: x[1], reverse=True)
                
                # حذف فایل‌ها تا رسیدن به حجم مجاز
                current_size = initial_size - deleted_size
                for filepath, age, size in files_with_age:
                    if current_size / (1024 * 1024) <= self.max_cache_size_mb:
                        break
                        
                    try:
                        os.remove(filepath)
                        logger.debug(f"فایل اضافی حذف شد: {filepath} - سن: {age:.2f} روز")
                        deleted_files += 1
                        deleted_size += size
                        current_size -= size
                    except OSError as e:
                        logger.warning(f"خطا در حذف فایل {filepath}: {e}")
            
            # ثبت آمار پاکسازی
            final_size = self.get_cache_size()
            final_size_mb = final_size / (1024 * 1024)
            
            logger.info(f"پاکسازی کش انجام شد.")
            logger.info(f"تعداد فایل‌های حذف شده: {deleted_files}")
            logger.info(f"فضای آزاد شده: {self.format_size(deleted_size)} ({deleted_size / (1024 * 1024):.2f} MB)")
            logger.info(f"حجم نهایی کش: {self.format_size(final_size)} ({final_size_mb:.2f} MB)")
            
            # به‌روزرسانی آمار
            cache_stats["current_size"] = final_size
            cache_stats["cleaned_files"] += deleted_files
            cache_stats["cleaned_size"] += deleted_size
            
            return cache_stats
    
    def write_debug_log(self) -> str:
        """
        نوشتن گزارش وضعیت کش در فایل گزارش
        
        Returns:
            مسیر فایل گزارش
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(self.debug_dir, f"debug_log_{timestamp}.txt")
        
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"=== گزارش وضعیت کش - {datetime.now().isoformat()} ===\n\n")
            
            # اطلاعات عمومی
            f.write("--- اطلاعات عمومی ---\n")
            f.write(f"مسیر کش: {self.cache_dir}\n")
            cache_size = self.get_cache_size()
            f.write(f"حجم فعلی کش: {self.format_size(cache_size)} ({cache_size / (1024 * 1024):.2f} MB)\n")
            f.write(f"حداکثر حجم مجاز: {self.format_size(self.max_cache_size_mb * 1024 * 1024)} ({self.max_cache_size_mb} MB)\n")
            
            # آمار کش
            f.write("\n--- آمار کش ---\n")
            for key, value in cache_stats.items():
                if key == "start_size" or key == "current_size" or key == "cleaned_size":
                    f.write(f"{key}: {self.format_size(value)} ({value / (1024 * 1024):.2f} MB)\n")
                else:
                    f.write(f"{key}: {value}\n")
                    
            # اطلاعات فایل‌ها
            f.write("\n--- فایل‌های بزرگ (بیش از 50MB) ---\n")
            large_files = []
            
            for dirpath, _, filenames in os.walk(self.cache_dir):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        size = os.path.getsize(filepath)
                        if size > 50 * 1024 * 1024:  # بیش از 50MB
                            age_days = self.get_file_age_days(filepath)
                            large_files.append((filepath, size, age_days))
                    except OSError:
                        continue
                        
            large_files.sort(key=lambda x: x[1], reverse=True)
            
            for filepath, size, age in large_files[:20]:  # فقط 20 فایل بزرگ
                f.write(f"{filepath} - {self.format_size(size)} - {age:.2f} روز\n")
                
            # اطلاعات فایل‌های موقت
            f.write("\n--- فایل‌های موقت ---\n")
            temp_files = []
            
            for dirpath, _, filenames in os.walk(self.cache_dir):
                for filename in filenames:
                    if self.is_temp_file(filename):
                        filepath = os.path.join(dirpath, filename)
                        try:
                            size = os.path.getsize(filepath)
                            age_days = self.get_file_age_days(filepath)
                            temp_files.append((filepath, size, age_days))
                        except OSError:
                            continue
                            
            temp_files.sort(key=lambda x: x[1], reverse=True)
            
            for filepath, size, age in temp_files[:20]:  # فقط 20 فایل موقت
                f.write(f"{filepath} - {self.format_size(size)} - {age:.2f} روز\n")
                
        logger.info(f"گزارش وضعیت کش نوشته شد: {log_path}")
        return log_path
    
    def get_stats(self) -> Dict[str, Any]:
        """
        دریافت آمار کش
        
        Returns:
            آمار کش
        """
        global cache_stats
        
        with cache_lock:
            # به‌روزرسانی حجم فعلی
            current_size = self.get_cache_size()
            cache_stats["current_size"] = current_size
            
            # کپی آمار
            stats = cache_stats.copy()
            
        return stats
    
    def start_background_cleanup(self):
        """راه‌اندازی پاکسازی خودکار در پس‌زمینه"""
        def cleanup_job():
            while True:
                try:
                    # اجرای پاکسازی
                    self.cleanup_cache()
                    
                    # انتظار تا پاکسازی بعدی
                    time.sleep(self.cleanup_interval_hours * 3600)
                except Exception as e:
                    logger.error(f"خطا در پاکسازی خودکار: {e}")
                    time.sleep(3600)  # انتظار 1 ساعت در صورت خطا
        
        # راه‌اندازی ترد پاکسازی
        cleanup_thread = threading.Thread(target=cleanup_job, daemon=True)
        cleanup_thread.start()
        
        logger.info(f"پاکسازی خودکار هر {self.cleanup_interval_hours} ساعت راه‌اندازی شد")

# تابع اصلی پاکسازی
def run_optimization(force: bool = False) -> Dict[str, Any]:
    """
    اجرای بهینه‌سازی کش
    
    Args:
        force: اجبار به پاکسازی بدون توجه به زمان آخرین پاکسازی
        
    Returns:
        آمار پاکسازی
    """
    # ایجاد فایل قفل برای جلوگیری از اجرای همزمان
    if os.path.exists(LOCK_FILE):
        # بررسی سن فایل قفل
        lock_age_seconds = time.time() - os.path.getmtime(LOCK_FILE)
        if lock_age_seconds < 3600:  # اگر قفل کمتر از 1 ساعت قدیمی است
            logger.warning("یک فرآیند پاکسازی دیگر در حال اجراست")
            return {"status": "locked", "lock_age_seconds": lock_age_seconds}
        else:
            # حذف قفل قدیمی
            try:
                os.remove(LOCK_FILE)
            except OSError:
                pass
    
    # ایجاد فایل قفل
    try:
        with open(LOCK_FILE, 'w') as f:
            f.write(str(time.time()))
    except OSError:
        pass
        
    try:
        # اجرای بهینه‌سازی
        optimizer = CacheOptimizer()
        stats = optimizer.cleanup_cache(force)
        
        # نوشتن گزارش وضعیت
        debug_log = optimizer.write_debug_log()
        
        # به‌روزرسانی آمار
        stats["debug_log"] = debug_log
        stats["status"] = "success"
        
        return stats
    except Exception as e:
        logger.error(f"خطا در بهینه‌سازی کش: {e}")
        return {"status": "error", "error": str(e)}
    finally:
        # حذف فایل قفل
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass

async def run_optimization_async(force: bool = False) -> Dict[str, Any]:
    """
    اجرای بهینه‌سازی کش به صورت ناهمگام
    
    Args:
        force: اجبار به پاکسازی بدون توجه به زمان آخرین پاکسازی
        
    Returns:
        آمار پاکسازی
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, run_optimization, force)

# راه‌اندازی پاکسازی خودکار
def start_background_optimization():
    """راه‌اندازی پاکسازی خودکار در پس‌زمینه"""
    optimizer = CacheOptimizer()
    optimizer.start_background_cleanup()
    return {"status": "started"}

# تست و نمونه استفاده
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "force":
        print("اجرای بهینه‌سازی اجباری...")
        stats = run_optimization(force=True)
    else:
        print("اجرای بهینه‌سازی عادی...")
        stats = run_optimization()
        
    print("\nآمار پاکسازی:")
    for key, value in stats.items():
        print(f"{key}: {value}")
        
    # نمایش فضای موجود دیسک
    import shutil
    disk_usage = shutil.disk_usage("/")
    print(f"\nفضای موجود دیسک: {disk_usage.free / (1024 ** 3):.2f} گیگابایت")
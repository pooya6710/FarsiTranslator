"""
بهینه‌سازی تنظیمات yt-dlp

این اسکریپت تنظیمات yt-dlp را برای عملکرد بهتر در محیط‌های با منابع محدود بهینه می‌کند.
به‌ویژه، این اسکریپت تمام اشارات به aria2c را حذف می‌کند تا با محدودیت‌های Railway سازگار باشد.
"""

import os
import sys
import logging
import importlib.util
import tempfile
import shutil
import time
from types import ModuleType
from typing import Dict, Any, List, Optional

# تنظیم لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class YtDlpOptimizer:
    """کلاس بهینه‌سازی تنظیمات yt-dlp"""
    
    def __init__(self):
        """مقداردهی اولیه کلاس"""
        self.ytdlp_module = None
        self.ytdlp_path = None
        self.site_packages_path = None
        self.original_config = {}
        self.temp_files = []
    
    def find_site_packages(self) -> Optional[str]:
        """یافتن مسیر site-packages"""
        try:
            for path in sys.path:
                if path.endswith('site-packages'):
                    logger.info(f"مسیر site-packages یافت شد: {path}")
                    self.site_packages_path = path
                    return path
            
            logger.warning("مسیر site-packages یافت نشد!")
            return None
        except Exception as e:
            logger.error(f"خطا در یافتن مسیر site-packages: {e}")
            return None
    
    def find_ytdlp_module(self) -> Optional[ModuleType]:
        """یافتن و بارگذاری ماژول yt-dlp"""
        try:
            # تلاش برای بارگذاری مستقیم
            try:
                import yt_dlp
                self.ytdlp_module = yt_dlp
                self.ytdlp_path = os.path.dirname(yt_dlp.__file__)
                logger.info(f"ماژول yt-dlp یافت شد: {self.ytdlp_path}")
                return yt_dlp
            except ImportError:
                logger.warning("وارد کردن مستقیم yt-dlp ناموفق بود، تلاش برای یافتن مسیر...")
                
            # اگر بارگذاری مستقیم ناموفق بود، تلاش برای یافتن مسیر ماژول
            if not self.site_packages_path:
                self.find_site_packages()
                
            if self.site_packages_path:
                possible_paths = [
                    os.path.join(self.site_packages_path, 'yt_dlp'),
                    os.path.join(self.site_packages_path, 'yt-dlp')
                ]
                
                for path in possible_paths:
                    if os.path.exists(path) and os.path.isdir(path):
                        self.ytdlp_path = path
                        logger.info(f"دایرکتوری yt-dlp یافت شد: {path}")
                        
                        # بارگذاری ماژول از مسیر
                        spec = importlib.util.spec_from_file_location(
                            "yt_dlp", 
                            os.path.join(path, "__init__.py")
                        )
                        if spec and spec.loader:
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                            self.ytdlp_module = module
                            return module
            
            logger.error("ماژول yt-dlp یافت نشد!")
            return None
        except Exception as e:
            logger.error(f"خطا در یافتن ماژول yt-dlp: {e}")
            return None
    
    def backup_original_config(self) -> bool:
        """ذخیره تنظیمات اصلی yt-dlp"""
        try:
            if not self.ytdlp_module:
                logger.error("ماژول yt-dlp بارگذاری نشده است!")
                return False
                
            # ذخیره تنظیمات مهم
            self.original_config = {
                "external_downloader": getattr(self.ytdlp_module.options, "DEFAULT_PARAMS", {}).get("external_downloader", None),
                "external_downloader_args": getattr(self.ytdlp_module.options, "DEFAULT_PARAMS", {}).get("external_downloader_args", None),
                "concurrent_fragment_downloads": getattr(self.ytdlp_module.options, "DEFAULT_PARAMS", {}).get("concurrent_fragment_downloads", 1),
                "nocheckcertificate": getattr(self.ytdlp_module.options, "DEFAULT_PARAMS", {}).get("nocheckcertificate", False),
                "socket_timeout": getattr(self.ytdlp_module.options, "DEFAULT_PARAMS", {}).get("socket_timeout", 30),
                "retries": getattr(self.ytdlp_module.options, "DEFAULT_PARAMS", {}).get("retries", 10)
            }
            
            logger.info("تنظیمات اصلی yt-dlp با موفقیت ذخیره شد.")
            return True
        except Exception as e:
            logger.error(f"خطا در ذخیره تنظیمات اصلی yt-dlp: {e}")
            return False
    
    def apply_optimized_config(self) -> bool:
        """اعمال تنظیمات بهینه به yt-dlp"""
        try:
            if not self.ytdlp_module:
                logger.error("ماژول yt-dlp بارگذاری نشده است!")
                return False
                
            # تنظیمات بهینه
            optimized_config = {
                "format": "best[filesize<50M]/best",  # محدودیت اندازه فایل برای تلگرام
                "external_downloader": None,  # غیرفعال کردن دانلودر خارجی (aria2c)
                "concurrent_fragment_downloads": 5,  # تعداد دانلود موازی برای تکه‌های ویدیو
                "retries": 5,  # کاهش تلاش‌های مجدد برای سرعت بیشتر
                "socket_timeout": 15,  # کاهش زمان انتظار سوکت
                "sleep_interval_requests": 1,  # فاصله بین درخواست‌ها
                "http_chunk_size": 10485760,  # اندازه چانک HTTP (10 مگابایت)
                "buffersize": 1024,  # اندازه بافر ذخیره‌سازی فایل
                "quiet": True,  # کاهش پیام‌های اضافی
                "progress_hooks": [],  # پاکسازی هوک‌های پیشرفت
                "nocheckcertificate": True,  # عدم بررسی گواهی SSL برای دور زدن برخی محدودیت‌ها
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
            }
            
            # اعمال تنظیمات به DEFAULT_PARAMS
            default_params = getattr(self.ytdlp_module.options, "DEFAULT_PARAMS", {})
            for key, value in optimized_config.items():
                default_params[key] = value
                
            # به‌روزرسانی در ماژول
            self.ytdlp_module.options.DEFAULT_PARAMS = default_params
            
            # تنظیم متغیرهای محیطی
            os.environ["YDL_NO_ARIA2C"] = "1"
            os.environ["HTTP_DOWNLOADER"] = "native"
            os.environ["YTDLP_DOWNLOADER"] = "native"
            os.environ["NO_EXTERNAL_DOWNLOADER"] = "1"
            os.environ["YTDLP_NO_ARIA2"] = "1"
            
            logger.info("تنظیمات بهینه yt-dlp با موفقیت اعمال شد.")
            return True
        except Exception as e:
            logger.error(f"خطا در اعمال تنظیمات بهینه yt-dlp: {e}")
            return False
    
    def disable_aria2c_references(self) -> bool:
        """غیرفعال کردن تمام اشارات به aria2c در کد yt-dlp"""
        try:
            if not self.ytdlp_path:
                logger.error("مسیر yt-dlp تعیین نشده است!")
                return False
                
            # فایل‌های اصلی که نیاز به بررسی دارند
            files_to_patch = [
                os.path.join(self.ytdlp_path, "downloader", "external.py"),
                os.path.join(self.ytdlp_path, "options.py"),
                os.path.join(self.ytdlp_path, "YoutubeDL.py")
            ]
            
            # جایگزینی aria2c در فایل‌ها
            replacements = [
                (r"'aria2c'", r"'disabled_downloader'"),
                (r"\"aria2c\"", r"\"disabled_downloader\""),
                (r"_EXTERNAL_DOWNLOADERS = \{.*?\}", r"_EXTERNAL_DOWNLOADERS = {}", re.DOTALL),
                (r"aria2c", r"disabled_downloader"),
                (r"get_suitable_downloader\(.*?\)", r"None")
            ]
            
            import re
            patched_files = 0
            
            for file_path in files_to_patch:
                if os.path.exists(file_path):
                    # ذخیره نسخه پشتیبان
                    backup_path = file_path + ".backup"
                    shutil.copy2(file_path, backup_path)
                    self.temp_files.append(backup_path)
                    
                    # خواندن محتوای فایل
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # اعمال جایگزینی‌ها
                    original_content = content
                    for pattern_data in replacements:
                        if len(pattern_data) >= 2:
                            pattern = pattern_data[0]
                            replacement = pattern_data[1]
                            flag = 0
                            if len(pattern_data) > 2:
                                # برای سازگاری با re.DOTALL
                                flag = 8  # مقدار re.DOTALL
                            content = re.sub(pattern, replacement, content, flags=flag)
                    
                    # ذخیره فایل اصلاح شده
                    if content != original_content:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        patched_files += 1
            
            if patched_files > 0:
                logger.info(f"{patched_files} فایل با موفقیت اصلاح شد.")
                return True
            else:
                logger.warning("هیچ فایلی نیاز به اصلاح نداشت.")
                return False
        except Exception as e:
            logger.error(f"خطا در غیرفعال کردن اشارات به aria2c: {e}")
            return False
    
    def cleanup(self):
        """پاکسازی فایل‌های موقت"""
        try:
            for file_path in self.temp_files:
                if os.path.exists(file_path):
                    os.remove(file_path)
            logger.info("پاکسازی فایل‌های موقت انجام شد.")
        except Exception as e:
            logger.error(f"خطا در پاکسازی فایل‌های موقت: {e}")
    
    def optimize(self) -> bool:
        """اجرای تمام مراحل بهینه‌سازی"""
        try:
            # یافتن ماژول yt-dlp
            if not self.find_ytdlp_module():
                return False
                
            # ذخیره تنظیمات اصلی
            if not self.backup_original_config():
                return False
                
            # اعمال تنظیمات بهینه
            if not self.apply_optimized_config():
                return False
                
            # غیرفعال کردن اشارات به aria2c
            if not self.disable_aria2c_references():
                # اگر غیرفعال کردن اشارات موفق نبود، می‌توانیم همچنان ادامه دهیم
                logger.warning("غیرفعال کردن اشارات به aria2c ناموفق بود، اما بهینه‌سازی ادامه یافت.")
                
            # سعی در بارگذاری مجدد ماژول
            try:
                if self.ytdlp_module is not None:
                    importlib.reload(self.ytdlp_module)
                    logger.info("ماژول yt-dlp با موفقیت بارگذاری مجدد شد.")
                else:
                    logger.warning("ماژول yt-dlp برای بارگذاری مجدد در دسترس نیست.")
            except Exception as e:
                logger.warning(f"بارگذاری مجدد ماژول yt-dlp ناموفق بود: {e}")
                
            logger.info("بهینه‌سازی yt-dlp با موفقیت انجام شد.")
            return True
        except Exception as e:
            logger.error(f"خطا در بهینه‌سازی yt-dlp: {e}")
            return False
        finally:
            self.cleanup()

def apply_ytdlp_optimization():
    """تابع کمکی برای بهینه‌سازی yt-dlp"""
    optimizer = YtDlpOptimizer()
    return optimizer.optimize()

if __name__ == "__main__":
    print("در حال بهینه‌سازی تنظیمات yt-dlp...")
    success = apply_ytdlp_optimization()
    
    if success:
        print("بهینه‌سازی yt-dlp با موفقیت انجام شد!")
        sys.exit(0)
    else:
        print("بهینه‌سازی yt-dlp ناموفق بود.")
        sys.exit(1)
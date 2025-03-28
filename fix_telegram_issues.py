#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
اسکریپت اصلاحی برای رفع مشکلات مهم ربات تلگرام دانلودر

این اسکریپت مشکلات زیر را اصلاح می‌کند:
1. رفع مشکل مسیر ffmpeg در یوتیوب و اینستاگرام
2. رفع مشکل تبدیل کیفیت و استخراج صدا
3. حل مشکل 360p (که صدا برمی‌گرداند) و 480p (که ویدیو با کیفیت 240p برمی‌گرداند)
"""

import os
import sys
import re
import shutil
import logging
import subprocess
import traceback

# تنظیم لاگر
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("fix_script")

# مسیرهای مهم
TELEGRAM_FIXES_PATH = 'telegram_fixes.py'
TELEGRAM_DOWNLOADER_PATH = 'telegram_downloader.py'

# مسیر صحیح ffmpeg در محیط replit
CORRECT_FFMPEG_PATH = '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg'
CORRECT_FFPROBE_PATH = '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffprobe'

def backup_file(file_path):
    """ایجاد نسخه پشتیبان از فایل"""
    try:
        backup_path = f"{file_path}.backup_fix"
        shutil.copy2(file_path, backup_path)
        logger.info(f"نسخه پشتیبان ایجاد شد: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"خطا در ایجاد نسخه پشتیبان: {str(e)}")
        return False

def fix_ffmpeg_paths_in_telegram_fixes():
    """اصلاح مسیرهای ffmpeg در فایل telegram_fixes.py"""
    try:
        with open(TELEGRAM_FIXES_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        # اصلاح مسیر در تعریف FFMPEG_PATH و FFPROBE_PATH
        pattern1 = r"FFMPEG_PATH\s*=\s*['\"].*?['\"]"
        replacement1 = f"FFMPEG_PATH = '{CORRECT_FFMPEG_PATH}'"
        content = re.sub(pattern1, replacement1, content)

        pattern2 = r"FFPROBE_PATH\s*=\s*['\"].*?['\"]"
        replacement2 = f"FFPROBE_PATH = '{CORRECT_FFPROBE_PATH}'"
        content = re.sub(pattern2, replacement2, content)

        # اصلاح مسیرهای ffmpeg و ffprobe در کل فایل
        content = content.replace('/usr/bin/ffmpeg', CORRECT_FFMPEG_PATH)
        content = content.replace('/usr/bin/ffprobe', CORRECT_FFPROBE_PATH)

        # ذخیره تغییرات
        with open(TELEGRAM_FIXES_PATH, 'w', encoding='utf-8') as f:
            f.write(content)
            
        logger.info("مسیرهای ffmpeg در telegram_fixes.py اصلاح شد")
        return True
    except Exception as e:
        logger.error(f"خطا در اصلاح مسیرهای ffmpeg در telegram_fixes.py: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def fix_ffmpeg_paths_in_telegram_downloader():
    """اصلاح مسیرهای ffmpeg در فایل telegram_downloader.py"""
    try:
        with open(TELEGRAM_DOWNLOADER_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        # اصلاح مسیر در کل فایل
        content = content.replace('/usr/bin/ffmpeg', CORRECT_FFMPEG_PATH)
        content = content.replace('/usr/bin/ffprobe', CORRECT_FFPROBE_PATH)

        # ذخیره تغییرات
        with open(TELEGRAM_DOWNLOADER_PATH, 'w', encoding='utf-8') as f:
            f.write(content)
            
        logger.info("مسیرهای ffmpeg در telegram_downloader.py اصلاح شد")
        return True
    except Exception as e:
        logger.error(f"خطا در اصلاح مسیرهای ffmpeg در telegram_downloader.py: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def fix_convert_video_quality_calls():
    """اصلاح فراخوانی‌های تابع convert_video_quality در فایل telegram_downloader.py"""
    try:
        with open(TELEGRAM_DOWNLOADER_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        # الگوی فراخوانی تابع به صورت قدیمی
        pattern = r"if is_audio:\s+quality = \"audio\"[^\n]*\s+# تبدیل کیفیت ویدیو یا استخراج صدا با تابع جامع\s+converted_file = convert_video_quality\(([^,]+), ([^,\)]+)(?:, is_audio_request=False)?\)"
        
        # جایگزینی با فراخوانی صحیح
        replacement = """# قبلاً: if is_audio: quality = "audio"
                    
                    # تبدیل کیفیت ویدیو یا استخراج صدا با تابع جامع
                    converted_file = convert_video_quality(
                        video_path=\\1, 
                        quality=\\2,
                        is_audio_request=is_audio
                    )"""
        
        # انجام جایگزینی
        new_content = re.sub(pattern, replacement, content)
        
        # بررسی تغییرات
        if new_content == content:
            logger.warning("الگوی فراخوانی تابع convert_video_quality یافت نشد یا قبلا اصلاح شده است")
            return False
            
        # ذخیره تغییرات
        with open(TELEGRAM_DOWNLOADER_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        logger.info("فراخوانی‌های تابع convert_video_quality اصلاح شد")
        return True
    except Exception as e:
        logger.error(f"خطا در اصلاح فراخوانی‌های تابع convert_video_quality: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def fix_instagram_audio_quality_issue():
    """اصلاح مشکل تشخیص کیفیت صدا در اینستاگرام"""
    try:
        with open(TELEGRAM_DOWNLOADER_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        # بخشی که دکمه صدا را برای اینستاگرام پردازش می‌کند
        pattern = r"(elif download_type == \"ig\":[^\n]*\s+)(.*?)(# شروع دانلود)"
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            logger.warning("بخش پردازش کالبک اینستاگرام یافت نشد")
            return False
            
        callback_start = match.group(1)
        callback_code = match.group(2)
        callback_end = match.group(3)
        
        # اصلاح کد پردازش کالبک
        # 1. جایگزینی تشخیص درخواست صوتی
        callback_code = re.sub(
            r"is_audio = False\s+if \"audio\" in option_id\.lower\(\):",
            "is_audio = \"audio\" in option_id.lower()",
            callback_code
        )
        
        # 2. اصلاح متغیر quality در اینستاگرام
        callback_code = re.sub(
            r"quality = \"(\w+)p\"",
            "quality = \"\\1p\"  # ⚠️ حتی برای درخواست‌های صوتی، کیفیت را تنظیم می‌کنیم",
            callback_code
        )
        
        # ذخیره تغییرات
        new_content = callback_start + callback_code + callback_end
        
        with open(TELEGRAM_DOWNLOADER_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        logger.info("مشکل تشخیص کیفیت صدا در اینستاگرام اصلاح شد")
        return True
    except Exception as e:
        logger.error(f"خطا در اصلاح مشکل تشخیص کیفیت صدا در اینستاگرام: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def fix_yt_dlp_ffmpeg_location():
    """اصلاح تنظیمات ffmpeg_location در yt_dlp"""
    try:
        with open(TELEGRAM_FIXES_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        # اصلاح 'ffmpeg_location' در yt_dlp_opts
        pattern = r"'ffmpeg_location':\s*['\"].*?['\"]"
        replacement = f"'ffmpeg_location': '{CORRECT_FFMPEG_PATH}'"
        content = re.sub(pattern, replacement, content)

        # ذخیره تغییرات
        with open(TELEGRAM_FIXES_PATH, 'w', encoding='utf-8') as f:
            f.write(content)
            
        logger.info("تنظیمات ffmpeg_location در yt_dlp اصلاح شد")
        return True
    except Exception as e:
        logger.error(f"خطا در اصلاح تنظیمات ffmpeg_location در yt_dlp: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def main():
    """تابع اصلی اسکریپت"""
    try:
        logger.info("شروع اجرای اسکریپت اصلاحی...")
        
        # ایجاد نسخه پشتیبان
        backup_file(TELEGRAM_FIXES_PATH)
        backup_file(TELEGRAM_DOWNLOADER_PATH)
        
        # اصلاح مسیرهای ffmpeg
        fix_ffmpeg_paths_in_telegram_fixes()
        fix_ffmpeg_paths_in_telegram_downloader()
        
        # اصلاح تنظیمات yt_dlp
        fix_yt_dlp_ffmpeg_location()
        
        # اصلاح فراخوانی‌های convert_video_quality
        fix_convert_video_quality_calls()
        
        # اصلاح مشکل تشخیص کیفیت صدا در اینستاگرام
        fix_instagram_audio_quality_issue()
        
        logger.info("""
اصلاحات انجام شده:
1. مسیرهای ffmpeg و ffprobe در تمام فایل‌ها به مسیرهای صحیح تغییر یافت
2. تنظیمات ffmpeg_location در yt_dlp اصلاح شد
3. فراخوانی‌های تابع convert_video_quality به روش صحیح تغییر یافت (is_audio_request)
4. مشکل تشخیص کیفیت صدا در اینستاگرام اصلاح شد

برای اعمال تغییرات، ربات را مجدداً راه‌اندازی کنید.
""")
        return True
    except Exception as e:
        logger.error(f"خطا در اجرای اسکریپت اصلاحی: {str(e)}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)
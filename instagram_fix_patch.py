#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
پچ اصلاحی برای رفع مشکل کیفیت 360p و درخواست صوتی در اینستاگرام

این اسکریپت باگ‌های مربوط به درخواست صوتی و تبدیل کیفیت را اصلاح می‌کند.
"""

import os
import sys
import logging
import traceback
import argparse
import inspect
import re
import shutil
import tempfile
from typing import Dict, List, Tuple, Any, Optional

# تنظیم لاگینگ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("instagram_fix_patch")

# مسیرهای مهم
TELEGRAM_FIXES_PATH = 'telegram_fixes.py'
TELEGRAM_DOWNLOADER_PATH = 'telegram_downloader.py'

def backup_file(file_path: str) -> bool:
    """ایجاد نسخه پشتیبان از فایل"""
    try:
        backup_path = f"{file_path}.backup"
        shutil.copy2(file_path, backup_path)
        logger.info(f"نسخه پشتیبان ایجاد شد: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"خطا در ایجاد نسخه پشتیبان: {str(e)}")
        return False

def patch_convert_video_quality() -> bool:
    """اصلاح تابع convert_video_quality در telegram_fixes.py"""
    try:
        with open(TELEGRAM_FIXES_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # الگوی تابع convert_video_quality
        pattern = r'def convert_video_quality\(video_path: str, quality: str = "720p"\) -> Optional\[str\]:'
        
        # جایگزینی با پارامتر جدید
        replacement = 'def convert_video_quality(video_path: str, quality: str = "720p", is_audio_request: bool = False) -> Optional[str]:'
        
        # جایگزینی تعریف تابع
        new_content = re.sub(pattern, replacement, content)
        
        # آیا تغییری ایجاد نشد؟
        if new_content == content:
            logger.warning("الگوی تابع convert_video_quality یافت نشد")
            return False
        
        # الگوی شرط تشخیص درخواست صوتی
        audio_pattern = r'if quality == "audio":'
        
        # جایگزینی با شرط جدید
        audio_replacement = 'if is_audio_request or quality == "audio":'
        
        # جایگزینی شرط تشخیص صدا
        new_content = re.sub(audio_pattern, audio_replacement, new_content)
        
        # ذخیره تغییرات
        with open(TELEGRAM_FIXES_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        logger.info("تابع convert_video_quality با موفقیت اصلاح شد")
        return True
    except Exception as e:
        logger.error(f"خطا در اصلاح تابع convert_video_quality: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def patch_download_with_quality() -> bool:
    """اصلاح تابع download_with_quality در telegram_fixes.py"""
    try:
        with open(TELEGRAM_FIXES_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # استخراج بدنه تابع download_with_quality
        pattern = r'async def download_with_quality\([^)]*\)[^{]*:\n(.*?)(?=\n\n[^\s])'
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            logger.warning("بدنه تابع download_with_quality یافت نشد")
            return False
        
        func_body = match.group(1)
        
        # اصلاح فراخوانی تابع convert_video_quality
        convert_pattern = r'converted_file = convert_video_quality\(downloaded_file, quality\)'
        convert_replacement = 'converted_file = convert_video_quality(\n                video_path=downloaded_file,\n                quality=quality,\n                is_audio_request=False\n            )'
        
        updated_body = re.sub(convert_pattern, convert_replacement, func_body)
        
        # اصلاح فراخوانی تابع extract_audio_from_video (برای صورت درخواست صوتی)
        audio_extract_pattern = r'audio_file = extract_audio_from_video\(downloaded_file\)'
        audio_extract_replacement = 'audio_file = convert_video_quality(\n                video_path=downloaded_file,\n                quality="audio",\n                is_audio_request=True\n            )'
        
        updated_body = re.sub(audio_extract_pattern, audio_extract_replacement, updated_body)
        
        # جایگزینی بدنه تابع در کل محتوا
        new_content = content.replace(func_body, updated_body)
        
        # ذخیره تغییرات
        with open(TELEGRAM_FIXES_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        logger.info("تابع download_with_quality با موفقیت اصلاح شد")
        return True
    except Exception as e:
        logger.error(f"خطا در اصلاح تابع download_with_quality: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def fix_instagram_callback() -> bool:
    """اصلاح پردازش کالبک‌های اینستاگرام در telegram_downloader.py"""
    try:
        with open(TELEGRAM_DOWNLOADER_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # یافتن بخش پردازش کالبک اینستاگرام
        pattern = r'elif download_type == "ig":(.*?)(?=\n\s*elif|$)'
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            logger.warning("بخش پردازش کالبک اینستاگرام یافت نشد")
            return False
        
        callback_section = match.group(1)
        
        # اضافه کردن تشخیص صریح درخواست صوتی
        audio_pattern = r'is_audio = False\s+if "audio" in option_id.lower\(\):'
        audio_replacement = 'is_audio_request = "audio" in option_id.lower()'
        
        updated_section = re.sub(audio_pattern, audio_replacement, callback_section)
        
        # اصلاح فراخوانی download_with_quality
        download_pattern = r'downloaded_file = await download_with_quality\(\s+url=url,\s+quality=quality,\s+is_audio=is_audio,\s+source_type="instagram"\s+\)'
        download_replacement = 'downloaded_file = await download_with_quality(\n                    url=url,\n                    quality=quality,\n                    is_audio=is_audio_request,\n                    source_type="instagram"\n                )'
        
        updated_section = re.sub(download_pattern, download_replacement, updated_section)
        
        # جایگزینی بخش در کل محتوا
        new_content = content.replace(callback_section, updated_section)
        
        # ذخیره تغییرات
        with open(TELEGRAM_DOWNLOADER_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        logger.info("پردازش کالبک اینستاگرام با موفقیت اصلاح شد")
        return True
    except Exception as e:
        logger.error(f"خطا در اصلاح پردازش کالبک اینستاگرام: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def find_and_fix_all_convert_video_quality_calls() -> int:
    """یافتن و اصلاح تمام فراخوانی‌های تابع convert_video_quality"""
    try:
        count = 0
        patterns = [
            (r'convert_video_quality\(([^,]+), ([^)]+)\)', r'convert_video_quality(\1, \2, is_audio_request=False)'),
            (r'convert_video_quality\(([^,]+), "audio"\)', r'convert_video_quality(\1, "audio", is_audio_request=True)'),
        ]
        
        # بررسی و اصلاح در telegram_downloader.py
        with open(TELEGRAM_DOWNLOADER_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        new_content = content
        for pattern, replacement in patterns:
            new_content = re.sub(pattern, replacement, new_content)
            
        if new_content != content:
            with open(TELEGRAM_DOWNLOADER_PATH, 'w', encoding='utf-8') as f:
                f.write(new_content)
            count += 1
            logger.info(f"فراخوانی‌های convert_video_quality در {TELEGRAM_DOWNLOADER_PATH} اصلاح شد")
        
        return count
    except Exception as e:
        logger.error(f"خطا در اصلاح فراخوانی‌های convert_video_quality: {str(e)}")
        logger.error(traceback.format_exc())
        return 0

def main():
    """تابع اصلی پچ"""
    try:
        logger.info("شروع اجرای پچ اصلاحی اینستاگرام...")
        
        # ایجاد نسخه پشتیبان
        backup_file(TELEGRAM_FIXES_PATH)
        backup_file(TELEGRAM_DOWNLOADER_PATH)
        
        # اصلاح توابع
        success1 = patch_convert_video_quality()
        success2 = patch_download_with_quality()
        success3 = fix_instagram_callback()
        count = find_and_fix_all_convert_video_quality_calls()
        
        if success1 and success2 and success3:
            logger.info("پچ با موفقیت اعمال شد!")
            logger.info(f"تعداد {count} فراخوانی تابع convert_video_quality اصلاح شد")
            
            logger.info("""
تغییرات انجام شده:
1. اضافه کردن پارامتر is_audio_request به تابع convert_video_quality
2. اصلاح منطق تشخیص درخواست صوتی در تابع download_with_quality
3. اصلاح پردازش کالبک‌های اینستاگرام برای تشخیص دقیق نوع فایل
4. اصلاح تمام فراخوانی‌های تابع convert_video_quality در کل پروژه
""")
            return True
        else:
            logger.warning("برخی از اصلاحات ناموفق بودند.")
            return False
            
    except Exception as e:
        logger.error(f"خطا در اجرای پچ: {str(e)}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)
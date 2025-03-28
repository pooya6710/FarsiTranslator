#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
پچ عیب‌یابی برای ربات تلگرام

این اسکریپت را برای عیب‌یابی و گزارش خطاهای مربوط به تبدیل کیفیت و پردازش ویدیو اجرا کنید.
"""

import os
import json
import sys
import logging
import subprocess
import traceback
from typing import Dict, List, Optional, Any, Tuple
import time
import datetime
from pathlib import Path

# تنظیم لاگینگ پیشرفته
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('debug_log.txt')
    ]
)

logger = logging.getLogger('debug_patch')

# مسیرهای مهم
TELEGRAM_DOWNLOADER_PATH = 'telegram_downloader.py'
TELEGRAM_FIXES_PATH = 'telegram_fixes.py'
DOWNLOADS_DIR = 'downloads'
DEBUG_DIR = os.path.join(DOWNLOADS_DIR, 'debug')

def setup_debug_environment():
    """آماده‌سازی محیط عیب‌یابی"""
    # ایجاد دایرکتوری‌های لازم
    os.makedirs(DEBUG_DIR, exist_ok=True)
    
    # ایجاد فایل لاگ جداگانه با تاریخ
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    debug_log_path = os.path.join(DEBUG_DIR, f'debug_log_{timestamp}.txt')
    file_handler = logging.FileHandler(debug_log_path)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    
    logger.info(f"محیط عیب‌یابی آماده شد. فایل لاگ: {debug_log_path}")
    return debug_log_path

def find_video_files(directory: str = DOWNLOADS_DIR) -> List[str]:
    """پیدا کردن فایل‌های ویدیویی در دایرکتوری"""
    video_extensions = ['.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv']
    video_files = []
    
    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext) for ext in video_extensions):
                video_files.append(os.path.join(root, file))
    
    return video_files

def find_audio_files(directory: str = DOWNLOADS_DIR) -> List[str]:
    """پیدا کردن فایل‌های صوتی در دایرکتوری"""
    audio_extensions = ['.mp3', '.m4a', '.aac', '.wav', '.ogg', '.opus']
    audio_files = []
    
    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext) for ext in audio_extensions):
                audio_files.append(os.path.join(root, file))
    
    return audio_files

def get_file_info(file_path: str) -> Dict:
    """دریافت اطلاعات فایل با استفاده از ffprobe"""
    if not os.path.exists(file_path):
        logger.error(f"فایل وجود ندارد: {file_path}")
        return {}
    
    try:
        # دستور ffprobe برای استخراج همه اطلاعات به فرمت JSON
        cmd = [
            '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            file_path
        ]
        
        logger.debug(f"اجرای دستور ffprobe: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"خطا در اجرای ffprobe: {result.stderr}")
            return {}
            
        # تبدیل خروجی JSON به دیکشنری
        file_info = json.loads(result.stdout)
        
        # خلاصه‌ای از اطلاعات مهم را لاگ می‌کنیم
        for stream in file_info.get('streams', []):
            if stream.get('codec_type') == 'video':
                logger.info(f"اطلاعات استریم ویدیو: " + 
                           f"رزولوشن: {stream.get('width', 'N/A')}x{stream.get('height', 'N/A')}, " +
                           f"کدک: {stream.get('codec_name', 'N/A')}")
            elif stream.get('codec_type') == 'audio':
                logger.info(f"اطلاعات استریم صوتی: " + 
                           f"کدک: {stream.get('codec_name', 'N/A')}, " +
                           f"کانال‌ها: {stream.get('channels', 'N/A')}")
        
        return file_info
    except Exception as e:
        logger.error(f"خطا در استخراج اطلاعات فایل: {str(e)}")
        logger.error(traceback.format_exc())
        return {}

def analyze_video_file(file_path: str) -> Dict:
    """تحلیل کامل فایل ویدیویی"""
    result = {
        "file_path": file_path,
        "file_size": 0,
        "duration": 0,
        "has_video": False,
        "has_audio": False,
        "video_info": {},
        "audio_info": {},
        "format_info": {},
        "is_valid": False
    }
    
    if not os.path.exists(file_path):
        logger.error(f"فایل وجود ندارد: {file_path}")
        return result
    
    # دریافت حجم فایل
    result["file_size"] = os.path.getsize(file_path)
    
    # دریافت اطلاعات فایل
    file_info = get_file_info(file_path)
    if not file_info:
        logger.error(f"نمی‌توان اطلاعات فایل را دریافت کرد: {file_path}")
        return result
    
    # استخراج اطلاعات مورد نیاز
    result["format_info"] = file_info.get('format', {})
    result["duration"] = float(result["format_info"].get('duration', 0))
    
    # بررسی استریم‌های ویدیو و صدا
    for stream in file_info.get('streams', []):
        if stream.get('codec_type') == 'video':
            result["has_video"] = True
            result["video_info"] = stream
        elif stream.get('codec_type') == 'audio':
            result["has_audio"] = True
            result["audio_info"] = stream
    
    # اگر حداقل یکی از استریم‌های ویدیو یا صدا وجود داشته باشد، فایل معتبر است
    result["is_valid"] = result["has_video"] or result["has_audio"]
    
    return result

def test_convert_video_quality(input_file: str, quality: str) -> Dict:
    """تست تبدیل کیفیت ویدیو با کیفیت مشخص"""
    result = {
        "input_file": input_file,
        "quality": quality,
        "output_file": None,
        "success": False,
        "error": None,
        "ffmpeg_output": None,
        "converted_info": None,
        "original_info": None
    }
    
    if not os.path.exists(input_file):
        result["error"] = f"فایل ورودی وجود ندارد: {input_file}"
        return result
    
    try:
        # دریافت اطلاعات فایل اصلی
        original_info = analyze_video_file(input_file)
        result["original_info"] = original_info
        
        if not original_info["is_valid"]:
            result["error"] = "فایل ورودی نامعتبر است"
            return result
        
        # تعیین ارتفاع متناسب با کیفیت
        target_height = {
            "1080p": 1080,
            "720p": 720,
            "480p": 480,
            "360p": 360,
            "240p": 240
        }.get(quality, 720)
        
        # ایجاد نام فایل خروجی
        timestamp = int(time.time())
        output_file = os.path.join(DEBUG_DIR, f"converted_{quality}_{timestamp}.mp4")
        result["output_file"] = output_file
        
        # تنظیم دستور ffmpeg
        cmd = [
            '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',
            '-i', input_file,
            '-c:v', 'libx264',
            '-c:a', 'copy',
            '-vf', f'scale=trunc(oh*a/2)*2:{target_height}',  # تضمین عرض زوج
            '-preset', 'fast',
            '-y',
            output_file
        ]
        
        logger.info(f"اجرای دستور ffmpeg: {' '.join(cmd)}")
        
        # اجرای دستور
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        result["ffmpeg_output"] = process.stderr
        
        if process.returncode != 0:
            result["error"] = f"خطا در اجرای ffmpeg: کد خروجی {process.returncode}"
            logger.error(result["error"])
            logger.error(process.stderr)
            return result
        
        # بررسی وجود فایل خروجی
        if not os.path.exists(output_file):
            result["error"] = "فایل خروجی ایجاد نشد"
            return result
        
        # بررسی حجم فایل خروجی
        if os.path.getsize(output_file) < 1000:  # کمتر از 1 کیلوبایت
            result["error"] = "فایل خروجی خیلی کوچک است"
            return result
        
        # تحلیل فایل خروجی
        converted_info = analyze_video_file(output_file)
        result["converted_info"] = converted_info
        
        if not converted_info["is_valid"]:
            result["error"] = "فایل خروجی نامعتبر است"
            return result
        
        # بررسی نتیجه تبدیل
        if not converted_info["has_video"]:
            result["error"] = "فایل خروجی ویدیو ندارد"
            return result
        
        actual_height = converted_info["video_info"].get("height")
        if not actual_height:
            result["error"] = "نمی‌توان ارتفاع خروجی را تعیین کرد"
            return result
        
        logger.info(f"تبدیل کیفیت انجام شد: ارتفاع مورد نظر={target_height}, ارتفاع واقعی={actual_height}")
        
        # تبدیل موفق
        result["success"] = True
        return result
    except Exception as e:
        logger.error(f"خطای غیرمنتظره در تبدیل کیفیت: {str(e)}")
        logger.error(traceback.format_exc())
        result["error"] = f"خطای غیرمنتظره: {str(e)}"
        return result

def test_extract_audio(input_file: str) -> Dict:
    """تست استخراج صدا از ویدیو"""
    result = {
        "input_file": input_file,
        "output_file": None,
        "success": False,
        "error": None,
        "ffmpeg_output": None,
        "audio_info": None,
        "original_info": None
    }
    
    if not os.path.exists(input_file):
        result["error"] = f"فایل ورودی وجود ندارد: {input_file}"
        return result
    
    try:
        # دریافت اطلاعات فایل اصلی
        original_info = analyze_video_file(input_file)
        result["original_info"] = original_info
        
        if not original_info["is_valid"]:
            result["error"] = "فایل ورودی نامعتبر است"
            return result
        
        if not original_info["has_audio"]:
            result["error"] = "فایل ورودی صدا ندارد"
            return result
        
        # ایجاد نام فایل خروجی
        timestamp = int(time.time())
        output_file = os.path.join(DEBUG_DIR, f"audio_{timestamp}.mp3")
        result["output_file"] = output_file
        
        # تنظیم دستور ffmpeg
        cmd = [
            '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',
            '-i', input_file,
            '-vn',  # بدون ویدیو
            '-acodec', 'libmp3lame',
            '-ab', '192k',
            '-ar', '44100',
            '-ac', '2',
            '-y',
            output_file
        ]
        
        logger.info(f"اجرای دستور ffmpeg برای استخراج صدا: {' '.join(cmd)}")
        
        # اجرای دستور
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        result["ffmpeg_output"] = process.stderr
        
        if process.returncode != 0:
            result["error"] = f"خطا در اجرای ffmpeg: کد خروجی {process.returncode}"
            logger.error(result["error"])
            logger.error(process.stderr)
            return result
        
        # بررسی وجود فایل خروجی
        if not os.path.exists(output_file):
            result["error"] = "فایل خروجی ایجاد نشد"
            return result
        
        # بررسی حجم فایل خروجی
        if os.path.getsize(output_file) < 1000:  # کمتر از 1 کیلوبایت
            result["error"] = "فایل صوتی خروجی خیلی کوچک است"
            return result
        
        # تحلیل فایل خروجی
        audio_info = analyze_video_file(output_file)
        result["audio_info"] = audio_info
        
        if not audio_info["is_valid"]:
            result["error"] = "فایل صوتی خروجی نامعتبر است"
            return result
        
        # بررسی نتیجه استخراج
        if not audio_info["has_audio"]:
            result["error"] = "فایل خروجی صدا ندارد"
            return result
        
        logger.info(f"استخراج صدا انجام شد: فرمت={audio_info['audio_info'].get('codec_name', 'نامشخص')}")
        
        # استخراج موفق
        result["success"] = True
        return result
    except Exception as e:
        logger.error(f"خطای غیرمنتظره در استخراج صدا: {str(e)}")
        logger.error(traceback.format_exc())
        result["error"] = f"خطای غیرمنتظره: {str(e)}"
        return result

def check_telegram_downloader_issues():
    """بررسی مشکلات بالقوه در کد ربات تلگرام"""
    issues = []
    
    try:
        if not os.path.exists(TELEGRAM_DOWNLOADER_PATH):
            issues.append(f"فایل {TELEGRAM_DOWNLOADER_PATH} وجود ندارد")
            return issues
        
        # بررسی الگوهای مشکل‌دار
        problem_patterns = [
            {
                "pattern": "if \"audio\" in option_id.lower():",
                "issue": "تشخیص فایل صوتی بر اساس شناسه گزینه به تنهایی می‌تواند گمراه‌کننده باشد",
                "suggestion": "بررسی دقیق‌تر با چند شرط مختلف"
            },
            {
                "pattern": "quality = \"audio\"",
                "issue": "تنظیم quality به مقدار 'audio' ممکن است باعث سردرگمی شود",
                "suggestion": "استفاده از متغیر جداگانه برای تعیین نوع فایل"
            },
            {
                "pattern": "is_audio = downloaded_file.endswith",
                "issue": "تشخیص نوع فایل بر اساس پسوند فایل می‌تواند نادرست باشد",
                "suggestion": "استفاده از منطق مشخص برای تعیین نوع خروجی"
            }
        ]
        
        with open(TELEGRAM_DOWNLOADER_PATH, "r", encoding="utf-8") as f:
            content = f.read()
            
        for issue in problem_patterns:
            if issue["pattern"] in content:
                issues.append(f"مشکل: {issue['issue']} | پیشنهاد: {issue['suggestion']}")
                
        return issues
    except Exception as e:
        logger.error(f"خطا در بررسی مشکلات کد: {str(e)}")
        issues.append(f"خطا در بررسی کد: {str(e)}")
        return issues

def check_telegram_fixes_issues():
    """بررسی مشکلات بالقوه در کد ماژول اصلاحات"""
    issues = []
    
    try:
        if not os.path.exists(TELEGRAM_FIXES_PATH):
            issues.append(f"فایل {TELEGRAM_FIXES_PATH} وجود ندارد")
            return issues
        
        # بررسی الگوهای مشکل‌دار
        problem_patterns = [
            {
                "pattern": "scale=",
                "issue": "مشکل احتمالی در نحوه استفاده از scale در ffmpeg",
                "suggestion": "بررسی دقیق پارامترهای scale برای اطمینان از عرض زوج"
            },
            {
                "pattern": "if quality == \"audio\":",
                "issue": "تصمیم‌گیری فقط بر اساس مقدار quality",
                "suggestion": "استفاده از پارامتر جداگانه برای تعیین نوع خروجی"
            }
        ]
        
        with open(TELEGRAM_FIXES_PATH, "r", encoding="utf-8") as f:
            content = f.read()
            
        for issue in problem_patterns:
            if issue["pattern"] in content:
                issues.append(f"مشکل در {TELEGRAM_FIXES_PATH}: {issue['issue']} | پیشنهاد: {issue['suggestion']}")
                
        return issues
    except Exception as e:
        logger.error(f"خطا در بررسی مشکلات کد: {str(e)}")
        issues.append(f"خطا در بررسی کد: {str(e)}")
        return issues

def main():
    """اجرای اصلی عیب‌یابی"""
    try:
        logger.info("شروع عیب‌یابی پیشرفته...")
        
        # آماده‌سازی محیط
        debug_log_path = setup_debug_environment()
        logger.info(f"فایل لاگ عیب‌یابی: {debug_log_path}")
        
        # بررسی مشکلات کد
        td_issues = check_telegram_downloader_issues()
        tf_issues = check_telegram_fixes_issues()
        
        all_issues = td_issues + tf_issues
        
        if all_issues:
            logger.info(f"تعداد {len(all_issues)} مشکل بالقوه در کد پیدا شد:")
            for i, issue in enumerate(all_issues, 1):
                logger.info(f"{i}. {issue}")
        else:
            logger.info("هیچ مشکل مشخصی در ساختار کد پیدا نشد.")
        
        # جستجوی فایل‌های ویدیویی
        video_files = find_video_files()
        logger.info(f"تعداد {len(video_files)} فایل ویدیویی پیدا شد.")
        
        # اگر فایل ویدیویی پیدا شد، اولین نمونه را برای تست استفاده می‌کنیم
        if video_files:
            test_file = video_files[0]
            logger.info(f"استفاده از فایل {test_file} برای تست...")
            
            # تحلیل فایل ویدیویی
            file_analysis = analyze_video_file(test_file)
            logger.info("== تحلیل فایل ویدیویی ==")
            logger.info(f"مسیر: {test_file}")
            logger.info(f"حجم: {file_analysis['file_size'] / 1024:.2f} کیلوبایت")
            logger.info(f"مدت: {file_analysis['duration']:.2f} ثانیه")
            logger.info(f"دارای ویدیو: {file_analysis['has_video']}")
            logger.info(f"دارای صدا: {file_analysis['has_audio']}")
            
            if file_analysis["has_video"]:
                resolution = f"{file_analysis['video_info'].get('width', 'N/A')}x{file_analysis['video_info'].get('height', 'N/A')}"
                logger.info(f"رزولوشن: {resolution}")
            
            # تست تبدیل کیفیت
            qualities_to_test = ["360p", "480p"]
            for quality in qualities_to_test:
                logger.info(f"\n== تست تبدیل به کیفیت {quality} ==")
                result = test_convert_video_quality(test_file, quality)
                
                if result["success"]:
                    logger.info(f"تبدیل به کیفیت {quality} موفق بود!")
                    conversion_change = "بدون تغییر"
                    
                    if (result["original_info"]["video_info"].get("height") != 
                        result["converted_info"]["video_info"].get("height")):
                        old_res = f"{result['original_info']['video_info'].get('width', 'N/A')}x{result['original_info']['video_info'].get('height', 'N/A')}"
                        new_res = f"{result['converted_info']['video_info'].get('width', 'N/A')}x{result['converted_info']['video_info'].get('height', 'N/A')}"
                        conversion_change = f"تغییر رزولوشن از {old_res} به {new_res}"
                    
                    logger.info(f"نتیجه تبدیل: {conversion_change}")
                else:
                    logger.error(f"تبدیل به کیفیت {quality} ناموفق بود: {result['error']}")
            
            # تست استخراج صدا
            logger.info("\n== تست استخراج صدا ==")
            audio_result = test_extract_audio(test_file)
            
            if audio_result["success"]:
                logger.info("استخراج صدا موفق بود!")
                logger.info(f"فایل صوتی: {audio_result['output_file']}")
                logger.info(f"حجم: {os.path.getsize(audio_result['output_file']) / 1024:.2f} کیلوبایت")
            else:
                logger.error(f"استخراج صدا ناموفق بود: {audio_result['error']}")
        else:
            logger.warning("هیچ فایل ویدیویی برای تست پیدا نشد.")
            
        # تست نمونه‌های خاص مشکل‌دار
        logger.info("\n=== تست‌های عمومی مشکلات شایع ===")
        
        # مشکل 1: عرض فرد
        logger.info("- تست مشکل عرض فرد (width not divisible by 2):")
        logger.info("این مشکل زمانی رخ می‌دهد که عرض ویدیو فرد باشد و باعث خطای ffmpeg می‌شود.")
        logger.info("راه حل: استفاده از 'scale=trunc(oh*a/2)*2:height' برای تضمین عرض زوج.")
        
        # مشکل 2: تشخیص نادرست نوع فایل
        logger.info("- تست مشکل تشخیص نوع فایل:")
        logger.info("این مشکل زمانی رخ می‌دهد که فقط از پسوند فایل برای تشخیص نوع استفاده شود.")
        logger.info("راه حل: تصمیم‌گیری مستقیم بر اساس انتخاب کاربر و پارامتر is_audio.")
        
        # مشکل 3: تبدیل کیفیت نامناسب
        logger.info("- تست مشکل تبدیل کیفیت نامناسب:")
        logger.info("این مشکل زمانی رخ می‌دهد که پارامترهای ffmpeg نامناسب باشند.")
        logger.info("راه حل: استفاده از پارامترهای ساده و مطمئن برای حفظ کیفیت و سازگاری.")
        
        logger.info("\n=== توصیه‌های نهایی ===")
        logger.info("1. استفاده از متغیرهای جداگانه و صریح برای تعیین نوع خروجی (صوتی یا ویدیویی)")
        logger.info("2. بازنویسی کامل منطق تشخیص نوع فایل با اولویت انتخاب کاربر")
        logger.info("3. استفاده از دستورات ffmpeg ساده و مطمئن با تنظیمات مناسب")
        logger.info("4. افزودن بررسی و تأیید فایل خروجی برای اطمینان از صحت عملیات")
        
        logger.info("\nعیب‌یابی به پایان رسید. نتایج کامل در فایل لاگ ذخیره شده است.")
        return True
    except Exception as e:
        logger.error(f"خطا در اجرای عیب‌یابی: {str(e)}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    main()
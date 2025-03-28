#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ماژول عیب‌یابی ویدیو

این ماژول شامل ابزارهای پیشرفته برای عیب‌یابی مشکلات تبدیل کیفیت ویدیو
و تشخیص نوع فایل است.
"""

import os
import subprocess
import logging
import json
import uuid
import time
import traceback
from typing import Dict, List, Tuple, Optional, Any

# تنظیم لاگر
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("video_debugger")

# مسیر ffmpeg
FFMPEG_PATH = '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg'
FFPROBE_PATH = '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffprobe'

def get_video_info(video_path: str) -> Dict:
    """
    دریافت اطلاعات کامل ویدیو با استفاده از ffprobe
    
    Args:
        video_path: مسیر فایل ویدیویی
        
    Returns:
        دیکشنری حاوی اطلاعات جامع ویدیو
    """
    if not os.path.exists(video_path):
        logger.error(f"فایل وجود ندارد: {video_path}")
        return {}
        
    try:
        # دستور ffprobe برای استخراج همه اطلاعات به فرمت JSON
        cmd = [
            FFPROBE_PATH,
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            video_path
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
        video_info = json.loads(result.stdout)
        
        # خلاصه‌ای از اطلاعات مهم را لاگ می‌کنیم
        for stream in video_info.get('streams', []):
            if stream.get('codec_type') == 'video':
                logger.info(f"اطلاعات استریم ویدیو: " + 
                           f"رزولوشن: {stream.get('width')}x{stream.get('height')}, " +
                           f"کدک: {stream.get('codec_name')}, " +
                           f"فرمت پیکسل: {stream.get('pix_fmt')}")
            elif stream.get('codec_type') == 'audio':
                logger.info(f"اطلاعات استریم صوتی: " + 
                           f"کدک: {stream.get('codec_name')}, " +
                           f"کانال‌ها: {stream.get('channels')}, " +
                           f"نرخ نمونه‌برداری: {stream.get('sample_rate')}")
        
        return video_info
    except Exception as e:
        logger.error(f"خطا در استخراج اطلاعات ویدیو: {str(e)}")
        logger.error(traceback.format_exc())
        return {}

def convert_video_with_debug(input_path: str, output_path: str, quality: str) -> bool:
    """
    تبدیل کیفیت ویدیو با گزارش دقیق پیشرفت و خطاها
    
    Args:
        input_path: مسیر فایل ورودی
        output_path: مسیر فایل خروجی
        quality: کیفیت هدف (1080p, 720p, 480p, 360p, 240p)
        
    Returns:
        True در صورت موفقیت، False در صورت خطا
    """
    if not os.path.exists(input_path):
        logger.error(f"فایل ورودی وجود ندارد: {input_path}")
        return False
        
    try:
        # ابتدا اطلاعات فایل ورودی را دریافت می‌کنیم
        input_info = get_video_info(input_path)
        if not input_info:
            logger.error("نمی‌توان اطلاعات فایل ورودی را دریافت کرد")
            return False
            
        # استخراج ارتفاع هدف بر اساس کیفیت
        target_height = {
            "1080p": 1080,
            "720p": 720,
            "480p": 480,
            "360p": 360,
            "240p": 240
        }.get(quality, 720)  # مقدار پیش‌فرض 720p
        
        logger.info(f"شروع تبدیل ویدیو به کیفیت {quality} (ارتفاع: {target_height})")
        
        # دستور ffmpeg برای تبدیل کیفیت - روش ساده و مطمئن
        cmd = [
            FFMPEG_PATH,
            '-i', input_path,
            '-c:v', 'libx264',
            '-c:a', 'copy',
            '-vf', f'scale=trunc(oh*a/2)*2:{target_height}',  # تضمین عرض زوج
            '-preset', 'fast',
            '-y',
            output_path
        ]
        
        # لاگ کامل دستور
        logger.debug(f"دستور ffmpeg: {' '.join(cmd)}")
        
        # اجرای دستور با ثبت خروجی کامل
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # خط‌به‌خط بافر شود
            universal_newlines=True
        )
        
        # پردازش خروجی خط به خط
        for line in process.stderr:
            line = line.strip()
            if "frame=" in line and "fps=" in line:
                # خط پیشرفت - فقط هر 100 فریم لاگ می‌کنیم تا لاگ بیش از حد نشود
                if "frame=" in line and "fps=" in line:
                    frames = line.split("frame=")[1].split("fps=")[0].strip()
                    if frames.isdigit() and int(frames) % 100 == 0:
                        logger.debug(f"پیشرفت: {line}")
            elif "Error" in line or "Invalid" in line or "Failed" in line:
                # خطای مهم
                logger.error(f"خطای ffmpeg: {line}")
            elif "width not divisible by 2" in line:
                # خطای عرض نامناسب
                logger.error(f"خطای عرض نامناسب: {line}")
        
        # منتظر اتمام پردازش می‌مانیم
        process.wait()
        
        # بررسی نتیجه
        if process.returncode == 0 and os.path.exists(output_path):
            output_info = get_video_info(output_path)
            if output_info:
                # بررسی کیفیت خروجی
                output_height = None
                for stream in output_info.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        output_height = stream.get('height')
                        break
                
                if output_height:
                    logger.info(f"تبدیل کیفیت ویدیو موفق: ارتفاع هدف: {target_height}, ارتفاع خروجی: {output_height}")
                    return True
                else:
                    logger.error("تبدیل انجام شد اما نمی‌توان ارتفاع خروجی را تعیین کرد")
            else:
                logger.error("تبدیل انجام شد اما نمی‌توان اطلاعات فایل خروجی را دریافت کرد")
        else:
            logger.error(f"خطا در تبدیل کیفیت ویدیو: کد خروجی {process.returncode}")
            
        return False
    except Exception as e:
        logger.error(f"خطای غیرمنتظره در تبدیل کیفیت ویدیو: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def extract_audio_with_debug(input_path: str, output_path: str) -> bool:
    """
    استخراج صدا از ویدیو با گزارش دقیق
    
    Args:
        input_path: مسیر فایل ویدیویی ورودی
        output_path: مسیر فایل صوتی خروجی
        
    Returns:
        True در صورت موفقیت، False در صورت خطا
    """
    if not os.path.exists(input_path):
        logger.error(f"فایل ورودی وجود ندارد: {input_path}")
        return False
        
    try:
        # ابتدا بررسی می‌کنیم که فایل ورودی صدا دارد یا خیر
        input_info = get_video_info(input_path)
        has_audio = False
        for stream in input_info.get('streams', []):
            if stream.get('codec_type') == 'audio':
                has_audio = True
                logger.info(f"فایل ورودی دارای صدا است: کدک={stream.get('codec_name')}")
                break
                
        if not has_audio:
            logger.warning("فایل ورودی هیچ استریم صوتی ندارد!")
        
        # دستور ffmpeg برای استخراج صدا - روش ساده و مطمئن
        cmd = [
            FFMPEG_PATH,
            '-i', input_path,
            '-vn',  # بدون ویدیو
            '-acodec', 'libmp3lame',
            '-ab', '192k',
            '-ar', '44100',
            '-ac', '2',
            '-y',  # جایگزینی فایل موجود
            output_path
        ]
        
        # لاگ کامل دستور
        logger.debug(f"دستور ffmpeg: {' '.join(cmd)}")
        
        # اجرای دستور با ثبت خروجی کامل
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # خط‌به‌خط بافر شود
            universal_newlines=True
        )
        
        # پردازش خروجی خط به خط
        for line in process.stderr:
            line = line.strip()
            if "time=" in line:
                # خط پیشرفت - فقط هر 10 ثانیه لاگ می‌کنیم
                if "time=" in line:
                    time_parts = line.split("time=")[1].split()[0].split(":")
                    if len(time_parts) == 3:
                        seconds = int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + float(time_parts[2])
                        if int(seconds) % 10 == 0:
                            logger.debug(f"پیشرفت استخراج صدا: {line}")
            elif "Error" in line or "Invalid" in line or "Failed" in line:
                # خطای مهم
                logger.error(f"خطای ffmpeg: {line}")
        
        # منتظر اتمام پردازش می‌مانیم
        process.wait()
        
        # بررسی نتیجه
        if process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            output_info = get_video_info(output_path)
            if output_info:
                # بررسی کیفیت خروجی
                for stream in output_info.get('streams', []):
                    if stream.get('codec_type') == 'audio':
                        logger.info(f"استخراج صدا موفق: کدک={stream.get('codec_name')}, " +
                                   f"نرخ نمونه‌برداری={stream.get('sample_rate')}, " +
                                   f"کانال‌ها={stream.get('channels')}")
                        return True
            else:
                logger.error("استخراج انجام شد اما نمی‌توان اطلاعات فایل خروجی را دریافت کرد")
                # بررسی حجم فایل
                file_size = os.path.getsize(output_path)
                logger.info(f"حجم فایل صوتی: {file_size} بایت")
                if file_size > 10000:  # حداقل 10 کیلوبایت
                    return True
        else:
            logger.error(f"خطا در استخراج صدا: کد خروجی {process.returncode}")
            
        return False
    except Exception as e:
        logger.error(f"خطای غیرمنتظره در استخراج صدا: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def analyze_option_selection(option_id: str, option_data: Dict) -> Dict:
    """
    تحلیل انتخاب گزینه توسط کاربر
    
    Args:
        option_id: شناسه گزینه انتخاب شده
        option_data: اطلاعات گزینه در صورت وجود
        
    Returns:
        دیکشنری حاوی نتایج تحلیل
    """
    result = {
        "option_id": option_id,
        "original_data": option_data,
        "is_audio": False,
        "quality": "unknown",
        "analysis": ""
    }
    
    try:
        # بررسی اینکه آیا این درخواست صوتی است
        if "audio" in option_id.lower():
            result["is_audio"] = True
            result["quality"] = "audio"
            result["analysis"] += "تشخیص درخواست صوتی از شناسه گزینه. "
        
        # بررسی کیفیت مورد نظر
        if "1080p" in option_id:
            result["quality"] = "1080p"
            result["analysis"] += "تشخیص کیفیت 1080p از شناسه گزینه. "
        elif "720p" in option_id:
            result["quality"] = "720p"
            result["analysis"] += "تشخیص کیفیت 720p از شناسه گزینه. "
        elif "480p" in option_id:
            result["quality"] = "480p"
            result["analysis"] += "تشخیص کیفیت 480p از شناسه گزینه. "
        elif "360p" in option_id:
            result["quality"] = "360p"
            result["analysis"] += "تشخیص کیفیت 360p از شناسه گزینه. "
        elif "240p" in option_id:
            result["quality"] = "240p"
            result["analysis"] += "تشخیص کیفیت 240p از شناسه گزینه. "
        
        # بررسی اطلاعات گزینه
        if option_data:
            if option_data.get("type") == "audio":
                result["is_audio"] = True
                result["analysis"] += "تشخیص درخواست صوتی از نوع گزینه. "
            
            if "quality" in option_data:
                result["quality"] = option_data["quality"]
                result["analysis"] += f"تشخیص کیفیت {option_data['quality']} از اطلاعات گزینه. "
        
        # تحلیل نهایی
        if result["is_audio"]:
            result["analysis"] += "نتیجه: این یک درخواست صوتی است. "
        else:
            result["analysis"] += f"نتیجه: این یک درخواست ویدیویی با کیفیت {result['quality']} است. "
        
        return result
    except Exception as e:
        logger.error(f"خطا در تحلیل انتخاب گزینه: {str(e)}")
        logger.error(traceback.format_exc())
        result["analysis"] += f"خطا در تحلیل: {str(e)}"
        return result

def debug_process_video(url: str, option_id: str, quality: str, is_audio: bool) -> Dict:
    """
    عیب‌یابی کامل پردازش ویدیو از URL
    
    Args:
        url: آدرس ویدیو
        option_id: شناسه گزینه انتخاب شده
        quality: کیفیت درخواستی
        is_audio: آیا درخواست صوتی است
        
    Returns:
        دیکشنری حاوی نتایج عیب‌یابی
    """
    result = {
        "url": url,
        "option_id": option_id,
        "requested_quality": quality,
        "is_audio_request": is_audio,
        "steps": [],
        "success": False,
        "final_file": None
    }
    
    logger.info(f"شروع عیب‌یابی برای URL: {url}")
    logger.info(f"شناسه گزینه: {option_id}, کیفیت: {quality}, درخواست صوتی: {is_audio}")
    
    try:
        # مرحله 1: دانلود ویدیو با کیفیت اصلی
        temp_dir = "/tmp/debug_videos"
        os.makedirs(temp_dir, exist_ok=True)
        
        download_id = uuid.uuid4().hex[:8]
        original_file = os.path.join(temp_dir, f"original_{download_id}.mp4")
        
        # اینجا فرض می‌کنیم که فایل ویدیو را دانلود کرده‌ایم
        # در یک پیاده‌سازی واقعی، باید از دانلودر استفاده کنید
        result["steps"].append({
            "step": "download",
            "status": "skipped in debug mode",
            "message": "این مرحله در حالت عیب‌یابی نادیده گرفته می‌شود. فرض بر این است که فایل اصلی دانلود شده است."
        })
        
        # مرحله 2: تحلیل فایل اصلی
        # برای تست، از یک فایل نمونه استفاده می‌کنیم
        sample_file = os.path.join(temp_dir, "sample.mp4")
        if not os.path.exists(sample_file):
            logger.warning(f"فایل نمونه {sample_file} وجود ندارد. نمی‌توان عیب‌یابی کامل را انجام داد.")
            result["steps"].append({
                "step": "analyze_original",
                "status": "skipped",
                "message": "فایل نمونه برای تحلیل وجود ندارد."
            })
            return result
        
        original_file = sample_file  # استفاده از فایل نمونه
        
        # تحلیل فایل اصلی
        original_info = get_video_info(original_file)
        if not original_info:
            result["steps"].append({
                "step": "analyze_original",
                "status": "failed",
                "message": "نمی‌توان اطلاعات فایل اصلی را دریافت کرد."
            })
            return result
            
        # استخراج اطلاعات مهم
        original_height = None
        original_width = None
        has_audio = False
        for stream in original_info.get('streams', []):
            if stream.get('codec_type') == 'video':
                original_height = stream.get('height')
                original_width = stream.get('width')
            elif stream.get('codec_type') == 'audio':
                has_audio = True
                
        result["steps"].append({
            "step": "analyze_original",
            "status": "success",
            "message": f"تحلیل فایل اصلی: ابعاد={original_width}x{original_height}, دارای صدا={has_audio}"
        })
        
        # مرحله 3: پردازش بر اساس درخواست (صوتی یا ویدیویی)
        if is_audio:
            # پردازش درخواست صوتی
            audio_output = os.path.join(temp_dir, f"audio_{download_id}.mp3")
            audio_success = extract_audio_with_debug(original_file, audio_output)
            
            if audio_success:
                result["steps"].append({
                    "step": "extract_audio",
                    "status": "success",
                    "message": f"استخراج صدا موفق: {audio_output}"
                })
                result["success"] = True
                result["final_file"] = audio_output
            else:
                result["steps"].append({
                    "step": "extract_audio",
                    "status": "failed",
                    "message": "استخراج صدا ناموفق بود."
                })
        else:
            # پردازش درخواست ویدیویی با کیفیت مشخص
            video_output = os.path.join(temp_dir, f"video_{quality}_{download_id}.mp4")
            video_success = convert_video_with_debug(original_file, video_output, quality)
            
            if video_success:
                result["steps"].append({
                    "step": "convert_video",
                    "status": "success",
                    "message": f"تبدیل کیفیت ویدیو موفق: {video_output}"
                })
                result["success"] = True
                result["final_file"] = video_output
            else:
                result["steps"].append({
                    "step": "convert_video",
                    "status": "failed",
                    "message": f"تبدیل کیفیت ویدیو به {quality} ناموفق بود."
                })
        
        return result
    except Exception as e:
        logger.error(f"خطای غیرمنتظره در عیب‌یابی: {str(e)}")
        logger.error(traceback.format_exc())
        result["steps"].append({
            "step": "error",
            "status": "failed",
            "message": f"خطای غیرمنتظره: {str(e)}"
        })
        return result
        
# تابع اصلی برای تست کد
def run_debug_test():
    """اجرای آزمایشی عیب‌یابی و گزارش نتایج"""
    try:
        logger.info("شروع تست عیب‌یابی ویدیو...")
        
        # ایجاد یک نتیجه تحلیل گزینه
        test_option = analyze_option_selection("instagram_360p", {"type": "video", "quality": "360p"})
        logger.info(f"نتیجه تحلیل گزینه: {json.dumps(test_option, ensure_ascii=False, indent=2)}")
        
        # تست عیب‌یابی با فایل نمونه
        sample_file = "/tmp/debug_videos/sample.mp4"
        if not os.path.exists(sample_file):
            logger.warning(f"فایل نمونه {sample_file} وجود ندارد. ایجاد یک فایل تست...")
            # در اینجا می‌توانید یک فایل تست ایجاد کنید یا از کاربر بخواهید یک فایل ارائه دهد
        
        # اجرای تست تبدیل کیفیت
        if os.path.exists(sample_file):
            test_output = "/tmp/debug_videos/test_360p.mp4"
            logger.info(f"تست تبدیل کیفیت ویدیو برای {sample_file} به {test_output}...")
            convert_success = convert_video_with_debug(sample_file, test_output, "360p")
            logger.info(f"نتیجه تست تبدیل کیفیت: {'موفق' if convert_success else 'ناموفق'}")
            
            # تست استخراج صدا
            audio_output = "/tmp/debug_videos/test_audio.mp3"
            logger.info(f"تست استخراج صدا برای {sample_file} به {audio_output}...")
            audio_success = extract_audio_with_debug(sample_file, audio_output)
            logger.info(f"نتیجه تست استخراج صدا: {'موفق' if audio_success else 'ناموفق'}")
            
            # تست کامل پردازش ویدیو
            debug_result = debug_process_video("https://example.com/test", "instagram_360p", "360p", False)
            logger.info(f"نتیجه تست عیب‌یابی کامل: {json.dumps(debug_result, ensure_ascii=False, indent=2)}")
        
        logger.info("تست عیب‌یابی به پایان رسید.")
    except Exception as e:
        logger.error(f"خطا در اجرای تست عیب‌یابی: {str(e)}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    run_debug_test()
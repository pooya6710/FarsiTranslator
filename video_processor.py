"""
پردازش پیشرفته ویدیو

این ماژول توابع پیشرفته برای پردازش ویدیو، تبدیل کیفیت و استخراج اطلاعات را ارائه می‌دهد.
"""

import os
import re
import logging
import time
import tempfile
import json
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple, Union, Any

# تنظیم لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# مسیرهای پیش‌فرض
FFMPEG_PATH = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
FFPROBE_PATH = shutil.which("ffprobe") or "/usr/bin/ffprobe"
TEMP_DIR = tempfile.gettempdir()

# تنظیمات کیفیت‌های مختلف ویدیو
VIDEO_QUALITY_SETTINGS = {
    "1080p": {
        "resolution": "1920x1080",
        "bitrate": "5000k",
        "audio_bitrate": "192k",
        "preset": "medium"
    },
    "720p": {
        "resolution": "1280x720",
        "bitrate": "2500k",
        "audio_bitrate": "128k",
        "preset": "medium"
    },
    "480p": {
        "resolution": "854x480",
        "bitrate": "1000k",
        "audio_bitrate": "128k",
        "preset": "fast"
    },
    "360p": {
        "resolution": "640x360",
        "bitrate": "700k",
        "audio_bitrate": "96k",
        "preset": "ultrafast"
    },
    "240p": {
        "resolution": "426x240",
        "bitrate": "400k",
        "audio_bitrate": "96k",
        "preset": "ultrafast"
    }
}

def get_video_info(video_path: str) -> Optional[Dict[str, Any]]:
    """
    استخراج اطلاعات ویدیو با ffprobe
    
    Args:
        video_path: مسیر فایل ویدیویی
        
    Returns:
        دیکشنری حاوی اطلاعات ویدیو یا None در صورت خطا
    """
    if not os.path.exists(video_path):
        logger.error(f"فایل ویدیو وجود ندارد: {video_path}")
        return None
        
    try:
        cmd = [
            FFPROBE_PATH,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"خطا در اجرای ffprobe: {result.stderr}")
            return None
            
        # تبدیل خروجی JSON به دیکشنری پایتون
        info = json.loads(result.stdout)
        
        # استخراج اطلاعات مهم
        video_info = {
            "format": info.get("format", {}),
            "duration": float(info.get("format", {}).get("duration", 0)),
            "size": int(info.get("format", {}).get("size", 0)),
            "bit_rate": int(info.get("format", {}).get("bit_rate", 0)),
            "streams": []
        }
        
        # استخراج اطلاعات استریم‌ها
        streams = info.get("streams", [])
        for stream in streams:
            codec_type = stream.get("codec_type")
            
            if codec_type == "video":
                video_info["video_codec"] = stream.get("codec_name")
                video_info["width"] = stream.get("width")
                video_info["height"] = stream.get("height")
                video_info["frame_rate"] = eval(stream.get("r_frame_rate", "0/1"))
                video_info["streams"].append(stream)
            elif codec_type == "audio":
                video_info["audio_codec"] = stream.get("codec_name")
                video_info["audio_channels"] = stream.get("channels")
                video_info["streams"].append(stream)
                
        return video_info
    except Exception as e:
        logger.error(f"خطا در استخراج اطلاعات ویدیو: {e}")
        return None

def convert_video_quality(input_path: str, quality: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    تبدیل کیفیت ویدیو با ffmpeg
    
    Args:
        input_path: مسیر فایل ورودی
        quality: کیفیت مورد نظر ('1080p', '720p', '480p', '360p', '240p')
        output_path: مسیر فایل خروجی (اختیاری)
        
    Returns:
        مسیر فایل خروجی یا None در صورت خطا
    """
    if not os.path.exists(input_path):
        logger.error(f"فایل ورودی وجود ندارد: {input_path}")
        return None
        
    try:
        # بررسی کیفیت
        if quality not in VIDEO_QUALITY_SETTINGS:
            logger.error(f"کیفیت نامعتبر: {quality}")
            return None
            
        # تنظیمات کیفیت
        quality_settings = VIDEO_QUALITY_SETTINGS[quality]
        
        # بررسی اطلاعات ویدیو
        video_info = get_video_info(input_path)
        if not video_info:
            logger.error("اطلاعات ویدیو دریافت نشد")
            return None
            
        # بررسی نیاز به تبدیل
        needs_conversion = True
        if video_info.get("width") and video_info.get("height"):
            target_width = int(quality_settings["resolution"].split("x")[0])
            target_height = int(quality_settings["resolution"].split("x")[1])
            
            if video_info["width"] <= target_width and video_info["height"] <= target_height:
                logger.info(f"ویدیو از قبل با کیفیت کمتر یا برابر {quality} است")
                
                # اگر مسیر خروجی خاصی مشخص شده است، یک کپی ساده انجام می‌دهیم
                if output_path:
                    shutil.copy2(input_path, output_path)
                    return output_path
                else:
                    return input_path
        
        # ایجاد مسیر خروجی
        if not output_path:
            dir_name = os.path.dirname(input_path)
            base_name = os.path.basename(input_path)
            name, ext = os.path.splitext(base_name)
            output_path = os.path.join(dir_name, f"{name}_video_{quality}{ext}")
            
        # ایجاد دستور ffmpeg
        cmd = [
            FFMPEG_PATH,
            "-i", input_path,
            "-c:v", "libx264",
            "-b:v", quality_settings["bitrate"],
            "-preset", quality_settings["preset"],
            "-vf", f"scale={quality_settings['resolution']}:force_original_aspect_ratio=decrease,pad={quality_settings['resolution']}:-1:-1:color=black",
            "-c:a", "aac",
            "-b:a", quality_settings["audio_bitrate"],
            "-movflags", "+faststart",
            "-y",
            output_path
        ]
        
        # اجرای دستور
        logger.info(f"در حال تبدیل به کیفیت {quality}...")
        result = subprocess.run(cmd, capture_output=True)
        
        if result.returncode != 0:
            logger.error(f"خطا در تبدیل ویدیو: {result.stderr.decode('utf-8', errors='ignore')}")
            return None
            
        # بررسی فایل خروجی
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"تبدیل با موفقیت انجام شد: {output_path}")
            return output_path
        else:
            logger.error("فایل خروجی ایجاد نشد یا خالی است")
            return None
            
    except Exception as e:
        logger.error(f"خطا در تبدیل کیفیت ویدیو: {e}")
        return None

def extract_audio(input_path: str, output_path: Optional[str] = None, audio_format: str = "mp3", bitrate: str = "192k") -> Optional[str]:
    """
    استخراج صدا از ویدیو با ffmpeg
    
    Args:
        input_path: مسیر فایل ورودی
        output_path: مسیر فایل خروجی (اختیاری)
        audio_format: فرمت صدای خروجی ('mp3', 'aac', 'm4a', 'ogg')
        bitrate: نرخ بیت صدا
        
    Returns:
        مسیر فایل صوتی خروجی یا None در صورت خطا
    """
    if not os.path.exists(input_path):
        logger.error(f"فایل ورودی وجود ندارد: {input_path}")
        return None
        
    try:
        # ایجاد مسیر خروجی
        if not output_path:
            dir_name = os.path.dirname(input_path)
            base_name = os.path.basename(input_path)
            name = os.path.splitext(base_name)[0]
            output_path = os.path.join(dir_name, f"{name}_audio_{int(time.time())%1000000:06d}.{audio_format}")
            
        # تنظیم انکودر صوتی
        audio_codec = "libmp3lame" if audio_format == "mp3" else "aac"
        
        # ایجاد دستور ffmpeg
        cmd = [
            FFMPEG_PATH,
            "-i", input_path,
            "-vn",  # بدون ویدیو
            "-c:a", audio_codec,
            "-b:a", bitrate,
            "-y",
            output_path
        ]
        
        # اجرای دستور
        logger.info(f"در حال استخراج صدا با فرمت {audio_format}...")
        result = subprocess.run(cmd, capture_output=True)
        
        if result.returncode != 0:
            logger.error(f"خطا در استخراج صدا: {result.stderr.decode('utf-8', errors='ignore')}")
            return None
            
        # بررسی فایل خروجی
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"استخراج صدا با موفقیت انجام شد: {output_path}")
            return output_path
        else:
            logger.error("فایل خروجی ایجاد نشد یا خالی است")
            return None
            
    except Exception as e:
        logger.error(f"خطا در استخراج صدا: {e}")
        return None

def extract_thumbnail(input_path: str, output_path: Optional[str] = None, time_offset: float = 5.0) -> Optional[str]:
    """
    استخراج تصویر بندانگشتی از ویدیو
    
    Args:
        input_path: مسیر فایل ورودی
        output_path: مسیر فایل خروجی (اختیاری)
        time_offset: زمان فریم (ثانیه)
        
    Returns:
        مسیر فایل تصویر خروجی یا None در صورت خطا
    """
    if not os.path.exists(input_path):
        logger.error(f"فایل ورودی وجود ندارد: {input_path}")
        return None
        
    try:
        # ایجاد مسیر خروجی
        if not output_path:
            dir_name = os.path.dirname(input_path)
            base_name = os.path.basename(input_path)
            name = os.path.splitext(base_name)[0]
            output_path = os.path.join(dir_name, f"{name}_thumbnail.jpg")
            
        # بررسی مدت زمان ویدیو
        video_info = get_video_info(input_path)
        if video_info:
            duration = video_info.get("duration", 0)
            # انتخاب زمان مناسب (20% از مدت ویدیو)
            if duration > 10:
                time_offset = min(duration * 0.2, 30)
                
        # ایجاد دستور ffmpeg
        cmd = [
            FFMPEG_PATH,
            "-ss", str(time_offset),
            "-i", input_path,
            "-vframes", "1",
            "-q:v", "2",  # کیفیت بالا
            "-y",
            output_path
        ]
        
        # اجرای دستور
        logger.info(f"در حال استخراج تصویر بندانگشتی...")
        result = subprocess.run(cmd, capture_output=True)
        
        if result.returncode != 0:
            logger.error(f"خطا در استخراج تصویر بندانگشتی: {result.stderr.decode('utf-8', errors='ignore')}")
            return None
            
        # بررسی فایل خروجی
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"استخراج تصویر بندانگشتی با موفقیت انجام شد: {output_path}")
            return output_path
        else:
            logger.error("فایل خروجی ایجاد نشد یا خالی است")
            return None
            
    except Exception as e:
        logger.error(f"خطا در استخراج تصویر بندانگشتی: {e}")
        return None

def optimize_for_telegram(input_path: str, max_size_mb: int = 50) -> Optional[str]:
    """
    بهینه‌سازی ویدیو برای آپلود در تلگرام
    
    Args:
        input_path: مسیر فایل ورودی
        max_size_mb: حداکثر حجم فایل به مگابایت
        
    Returns:
        مسیر فایل بهینه‌سازی شده یا None در صورت خطا
    """
    if not os.path.exists(input_path):
        logger.error(f"فایل ورودی وجود ندارد: {input_path}")
        return None
        
    try:
        # بررسی حجم فعلی فایل
        current_size = os.path.getsize(input_path)
        current_size_mb = current_size / (1024 * 1024)
        
        # اگر فایل از قبل کوچکتر است، نیازی به بهینه‌سازی نیست
        if current_size_mb <= max_size_mb:
            logger.info(f"فایل از قبل کوچکتر از حد مجاز است ({current_size_mb:.2f} MB)")
            return input_path
            
        # ایجاد مسیر خروجی
        dir_name = os.path.dirname(input_path)
        base_name = os.path.basename(input_path)
        name, ext = os.path.splitext(base_name)
        output_path = os.path.join(dir_name, f"{name}_telegram{ext}")
        
        # دریافت اطلاعات ویدیو
        video_info = get_video_info(input_path)
        if not video_info:
            logger.error("اطلاعات ویدیو دریافت نشد")
            return None
            
        # محاسبه نسبت کاهش اندازه
        reduction_ratio = max_size_mb / current_size_mb
        
        # محاسبه تنظیمات بهینه‌سازی بر اساس ویژگی‌های فایل و نسبت کاهش
        target_bitrate = int(video_info.get("bit_rate", 2000000) * reduction_ratio * 0.9)
        target_bitrate = max(target_bitrate, 400000)  # حداقل 400Kbps
        
        # بررسی رزولوشن
        width = video_info.get("width", 0)
        height = video_info.get("height", 0)
        target_resolution = None
        
        if width and height:
            if width > 1280 or height > 720:
                target_resolution = "1280x720"
            elif width > 854 or height > 480:
                target_resolution = "854x480"
            elif width > 640 or height > 360:
                target_resolution = "640x360"
                
        # تنظیم دستور ffmpeg
        cmd = [
            FFMPEG_PATH,
            "-i", input_path,
            "-c:v", "libx264",
            "-preset", "ultrafast",  # سریع‌ترین انکودینگ
            "-b:v", f"{target_bitrate}",
            "-maxrate", f"{int(target_bitrate * 1.5)}",
            "-bufsize", f"{int(target_bitrate * 3)}",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",  # برای پخش سریع‌تر
            "-y",
            output_path
        ]
        
        # اگر نیاز به تغییر رزولوشن باشد
        if target_resolution:
            cmd.insert(-2, "-vf")
            cmd.insert(-2, f"scale={target_resolution}:force_original_aspect_ratio=decrease")
            
        # اجرای دستور
        logger.info(f"در حال بهینه‌سازی ویدیو برای تلگرام (هدف: {max_size_mb}MB)...")
        result = subprocess.run(cmd, capture_output=True)
        
        if result.returncode != 0:
            logger.error(f"خطا در بهینه‌سازی ویدیو: {result.stderr.decode('utf-8', errors='ignore')}")
            return None
            
        # بررسی فایل خروجی
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            new_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            logger.info(f"بهینه‌سازی ویدیو با موفقیت انجام شد: {new_size_mb:.2f} MB")
            
            # اگر هنوز بزرگتر از حد مجاز است، تلاش دوباره با کیفیت پایین‌تر
            if new_size_mb > max_size_mb:
                logger.warning(f"فایل هنوز بزرگتر از حد مجاز است، تلاش مجدد...")
                # کاهش بیشتر کیفیت
                second_output = os.path.join(dir_name, f"{name}_telegram_extra{ext}")
                
                cmd2 = [
                    FFMPEG_PATH,
                    "-i", output_path,
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-crf", "28",  # کیفیت پایین‌تر
                    "-vf", "scale=640:360:force_original_aspect_ratio=decrease",
                    "-c:a", "aac",
                    "-b:a", "96k",
                    "-movflags", "+faststart",
                    "-y",
                    second_output
                ]
                
                result2 = subprocess.run(cmd2, capture_output=True)
                
                if result2.returncode == 0 and os.path.exists(second_output):
                    final_size_mb = os.path.getsize(second_output) / (1024 * 1024)
                    logger.info(f"بهینه‌سازی ثانویه: {final_size_mb:.2f} MB")
                    # پاکسازی فایل میانی
                    try:
                        os.remove(output_path)
                    except:
                        pass
                    return second_output
                else:
                    logger.error("بهینه‌سازی ثانویه ناموفق بود")
            
            return output_path
        else:
            logger.error("فایل خروجی ایجاد نشد یا خالی است")
            return None
            
    except Exception as e:
        logger.error(f"خطا در بهینه‌سازی ویدیو: {e}")
        return None

def merge_video_audio(video_path: str, audio_path: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    ترکیب فایل‌های ویدیو و صدا
    
    Args:
        video_path: مسیر فایل ویدیو
        audio_path: مسیر فایل صدا
        output_path: مسیر فایل خروجی (اختیاری)
        
    Returns:
        مسیر فایل ترکیب شده یا None در صورت خطا
    """
    if not os.path.exists(video_path):
        logger.error(f"فایل ویدیو وجود ندارد: {video_path}")
        return None
        
    if not os.path.exists(audio_path):
        logger.error(f"فایل صدا وجود ندارد: {audio_path}")
        return None
        
    try:
        # ایجاد مسیر خروجی
        if not output_path:
            dir_name = os.path.dirname(video_path)
            base_name = os.path.basename(video_path)
            name, ext = os.path.splitext(base_name)
            output_path = os.path.join(dir_name, f"{name}_merged{ext}")
            
        # ایجاد دستور ffmpeg
        cmd = [
            FFMPEG_PATH,
            "-i", video_path,  # ویدیو
            "-i", audio_path,  # صدا
            "-c:v", "copy",    # کپی ویدیو بدون تغییر
            "-c:a", "aac",     # انکود صدا با AAC
            "-map", "0:v:0",   # استفاده از اولین استریم ویدیویی
            "-map", "1:a:0",   # استفاده از اولین استریم صوتی
            "-shortest",       # طول فایل بر اساس کوتاه‌ترین استریم
            "-y",
            output_path
        ]
        
        # اجرای دستور
        logger.info(f"در حال ترکیب ویدیو و صدا...")
        result = subprocess.run(cmd, capture_output=True)
        
        if result.returncode != 0:
            logger.error(f"خطا در ترکیب ویدیو و صدا: {result.stderr.decode('utf-8', errors='ignore')}")
            return None
            
        # بررسی فایل خروجی
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"ترکیب با موفقیت انجام شد: {output_path}")
            return output_path
        else:
            logger.error("فایل خروجی ایجاد نشد یا خالی است")
            return None
            
    except Exception as e:
        logger.error(f"خطا در ترکیب ویدیو و صدا: {e}")
        return None

def extract_frames(input_path: str, output_dir: Optional[str] = None, fps: float = 1.0) -> Optional[List[str]]:
    """
    استخراج فریم‌های ویدیو با نرخ مشخص
    
    Args:
        input_path: مسیر فایل ویدیو
        output_dir: مسیر دایرکتوری خروجی (اختیاری)
        fps: تعداد فریم در ثانیه
        
    Returns:
        لیست مسیرهای فریم‌ها یا None در صورت خطا
    """
    if not os.path.exists(input_path):
        logger.error(f"فایل ویدیو وجود ندارد: {input_path}")
        return None
        
    try:
        # ایجاد مسیر خروجی
        if not output_dir:
            dir_name = os.path.dirname(input_path)
            base_name = os.path.basename(input_path)
            name, _ = os.path.splitext(base_name)
            output_dir = os.path.join(dir_name, f"{name}_frames")
            
        # ایجاد دایرکتوری
        os.makedirs(output_dir, exist_ok=True)
        
        # مسیر الگوی خروجی
        output_pattern = os.path.join(output_dir, "frame_%04d.jpg")
        
        # ایجاد دستور ffmpeg
        cmd = [
            FFMPEG_PATH,
            "-i", input_path,
            "-vf", f"fps={fps}",  # فیلتر نرخ فریم
            "-q:v", "2",          # کیفیت بالا
            "-y",
            output_pattern
        ]
        
        # اجرای دستور
        logger.info(f"در حال استخراج فریم‌ها با نرخ {fps} فریم در ثانیه...")
        result = subprocess.run(cmd, capture_output=True)
        
        if result.returncode != 0:
            logger.error(f"خطا در استخراج فریم‌ها: {result.stderr.decode('utf-8', errors='ignore')}")
            return None
            
        # بررسی فایل‌های خروجی
        frame_files = [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.startswith("frame_") and f.endswith(".jpg")]
        frame_files.sort()
        
        if frame_files:
            logger.info(f"{len(frame_files)} فریم با موفقیت استخراج شد")
            return frame_files
        else:
            logger.error("هیچ فریمی استخراج نشد")
            return None
            
    except Exception as e:
        logger.error(f"خطا در استخراج فریم‌ها: {e}")
        return None

def create_timelapse(input_path: str, output_path: Optional[str] = None, speed_factor: float = 10.0) -> Optional[str]:
    """
    ایجاد ویدیوی تایم‌لپس (سریع‌شده)
    
    Args:
        input_path: مسیر فایل ویدیو
        output_path: مسیر فایل خروجی (اختیاری)
        speed_factor: ضریب سرعت
        
    Returns:
        مسیر فایل خروجی یا None در صورت خطا
    """
    if not os.path.exists(input_path):
        logger.error(f"فایل ویدیو وجود ندارد: {input_path}")
        return None
        
    try:
        # ایجاد مسیر خروجی
        if not output_path:
            dir_name = os.path.dirname(input_path)
            base_name = os.path.basename(input_path)
            name, ext = os.path.splitext(base_name)
            output_path = os.path.join(dir_name, f"{name}_timelapse{ext}")
            
        # محاسبه نرخ خروجی از نرخ ورودی
        video_info = get_video_info(input_path)
        if not video_info:
            logger.error("اطلاعات ویدیو دریافت نشد")
            return None
            
        # ایجاد دستور ffmpeg
        cmd = [
            FFMPEG_PATH,
            "-i", input_path,
            "-filter_complex", f"[0:v]setpts=PTS/{speed_factor}[v];[0:a]atempo={min(speed_factor, 2.0)}[a]",
            "-map", "[v]",
            "-map", "[a]" if video_info.get("audio_codec") else "",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-y",
            output_path
        ]
        
        # حذف آرگومان‌های خالی
        cmd = [c for c in cmd if c]
        
        # اجرای دستور
        logger.info(f"در حال ایجاد تایم‌لپس با ضریب سرعت {speed_factor}...")
        result = subprocess.run(cmd, capture_output=True)
        
        if result.returncode != 0:
            logger.error(f"خطا در ایجاد تایم‌لپس: {result.stderr.decode('utf-8', errors='ignore')}")
            return None
            
        # بررسی فایل خروجی
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"تایم‌لپس با موفقیت ایجاد شد: {output_path}")
            return output_path
        else:
            logger.error("فایل خروجی ایجاد نشد یا خالی است")
            return None
            
    except Exception as e:
        logger.error(f"خطا در ایجاد تایم‌لپس: {e}")
        return None

def add_watermark(input_path: str, watermark_text: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    افزودن واترمارک متنی به ویدیو
    
    Args:
        input_path: مسیر فایل ویدیو
        watermark_text: متن واترمارک
        output_path: مسیر فایل خروجی (اختیاری)
        
    Returns:
        مسیر فایل خروجی یا None در صورت خطا
    """
    if not os.path.exists(input_path):
        logger.error(f"فایل ویدیو وجود ندارد: {input_path}")
        return None
        
    try:
        # ایجاد مسیر خروجی
        if not output_path:
            dir_name = os.path.dirname(input_path)
            base_name = os.path.basename(input_path)
            name, ext = os.path.splitext(base_name)
            output_path = os.path.join(dir_name, f"{name}_watermark{ext}")
            
        # ایجاد دستور ffmpeg
        cmd = [
            FFMPEG_PATH,
            "-i", input_path,
            "-vf", f"drawtext=text='{watermark_text}':fontcolor=white:fontsize=24:alpha=0.5:x=w-tw-10:y=h-th-10",
            "-codec:a", "copy",  # کپی صدا بدون تغییر
            "-y",
            output_path
        ]
        
        # اجرای دستور
        logger.info(f"در حال افزودن واترمارک...")
        result = subprocess.run(cmd, capture_output=True)
        
        if result.returncode != 0:
            logger.error(f"خطا در افزودن واترمارک: {result.stderr.decode('utf-8', errors='ignore')}")
            return None
            
        # بررسی فایل خروجی
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"واترمارک با موفقیت اضافه شد: {output_path}")
            return output_path
        else:
            logger.error("فایل خروجی ایجاد نشد یا خالی است")
            return None
            
    except Exception as e:
        logger.error(f"خطا در افزودن واترمارک: {e}")
        return None

# آزمایش ماژول
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python video_processor.py input_video [operation] [quality]")
        print("Operations: info, convert, extract_audio, optimize, thumbnail")
        sys.exit(1)
        
    input_video = sys.argv[1]
    operation = sys.argv[2] if len(sys.argv) > 2 else "info"
    quality = sys.argv[3] if len(sys.argv) > 3 else "720p"
    
    if operation == "info":
        info = get_video_info(input_video)
        if info:
            print(f"Video Information:")
            print(f"Format: {info.get('format', {}).get('format_name')}")
            print(f"Duration: {info.get('duration')} seconds")
            print(f"Size: {info.get('size') / (1024 * 1024):.2f} MB")
            print(f"Bitrate: {info.get('bit_rate') / 1000:.2f} Kbps")
            print(f"Resolution: {info.get('width')}x{info.get('height')}")
            print(f"Video codec: {info.get('video_codec')}")
            print(f"Audio codec: {info.get('audio_codec')}")
            
    elif operation == "convert":
        output = convert_video_quality(input_video, quality)
        if output:
            print(f"Conversion successful: {output}")
            
    elif operation == "extract_audio":
        output = extract_audio(input_video)
        if output:
            print(f"Audio extraction successful: {output}")
            
    elif operation == "optimize":
        output = optimize_for_telegram(input_video)
        if output:
            print(f"Optimization successful: {output}")
            
    elif operation == "thumbnail":
        output = extract_thumbnail(input_video)
        if output:
            print(f"Thumbnail extraction successful: {output}")
            
    else:
        print(f"Unknown operation: {operation}")
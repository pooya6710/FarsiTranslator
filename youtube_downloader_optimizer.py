"""
بهینه‌سازی پیشرفته دانلود یوتیوب

این ماژول تنظیمات و روش‌های دانلود ویدیوهای یوتیوب را بهینه می‌کند
"""

import os
import re
import logging
import time
import tempfile
import json
import subprocess
from typing import Dict, List, Optional, Tuple, Any, Union
import shutil

# تنظیم لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# تنظیم مسیرها و متغیرهای پیکربندی
FFMPEG_PATH = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
FFPROBE_PATH = shutil.which("ffprobe") or "/usr/bin/ffprobe"
TEMP_DIR = tempfile.gettempdir()

# هدرهای HTTP
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
HTTP_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-US,en;q=0.9,fa;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Referer": "https://www.google.com/",
    "Origin": "https://www.youtube.com"
}

# فرمت‌های بهینه برای کیفیت‌های مختلف
OPTIMAL_FORMATS = {
    "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]",
    "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]",
    "480p": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]",
    "360p": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]",
    "240p": "bestvideo[height<=240][ext=mp4]+bestaudio[ext=m4a]/best[height<=240][ext=mp4]",
    "mp3": "bestaudio[ext=m4a]/bestaudio"
}

def create_optimized_yt_dlp_options(quality: str = "720p") -> Dict[str, Any]:
    """
    ایجاد تنظیمات بهینه yt-dlp برای دانلود ویدیوهای یوتیوب
    
    Args:
        quality: کیفیت مورد نظر ویدیو (1080p, 720p, 480p, 360p, 240p, mp3)
        
    Returns:
        دیکشنری حاوی تنظیمات بهینه yt-dlp
    """
    is_audio_only = quality == "mp3"
    
    # تنظیمات پایه
    ydl_opts = {
        'format': OPTIMAL_FORMATS.get(quality, OPTIMAL_FORMATS["720p"]),
        'outtmpl': os.path.join(TEMP_DIR, '%(title)s_%(id)s.%(ext)s'),
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0',
        'sleep_interval': 1,  # فاصله بین درخواست‌ها (ثانیه)
        'max_sleep_interval': 5,
        'sleep_interval_requests': 1,
        'max_retries': 10,  # حداکثر تلاش‌های مجدد
        'retries': 3,  # تلاش‌های اولیه
        'fragment_retries': 10,
        'skip_unavailable_fragments': True,
        'overwrites': True,
        'http_chunk_size': 10485760,  # اندازه چانک HTTP (10 مگابایت)
        'buffersize': 1024,  # اندازه بافر
        'noprogress': True,
        'geo_bypass': True,
        'http_headers': HTTP_HEADERS,
        'socket_timeout': 30,
        'concurrent_fragment_downloads': 5,  # تعداد دانلود موازی
    }
    
    # تنظیمات ویژه برای فقط صدا
    if is_audio_only:
        postprocessors = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
        ydl_opts['postprocessors'] = postprocessors
        ydl_opts['keepvideo'] = False
    else:
        # تنظیمات فایل خروجی برای ویدیو
        ydl_opts['merge_output_format'] = 'mp4'
        ydl_opts['postprocessor_args'] = [
            '-threads', '2',  # تعداد ترد‌ها
            '-movflags', '+faststart',  # فست استارت برای پخش سریع‌تر
            '-preset', 'ultrafast',  # سرعت انکود
        ]
    
    return ydl_opts

def optimize_yt_dlp_for_speed():
    """
    بهینه‌سازی yt-dlp برای افزایش سرعت دانلود
    این تابع تغییرات مستقیم در ماژول yt-dlp ایجاد می‌کند
    """
    try:
        import yt_dlp
        
        # 1. بهینه‌سازی تنظیمات پیش‌فرض
        default_params = getattr(yt_dlp.options, "DEFAULT_PARAMS", {})
        
        speed_optimizations = {
            'fragment_retries': 10,
            'retries': 3,
            'skip_unavailable_fragments': True,
            'overwrites': True,
            'http_chunk_size': 10485760,
            'buffersize': 1024,
            'concurrent_fragment_downloads': 5,
            'socket_timeout': 30,
            'quiet': True,
            'noprogress': True,
        }
        
        # اعمال تنظیمات سرعت
        for key, value in speed_optimizations.items():
            default_params[key] = value
            
        # 2. تنظیم زمان‌بندی درخواست‌ها
        default_params['sleep_interval'] = 1
        default_params['max_sleep_interval'] = 5
        default_params['sleep_interval_requests'] = 1
        
        # 3. تنظیم هدرهای HTTP
        default_params['http_headers'] = HTTP_HEADERS
        
        # 4. فعال‌سازی دانلود موازی
        default_params['concurrent_fragment_downloads'] = 5
        
        # 5. بروزرسانی تنظیمات در ماژول
        yt_dlp.options.DEFAULT_PARAMS = default_params
        
        logger.info("تنظیمات yt-dlp با موفقیت برای افزایش سرعت بهینه شد")
        return True
    except Exception as e:
        logger.error(f"خطا در بهینه‌سازی yt-dlp: {e}")
        return False

def download_with_optimized_settings(url: str, quality: str = "720p", output_path: str = None) -> Optional[str]:
    """
    دانلود ویدیوی یوتیوب با تنظیمات بهینه
    
    Args:
        url: آدرس ویدیوی یوتیوب
        quality: کیفیت مورد نظر (1080p, 720p, 480p, 360p, 240p, mp3)
        output_path: مسیر خروجی دلخواه (اختیاری)
        
    Returns:
        مسیر فایل دانلود شده یا None در صورت خطا
    """
    try:
        import yt_dlp
        
        # بهینه‌سازی yt-dlp
        optimize_yt_dlp_for_speed()
        
        # ایجاد تنظیمات بهینه
        ydl_opts = create_optimized_yt_dlp_options(quality)
        
        # اگر مسیر خروجی تعیین شده باشد
        if output_path:
            ydl_opts['outtmpl'] = output_path
        
        # ارزیابی اطلاعات ویدیو قبل از دانلود
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    logger.error("اطلاعات ویدیو دریافت نشد")
                    return None
                
                # برای فرمت mp3، پسوند را به mp3 تغییر می‌دهیم
                if quality == "mp3":
                    output_file = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')
                else:
                    output_file = ydl.prepare_filename(info)
                
                # شروع دانلود
                logger.info(f"شروع دانلود با کیفیت {quality}: {info.get('title', 'ویدیوی ناشناس')}")
                ydl.download([url])
                
                # بررسی وجود فایل
                if os.path.exists(output_file):
                    logger.info(f"دانلود با موفقیت انجام شد: {output_file}")
                    return output_file
                
                # ممکن است پسوند فایل تغییر کرده باشد، پس کمی جستجو می‌کنیم
                base_path = os.path.splitext(output_file)[0]
                potential_files = [
                    f"{base_path}.mp4",
                    f"{base_path}.webm",
                    f"{base_path}.mkv",
                    f"{base_path}.mp3",
                    f"{base_path}.m4a"
                ]
                
                for potential_file in potential_files:
                    if os.path.exists(potential_file):
                        logger.info(f"فایل خروجی با نام دیگری پیدا شد: {potential_file}")
                        return potential_file
                
                logger.error("فایل خروجی پیدا نشد")
                return None
        except Exception as e:
            logger.error(f"خطا در دانلود ویدیو: {e}")
            return None
            
    except ImportError:
        logger.error("ماژول yt-dlp نصب نشده است")
        return None

def optimize_video_for_upload(input_path: str, max_size_mb: int = 50) -> Optional[str]:
    """
    بهینه‌سازی ویدیو برای آپلود در تلگرام
    
    Args:
        input_path: مسیر فایل ویدیویی
        max_size_mb: حداکثر حجم فایل به مگابایت
        
    Returns:
        مسیر فایل بهینه‌سازی شده یا None در صورت خطا
    """
    try:
        if not os.path.exists(input_path):
            logger.error(f"فایل ورودی وجود ندارد: {input_path}")
            return None
            
        # بررسی حجم فعلی فایل
        current_size_mb = os.path.getsize(input_path) / (1024 * 1024)
        
        # اگر فایل از قبل کوچکتر از حد مجاز است، نیازی به بهینه‌سازی نیست
        if current_size_mb <= max_size_mb:
            logger.info(f"فایل از قبل کوچکتر از حد مجاز است ({current_size_mb:.2f} MB)")
            return input_path
            
        # ایجاد مسیر خروجی
        dir_name = os.path.dirname(input_path)
        base_name = os.path.basename(input_path)
        name, ext = os.path.splitext(base_name)
        output_path = os.path.join(dir_name, f"{name}_optimized{ext}")
        
        # محاسبه نسبت کاهش مورد نیاز
        reduction_ratio = max_size_mb / current_size_mb
        target_bitrate = int(reduction_ratio * 800000)  # بیت‌ریت پایه 800Kbps
        target_bitrate = max(target_bitrate, 400000)  # حداقل بیت‌ریت 400Kbps
        
        # ایجاد دستور ffmpeg
        cmd = [
            FFMPEG_PATH,
            '-i', input_path,
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-b:v', f"{target_bitrate}",
            '-maxrate', f"{target_bitrate}",
            '-bufsize', f"{target_bitrate * 2}",
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            '-y',
            output_path
        ]
        
        # اجرای دستور
        logger.info(f"در حال بهینه‌سازی ویدیو برای آپلود (هدف: {max_size_mb} MB)...")
        result = subprocess.run(cmd, capture_output=True)
        
        if result.returncode != 0:
            logger.error(f"خطا در بهینه‌سازی ویدیو: {result.stderr.decode('utf-8', errors='ignore')}")
            return None
            
        # بررسی حجم فایل خروجی
        if os.path.exists(output_path):
            new_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            
            # اگر هنوز فایل بزرگ است، یک روش دیگر را امتحان می‌کنیم
            if new_size_mb > max_size_mb:
                logger.warning(f"حجم فایل هنوز بیش از حد مجاز است: {new_size_mb:.2f} MB")
                secondary_output = os.path.join(dir_name, f"{name}_extra_compressed{ext}")
                
                # کاهش رزولوشن برای صرفه‌جویی بیشتر در حجم
                resolution_scale = 0.75  # کاهش 25% اندازه
                cmd2 = [
                    FFMPEG_PATH,
                    '-i', output_path,
                    '-c:v', 'libx264',
                    '-preset', 'ultrafast',
                    '-crf', '32',
                    '-vf', f'scale=iw*{resolution_scale}:ih*{resolution_scale}',
                    '-c:a', 'aac',
                    '-b:a', '96k',
                    '-y',
                    secondary_output
                ]
                
                result2 = subprocess.run(cmd2, capture_output=True)
                
                if result2.returncode == 0 and os.path.exists(secondary_output):
                    final_size_mb = os.path.getsize(secondary_output) / (1024 * 1024)
                    logger.info(f"بهینه‌سازی ثانویه: {final_size_mb:.2f} MB")
                    
                    # پاکسازی فایل میانی
                    try:
                        os.remove(output_path)
                    except:
                        pass
                        
                    return secondary_output
                else:
                    logger.error("بهینه‌سازی ثانویه ناموفق بود")
                    return output_path
            else:
                logger.info(f"بهینه‌سازی با موفقیت انجام شد: {new_size_mb:.2f} MB")
                return output_path
        else:
            logger.error("فایل خروجی ایجاد نشد")
            return None
            
    except Exception as e:
        logger.error(f"خطا در بهینه‌سازی ویدیو: {e}")
        return None

def get_best_youtube_thumbnail(video_id: str) -> Optional[str]:
    """
    دریافت بهترین تصویر بندانگشتی ویدیوی یوتیوب
    
    Args:
        video_id: شناسه ویدیوی یوتیوب
        
    Returns:
        آدرس URL تصویر بندانگشتی یا None در صورت خطا
    """
    try:
        # ترتیب کیفیت تصاویر بندانگشتی یوتیوب
        thumbnail_urls = [
            f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",  # بهترین کیفیت
            f"https://i.ytimg.com/vi/{video_id}/sddefault.jpg",       # استاندارد بزرگ
            f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",       # با کیفیت بالا
            f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",       # متوسط
            f"https://i.ytimg.com/vi/{video_id}/default.jpg"          # استاندارد
        ]
        
        import requests
        
        # بررسی هر URL
        for url in thumbnail_urls:
            try:
                response = requests.head(url, timeout=5)
                if response.status_code == 200:
                    return url
            except:
                continue
                
        return None
    except Exception as e:
        logger.error(f"خطا در دریافت تصویر بندانگشتی: {e}")
        return None

def extract_video_id_from_url(url: str) -> Optional[str]:
    """
    استخراج شناسه ویدیوی یوتیوب از URL
    
    Args:
        url: آدرس ویدیوی یوتیوب
        
    Returns:
        شناسه ویدیو یا None در صورت خطا
    """
    try:
        youtube_patterns = [
            r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})'
        ]
        
        for pattern in youtube_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
                
        return None
    except Exception as e:
        logger.error(f"خطا در استخراج شناسه ویدیو: {e}")
        return None

def get_youtube_video_info(url: str) -> Optional[Dict[str, Any]]:
    """
    دریافت اطلاعات ویدیوی یوتیوب
    
    Args:
        url: آدرس ویدیوی یوتیوب
        
    Returns:
        دیکشنری حاوی اطلاعات ویدیو یا None در صورت خطا
    """
    try:
        import yt_dlp
        
        ydl_opts = {
            'format': 'best',
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'noplaylist': True,
            'youtube_include_dash_manifest': False,
            'http_headers': HTTP_HEADERS
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return None
                
            # استخراج اطلاعات مهم
            video_info = {
                'id': info.get('id'),
                'title': info.get('title'),
                'description': info.get('description'),
                'duration': info.get('duration'),
                'view_count': info.get('view_count'),
                'like_count': info.get('like_count'),
                'uploader': info.get('uploader'),
                'channel_id': info.get('channel_id'),
                'upload_date': info.get('upload_date'),
                'webpage_url': info.get('webpage_url'),
                'formats': []
            }
            
            # استخراج فرمت‌های موجود
            formats = info.get('formats', [])
            for fmt in formats:
                if fmt.get('resolution') != 'audio only':
                    format_info = {
                        'format_id': fmt.get('format_id'),
                        'resolution': fmt.get('resolution'),
                        'ext': fmt.get('ext'),
                        'filesize': fmt.get('filesize'),
                        'width': fmt.get('width'),
                        'height': fmt.get('height')
                    }
                    video_info['formats'].append(format_info)
            
            # دریافت تصویر بندانگشتی باکیفیت
            video_id = info.get('id')
            if video_id:
                thumbnail_url = get_best_youtube_thumbnail(video_id)
                if thumbnail_url:
                    video_info['thumbnail'] = thumbnail_url
                else:
                    video_info['thumbnail'] = info.get('thumbnail')
            
            return video_info
    except Exception as e:
        logger.error(f"خطا در دریافت اطلاعات ویدیو: {e}")
        return None

if __name__ == "__main__":
    # تست عملکرد
    import sys
    
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
        quality = sys.argv[2] if len(sys.argv) > 2 else "720p"
        
        print(f"دریافت اطلاعات ویدیو: {test_url}")
        info = get_youtube_video_info(test_url)
        if info:
            print(f"عنوان: {info.get('title')}")
            print(f"کانال: {info.get('uploader')}")
            print(f"مدت: {info.get('duration')} ثانیه")
            print(f"تصویر بندانگشتی: {info.get('thumbnail')}")
            
        print(f"شروع دانلود با کیفیت {quality}...")
        file_path = download_with_optimized_settings(test_url, quality)
        
        if file_path:
            print(f"دانلود با موفقیت انجام شد: {file_path}")
            
            print("بهینه‌سازی برای آپلود...")
            optimized_path = optimize_video_for_upload(file_path)
            
            if optimized_path:
                print(f"بهینه‌سازی با موفقیت انجام شد: {optimized_path}")
                print(f"حجم اصلی: {os.path.getsize(file_path) / (1024 * 1024):.2f} MB")
                print(f"حجم بهینه: {os.path.getsize(optimized_path) / (1024 * 1024):.2f} MB")
            else:
                print("بهینه‌سازی ناموفق بود.")
        else:
            print("دانلود ناموفق بود.")
    else:
        print("لطفاً یک URL یوتیوب را به عنوان آرگومان وارد کنید.")
        print("مثال: python youtube_downloader_optimizer.py https://www.youtube.com/watch?v=dQw4w9WgXcQ 720p")
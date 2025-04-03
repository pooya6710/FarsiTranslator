"""
ماژول پردازش پیشرفته ویدیو

این ماژول شامل توابع پیشرفته برای بهینه‌سازی پردازش ویدیو و کاهش مصرف منابع است.
"""

import os
import subprocess
import tempfile
import logging
import shutil
import json
from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path

# تنظیم لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# مسیر ffmpeg - به صورت خودکار پیدا می‌شود
FFMPEG_PATH = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
FFPROBE_PATH = shutil.which("ffprobe") or "/usr/bin/ffprobe"

class VideoProcessor:
    """کلاس مدیریت و بهینه‌سازی پردازش ویدیو"""
    
    def __init__(self, ffmpeg_path: str = None, ffprobe_path: str = None):
        """
        مقداردهی اولیه کلاس
        
        Args:
            ffmpeg_path: مسیر دلخواه ffmpeg
            ffprobe_path: مسیر دلخواه ffprobe
        """
        self.ffmpeg_path = ffmpeg_path or FFMPEG_PATH
        self.ffprobe_path = ffprobe_path or FFPROBE_PATH
        
        # تنظیمات پیش‌فرض ffmpeg
        self.default_ffmpeg_options = {
            "threads": 2,                    # تعداد ترد‌ها - برای سرورهای با CPU محدود
            "preset": "ultrafast",           # سرعت انکود - برای کارایی بهتر
            "crf": 28,                       # کیفیت ثابت - تعادل بین حجم و کیفیت
            "max_muxing_queue_size": 1024    # مقدار صف برای جلوگیری از خطای مالتی‌پلکسینگ
        }
    
    def get_video_info(self, video_path: str) -> Optional[Dict]:
        """
        دریافت اطلاعات فایل ویدیویی با استفاده از ffprobe
        
        Args:
            video_path: مسیر فایل ویدیویی
            
        Returns:
            دیکشنری حاوی اطلاعات ویدیو یا None در صورت خطا
        """
        try:
            if not os.path.exists(video_path):
                logger.error(f"فایل ویدیو وجود ندارد: {video_path}")
                return None
                
            cmd = [
                self.ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)
            
            # پردازش و ساده‌سازی اطلاعات
            video_info = {
                'duration': float(info.get('format', {}).get('duration', 0)),
                'size': int(info.get('format', {}).get('size', 0)),
                'bit_rate': int(info.get('format', {}).get('bit_rate', 0)),
                'format_name': info.get('format', {}).get('format_name', ''),
                'streams': []
            }
            
            # پردازش استریم‌ها
            for stream in info.get('streams', []):
                stream_type = stream.get('codec_type')
                
                if stream_type == 'video':
                    video_stream = {
                        'width': stream.get('width'),
                        'height': stream.get('height'),
                        'codec': stream.get('codec_name'),
                        'fps': eval(stream.get('r_frame_rate', '0/1')),
                        'bit_rate': stream.get('bit_rate'),
                        'duration': stream.get('duration')
                    }
                    video_info['streams'].append(('video', video_stream))
                    
                elif stream_type == 'audio':
                    audio_stream = {
                        'codec': stream.get('codec_name'),
                        'channels': stream.get('channels'),
                        'sample_rate': stream.get('sample_rate'),
                        'bit_rate': stream.get('bit_rate'),
                        'duration': stream.get('duration')
                    }
                    video_info['streams'].append(('audio', audio_stream))
            
            return video_info
            
        except Exception as e:
            logger.error(f"خطا در دریافت اطلاعات ویدیو: {e}")
            return None
    
    def check_video_quality(self, video_path: str) -> Optional[str]:
        """
        بررسی کیفیت ویدیو (رزولوشن)
        
        Args:
            video_path: مسیر فایل ویدیویی
            
        Returns:
            کیفیت ویدیو (1080p, 720p, 480p, 360p, 240p) یا None در صورت خطا
        """
        try:
            info = self.get_video_info(video_path)
            if not info:
                return None
                
            # یافتن استریم ویدیویی
            for stream_type, stream in info.get('streams', []):
                if stream_type == 'video':
                    height = stream.get('height', 0)
                    
                    if height >= 1080:
                        return "1080p"
                    elif height >= 720:
                        return "720p"
                    elif height >= 480:
                        return "480p"
                    elif height >= 360:
                        return "360p"
                    elif height >= 240:
                        return "240p"
                    else:
                        return f"{height}p"
            
            return None
            
        except Exception as e:
            logger.error(f"خطا در بررسی کیفیت ویدیو: {e}")
            return None
    
    def convert_video_quality(self, input_path: str, quality: str, output_path: str = None) -> Optional[str]:
        """
        تبدیل کیفیت ویدیو با استفاده از تنظیمات بهینه
        
        Args:
            input_path: مسیر فایل ورودی
            quality: کیفیت مورد نظر (1080p, 720p, 480p, 360p, 240p)
            output_path: مسیر فایل خروجی (اختیاری)
            
        Returns:
            مسیر فایل خروجی یا None در صورت خطا
        """
        try:
            if not os.path.exists(input_path):
                logger.error(f"فایل ورودی وجود ندارد: {input_path}")
                return None
                
            # تنظیم ابعاد بر اساس کیفیت
            resolution_map = {
                "1080p": "1920:1080",
                "720p": "1280:720",
                "480p": "854:480",
                "360p": "640:360",
                "240p": "426:240"
            }
            
            if quality not in resolution_map:
                logger.error(f"کیفیت نامعتبر: {quality}")
                return None
                
            # اگر مسیر خروجی تعیین نشده، یک مسیر موقت ایجاد می‌کنیم
            if not output_path:
                dir_name = os.path.dirname(input_path)
                base_name = os.path.basename(input_path)
                name, ext = os.path.splitext(base_name)
                output_path = os.path.join(dir_name, f"{name}_{quality}{ext}")
            
            # بررسی فایل فعلی
            current_quality = self.check_video_quality(input_path)
            if current_quality == quality:
                logger.info(f"فایل ورودی از قبل در کیفیت {quality} است. کپی ساده انجام می‌شود.")
                shutil.copy(input_path, output_path)
                return output_path
            
            # اگر کیفیت فعلی کمتر از کیفیت درخواستی است، هشدار می‌دهیم
            if current_quality and current_quality in resolution_map and resolution_map[current_quality] < resolution_map[quality]:
                logger.warning(f"افزایش کیفیت از {current_quality} به {quality} ممکن است باعث افت کیفیت شود.")
            
            # ایجاد دستور ffmpeg با تنظیمات بهینه
            resolution = resolution_map[quality]
            cmd = [
                self.ffmpeg_path,
                '-i', input_path,
                '-c:v', 'libx264',
                '-preset', self.default_ffmpeg_options['preset'],
                '-crf', str(self.default_ffmpeg_options['crf']),
                '-vf', f'scale={resolution}:force_original_aspect_ratio=decrease,pad={resolution}:(ow-iw)/2:(oh-ih)/2,setsar=1',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-threads', str(self.default_ffmpeg_options['threads']),
                '-max_muxing_queue_size', str(self.default_ffmpeg_options['max_muxing_queue_size']),
                '-y',
                output_path
            ]
            
            # اجرای دستور
            logger.info(f"در حال تبدیل ویدیو به کیفیت {quality}...")
            subprocess.run(cmd, capture_output=True, check=True)
            
            if os.path.exists(output_path):
                logger.info(f"تبدیل ویدیو به کیفیت {quality} با موفقیت انجام شد.")
                return output_path
            else:
                logger.error("فایل خروجی ایجاد نشد.")
                return None
                
        except subprocess.CalledProcessError as e:
            logger.error(f"خطا در اجرای ffmpeg: {e}")
            if e.stderr:
                logger.error(f"خروجی خطا: {e.stderr.decode('utf-8', errors='ignore')}")
            return None
        except Exception as e:
            logger.error(f"خطا در تبدیل کیفیت ویدیو: {e}")
            return None
    
    def extract_audio(self, video_path: str, output_format: str = 'mp3', bitrate: str = '192k') -> Optional[str]:
        """
        استخراج صدا از فایل ویدیویی
        
        Args:
            video_path: مسیر فایل ویدیویی
            output_format: فرمت خروجی صدا (mp3, m4a, wav, ogg)
            bitrate: نرخ بیت خروجی
            
        Returns:
            مسیر فایل صوتی ایجاد شده یا None در صورت خطا
        """
        try:
            if not os.path.exists(video_path):
                logger.error(f"فایل ویدیو وجود ندارد: {video_path}")
                return None
                
            # تعیین کدک مناسب برای فرمت خروجی
            codec_map = {
                "mp3": "libmp3lame",
                "m4a": "aac",
                "wav": "pcm_s16le",
                "ogg": "libvorbis"
            }
            
            if output_format not in codec_map:
                logger.error(f"فرمت صوتی نامعتبر: {output_format}")
                return None
                
            # ایجاد مسیر خروجی
            dir_name = os.path.dirname(video_path)
            base_name = os.path.basename(video_path)
            name, _ = os.path.splitext(base_name)
            output_path = os.path.join(dir_name, f"{name}_audio.{output_format}")
            
            # ایجاد دستور ffmpeg
            cmd = [
                self.ffmpeg_path,
                '-i', video_path,
                '-vn',  # حذف ویدیو
                '-c:a', codec_map[output_format],
                '-b:a', bitrate,
                '-threads', str(self.default_ffmpeg_options['threads']),
                '-y',
                output_path
            ]
            
            # اجرای دستور
            logger.info(f"در حال استخراج صدا به فرمت {output_format}...")
            subprocess.run(cmd, capture_output=True, check=True)
            
            if os.path.exists(output_path):
                logger.info(f"استخراج صدا به فرمت {output_format} با موفقیت انجام شد.")
                return output_path
            else:
                logger.error("فایل خروجی ایجاد نشد.")
                return None
                
        except subprocess.CalledProcessError as e:
            logger.error(f"خطا در اجرای ffmpeg: {e}")
            if e.stderr:
                logger.error(f"خروجی خطا: {e.stderr.decode('utf-8', errors='ignore')}")
            return None
        except Exception as e:
            logger.error(f"خطا در استخراج صدا: {e}")
            return None
    
    def optimize_for_telegram(self, video_path: str, max_size_mb: int = 50) -> Optional[str]:
        """
        بهینه‌سازی ویدیو برای آپلود در تلگرام (کاهش حجم)
        
        Args:
            video_path: مسیر فایل ویدیویی
            max_size_mb: حداکثر حجم فایل به مگابایت
            
        Returns:
            مسیر فایل بهینه‌سازی شده یا None در صورت خطا
        """
        try:
            if not os.path.exists(video_path):
                logger.error(f"فایل ویدیو وجود ندارد: {video_path}")
                return None
                
            # بررسی حجم فعلی فایل
            current_size_mb = os.path.getsize(video_path) / (1024 * 1024)
            
            # اگر فایل از قبل کوچکتر از حد مجاز است، نیازی به بهینه‌سازی نیست
            if current_size_mb <= max_size_mb:
                logger.info(f"فایل از قبل کوچکتر از حد مجاز است ({current_size_mb:.2f} MB). نیازی به بهینه‌سازی نیست.")
                return video_path
                
            # دریافت اطلاعات ویدیو
            info = self.get_video_info(video_path)
            if not info:
                return None
                
            # ایجاد مسیر خروجی
            dir_name = os.path.dirname(video_path)
            base_name = os.path.basename(video_path)
            name, ext = os.path.splitext(base_name)
            output_path = os.path.join(dir_name, f"{name}_telegram{ext}")
            
            # محاسبه نسبت کاهش مورد نیاز
            reduction_ratio = max_size_mb / current_size_mb
            
            # تنظیمات بهینه‌سازی
            crf_value = min(28 + int((1 - reduction_ratio) * 10), 35)  # افزایش CRF برای کاهش حجم (محدوده 28-35)
            
            # ایجاد دستور ffmpeg
            cmd = [
                self.ffmpeg_path,
                '-i', video_path,
                '-c:v', 'libx264',
                '-preset', self.default_ffmpeg_options['preset'],
                '-crf', str(crf_value),
                '-c:a', 'aac',
                '-b:a', '96k',  # کاهش کیفیت صدا برای صرفه‌جویی در حجم
                '-threads', str(self.default_ffmpeg_options['threads']),
                '-max_muxing_queue_size', str(self.default_ffmpeg_options['max_muxing_queue_size']),
                '-y',
                output_path
            ]
            
            # اجرای دستور
            logger.info(f"در حال بهینه‌سازی ویدیو برای تلگرام (هدف: {max_size_mb} MB)...")
            subprocess.run(cmd, capture_output=True, check=True)
            
            # بررسی نتیجه
            if os.path.exists(output_path):
                new_size_mb = os.path.getsize(output_path) / (1024 * 1024)
                
                # اگر هنوز فایل بزرگ است و نیاز به کاهش بیشتر دارد
                if new_size_mb > max_size_mb:
                    # اگر نسبت کاهش خیلی زیاد است، کاهش رزولوشن را امتحان می‌کنیم
                    second_output_path = os.path.join(dir_name, f"{name}_telegram_reduced{ext}")
                    
                    # کاهش رزولوشن برای صرفه‌جویی بیشتر در حجم
                    cmd2 = [
                        self.ffmpeg_path,
                        '-i', output_path,
                        '-c:v', 'libx264',
                        '-preset', self.default_ffmpeg_options['preset'],
                        '-crf', '32',
                        '-vf', 'scale=iw*0.75:ih*0.75',  # کاهش 25% ابعاد
                        '-c:a', 'aac',
                        '-b:a', '64k',  # کاهش بیشتر کیفیت صدا
                        '-threads', str(self.default_ffmpeg_options['threads']),
                        '-max_muxing_queue_size', str(self.default_ffmpeg_options['max_muxing_queue_size']),
                        '-y',
                        second_output_path
                    ]
                    
                    logger.info("نیاز به کاهش بیشتر حجم است. کاهش رزولوشن...")
                    subprocess.run(cmd2, capture_output=True, check=True)
                    
                    if os.path.exists(second_output_path):
                        # پاکسازی فایل میانی
                        os.remove(output_path)
                        final_size_mb = os.path.getsize(second_output_path) / (1024 * 1024)
                        logger.info(f"بهینه‌سازی با موفقیت انجام شد. حجم نهایی: {final_size_mb:.2f} MB")
                        return second_output_path
                    else:
                        logger.error("فایل خروجی ثانویه ایجاد نشد.")
                        return output_path
                else:
                    logger.info(f"بهینه‌سازی با موفقیت انجام شد. حجم نهایی: {new_size_mb:.2f} MB")
                    return output_path
            else:
                logger.error("فایل خروجی ایجاد نشد.")
                return None
                
        except subprocess.CalledProcessError as e:
            logger.error(f"خطا در اجرای ffmpeg: {e}")
            if e.stderr:
                logger.error(f"خروجی خطا: {e.stderr.decode('utf-8', errors='ignore')}")
            return None
        except Exception as e:
            logger.error(f"خطا در بهینه‌سازی ویدیو برای تلگرام: {e}")
            return None

# افزودن توابع ساده برای استفاده مستقیم
def convert_video_quality(input_path: str, quality: str, output_path: str = None) -> Optional[str]:
    """تابع ساده شده برای تبدیل کیفیت ویدیو"""
    processor = VideoProcessor()
    return processor.convert_video_quality(input_path, quality, output_path)

def extract_audio(video_path: str, output_format: str = 'mp3', bitrate: str = '192k') -> Optional[str]:
    """تابع ساده شده برای استخراج صدا از ویدیو"""
    processor = VideoProcessor()
    return processor.extract_audio(video_path, output_format, bitrate)

def optimize_for_telegram(video_path: str, max_size_mb: int = 50) -> Optional[str]:
    """تابع ساده شده برای بهینه‌سازی ویدیو برای تلگرام"""
    processor = VideoProcessor()
    return processor.optimize_for_telegram(video_path, max_size_mb)

def get_video_info(video_path: str) -> Optional[Dict]:
    """تابع ساده شده برای دریافت اطلاعات ویدیو"""
    processor = VideoProcessor()
    return processor.get_video_info(video_path)

def check_video_quality(video_path: str) -> Optional[str]:
    """تابع ساده شده برای بررسی کیفیت ویدیو"""
    processor = VideoProcessor()
    return processor.check_video_quality(video_path)

# کد تست برای اجرای مستقیم فایل
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        if os.path.exists(test_file):
            processor = VideoProcessor()
            
            print("1. دریافت اطلاعات ویدیو")
            info = processor.get_video_info(test_file)
            if info:
                print(f"  - مدت: {info['duration']} ثانیه")
                print(f"  - حجم: {info['size'] / (1024*1024):.2f} MB")
                print(f"  - قالب: {info['format_name']}")
                
                for stream_type, stream in info['streams']:
                    if stream_type == 'video':
                        print(f"  - استریم ویدیو: {stream['width']}x{stream['height']}, کدک: {stream['codec']}")
                    elif stream_type == 'audio':
                        print(f"  - استریم صدا: کانال‌ها: {stream['channels']}, کدک: {stream['codec']}")
            
            print("\n2. بررسی کیفیت ویدیو")
            quality = processor.check_video_quality(test_file)
            print(f"  - کیفیت تشخیص داده شده: {quality}")
            
            print("\n3. آزمایش تبدیل کیفیت (نسخه آزمایشی 360p)")
            if quality != "360p":
                converted = processor.convert_video_quality(test_file, "360p")
                if converted:
                    print(f"  - فایل تبدیل شده: {converted}")
                    print(f"  - حجم جدید: {os.path.getsize(converted) / (1024*1024):.2f} MB")
                else:
                    print("  - تبدیل ناموفق بود.")
            else:
                print("  - فایل از قبل در کیفیت 360p است. تبدیل انجام نشد.")
            
            print("\n4. آزمایش استخراج صدا")
            audio = processor.extract_audio(test_file)
            if audio:
                print(f"  - فایل صوتی: {audio}")
                print(f"  - حجم فایل صوتی: {os.path.getsize(audio) / (1024*1024):.2f} MB")
            else:
                print("  - استخراج صدا ناموفق بود.")
                
            print("\nآزمایش‌ها به پایان رسید.")
        else:
            print(f"فایل {test_file} وجود ندارد.")
    else:
        print("لطفاً یک فایل ویدیویی را به عنوان آرگومان تعیین کنید.")
        print("مثال: python video_processor.py /path/to/video.mp4")
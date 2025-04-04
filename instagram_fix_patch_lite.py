#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
نسخه سبک پچ برای رفع مشکل دانلود اینستاگرام بدون احراز هویت

این اسکریپت مشکل دانلود محتوا از اینستاگرام را بدون نیاز به لاگین رفع می‌کند.
"""

import os
import sys
import re
import json
import uuid
import random
import string
import logging
import time
import requests
import sqlite3
import tempfile
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime, timedelta

# تنظیم لاگینگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ثابت‌های مهم
DEFAULT_USER_AGENTS = [
    # User-Agent های موبایل
    'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.85 Mobile Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/98.0.4758.85 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Mobile Safari/537.36',
    # User-Agent های دسکتاپ
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36'
]

# مسیر فایل کوکی‌ها
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instagram_cookies.json")
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads", "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

class InstagramCookieGenerator:
    """کلاس ایجاد و مدیریت کوکی‌های اینستاگرام"""
    
    def __init__(self):
        """مقداردهی اولیه"""
        self.cookie_file = COOKIE_FILE
        self.cookies = self._load_cookies()
        self.last_generation_time = datetime.now() - timedelta(hours=2)  # شروع با یک مقدار قدیمی
        
    def _load_cookies(self) -> List[Dict]:
        """بارگذاری کوکی‌های ذخیره شده یا ایجاد فایل جدید"""
        if os.path.exists(self.cookie_file):
            try:
                with open(self.cookie_file, 'r') as f:
                    cookies = json.load(f)
                    if isinstance(cookies, list) and len(cookies) > 0:
                        logger.info(f"{len(cookies)} کوکی از فایل بارگذاری شد")
                        return cookies
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"خطا در بارگذاری فایل کوکی: {e}")
        
        # ایجاد کوکی‌های پیش‌فرض
        logger.info("ایجاد کوکی‌های پیش‌فرض")
        default_cookies = self._generate_random_cookies(5)
        self._save_cookies(default_cookies)
        return default_cookies
    
    def _save_cookies(self, cookies: List[Dict]) -> None:
        """ذخیره کوکی‌ها در فایل"""
        try:
            with open(self.cookie_file, 'w') as f:
                json.dump(cookies, f, indent=2)
            logger.info(f"{len(cookies)} کوکی در فایل ذخیره شد")
        except IOError as e:
            logger.error(f"خطا در ذخیره کوکی‌ها: {e}")
    
    def _generate_random_cookies(self, count: int = 3) -> List[Dict]:
        """ایجاد کوکی‌های تصادفی"""
        cookies = []
        
        for _ in range(count):
            # ایجاد شناسه‌های تصادفی برای کوکی‌ها
            mid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=26))
            ig_did = str(uuid.uuid4())
            csrftoken = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32))
            ds_user_id = str(random.randint(1000000000, 9999999999))
            sessionid = f"{ds_user_id}%3A{csrftoken}%3A{random.randint(1, 10)}"
            
            cookie = {
                "name": "instagram.com",
                "domain": ".instagram.com",
                "cookies": [
                    {"name": "mid", "value": mid},
                    {"name": "ig_did", "value": ig_did},
                    {"name": "csrftoken", "value": csrftoken},
                    {"name": "ds_user_id", "value": ds_user_id},
                    {"name": "sessionid", "value": sessionid},
                    {"name": "ig_nrcb", "value": "1"}
                ]
            }
            cookies.append(cookie)
        
        self.last_generation_time = datetime.now()
        return cookies
    
    def get_cookie_file(self) -> str:
        """دریافت مسیر فایل کوکی برای استفاده با yt-dlp"""
        # بررسی اگر کوکی‌ها قدیمی هستند (بیش از 30 دقیقه)
        if (datetime.now() - self.last_generation_time).total_seconds() > 1800:  # 30 دقیقه
            logger.info("کوکی‌ها قدیمی هستند، ایجاد کوکی‌های جدید")
            self.cookies = self._generate_random_cookies(5)
            self._save_cookies(self.cookies)
        
        # ایجاد فایل کوکی موقت برای yt-dlp
        # yt-dlp از فرمت Netscape HTTP Cookie File استفاده می‌کند
        cookie_temp_file = os.path.join(TEMP_DIR, f"instagram_cookies_{uuid.uuid4().hex[:8]}.txt")
        
        with open(cookie_temp_file, 'w') as f:
            f.write("# Netscape HTTP Cookie File\n")
            for cookie_set in self.cookies:
                domain = cookie_set["domain"]
                for cookie in cookie_set["cookies"]:
                    # domain, flag, path, secure, expiry, name, value
                    f.write(f"{domain}\tTRUE\t/\tTRUE\t{int(time.time()) + 86400}\t{cookie['name']}\t{cookie['value']}\n")
        
        logger.info(f"فایل کوکی موقت ایجاد شد: {cookie_temp_file}")
        return cookie_temp_file
    
    def get_as_dict(self) -> Dict[str, str]:
        """دریافت کوکی‌ها به صورت دیکشنری برای استفاده با requests"""
        if not self.cookies or len(self.cookies) == 0:
            return {}
        
        # انتخاب یک ست کوکی تصادفی
        cookie_set = random.choice(self.cookies)
        cookie_dict = {}
        
        for cookie in cookie_set["cookies"]:
            cookie_dict[cookie["name"]] = cookie["value"]
        
        return cookie_dict

def patch_ytdlp_for_instagram():
    """
    پچ yt-dlp برای دانلود از اینستاگرام
    با ایجاد کوکی‌های تصادفی و تنظیم آپشن‌های دانلود
    """
    try:
        import yt_dlp
        logger.info("yt-dlp یافت شد، شروع پچ")
        
        # ایجاد مدیریت کننده کوکی
        cookie_manager = InstagramCookieGenerator()
        
        # فایل کوکی برای yt-dlp
        cookie_file = cookie_manager.get_cookie_file()
        
        # پچ کردن yt-dlp با استفاده از monkey patching
        original_YoutubeDL_init = yt_dlp.YoutubeDL.__init__
        
        def patched_YoutubeDL_init(self, *args, **kwargs):
            # فراخوانی تابع اصلی
            original_YoutubeDL_init(self, *args, **kwargs)
            
            # بررسی اگر درخواست برای اینستاگرام است
            if 'instagram.com' in str(args) or 'instagram.com' in str(kwargs):
                logger.info("پچ yt-dlp برای اینستاگرام اعمال شد")
                
                # افزودن کوکی به آپشن‌ها
                if not self.params.get('cookiefile'):
                    self.params['cookiefile'] = cookie_file
                
                # افزودن User-Agent تصادفی
                if not self.params.get('user_agent'):
                    self.params['user_agent'] = random.choice(DEFAULT_USER_AGENTS)
                
                # تنظیمات بیشتر برای دور زدن محدودیت‌ها
                self.params['extractor_retries'] = 5
                self.params['fragment_retries'] = 10
                self.params['skip_download_archive'] = True
                self.params['force_generic_extractor'] = False
                
                # تنظیمات http
                if 'http_headers' not in self.params:
                    self.params['http_headers'] = {}
                
                self.params['http_headers'].update({
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Origin': 'https://www.instagram.com',
                    'Referer': 'https://www.instagram.com/',
                    'User-Agent': self.params['user_agent'],
                    'DNT': '1',
                    'Connection': 'keep-alive'
                })
        
        # اعمال پچ
        yt_dlp.YoutubeDL.__init__ = patched_YoutubeDL_init
        logger.info("پچ yt-dlp با موفقیت اعمال شد")
        
        return True
    except ImportError:
        logger.error("yt-dlp نصب نشده است")
        return False
    except Exception as e:
        logger.error(f"خطا در پچ yt-dlp: {e}")
        return False

def get_instagram_headers_and_cookies():
    """تولید هدرها و کوکی‌های مناسب برای درخواست‌های مستقیم به اینستاگرام"""
    cookie_manager = InstagramCookieGenerator()
    cookies = cookie_manager.get_as_dict()
    
    headers = {
        'User-Agent': random.choice(DEFAULT_USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Origin': 'https://www.instagram.com',
        'Referer': 'https://www.instagram.com/',
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
        'TE': 'Trailers',
        'DNT': '1'
    }
    
    return headers, cookies

def extract_shortcode_from_url(url: str) -> Optional[str]:
    """استخراج کد کوتاه از URL اینستاگرام"""
    patterns = [
        r'instagram\.com/p/([A-Za-z0-9_-]+)',       # پست معمولی
        r'instagram\.com/reel/([A-Za-z0-9_-]+)',    # ریل
        r'instagram\.com/tv/([A-Za-z0-9_-]+)',      # IGTV
        r'instagr\.am/p/([A-Za-z0-9_-]+)',          # لینک کوتاه پست
        r'instagr\.am/reel/([A-Za-z0-9_-]+)',       # لینک کوتاه ریل
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def download_instagram_content(url: str, output_path: str, quality: str = "best") -> Optional[str]:
    """
    دانلود محتوا از اینستاگرام با روش‌های پیشرفته
    
    Args:
        url: آدرس پست اینستاگرام
        output_path: مسیر خروجی فایل
        quality: کیفیت درخواستی (best, 1080p, 720p, 480p, 360p, 240p, audio)
        
    Returns:
        مسیر فایل دانلود شده یا None در صورت خطا
    """
    try:
        import yt_dlp
        
        # اطمینان از اعمال پچ
        patch_ytdlp_for_instagram()
        
        shortcode = extract_shortcode_from_url(url)
        if not shortcode:
            logger.error(f"کد کوتاه اینستاگرام برای URL استخراج نشد: {url}")
            return None
        
        logger.info(f"دانلود محتوای اینستاگرام با کد کوتاه: {shortcode}, کیفیت: {quality}")
        
        # تعیین فرمت خروجی براساس کیفیت
        if quality == "audio":
            format_spec = 'bestaudio/best'
            ext = 'mp3'
            final_filename = f"instagram_audio_{shortcode}.{ext}"
            postprocessors = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        else:
            # تنظیم فرمت بر اساس کیفیت انتخاب شده با روش جدید
            if quality == "240p":
                format_spec = 'worstvideo+bestaudio/worst[height>=240]/worst'
            elif quality == "360p":
                format_spec = 'best[height<=360]/bestvideo[height<=360]+bestaudio/best'
            elif quality == "480p":
                format_spec = 'best[height<=480]/bestvideo[height<=480]+bestaudio/best'
            elif quality == "720p":
                format_spec = 'best[height<=720]/bestvideo[height<=720]+bestaudio/best'
            elif quality == "1080p":
                format_spec = 'best[height<=1080]/bestvideo[height<=1080]+bestaudio/best'
            else:
                format_spec = 'best'
            
            ext = 'mp4'
            final_filename = f"instagram_video_{shortcode}.{ext}"
            postprocessors = []
        
        # تنظیم مسیر خروجی
        output_file = os.path.join(output_path, final_filename)
        
        # دریافت کوکی فایل
        cookie_manager = InstagramCookieGenerator()
        cookie_file = cookie_manager.get_cookie_file()
        
        # تنظیمات دانلود
        ydl_opts = {
            'format': format_spec,
            'outtmpl': output_file if quality != "audio" else output_file.replace(f'.{ext}', '.%(ext)s'),
            'cookiefile': cookie_file,
            'quiet': True,
            'no_warnings': True,
            'user_agent': random.choice(DEFAULT_USER_AGENTS),
            'retries': 15,
            'fragment_retries': 10,
            'http_headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Origin': 'https://www.instagram.com',
                'Referer': 'https://www.instagram.com/',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Pragma': 'no-cache',
                'Cache-Control': 'no-cache'
            },
            'postprocessors': postprocessors,
            'extractor_retries': 5,
            'skip_download_archive': True,
            'force_generic_extractor': False,
            'sleep_interval': 1,
            'max_sleep_interval': 5,
            'prefer_ffmpeg': True,
            'ffmpeg_location': '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg'
        }
        
        # انجام دانلود با روش‌های مختلف
        success = False
        downloaded_file = None
        
        # روش 1: دانلود مستقیم با تنظیمات کامل
        try:
            logger.info(f"تلاش دانلود با روش 1: {url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # بررسی موفقیت دانلود
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                success = True
                downloaded_file = output_file
                logger.info(f"دانلود با روش 1 موفق: {output_file}")
            elif quality == "audio":
                # بررسی فایل‌های با پسوندهای مختلف برای حالت صوتی
                for potential_ext in ['mp3', 'm4a', 'aac', 'wav', 'webm']:
                    potential_file = output_file.replace('.mp3', f'.{potential_ext}')
                    if os.path.exists(potential_file) and os.path.getsize(potential_file) > 0:
                        success = True
                        downloaded_file = potential_file
                        logger.info(f"دانلود صوتی با روش 1 موفق: {potential_file}")
                        break
        except Exception as e:
            logger.warning(f"خطا در روش 1 دانلود: {e}")
        
        # روش 2: استفاده از User-Agent متفاوت
        if not success:
            try:
                logger.info(f"تلاش دانلود با روش 2: {url}")
                # تغییر User-Agent
                ydl_opts['user_agent'] = random.choice(DEFAULT_USER_AGENTS)
                ydl_opts['http_headers']['User-Agent'] = ydl_opts['user_agent']
                ydl_opts['format'] = 'best'  # استفاده از ساده‌ترین فرمت
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                
                # بررسی موفقیت دانلود
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    success = True
                    downloaded_file = output_file
                    logger.info(f"دانلود با روش 2 موفق: {output_file}")
                elif quality == "audio":
                    # بررسی فایل‌های با پسوندهای مختلف برای حالت صوتی
                    for potential_ext in ['mp3', 'm4a', 'aac', 'wav', 'webm']:
                        potential_file = output_file.replace('.mp3', f'.{potential_ext}')
                        if os.path.exists(potential_file) and os.path.getsize(potential_file) > 0:
                            success = True
                            downloaded_file = potential_file
                            logger.info(f"دانلود صوتی با روش 2 موفق: {potential_file}")
                            break
            except Exception as e:
                logger.warning(f"خطا در روش 2 دانلود: {e}")
        
        # روش 3: استفاده از درخواست مستقیم اگر روش‌های قبلی شکست خوردند
        if not success:
            try:
                logger.info(f"تلاش دانلود با روش 3 (درخواست مستقیم): {url}")
                
                # تلاش برای دریافت URL مستقیم ویدیو
                headers, cookies = get_instagram_headers_and_cookies()
                response = requests.get(url, headers=headers, cookies=cookies, timeout=15)
                
                # الگوهای URL ویدیو در صفحه
                video_patterns = [
                    r'"video_url":"([^"]+)"',
                    r'property="og:video" content="([^"]+)"',
                    r'<video[^>]+src="([^"]+)"',
                    r'"contentUrl":\s*"([^"]+)"'
                ]
                
                video_url = None
                for pattern in video_patterns:
                    match = re.search(pattern, response.text)
                    if match:
                        video_url = match.group(1).replace('\\u0026', '&')
                        logger.info(f"URL مستقیم با الگوی {pattern} یافت شد")
                        break
                
                if video_url:
                    # دانلود مستقیم فایل
                    download_headers = {
                        'User-Agent': random.choice(DEFAULT_USER_AGENTS),
                        'Accept': '*/*',
                        'Accept-Encoding': 'identity;q=1, *;q=0',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Referer': url,
                        'Range': 'bytes=0-'
                    }
                    
                    video_response = requests.get(video_url, headers=download_headers, stream=True, timeout=30)
                    video_response.raise_for_status()
                    
                    with open(output_file, 'wb') as f:
                        for chunk in video_response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                        success = True
                        downloaded_file = output_file
                        logger.info(f"دانلود با درخواست مستقیم موفق: {output_file}")
                else:
                    logger.warning("URL مستقیم ویدیو یافت نشد")
            except Exception as e:
                logger.warning(f"خطا در روش 3 دانلود: {e}")
        
        # پردازش نهایی فایل دانلود شده
        if success and downloaded_file:
            # فقط برای ویدیو - تبدیل کیفیت اگر لازم باشد
            if quality != "audio" and quality != "best":
                try:
                    from telegram_fixes import convert_video_quality
                    logger.info(f"تبدیل کیفیت ویدیو به {quality}")
                    converted_file = convert_video_quality(downloaded_file, quality, is_audio_request=False)
                    if converted_file and os.path.exists(converted_file):
                        logger.info(f"تبدیل کیفیت موفق: {converted_file}")
                        return converted_file
                except Exception as e:
                    logger.error(f"خطا در تبدیل کیفیت: {e}")
            elif quality == "audio" and not downloaded_file.lower().endswith(('.mp3', '.m4a', '.aac', '.wav')):
                # تبدیل به صوت اگر فایل ویدیویی دانلود شده
                try:
                    from audio_processing import extract_audio
                    logger.info(f"تبدیل به صوت: {downloaded_file}")
                    audio_file = extract_audio(downloaded_file, 'mp3', '192k')
                    if audio_file and os.path.exists(audio_file):
                        logger.info(f"تبدیل به صوت موفق: {audio_file}")
                        return audio_file
                except Exception as e:
                    logger.error(f"خطا در تبدیل به صوت: {e}")
            
            return downloaded_file
        
        logger.error("تمام روش‌های دانلود شکست خوردند")
        return None
    except ImportError as e:
        logger.error(f"کتابخانه‌های لازم یافت نشدند: {e}")
        return None
    except Exception as e:
        logger.error(f"خطای کلی در دانلود: {e}")
        return None

def main():
    """اجرای اصلی پچ"""
    logger.info("شروع پچ سبک برای رفع مشکل دانلود اینستاگرام")
    
    # پچ کردن yt-dlp
    if patch_ytdlp_for_instagram():
        logger.info("پچ yt-dlp با موفقیت انجام شد")
    else:
        logger.error("خطا در پچ yt-dlp")
    
    # تست دانلود اگر URL ارائه شده باشد
    if len(sys.argv) > 1:
        url = sys.argv[1]
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
        
        logger.info(f"تست دانلود از URL: {url}")
        result = download_instagram_content(url, output_dir)
        
        if result:
            logger.info(f"دانلود موفق: {result}")
        else:
            logger.error("دانلود ناموفق")

if __name__ == "__main__":
    main()
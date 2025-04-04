#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ماژول دانلودر پیشرفته اینستاگرام

این ماژول روش‌های مختلف برای دانلود محتوا از اینستاگرام بدون نیاز به احراز هویت را فراهم می‌کند.
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
import subprocess
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
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36',
    # User-Agent های اختصاصی اینستاگرام
    'Instagram 219.0.0.12.117 Android (30/11; 420dpi; 1080x2126; Google/google; Pixel 5; redfin; redfin; en_US; 346138365)',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 234.0.0.8.116 (iPhone13,2; iOS 15_0; en_US; en-US; scale=3.00; 1170x2532; 367572442)',
]

# اطلاعات دسترسی به API اینستاگرام
IG_APP_ID = '936619743392459'
IG_WWW_CLAIM = '0'
IG_QUERY_HASH = [
    'b3055c01b4b222b8a47dc12b090e4e64',
    '9f8827793ef34641b2fb195d4d41151c',
    '2c4c2e343a8f64c625ba02b2aa12c7f8',
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
    
    def _generate_random_cookies(self, count: int = 5) -> List[Dict]:
        """ایجاد کوکی‌های تصادفی قوی‌تر"""
        cookies = []
        
        for _ in range(count):
            # ایجاد شناسه‌های تصادفی برای کوکی‌ها با فرمت دقیق‌تر
            mid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=26))
            ig_did = str(uuid.uuid4())
            csrftoken = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32))
            ds_user_id = str(random.randint(1000000000, 9999999999))
            sessionid = f"{ds_user_id}%3A{csrftoken}%3A{random.randint(1, 21)}"
            rur = "PRN"
            ig_direct_region_hint = random.choice(["ATN", "FRC", "AST", "USC"])
            
            cookie = {
                "name": "instagram.com",
                "domain": ".instagram.com",
                "cookies": [
                    {"name": "mid", "value": mid},
                    {"name": "ig_did", "value": ig_did},
                    {"name": "csrftoken", "value": csrftoken},
                    {"name": "ds_user_id", "value": ds_user_id},
                    {"name": "sessionid", "value": sessionid},
                    {"name": "ig_nrcb", "value": "1"},
                    {"name": "rur", "value": rur},
                    {"name": "ig_direct_region_hint", "value": ig_direct_region_hint}
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
    پچ yt-dlp برای دانلود از اینستاگرام با چندین روش مختلف
    """
    try:
        import yt_dlp
        logger.info("yt-dlp یافت شد، شروع پچ پیشرفته")
        
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
                self.params['extractor_retries'] = 10
                self.params['fragment_retries'] = 15
                self.params['skip_download_archive'] = True
                self.params['force_generic_extractor'] = False
                self.params['sleep_interval'] = 1
                self.params['max_sleep_interval'] = 5
                
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
                    'Connection': 'keep-alive',
                    'X-IG-App-ID': IG_APP_ID,
                    'X-IG-WWW-Claim': IG_WWW_CLAIM,
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
        'Accept-Encoding': 'gzip, deflate, br',
        'Origin': 'https://www.instagram.com',
        'Referer': 'https://www.instagram.com/',
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
        'TE': 'Trailers',
        'DNT': '1',
        'X-IG-App-ID': IG_APP_ID,
        'X-IG-WWW-Claim': IG_WWW_CLAIM,
        'X-Instagram-AJAX': '1',
        'X-Requested-With': 'XMLHttpRequest',
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

def _download_with_direct_request(url: str, shortcode: str, output_path: str, quality: str) -> Optional[str]:
    """
    دانلود مستقیم محتوای اینستاگرام با استفاده از API غیررسمی
    
    Args:
        url: آدرس پست اینستاگرام
        shortcode: کد کوتاه استخراج شده
        output_path: مسیر خروجی
        quality: کیفیت درخواستی
        
    Returns:
        مسیر فایل دانلود شده یا None در صورت خطا
    """
    try:
        logger.info(f"تلاش دانلود مستقیم برای {shortcode}")
        
        # دریافت هدرها و کوکی‌های تصادفی
        headers, cookies = get_instagram_headers_and_cookies()
        
        # Mobile User-Agent برای درخواست با ظاهر دستگاه‌های موبایل
        headers['User-Agent'] = 'Mozilla/5.0 (Linux; Android 10; SM-G9750) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Mobile Safari/537.36'
        
        # آدرس‌های مختلف برای تلاش دسترسی به محتوا
        base_url = f"https://www.instagram.com/p/{shortcode}/"
        graphql_url = "https://www.instagram.com/graphql/query/"
        alt_url = f"https://www.instagram.com/reel/{shortcode}/"
        i_url = f"https://i.instagram.com/api/v1/media/{shortcode}/info/"
        embed_url = f"https://www.instagram.com/p/{shortcode}/embed/"
        
        # تعیین فرمت خروجی
        is_audio = quality == "audio"
        ext = "mp3" if is_audio else "mp4"
        final_filename = f"instagram_{'audio' if is_audio else 'video'}_{shortcode}.{ext}"
        output_file = os.path.join(output_path, final_filename)
        
        # تلاش با روش صفحه HTML اصلی
        response = requests.get(base_url, headers=headers, cookies=cookies, timeout=10)
        
        # الگوهای جستجو برای URL ویدیو در HTML
        video_patterns = [
            r'"video_url":"([^"]+)"',
            r'"video_versions":\[{"type":\d+,"width":\d+,"height":\d+,"url":"([^"]+)"',
            r'property="og:video" content="([^"]+)"',
            r'<video[^>]+src="([^"]+)"',
            r'"contentUrl": "([^"]+)"',
            r'"video_url":"([^"]+)"',
            r'"playable_url":"([^"]+)"',
            r'"media_preview_url":"([^"]+)"'
        ]
        
        media_url = None
        
        # بررسی الگوها در پاسخ
        for pattern in video_patterns:
            matches = re.findall(pattern, response.text)
            if matches:
                media_url = matches[0].replace('\\u0026', '&').replace('\\/', '/')
                logger.info(f"URL مدیا با الگوی regex پیدا شد: {pattern}")
                break
        
        # اگر روش اول موفق نبود، تلاش با صفحه embed
        if not media_url:
            logger.info("تلاش با صفحه embed")
            response = requests.get(embed_url, headers=headers, cookies=cookies, timeout=10)
            
            for pattern in video_patterns:
                matches = re.findall(pattern, response.text)
                if matches:
                    media_url = matches[0].replace('\\u0026', '&').replace('\\/', '/')
                    logger.info(f"URL مدیا با الگوی regex در صفحه embed پیدا شد: {pattern}")
                    break
        
        # اگر روش دوم موفق نبود، تلاش با API موبایل
        if not media_url:
            logger.info("تلاش با API موبایل")
            mobile_headers = headers.copy()
            mobile_headers['User-Agent'] = 'Instagram 219.0.0.12.117 Android (30/11; 420dpi; 1080x2126; Google/google; Pixel 5; redfin; redfin; en_US; 346138365)'
            
            response = requests.get(i_url, headers=mobile_headers, cookies=cookies, timeout=10)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    if 'items' in data and len(data['items']) > 0:
                        item = data['items'][0]
                        
                        if 'video_versions' in item and len(item['video_versions']) > 0:
                            # برای ویدیو
                            media_url = item['video_versions'][0]['url']
                            logger.info(f"URL مدیا از API موبایل پیدا شد (ویدیو): {media_url}")
                        elif 'carousel_media' in item:
                            # برای آلبوم (اولین ویدیو)
                            for carousel_item in item['carousel_media']:
                                if 'video_versions' in carousel_item and len(carousel_item['video_versions']) > 0:
                                    media_url = carousel_item['video_versions'][0]['url']
                                    logger.info(f"URL مدیا از API موبایل پیدا شد (کاروسل): {media_url}")
                                    break
                except Exception as e:
                    logger.warning(f"خطا در پردازش پاسخ API موبایل: {e}")
        
        # اگر روش سوم موفق نبود، تلاش با صفحه رییل
        if not media_url:
            logger.info("تلاش با صفحه رییل")
            response = requests.get(alt_url, headers=headers, cookies=cookies, timeout=10)
            
            for pattern in video_patterns:
                matches = re.findall(pattern, response.text)
                if matches:
                    media_url = matches[0].replace('\\u0026', '&').replace('\\/', '/')
                    logger.info(f"URL مدیا با الگوی regex در صفحه رییل پیدا شد: {pattern}")
                    break
        
        # اگر URL پیدا شد، دانلود کنیم
        if media_url:
            logger.info(f"شروع دانلود مستقیم از URL: {media_url}")
            
            # ایجاد هدرهای جدید برای دانلود
            dl_headers = {
                'User-Agent': headers['User-Agent'],
                'Accept': '*/*',
                'Accept-Encoding': 'identity;q=1, *;q=0',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': base_url,
                'Range': 'bytes=0-',
                'Connection': 'keep-alive'
            }
            
            response = requests.get(media_url, headers=dl_headers, stream=True, timeout=30)
            
            if response.status_code in [200, 206]:
                with open(output_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                # بررسی فایل نهایی
                if os.path.exists(output_file) and os.path.getsize(output_file) > 1024:  # حداقل 1KB
                    # اگر درخواست صوتی بود، تبدیل به MP3
                    if is_audio:
                        try:
                            audio_output = output_file.replace('.mp4', '.mp3')
                            ffmpeg_cmd = [
                                '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',
                                '-i', output_file,
                                '-vn',
                                '-ab', '192k',
                                '-ar', '44100',
                                '-y',
                                audio_output
                            ]
                            
                            subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            
                            if os.path.exists(audio_output) and os.path.getsize(audio_output) > 0:
                                logger.info(f"تبدیل به MP3 موفق: {audio_output}")
                                return audio_output
                            else:
                                logger.warning("تبدیل به MP3 ناموفق بود")
                                return output_file
                        except Exception as e:
                            logger.warning(f"خطا در تبدیل به MP3: {e}")
                            return output_file
                    else:
                        return output_file
                else:
                    logger.warning(f"فایل دانلود شده خالی یا ناقص است: {output_file}")
            else:
                logger.warning(f"دانلود مستقیم ناموفق با کد وضعیت: {response.status_code}")
        else:
            logger.warning("هیچ URL مدیایی پیدا نشد")
    
    except Exception as e:
        logger.error(f"خطا در دانلود مستقیم: {e}")
    
    return None

def _download_with_api_method(url: str, shortcode: str, output_path: str, quality: str) -> Optional[str]:
    """
    دانلود با استفاده از API اینستاگرام
    
    Args:
        url: آدرس پست اینستاگرام
        shortcode: کد کوتاه استخراج شده
        output_path: مسیر خروجی
        quality: کیفیت درخواستی
        
    Returns:
        مسیر فایل دانلود شده یا None در صورت خطا
    """
    try:
        # تولید ID تصادفی برای درخواست GraphQL
        query_hash = random.choice(IG_QUERY_HASH)
        
        # API گرافیکی برای دریافت اطلاعات پست
        graphql_url = f"https://www.instagram.com/graphql/query/?query_hash={query_hash}&variables={{\"shortcode\":\"{shortcode}\"}}"
        
        # تعیین فرمت خروجی
        is_audio = quality == "audio"
        ext = "mp3" if is_audio else "mp4"
        final_filename = f"instagram_api_{'audio' if is_audio else 'video'}_{shortcode}.{ext}"
        output_file = os.path.join(output_path, final_filename)
        
        # دریافت هدرها و کوکی‌های تصادفی
        headers, cookies = get_instagram_headers_and_cookies()
        
        # درخواست به API گرافیکی
        response = requests.get(graphql_url, headers=headers, cookies=cookies, timeout=10)
        
        if response.status_code == 200:
            try:
                data = response.json()
                
                # استخراج URL ویدیو
                media_url = None
                if 'data' in data and 'shortcode_media' in data['data']:
                    media = data['data']['shortcode_media']
                    
                    if 'video_url' in media:
                        media_url = media['video_url']
                    elif 'video_resources' in media and len(media['video_resources']) > 0:
                        media_url = media['video_resources'][0]['src']
                
                # اگر URL پیدا شد، دانلود کنیم
                if media_url:
                    logger.info(f"شروع دانلود از API GraphQL با URL: {media_url}")
                    
                    # ایجاد هدرهای جدید برای دانلود
                    dl_headers = {
                        'User-Agent': headers['User-Agent'],
                        'Accept': '*/*',
                        'Accept-Encoding': 'identity;q=1, *;q=0',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Referer': url,
                        'Range': 'bytes=0-',
                        'Connection': 'keep-alive'
                    }
                    
                    response = requests.get(media_url, headers=dl_headers, stream=True, timeout=30)
                    
                    if response.status_code in [200, 206]:
                        with open(output_file, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        
                        # بررسی فایل نهایی
                        if os.path.exists(output_file) and os.path.getsize(output_file) > 1024:  # حداقل 1KB
                            # اگر درخواست صوتی بود، تبدیل به MP3
                            if is_audio:
                                try:
                                    audio_output = output_file.replace('.mp4', '.mp3')
                                    ffmpeg_cmd = [
                                        '/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg',
                                        '-i', output_file,
                                        '-vn',
                                        '-ab', '192k',
                                        '-ar', '44100',
                                        '-y',
                                        audio_output
                                    ]
                                    
                                    subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                                    
                                    if os.path.exists(audio_output) and os.path.getsize(audio_output) > 0:
                                        logger.info(f"تبدیل به MP3 موفق: {audio_output}")
                                        return audio_output
                                    else:
                                        logger.warning("تبدیل به MP3 ناموفق بود")
                                        return output_file
                                except Exception as e:
                                    logger.warning(f"خطا در تبدیل به MP3: {e}")
                                    return output_file
                            else:
                                return output_file
                        else:
                            logger.warning(f"فایل دانلود شده خالی یا ناقص است: {output_file}")
                    else:
                        logger.warning(f"دانلود از GraphQL API ناموفق با کد وضعیت: {response.status_code}")
                else:
                    logger.warning("هیچ URL مدیایی از GraphQL API پیدا نشد")
            except Exception as e:
                logger.warning(f"خطا در پردازش پاسخ GraphQL API: {e}")
        else:
            logger.warning(f"درخواست GraphQL API ناموفق با کد وضعیت: {response.status_code}")
    
    except Exception as e:
        logger.error(f"خطا در دانلود با API GraphQL: {e}")
    
    return None

def _download_with_browser_emulation(url: str, shortcode: str, output_path: str, quality: str) -> Optional[str]:
    """
    دانلود با شبیه‌سازی مرورگر
    
    Args:
        url: آدرس پست اینستاگرام
        shortcode: کد کوتاه استخراج شده
        output_path: مسیر خروجی
        quality: کیفیت درخواستی
        
    Returns:
        مسیر فایل دانلود شده یا None در صورت خطا
    """
    try:
        logger.info(f"تلاش دانلود با شبیه‌سازی مرورگر برای {shortcode}")
        
        # تعیین فرمت خروجی
        is_audio = quality == "audio"
        ext = "mp3" if is_audio else "mp4"
        final_filename = f"instagram_browser_{'audio' if is_audio else 'video'}_{shortcode}.{ext}"
        output_file = os.path.join(output_path, final_filename)
        
        # آماده‌سازی دستور yt-dlp با تنظیمات ویژه
        cookie_manager = InstagramCookieGenerator()
        cookie_file = cookie_manager.get_cookie_file()
        
        # تنظیم پارامترهای دانلود
        format_spec = 'bestaudio/best' if is_audio else 'best'
        
        yt_dlp_cmd = [
            sys.executable, '-m', 'yt_dlp',
            '--cookies', cookie_file,
            '--format', format_spec,
            '--user-agent', random.choice(DEFAULT_USER_AGENTS),
            '--force-generic-extractor',
            '--no-check-certificate',
            '--no-warnings',
            '--quiet',
            '--retries', '10',
            '--fragment-retries', '10',
            '--http-headers', json.dumps({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Origin': 'https://www.instagram.com',
                'Referer': 'https://www.instagram.com/',
                'X-IG-App-ID': IG_APP_ID,
                'X-IG-WWW-Claim': IG_WWW_CLAIM,
            }),
            '-o', output_file if not is_audio else output_file.replace('.mp3', '.%(ext)s'),
        ]
        
        # برای صدا، افزودن پست‌پروسسور
        if is_audio:
            yt_dlp_cmd.extend([
                '--extract-audio',
                '--audio-format', 'mp3',
                '--audio-quality', '192k',
            ])
        
        # اضافه کردن URL
        yt_dlp_cmd.append(url)
        
        # اجرای دستور
        subprocess.run(yt_dlp_cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # بررسی فایل نهایی
        if is_audio:
            for potential_ext in ['mp3', 'm4a', 'aac', 'wav', 'webm']:
                potential_file = output_file.replace('.mp3', f'.{potential_ext}')
                if os.path.exists(potential_file) and os.path.getsize(potential_file) > 0:
                    logger.info(f"دانلود صوتی با شبیه‌سازی مرورگر موفق: {potential_file}")
                    return potential_file
        else:
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                logger.info(f"دانلود با شبیه‌سازی مرورگر موفق: {output_file}")
                return output_file
        
        logger.warning("دانلود با شبیه‌سازی مرورگر ناموفق بود")
    except Exception as e:
        logger.error(f"خطا در دانلود با شبیه‌سازی مرورگر: {e}")
    
    return None

def download_instagram_content(url: str, output_path: str, quality: str = "best") -> Optional[str]:
    """
    دانلود محتوا از اینستاگرام با ترکیبی از چندین روش
    
    Args:
        url: آدرس پست اینستاگرام
        output_path: مسیر خروجی فایل
        quality: کیفیت درخواستی (best, 1080p, 720p, 480p, 360p, 240p, audio)
        
    Returns:
        مسیر فایل دانلود شده یا None در صورت خطا
    """
    try:
        # اطمینان از اعمال پچ
        patch_ytdlp_for_instagram()
        
        shortcode = extract_shortcode_from_url(url)
        if not shortcode:
            logger.error(f"کد کوتاه اینستاگرام برای URL استخراج نشد: {url}")
            return None
        
        logger.info(f"دانلود محتوای اینستاگرام با کد کوتاه: {shortcode}, کیفیت: {quality}")
        
        # یک ساختار کلی برای تست همه روش‌ها به ترتیب
        methods = [
            ("درخواست مستقیم", lambda: _download_with_direct_request(url, shortcode, output_path, quality)),
            ("API GraphQL", lambda: _download_with_api_method(url, shortcode, output_path, quality)),
            ("شبیه‌سازی مرورگر", lambda: _download_with_browser_emulation(url, shortcode, output_path, quality))
        ]
        
        for method_name, method_func in methods:
            try:
                logger.info(f"تلاش دانلود با روش {method_name}...")
                result = method_func()
                if result:
                    logger.info(f"دانلود با روش {method_name} موفق: {result}")
                    return result
            except Exception as e:
                logger.warning(f"خطا در روش {method_name}: {e}")
        
        # اگر هیچ کدام از روش‌ها موفق نبودند
        logger.error("تمام روش‌های دانلود با شکست مواجه شدند")
        
        return None
    except Exception as e:
        logger.error(f"خطای نهایی در دانلود اینستاگرام: {e}")
        return None

def main():
    """
    اجرای اصلی ماژول
    """
    # اطمینان از اعمال پچ yt-dlp
    patch_ytdlp_for_instagram()
    
    # تست روش‌های مختلف دانلود
    url = "https://www.instagram.com/reel/CxIoBLSt8on/"
    output_path = TEMP_DIR
    
    # تست با کیفیت‌های مختلف
    qualities = ["1080p", "audio"]
    
    for quality in qualities:
        logger.info(f"تست دانلود با کیفیت {quality}...")
        result = download_instagram_content(url, output_path, quality)
        
        if result:
            logger.info(f"دانلود موفق با کیفیت {quality}: {result}")
        else:
            logger.error(f"دانلود با کیفیت {quality} ناموفق بود")

if __name__ == "__main__":
    main()
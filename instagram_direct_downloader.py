#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ماژول دانلودر مستقیم اینستاگرام

این ماژول روش‌های جدید و مستقیم برای دانلود محتوا از اینستاگرام بدون نیاز به احراز هویت را فراهم می‌کند.
"""

import os
import re
import sys
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
    # User-Agent های رسمی کلاینت اینستاگرام - نسخه‌های جدید ۲۰۲۵ (با اولویت ویژه برای API)
    'Instagram 301.0.0.37.111 Android (35/14; 480dpi; 1080x2400; Google; Pixel 8; GP4BC; google; en_US; 532277295)',
    'Instagram 309.0.0.14.119 Android (34/14; 440dpi; 1080x2400; Samsung; SM-S918B; brogsp; exynos2300; en_US; 551409764)',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 312.0.0.0.67 (iPhone15,4; iOS 18_1; en_US; en-US; scale=3.00; 1170x2532; 537948800)',
    
    # User-Agent های اینستاگرام وب و PWA - به‌روز برای ۲۰۲۵
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Instagram Web App',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15 Instagram/312.0',
    
    # User-Agent های موبایل به‌روز شده iOS 17/18 و Android 14/15
    'Mozilla/5.0 (iPhone; CPU iPhone OS 18_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 15; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36'
]

# کوکی‌های ایجاد شده با روش‌های مختلف (با دقت بالا)
DEFAULT_COOKIES = [
    {
        'csrftoken': ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32)),
        'sessionid': ''.join(random.choice(string.digits) for _ in range(10)) + '%3A' + ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32)) + '%3A' + ''.join(random.choice(string.digits) for _ in range(2)),
        'ds_user_id': ''.join(random.choice(string.digits) for _ in range(10)),
        'ig_did': ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(32)),
        'mid': ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(26)),
        'datr': ''.join(random.choice(string.ascii_letters) for _ in range(22)) + '.',
        'rur': '"RVA,'+ ''.join(random.choice(string.digits) for _ in range(10)) + '\\054' + str(int(time.time())) + ':01f"',
    },
    {
        'csrftoken': ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32)),
        'sessionid': '',
        'ds_user_id': '',
        'ig_did': ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(32)),
        'mid': ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(26)),
        'datr': ''.join(random.choice(string.ascii_letters) for _ in range(22)) + '.',
        'ig_nrcb': '1',
        'dpr': '2',
    }
]

# مسیر دایرکتوری دانلودها
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads", "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

def extract_shortcode_from_url(url: str) -> Optional[str]:
    """استخراج کد کوتاه از URL اینستاگرام با الگوهای مختلف"""
    patterns = [
        r'instagram\.com/p/([A-Za-z0-9_-]+)',       # پست معمولی
        r'instagram\.com/reel/([A-Za-z0-9_-]+)',    # ریل
        r'instagram\.com/tv/([A-Za-z0-9_-]+)',      # IGTV
        r'instagr\.am/p/([A-Za-z0-9_-]+)',          # لینک کوتاه پست
        r'instagr\.am/reel/([A-Za-z0-9_-]+)',       # لینک کوتاه ریل
        r'\/p\/([A-Za-z0-9_-]+)',                  # تطبیق ساده‌تر برای /p/
        r'\/reel\/([A-Za-z0-9_-]+)',               # تطبیق ساده‌تر برای /reel/
        r'\/tv\/([A-Za-z0-9_-]+)',                 # تطبیق ساده‌تر برای /tv/
    ]
    
    # پاکسازی URL از پارامترهای اضافی
    cleaned_url = url.split('?')[0].split('#')[0]
    
    for pattern in patterns:
        match = re.search(pattern, cleaned_url)
        if match:
            result = match.group(1)
            # بررسی اضافی برای جدا کردن / در آخر شورت‌کد
            if result.endswith('/'):
                result = result[:-1]
            return result
    
    # تلاش برای استخراج با الگوی ساده‌تر
    parts = cleaned_url.split('/')
    for part in parts:
        if part and 5 <= len(part) <= 15 and re.match(r'^[A-Za-z0-9_-]+$', part):
            # شورت کدها معمولاً بین 5 تا 15 کاراکتر هستند
            return part
    
    return None

def generate_headers(is_mobile: bool = True) -> Dict[str, str]:
    """
    تولید هدرهای مناسب برای درخواست‌های اینستاگرام
    
    Args:
        is_mobile: آیا از User-Agent موبایل استفاده شود؟
        
    Returns:
        دیکشنری هدرها
    """
    # انتخاب User-Agent
    if is_mobile:
        user_agent = random.choice(DEFAULT_USER_AGENTS[:2])  # موبایل
    else:
        user_agent = random.choice(DEFAULT_USER_AGENTS[2:])  # دسکتاپ
    
    # هدرهای عمومی
    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Origin': 'https://www.instagram.com',
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
        'TE': 'Trailers',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-User': '?1',
        'DNT': '1',
    }
    
    # هدرهای خاص موبایل
    if is_mobile:
        headers.update({
            'X-IG-App-ID': '936619743392459',
            'X-IG-WWW-Claim': '0',
        })
    
    return headers

def generate_session_storage() -> Dict[str, str]:
    """
    تولید localStorage/sessionStorage تصادفی برای شبیه‌سازی مرورگر
    
    Returns:
        دیکشنری sessionStorage
    """
    return {
        'ig-storage-version': '10',
        'ig-u-ig-direct-privacy': 'all',
        'ig-u-ig-direct-swipe': 'true',
        'ig-u-ig-iab-tc': 'true',
        'ig-is-experience-logged-in': 'true',
        'ig-is-prerelease-universe': 'false',
        'ig-u-ds-user-id': str(random.randint(10000000, 999999999)),
        'ig-frontend-path': '/',
    }

def download_with_embed_api(url: str, shortcode: str, output_path: str, quality: str) -> Optional[str]:
    """
    دانلود محتوا با استفاده از API امبد اینستاگرام
    این متد از API امبد اینستاگرام استفاده می‌کند که نیاز به لاگین ندارد
    و از محدودیت‌های نرخ (rate limit) عادی اینستاگرام دور می‌زند.
    
    Args:
        url: آدرس پست اینستاگرام
        shortcode: کد کوتاه استخراج شده
        output_path: مسیر خروجی
        quality: کیفیت درخواستی
        
    Returns:
        مسیر فایل دانلود شده یا None در صورت خطا
    """
    try:
        logger.info(f"تلاش دانلود با API امبد برای {shortcode}")
        
        # تعیین فرمت خروجی
        is_audio = quality == "audio"
        ext = "mp3" if is_audio else "mp4"
        final_filename = f"instagram_embed_{'audio' if is_audio else 'video'}_{shortcode}.{ext}"
        output_file = os.path.join(output_path, final_filename)
        
        # آدرس امبد - با تشخیص نوع محتوا (ریل یا پست)
        if 'reel' in url.lower():
            embed_url = f"https://www.instagram.com/reel/{shortcode}/embed/"
            logger.info(f"استفاده از URL امبد نوع ریل (reel): {embed_url}")
        else:
            embed_url = f"https://www.instagram.com/p/{shortcode}/embed/"
            logger.info(f"استفاده از URL امبد نوع پست عادی: {embed_url}")
        
        # هدرها برای درخواست امبد - اصلاح شده برای دور زدن محدودیت‌ها
        headers = generate_headers(is_mobile=False)
        headers['Referer'] = 'https://www.instagram.com/'
        headers['X-Instagram-AJAX'] = '1'
        headers['X-IG-App-ID'] = '936619743392459'
        headers['X-ASBD-ID'] = '129477'
        
        # افزودن کوکی برای دور زدن محدودیت‌های دسترسی
        session = requests.Session()
        # اضافه کردن کوکی‌های حیاتی
        for key, value in DEFAULT_COOKIES[0].items():
            session.cookies.set(key, value, domain='.instagram.com')
            
        # درخواست به صفحه امبد
        response = session.get(embed_url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            logger.warning(f"دسترسی به صفحه امبد ناموفق با کد وضعیت: {response.status_code}")
            return None
        
        # الگوهای جستجو برای URL ویدیو در HTML - بهبود پیدا کرده با الگوهای دقیق‌تر
        video_patterns = [
            r'\"video_url\":\"([^\"]+)\"',
            r'property="og:video" content="([^"]+)"',
            r'<video[^>]+src="([^"]+)"',
            r'<source src="([^"]+)"',
            r'"contentUrl":"([^"]+)"',
            r'"video":{"contentUrl":"([^"]+)"',
            r'video_url":"([^"]+)"',
            r'"video":\s*{\s*"contentUrl":\s*"([^"]+)"',
            r'"@type":\s*"VideoObject",\s*"contentUrl":\s*"([^"]+)"',
            r'<meta property="og:video:secure_url" content="([^"]+)"',
            r'<meta name="twitter:player:stream" content="([^"]+)"',
        ]
        
        media_url = None
        
        # بررسی الگوها در پاسخ
        for pattern in video_patterns:
            matches = re.findall(pattern, response.text)
            if matches:
                media_url = matches[0].replace('\\u0026', '&').replace('\\/', '/')
                logger.info(f"URL مدیا با الگوی regex در امبد پیدا شد: {pattern}")
                break
        
        if not media_url:
            # جستجوی عمیق‌تر برای JSON داده‌ها
            json_data_matches = re.findall(r'window\._sharedData\s*=\s*(\{.+?\});</script>', response.text)
            if json_data_matches:
                try:
                    shared_data = json.loads(json_data_matches[0])
                    # استخراج URL ویدیو از shared_data
                    if 'entry_data' in shared_data and 'PostPage' in shared_data['entry_data']:
                        post = shared_data['entry_data']['PostPage'][0]['graphql']['shortcode_media']
                        if 'video_url' in post:
                            media_url = post['video_url']
                except Exception as e:
                    logger.warning(f"خطا در استخراج داده‌های JSON از صفحه امبد: {e}")
        
        # اگر هنوز URL پیدا نشده، جستجوی عمیق‌تر
        if not media_url:
            # جستجو برای متغیرهای جاوااسکریپت
            js_vars_matches = re.findall(r'window\.__additionalDataLoaded\s*\(\s*[\'"][^\'"]+[\'"]\s*,\s*(\{.+?\})\);', response.text)
            if js_vars_matches:
                try:
                    additional_data = json.loads(js_vars_matches[0])
                    # استخراج URL ویدیو از additional_data
                    if 'graphql' in additional_data and 'shortcode_media' in additional_data['graphql']:
                        post = additional_data['graphql']['shortcode_media']
                        if 'video_url' in post:
                            media_url = post['video_url']
                except Exception as e:
                    logger.warning(f"خطا در استخراج داده‌های اضافی از صفحه امبد: {e}")
        
        # جستجو برای JSON در متا تگ‌ها
        if not media_url:
            json_ld_matches = re.findall(r'<script type="application/ld\\+json">(.+?)</script>', response.text, re.DOTALL)
            if json_ld_matches:
                try:
                    for json_ld in json_ld_matches:
                        data = json.loads(json_ld)
                        if 'contentUrl' in data:
                            media_url = data['contentUrl']
                            break
                        elif '@graph' in data:
                            for item in data['@graph']:
                                if 'contentUrl' in item:
                                    media_url = item['contentUrl']
                                    break
                except Exception as e:
                    logger.warning(f"خطا در استخراج JSON-LD از صفحه امبد: {e}")
        
        # اگر URL پیدا شد، دانلود کنیم
        if media_url:
            logger.info(f"شروع دانلود مستقیم از URL امبد: {media_url}")
            
            # ایجاد هدرهای جدید برای دانلود
            dl_headers = {
                'User-Agent': headers['User-Agent'],
                'Accept': '*/*',
                'Accept-Encoding': 'identity;q=1, *;q=0',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': embed_url,
                'Range': 'bytes=0-',
                'Connection': 'keep-alive'
            }
            
            response = session.get(media_url, headers=dl_headers, stream=True, timeout=30)
            
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
            logger.warning("هیچ URL مدیایی از صفحه امبد پیدا نشد")
    
    except Exception as e:
        logger.error(f"خطا در دانلود با API امبد: {e}")
    
    return None

def download_with_graphql_api(url: str, shortcode: str, output_path: str, quality: str) -> Optional[str]:
    """
    دانلود محتوا با استفاده از GraphQL API اینستاگرام (روش جدید و قدرتمند)
    این روش با استفاده از API داخلی GraphQL اینستاگرام که برای وب اپلیکیشن طراحی شده است کار می‌کند.
    شناسه‌های API به صورت تصادفی ایجاد می‌شوند تا از مسدود شدن جلوگیری شود.
    
    Args:
        url: آدرس پست اینستاگرام
        shortcode: کد کوتاه استخراج شده
        output_path: مسیر خروجی
        quality: کیفیت درخواستی (best, 1080p, 720p, 480p, 360p, 240p, audio)
        
    Returns:
        مسیر فایل دانلود شده یا None در صورت خطا
    """
    try:
        logger.info(f"تلاش دانلود با GraphQL API برای {shortcode}")
        
        # تعیین فرمت خروجی
        is_audio = quality == "audio"
        ext = "mp3" if is_audio else "mp4"
        final_filename = f"instagram_graphql_{'audio' if is_audio else 'video'}_{shortcode}.{ext}"
        output_file = os.path.join(output_path, final_filename)
        
        # آماده‌سازی GraphQL query با استفاده از شورت‌کد
        graphql_url = "https://www.instagram.com/graphql/query/"
        query_hash = "b3055c01b4b222b8a47dc12b090e4e64"  # hash برای media shortcode
        
        variables = {
            "shortcode": shortcode,
            "child_comment_count": 0,
            "fetch_comment_count": 0,
            "parent_comment_count": 0,
            "has_threaded_comments": False
        }
        
        # پارامترهای query string
        params = {
            "query_hash": query_hash,
            "variables": json.dumps(variables)
        }
        
        # انتخاب User-Agent و هدرهای مناسب
        headers = {
            'User-Agent': random.choice(DEFAULT_USER_AGENTS),
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': f'https://www.instagram.com/p/{shortcode}/',
            'X-IG-App-ID': '936619743392459',
            'X-Requested-With': 'XMLHttpRequest',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
        }
        
        # استفاده از کوکی‌های پیش‌فرض (اختیاری)
        cookies = random.choice(DEFAULT_COOKIES)
        
        # ایجاد session با کوکی‌های تصادفی
        session = requests.Session()
        for key, value in cookies.items():
            if value:  # فقط کوکی‌های غیر خالی را اضافه کن
                session.cookies.set(key, value, domain='.instagram.com')
        
        # ارسال درخواست GraphQL
        response = session.get(graphql_url, params=params, headers=headers, timeout=15)
        
        media_url = None
        
        # پردازش پاسخ
        if response.status_code == 200:
            try:
                data = response.json()
                if 'data' in data and 'shortcode_media' in data['data']:
                    media = data['data']['shortcode_media']
                    
                    # تلاش برای یافتن URL ویدیو
                    if 'video_url' in media:
                        media_url = media['video_url']
                        logger.info(f"URL ویدیو از GraphQL پیدا شد: {media_url}")
                    elif 'edge_sidecar_to_children' in media:
                        # برای پست‌های چندتایی (کاروسل)
                        edges = media['edge_sidecar_to_children']['edges']
                        for edge in edges:
                            node = edge['node']
                            if 'video_url' in node:
                                media_url = node['video_url']
                                logger.info(f"URL ویدیو از کاروسل GraphQL پیدا شد: {media_url}")
                                break
            except Exception as e:
                logger.warning(f"خطا در پردازش پاسخ GraphQL: {e}")
        else:
            logger.warning(f"درخواست GraphQL ناموفق با کد وضعیت: {response.status_code}")
            
        # اگر URL پیدا شد، دانلود کنیم
        if media_url:
            logger.info(f"شروع دانلود مستقیم از GraphQL URL: {media_url}")
            
            # ایجاد هدرهای جدید برای دانلود
            dl_headers = {
                'User-Agent': headers['User-Agent'],
                'Accept': '*/*',
                'Accept-Encoding': 'identity;q=1, *;q=0',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': f'https://www.instagram.com/p/{shortcode}/',
                'Range': 'bytes=0-',
                'Connection': 'keep-alive'
            }
            
            response = session.get(media_url, headers=dl_headers, stream=True, timeout=30)
            
            if response.status_code in [200, 206]:
                with open(output_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                # بررسی فایل نهایی
                if os.path.exists(output_file) and os.path.getsize(output_file) > 10240:  # حداقل 10KB
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
            logger.warning("هیچ URL مدیایی از GraphQL پیدا نشد")
    
    except Exception as e:
        logger.error(f"خطا در دانلود با GraphQL API: {e}")
    
    return None


def download_with_public_api(url: str, shortcode: str, output_path: str, quality: str) -> Optional[str]:
    """
    دانلود محتوا با استفاده از Public API اینستاگرام (oEmbed)
    
    Args:
        url: آدرس پست اینستاگرام
        shortcode: کد کوتاه استخراج شده
        output_path: مسیر خروجی
        quality: کیفیت درخواستی
        
    Returns:
        مسیر فایل دانلود شده یا None در صورت خطا
    """
    try:
        logger.info(f"تلاش دانلود با Public API برای {shortcode}")
        
        # تعیین فرمت خروجی
        is_audio = quality == "audio"
        ext = "mp3" if is_audio else "mp4"
        final_filename = f"instagram_public_{'audio' if is_audio else 'video'}_{shortcode}.{ext}"
        output_file = os.path.join(output_path, final_filename)
        
        # آماده‌سازی URL های API عمومی
        oembed_url = f"https://api.instagram.com/oembed/?url=https://www.instagram.com/p/{shortcode}/"
        public_url = f"https://www.instagram.com/p/{shortcode}/?__a=1&__d=dis"
        
        # انتخاب User-Agent و هدرهای مناسب
        headers = {
            'User-Agent': DEFAULT_USER_AGENTS[4],  # User-Agent دسکتاپ
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.instagram.com/',
            'X-IG-App-ID': '936619743392459',
            'X-Requested-With': 'XMLHttpRequest',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        }
        
        # استفاده از کوکی‌های پیش‌فرض (اختیاری)
        cookies = DEFAULT_COOKIES[1]  # کوکی‌های ساده‌تر
        
        # ایجاد session با کوکی‌های تصادفی
        session = requests.Session()
        for key, value in cookies.items():
            if value:  # فقط کوکی‌های غیر خالی را اضافه کن
                session.cookies.set(key, value, domain='.instagram.com')
        
        # ابتدا امتحان API عمومی جدید
        response = session.get(public_url, headers=headers, timeout=10)
        media_url = None
        
        # پردازش پاسخ
        if response.status_code == 200:
            try:
                data = response.json()
                # استخراج URL ویدیو از ساختارهای مختلف API
                if 'items' in data and len(data['items']) > 0:
                    item = data['items'][0]
                    if 'video_versions' in item and len(item['video_versions']) > 0:
                        media_url = item['video_versions'][0]['url']
                    elif 'carousel_media' in item:
                        for media_item in item['carousel_media']:
                            if 'video_versions' in media_item and len(media_item['video_versions']) > 0:
                                media_url = media_item['video_versions'][0]['url']
                                break
            except Exception as e:
                logger.warning(f"خطا در پردازش پاسخ Public API: {e}")
                
        # اگر روش اول شکست خورد، روش oEmbed را امتحان کنیم
        if not media_url:
            try:
                response = session.get(oembed_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    # از oEmbed فقط thumbnail_url را می‌گیریم و سپس آن را دستکاری میکنیم
                    if 'thumbnail_url' in data:
                        thumbnail_url = data['thumbnail_url']
                        # تلاش برای تبدیل thumbnail_url به video_url
                        if thumbnail_url:
                            # در برخی موارد، می‌توان URL تامبنیل را به URL ویدیو تبدیل کرد
                            possible_video_url = thumbnail_url.replace('/s640x640/', '/').replace('_n.jpg', '.mp4')
                            # امتحان این URL
                            head_response = session.head(possible_video_url, headers=headers, timeout=5)
                            if head_response.status_code == 200:
                                media_url = possible_video_url
            except Exception as e:
                logger.warning(f"خطا در پردازش پاسخ oEmbed: {e}")
                
        # اگر URL پیدا شد، دانلود کنیم
        if media_url:
            logger.info(f"شروع دانلود مستقیم از Public API URL: {media_url}")
            
            # ایجاد هدرهای جدید برای دانلود
            dl_headers = {
                'User-Agent': headers['User-Agent'],
                'Accept': '*/*',
                'Accept-Encoding': 'identity;q=1, *;q=0',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': f'https://www.instagram.com/p/{shortcode}/',
                'Range': 'bytes=0-',
                'Connection': 'keep-alive'
            }
            
            response = session.get(media_url, headers=dl_headers, stream=True, timeout=30)
            
            if response.status_code in [200, 206]:
                with open(output_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                # بررسی فایل نهایی
                if os.path.exists(output_file) and os.path.getsize(output_file) > 10240:  # حداقل 10KB
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
            logger.warning("هیچ URL مدیایی از Public API پیدا نشد")
    
    except Exception as e:
        logger.error(f"خطا در دانلود با Public API: {e}")
    
    return None


def download_with_mobile_api(url: str, shortcode: str, output_path: str, quality: str) -> Optional[str]:
    """
    دانلود محتوا با استفاده از API موبایل اینستاگرام
    
    Args:
        url: آدرس پست اینستاگرام
        shortcode: کد کوتاه استخراج شده
        output_path: مسیر خروجی
        quality: کیفیت درخواستی
        
    Returns:
        مسیر فایل دانلود شده یا None در صورت خطا
    """
    try:
        logger.info(f"تلاش دانلود با API موبایل برای {shortcode}")
        
        # تعیین فرمت خروجی
        is_audio = quality == "audio"
        ext = "mp3" if is_audio else "mp4"
        final_filename = f"instagram_mobile_{'audio' if is_audio else 'video'}_{shortcode}.{ext}"
        output_file = os.path.join(output_path, final_filename)
        
        # آدرس‌های API موبایل
        api_url = f"https://i.instagram.com/api/v1/media/{shortcode}/info/"
        
        # هدرها برای API موبایل - بسیار مهم
        headers = {
            'User-Agent': 'Instagram 243.0.0.16.111 Android (31/12; 480dpi; 1080x2298; OPPO; CPH2269; OP4F2F; mt6885; en_US; 384108453)',
            'Accept': '*/*',
            'Accept-Language': 'en-US',
            'Accept-Encoding': 'gzip, deflate, br',
            'X-IG-App-ID': '936619743392459',
            'X-IG-WWW-Claim': '0',
            'X-IG-Device-ID': ''.join(random.choice(string.hexdigits) for _ in range(16)),
            'X-IG-Android-ID': ''.join(random.choice(string.hexdigits) for _ in range(16)),
            'X-IG-Connection-Type': 'WIFI',
            'X-IG-Capabilities': '3brTv10=',
            'X-IG-App-Locale': 'en_US',
            'X-FB-HTTP-Engine': 'Liger',
            'Connection': 'keep-alive',
        }
        
        # درخواست به API موبایل
        session = requests.Session()
        response = session.get(api_url, headers=headers, timeout=10)
        
        media_url = None
        
        if response.status_code == 200:
            try:
                data = response.json()
                
                if 'items' in data and len(data['items']) > 0:
                    item = data['items'][0]
                    
                    if 'video_versions' in item and len(item['video_versions']) > 0:
                        # برای ویدیو - انتخاب بهترین کیفیت
                        media_url = item['video_versions'][0]['url']
                        logger.info(f"URL مدیا از API موبایل پیدا شد (ویدیو): {media_url}")
                    elif 'carousel_media' in item:
                        # برای آلبوم - بررسی تمام آیتم‌ها برای یافتن ویدیو
                        for carousel_item in item['carousel_media']:
                            if 'video_versions' in carousel_item and len(carousel_item['video_versions']) > 0:
                                media_url = carousel_item['video_versions'][0]['url']
                                logger.info(f"URL مدیا از API موبایل پیدا شد (کاروسل): {media_url}")
                                break
            except Exception as e:
                logger.warning(f"خطا در پردازش پاسخ API موبایل: {e}")
        else:
            logger.warning(f"دسترسی به API موبایل ناموفق با کد وضعیت: {response.status_code}")
        
        # اگر URL پیدا شد، دانلود کنیم
        if media_url:
            logger.info(f"شروع دانلود مستقیم از URL موبایل: {media_url}")
            
            # ایجاد هدرهای جدید برای دانلود
            dl_headers = {
                'User-Agent': headers['User-Agent'],
                'Accept': '*/*',
                'Accept-Encoding': 'identity;q=1, *;q=0',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive'
            }
            
            response = session.get(media_url, headers=dl_headers, stream=True, timeout=30)
            
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
        
    except Exception as e:
        logger.error(f"خطا در دانلود با API موبایل: {e}")
    
    return None

def download_with_direct_method(url: str, shortcode: str, output_path: str, quality: str) -> Optional[str]:
    """
    دانلود محتوا با استفاده از روش مستقیم و بررسی تمام اسکریپت‌های صفحه
    
    Args:
        url: آدرس پست اینستاگرام
        shortcode: کد کوتاه استخراج شده
        output_path: مسیر خروجی
        quality: کیفیت درخواستی
        
    Returns:
        مسیر فایل دانلود شده یا None در صورت خطا
    """
    try:
        logger.info(f"تلاش دانلود با روش کامل و بررسی اسکریپت‌ها برای {shortcode}")
        
        # تعیین فرمت خروجی
        is_audio = quality == "audio"
        ext = "mp3" if is_audio else "mp4"
        final_filename = f"instagram_direct_{'audio' if is_audio else 'video'}_{shortcode}.{ext}"
        output_file = os.path.join(output_path, final_filename)
        
        # روش مستقیم: حمله از چندین جهت به صفحه برای یافتن URL ویدیو
        session = requests.Session()
        
        # روش 1: صفحه رییل (مناسب برای رییل‌ها)
        reel_url = f"https://www.instagram.com/reel/{shortcode}/"
        headers_mobile = generate_headers(is_mobile=True)
        response = session.get(reel_url, headers=headers_mobile, timeout=10)
        
        # الگوهای جستجو - بهینه شده
        video_patterns = [
            r'"video_url":"([^"]+)"',
            r'"video":{[^}]+"contentUrl":"([^"]+)"',
            r'"contentUrl":"([^"]+)"',
            r'"contentUrl"\s*:\s*"([^"]+)"',
            r'<meta property="og:video" content="([^"]+)"',
            r'<meta property="og:video:secure_url" content="([^"]+)"',
            r'<video[^>]+src="([^"]+)"',
            r'<source src="([^"]+)"',
            r'"video_versions":\[{"type":\d+,"width":\d+,"height":\d+,"url":"([^"]+)"',
            r'"playable_url":"([^"]+)"',
            r'"playable_url_quality_hd":"([^"]+)"',
        ]
        
        media_url = None
        media_sources = []
        
        # تلاش برای یافتن URL ویدیو در صفحه رییل با الگوها
        for pattern in video_patterns:
            matches = re.findall(pattern, response.text)
            if matches:
                for match in matches:
                    cleaned_url = match.replace('\\u0026', '&').replace('\\/', '/')
                    media_sources.append(cleaned_url)
                    logger.info(f"URL مدیا با الگوی regex پیدا شد: {pattern}")
        
        # روش 2: صفحه پست معمولی
        if not media_sources:
            post_url = f"https://www.instagram.com/p/{shortcode}/"
            headers_desktop = generate_headers(is_mobile=False)
            response = session.get(post_url, headers=headers_desktop, timeout=10)
            
            for pattern in video_patterns:
                matches = re.findall(pattern, response.text)
                if matches:
                    for match in matches:
                        cleaned_url = match.replace('\\u0026', '&').replace('\\/', '/')
                        media_sources.append(cleaned_url)
                        logger.info(f"URL مدیا با الگوی regex در صفحه پست پیدا شد: {pattern}")
        
        # روش 3: جستجوی شیء shared_data در کد جاوااسکریپت
        if not media_sources and ('window._sharedData' in response.text or 'window.__additionalDataLoaded' in response.text):
            # استخراج اطلاعات از shared_data
            shared_data_matches = re.findall(r'window\._sharedData\s*=\s*(\{.+?\});</script>', response.text)
            if shared_data_matches:
                try:
                    shared_data = json.loads(shared_data_matches[0])
                    
                    # گشتن در ساختار پیچیده برای یافتن ویدیو
                    if 'entry_data' in shared_data:
                        if 'PostPage' in shared_data['entry_data']:
                            posts = shared_data['entry_data']['PostPage']
                            for post in posts:
                                if 'graphql' in post and 'shortcode_media' in post['graphql']:
                                    media = post['graphql']['shortcode_media']
                                    if 'video_url' in media:
                                        media_sources.append(media['video_url'])
                except Exception as e:
                    logger.warning(f"خطا در استخراج shared_data: {e}")
            
            # استخراج اطلاعات از additionalData
            additional_data_matches = re.findall(r'window\.__additionalDataLoaded\s*\(\s*[\'"][^\'"]+[\'"]\s*,\s*(\{.+?\})\);', response.text)
            if additional_data_matches:
                try:
                    for data_match in additional_data_matches:
                        additional_data = json.loads(data_match)
                        if 'graphql' in additional_data and 'shortcode_media' in additional_data['graphql']:
                            media = additional_data['graphql']['shortcode_media']
                            if 'video_url' in media:
                                media_sources.append(media['video_url'])
                except Exception as e:
                    logger.warning(f"خطا در استخراج additionalData: {e}")
        
        # روش 4: استفاده از قالب موبایل ویژه API
        if not media_sources:
            mobile_api_result = download_with_mobile_api(url, shortcode, output_path, quality)
            if mobile_api_result:
                return mobile_api_result
        
        # روش 5: استفاده از قالب امبد
        if not media_sources:
            embed_api_result = download_with_embed_api(url, shortcode, output_path, quality)
            if embed_api_result:
                return embed_api_result
        
        # انتخاب بهترین URL از منابع پیدا شده
        if media_sources:
            # ترجیح به URL‌های اصلی اینستاگرام
            for source in media_sources:
                if 'cdninstagram.com' in source or 'fbcdn.net' in source:
                    media_url = source
                    break
            
            # اگر URL خاصی پیدا نشد، از اولین منبع استفاده کن
            if not media_url and media_sources:
                media_url = media_sources[0]
        
        # اگر URL پیدا شد، دانلود کنیم
        if media_url:
            logger.info(f"شروع دانلود مستقیم از URL: {media_url}")
            
            # ایجاد هدرهای جدید برای دانلود
            dl_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': '*/*',
                'Accept-Encoding': 'identity;q=1, *;q=0',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': url,
                'Range': 'bytes=0-',
                'Connection': 'keep-alive'
            }
            
            response = session.get(media_url, headers=dl_headers, stream=True, timeout=30)
            
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

def download_with_curl_method(url: str, shortcode: str, output_path: str, quality: str) -> Optional[str]:
    """
    دانلود محتوا با استفاده از curl برای دور زدن محدودیت‌های احتمالی
    
    Args:
        url: آدرس پست اینستاگرام
        shortcode: کد کوتاه استخراج شده
        output_path: مسیر خروجی
        quality: کیفیت درخواستی
        
    Returns:
        مسیر فایل دانلود شده یا None در صورت خطا
    """
    try:
        logger.info(f"تلاش دانلود با روش curl برای {shortcode}")
        
        # تعیین فرمت خروجی
        is_audio = quality == "audio"
        ext = "mp3" if is_audio else "mp4"
        final_filename = f"instagram_curl_{'audio' if is_audio else 'video'}_{shortcode}.{ext}"
        output_file = os.path.join(output_path, final_filename)
        
        # ابتدا باید URL ویدیو را از یکی از روش‌های قبلی پیدا کنیم
        # روش 1: صفحه رییل
        headers = generate_headers(is_mobile=True)
        session = requests.Session()
        
        reel_url = f"https://www.instagram.com/reel/{shortcode}/"
        response = session.get(reel_url, headers=headers, timeout=10)
        
        video_patterns = [
            r'"video_url":"([^"]+)"',
            r'"contentUrl":"([^"]+)"',
            r'<meta property="og:video" content="([^"]+)"',
        ]
        
        media_url = None
        
        # بررسی الگوها در پاسخ
        for pattern in video_patterns:
            matches = re.findall(pattern, response.text)
            if matches:
                media_url = matches[0].replace('\\u0026', '&').replace('\\/', '/')
                logger.info(f"URL مدیا با الگوی regex پیدا شد: {pattern}")
                break
        
        # اگر URL پیدا نشد، از روش‌های دیگر استفاده کن
        if not media_url:
            embed_url = f"https://www.instagram.com/p/{shortcode}/embed/"
            embed_headers = generate_headers(is_mobile=False)
            response = session.get(embed_url, headers=embed_headers, timeout=10)
            
            for pattern in video_patterns:
                matches = re.findall(pattern, response.text)
                if matches:
                    media_url = matches[0].replace('\\u0026', '&').replace('\\/', '/')
                    logger.info(f"URL مدیا با الگوی regex در صفحه امبد پیدا شد: {pattern}")
                    break
        
        # اگر URL پیدا شد، با curl دانلود کنیم
        if media_url:
            logger.info(f"شروع دانلود با curl از URL: {media_url}")
            
            # ساخت دستور curl
            user_agent = random.choice(DEFAULT_USER_AGENTS)
            
            curl_cmd = [
                'curl',
                '-L',  # دنبال کردن ریدایرکت‌ها
                '-s',  # حالت سایلنت
                '-o', output_file,  # فایل خروجی
                '-H', f'User-Agent: {user_agent}',
                '-H', f'Referer: {url}',
                '-H', 'Accept: */*',
                '-H', 'Accept-Encoding: identity;q=1, *;q=0',
                media_url
            ]
            
            # اجرای curl با زمان‌سنجی
            start_time = time.time()
            process = subprocess.run(curl_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            download_time = time.time() - start_time
            
            # بررسی نتیجه دانلود
            if process.returncode == 0 and os.path.exists(output_file) and os.path.getsize(output_file) > 1024:
                logger.info(f"دانلود با curl موفق بود: {output_file} ({os.path.getsize(output_file)} بایت در {download_time:.2f} ثانیه)")
                
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
                logger.warning(f"دانلود با curl ناموفق بود: {process.stderr.decode('utf-8', errors='ignore')}")
        else:
            logger.warning("هیچ URL مدیایی برای دانلود با curl پیدا نشد")
    
    except Exception as e:
        logger.error(f"خطا در دانلود با روش curl: {e}")
    
    return None

def download_instagram_content(url: str, output_path: str, quality: str = "best") -> Optional[str]:
    """
    دانلود محتوا از اینستاگرام با استفاده از همه روش‌های ممکن
    این تابع برای دانلود بدون نیاز به لاگین طراحی شده و از چندین روش پشت سر هم استفاده می‌کند.
    اولویت دانلود با استفاده از API های رسمی اینستاگرام است که نیاز به لاگین ندارند.
    
    این تابع بخشی از ماژول instagram_direct_downloader است که برای استفاده در ربات تلگرام 
    طراحی شده است. این تابع با استفاده از روش‌های مختلف سعی می‌کند بدون احراز هویت محتوا را دانلود کند.
    
    Args:
        url: آدرس پست اینستاگرام
        output_path: مسیر خروجی
        quality: کیفیت درخواستی (best, 1080p, 720p, 480p, 360p, 240p, audio)
        
    Returns:
        مسیر فایل دانلود شده یا None در صورت خطا
    """
    # اطمینان از وجود دایرکتوری خروجی
    os.makedirs(output_path, exist_ok=True)
    
    logger.info(f"شروع دانلود مستقیم اینستاگرام: {url} با کیفیت {quality}")
    logger.info(f"دایرکتوری خروجی: {output_path}")
    
    # نرمال‌سازی URL
    url = url.split('?')[0].split('#')[0]
    if not url.endswith('/'):
        url = url + '/'
    shortcode = extract_shortcode_from_url(url)
    if not shortcode:
        logger.error(f"کد کوتاه اینستاگرام برای URL استخراج نشد: {url}")
        return None
    
    logger.info(f"شروع دانلود از اینستاگرام با کد کوتاه: {shortcode}, کیفیت: {quality}")
    
    # ایجاد محل ذخیره‌سازی موقت برای این دانلود
    download_dir = os.path.join(output_path, f"instagram_{shortcode}")
    os.makedirs(download_dir, exist_ok=True)
    
    # لیست روش‌های مختلف دانلود به ترتیب اولویت - اصلاح شده با اولویت‌های جدید
    # مرتب‌سازی روش‌های دانلود براساس میزان موفقیت در دور زدن محدودیت‌های اینستاگرام
    methods = []
    
    # متدها را بر اساس کیفیت درخواستی اولویت‌بندی می‌کنیم
    if quality == "audio":
        # برای درخواست‌های صوتی، روش‌های خاص اولویت بالاتری دارند
        methods = [
            # روش گراف‌کوئری با اولویت اول - روش جدید و قوی
            ("GraphQL API", lambda: download_with_graphql_api(url, shortcode, download_dir, quality)),
            # API موبایل برای صدا خوب عمل می‌کند
            ("API موبایل", lambda: download_with_mobile_api(url, shortcode, download_dir, quality)),
            # API امبد برای صدا
            ("API امبد", lambda: download_with_embed_api(url, shortcode, download_dir, quality)),
            # سایر روش‌ها
            ("Public API", lambda: download_with_public_api(url, shortcode, download_dir, quality)),
            ("روش مستقیم کامل", lambda: download_with_direct_method(url, shortcode, download_dir, quality)),
            ("روش curl", lambda: download_with_curl_method(url, shortcode, download_dir, quality))
        ]
    elif "240p" in quality or "360p" in quality:
        # برای کیفیت‌های پایین، API موبایل بهتر است
        methods = [
            ("API موبایل", lambda: download_with_mobile_api(url, shortcode, download_dir, quality)),
            ("GraphQL API", lambda: download_with_graphql_api(url, shortcode, download_dir, quality)),
            ("API امبد", lambda: download_with_embed_api(url, shortcode, download_dir, quality)),
            ("Public API", lambda: download_with_public_api(url, shortcode, download_dir, quality)),
            ("روش مستقیم کامل", lambda: download_with_direct_method(url, shortcode, download_dir, quality)),
            ("روش curl", lambda: download_with_curl_method(url, shortcode, download_dir, quality))
        ]
    elif "1080p" in quality or "720p" in quality or "best" in quality:
        # برای کیفیت‌های بالا، GraphQL API بهتر است
        methods = [
            ("GraphQL API", lambda: download_with_graphql_api(url, shortcode, download_dir, quality)),
            ("API امبد", lambda: download_with_embed_api(url, shortcode, download_dir, quality)),
            ("Public API", lambda: download_with_public_api(url, shortcode, download_dir, quality)),
            ("API موبایل", lambda: download_with_mobile_api(url, shortcode, download_dir, quality)),
            ("روش مستقیم کامل", lambda: download_with_direct_method(url, shortcode, download_dir, quality)),
            ("روش curl", lambda: download_with_curl_method(url, shortcode, download_dir, quality))
        ]
    else:
        # پیش‌فرض برای سایر کیفیت‌ها
        methods = [
            # روش گراف‌کوئری با اولویت اول - روش جدید و قوی
            ("GraphQL API", lambda: download_with_graphql_api(url, shortcode, download_dir, quality)),
            # API امبد با اولویت دوم
            ("API امبد", lambda: download_with_embed_api(url, shortcode, download_dir, quality)),
            # روش با استفاده از Public API
            ("Public API", lambda: download_with_public_api(url, shortcode, download_dir, quality)),
            # API موبایل 
            ("API موبایل", lambda: download_with_mobile_api(url, shortcode, download_dir, quality)),
            # روش مستقیم کامل
            ("روش مستقیم کامل", lambda: download_with_direct_method(url, shortcode, download_dir, quality)),
            # روش curl با اولویت آخر
            ("روش curl", lambda: download_with_curl_method(url, shortcode, download_dir, quality))
        ]
    
    downloaded_file = None
    
    # امتحان همه روش‌ها به ترتیب تا یکی موفق شود
    for method_name, method_func in methods:
        try:
            logger.info(f"تلاش دانلود با {method_name}...")
            result = method_func()
            if result and os.path.exists(result) and os.path.getsize(result) > 1024:  # حداقل 1KB
                logger.info(f"دانلود با {method_name} موفق: {result}")
                downloaded_file = result
                break
        except Exception as e:
            logger.warning(f"خطا در {method_name}: {e}")
    
    # اگر فایل با کیفیت مورد نظر دانلود شد
    if downloaded_file:
        # مسیر نهایی با نام استاندارد
        final_ext = "mp3" if quality == "audio" else "mp4"
        final_filename = f"instagram_{shortcode}_{quality}.{final_ext}"
        final_path = os.path.join(output_path, final_filename)
        
        # انتقال فایل به مسیر نهایی
        try:
            import shutil
            shutil.copy2(downloaded_file, final_path)
            logger.info(f"فایل دانلود شده به مسیر نهایی منتقل شد: {final_path}")
            
            # پاکسازی دایرکتوری موقت
            try:
                shutil.rmtree(download_dir)
            except:
                pass
                
            return final_path
        except Exception as e:
            logger.error(f"خطا در انتقال فایل دانلود شده: {e}")
            return downloaded_file
    
    logger.error("تمام روش‌های دانلود با شکست مواجه شدند")
    return None

def main():
    """اجرای تست ماژول"""
    # تست دانلود یک ویدیوی اینستاگرام
    test_url = "https://www.instagram.com/reel/CxIoBLSt8on/"
    output_path = TEMP_DIR
    
    # تست با کیفیت‌های مختلف
    qualities = ["best", "1080p", "audio"]
    
    for quality in qualities:
        logger.info(f"تست دانلود با کیفیت {quality}...")
        start_time = time.time()
        result = download_instagram_content(test_url, output_path, quality)
        elapsed_time = time.time() - start_time
        
        if result:
            file_size = os.path.getsize(result) / (1024 * 1024)  # به مگابایت
            logger.info(f"دانلود موفق با کیفیت {quality}: {result} ({file_size:.2f} MB در {elapsed_time:.2f} ثانیه)")
        else:
            logger.error(f"دانلود با کیفیت {quality} ناموفق بود")

if __name__ == "__main__":
    main()
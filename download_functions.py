#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
توابع دانلود برای ربات تلگرام

این ماژول شامل توابع دانلود برای ویدیوهای یوتیوب و اینستاگرام است.
"""

import os
import time
import logging
import traceback
from typing import Dict, Optional, Union

from telegram import Update
from telegram.ext import ContextTypes
import yt_dlp

# تنظیم لاگر
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ثابت‌های مسیر
TEMP_DOWNLOAD_DIR = os.path.join(os.getcwd(), 'downloads')

# پیام‌های خطا و وضعیت
ERROR_MESSAGES = {
    "generic_error": "❌ خطایی رخ داد. لطفاً مجدداً تلاش کنید.",
    "download_failed": "❌ دانلود ناموفق بود. لطفاً مجدداً تلاش کنید.",
    "conversion_failed": "❌ تبدیل فایل ناموفق بود. لطفاً مجدداً تلاش کنید.",
    "quality_not_available": "❌ کیفیت انتخاب شده در دسترس نیست. لطفاً کیفیت دیگری انتخاب کنید."
}

STATUS_MESSAGES = {
    "downloading": "⏳ در حال دانلود... لطفاً صبر کنید.",
    "converting": "⏳ در حال تبدیل فایل... لطفاً صبر کنید.",
    "uploading": "⏳ در حال آپلود فایل... لطفاً صبر کنید.",
    "completed": "✅ دانلود با موفقیت انجام شد."
}

def is_valid_file(file_path: str) -> bool:
    """
    بررسی می‌کند که آیا فایل معتبر است
    
    Args:
        file_path: مسیر فایل
        
    Returns:
        True اگر فایل معتبر است، در غیر این صورت False
    """
    if not file_path or not os.path.exists(file_path):
        return False
    
    # بررسی حداقل اندازه فایل (10 کیلوبایت)
    if os.path.getsize(file_path) < 10240:
        return False
        
    return True

def is_video_file(file_path: str) -> bool:
    """
    بررسی می‌کند که آیا فایل از نوع ویدیو است
    
    Args:
        file_path: مسیر فایل
        
    Returns:
        True اگر فایل ویدیویی است، در غیر این صورت False
    """
    if not is_valid_file(file_path):
        return False
    
    video_extensions = ('.mp4', '.mkv', '.avi', '.webm', '.mov', '.flv')
    return file_path.lower().endswith(video_extensions)

def is_audio_file(file_path: str) -> bool:
    """
    بررسی می‌کند که آیا فایل از نوع صوتی است
    
    Args:
        file_path: مسیر فایل
        
    Returns:
        True اگر فایل صوتی است، در غیر این صورت False
    """
    if not is_valid_file(file_path):
        return False
    
    audio_extensions = ('.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg')
    return file_path.lower().endswith(audio_extensions)

def human_readable_size(size_bytes: int) -> str:
    """
    تبدیل حجم فایل از بایت به فرمت خوانا برای انسان
    
    Args:
        size_bytes: حجم فایل به بایت
        
    Returns:
        رشته حاوی حجم فایل با واحد مناسب
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

async def download_youtube_with_option(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, option: Dict) -> None:
    """
    دانلود ویدیوی یوتیوب با گزینه انتخاب شده
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: کانتکست تلگرام
        url: آدرس یوتیوب
        option: گزینه انتخاب شده برای دانلود (شامل کیفیت و نوع)
    """
    query = update.callback_query
    user_id = update.effective_user.id
    
    try:
        # تنظیم پیام وضعیت
        await query.edit_message_text(STATUS_MESSAGES["downloading"])
        
        # ایجاد دانلودر یوتیوب
        from telegram_downloader import YouTubeDownloader
        downloader = YouTubeDownloader()
        
        # تعیین نوع دانلود (ویدیو یا صدا)
        is_audio = option.get('type') == 'audio' or 'audio' in option.get('quality', '').lower()
        
        if is_audio:
            # دانلود صدا
            logger.info(f"درخواست دانلود صدای یوتیوب: {url}")
            downloaded_file = await downloader.download_audio(url)
        else:
            # دانلود ویدیو با کیفیت مشخص
            quality = option.get('quality', '720p')
            logger.info(f"درخواست دانلود ویدیوی یوتیوب با کیفیت {quality}: {url}")
            downloaded_file = await downloader.download_video(url, quality)
        
        # بررسی نتیجه دانلود
        if not downloaded_file or not os.path.exists(downloaded_file):
            logger.error(f"دانلود ناموفق بود: {url}")
            await query.edit_message_text(ERROR_MESSAGES["download_failed"])
            return
            
        # دریافت اطلاعات ویدیو
        video_info = await downloader.get_video_info(url)
        video_title = video_info.get('title', 'ویدیوی دانلود شده')
        
        # ارسال فایل دانلود شده
        await query.edit_message_text(STATUS_MESSAGES["uploading"])
        
        file_size = os.path.getsize(downloaded_file)
        caption = f"🎬 {video_title}\n\n"
        caption += f"📊 کیفیت: {option.get('display_name', option.get('quality', 'نامشخص'))}\n"
        caption += f"📦 حجم: {human_readable_size(file_size)}"
        
        if is_audio:
            # ارسال فایل صوتی
            await context.bot.send_audio(
                chat_id=user_id,
                audio=open(downloaded_file, 'rb'),
                caption=caption,
                title=video_title
            )
        elif is_video_file(downloaded_file):
            # ارسال ویدیو
            thumb_path = video_info.get('thumbnail')  # اگر در دسترس باشد
            
            await context.bot.send_video(
                chat_id=user_id,
                video=open(downloaded_file, 'rb'),
                caption=caption,
                thumb=open(thumb_path, 'rb') if thumb_path and os.path.exists(thumb_path) else None
            )
        else:
            # ارسال به عنوان فایل معمولی
            await context.bot.send_document(
                chat_id=user_id,
                document=open(downloaded_file, 'rb'),
                caption=caption
            )
        
        # پیام تکمیل دانلود
        await query.edit_message_text(STATUS_MESSAGES["completed"])
        
    except Exception as e:
        logger.error(f"خطا در دانلود یوتیوب: {str(e)}")
        logger.error(f"جزئیات خطا: {traceback.format_exc()}")
        await query.edit_message_text(ERROR_MESSAGES["generic_error"])
        return None
        
async def download_youtube(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, option_id: str) -> None:
    """
    دانلود ویدیوی یوتیوب با شناسه گزینه
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: کانتکست تلگرام
        url: آدرس یوتیوب
        option_id: شناسه گزینه انتخاب شده
    """
    query = update.callback_query
    user_id = update.effective_user.id
    
    try:
        # تنظیم پیام وضعیت
        await query.edit_message_text(STATUS_MESSAGES["downloading"])
        
        # ایجاد دانلودر یوتیوب
        from telegram_downloader import YouTubeDownloader
        downloader = YouTubeDownloader()
        
        # تعیین نوع دانلود (ویدیو یا صدا)
        is_audio = option_id == 'audio'
        
        if is_audio:
            # دانلود صدا
            logger.info(f"درخواست دانلود صدای یوتیوب: {url}")
            downloaded_file = await downloader.download_audio(url)
            quality_display = "فقط صدا (MP3)"
        else:
            # تعیین کیفیت بر اساس option_id
            try:
                option_num = int(option_id)
                
                # نگاشت شماره گزینه به کیفیت متناظر
                if option_num == 0:
                    format_option = "1080p"
                    quality_display = "کیفیت Full HD (1080p)"
                elif option_num == 1:
                    format_option = "720p"
                    quality_display = "کیفیت HD (720p)"
                elif option_num == 2:
                    format_option = "480p"
                    quality_display = "کیفیت متوسط (480p)"
                elif option_num == 3:
                    format_option = "360p" 
                    quality_display = "کیفیت پایین (360p)"
                elif option_num == 4:
                    format_option = "240p"
                    quality_display = "کیفیت خیلی پایین (240p)"
                else:
                    format_option = "720p"  # کیفیت پیش‌فرض
                    quality_display = "کیفیت استاندارد (720p)"
            except ValueError:
                format_option = option_id
                quality_display = f"کیفیت {option_id}"
            
            # دانلود ویدیو
            logger.info(f"درخواست دانلود ویدیو با کیفیت {format_option}: {url}")
            downloaded_file = await downloader.download_video(url, format_option)
            
        # بررسی نتیجه دانلود
        if not downloaded_file or not os.path.exists(downloaded_file):
            logger.error(f"دانلود ناموفق بود: {url}")
            await query.edit_message_text(ERROR_MESSAGES["download_failed"])
            return
            
        # دریافت اطلاعات ویدیو
        video_info = await downloader.get_video_info(url)
        video_title = video_info.get('title', 'ویدیوی دانلود شده')
        
        # ارسال فایل دانلود شده
        await query.edit_message_text(STATUS_MESSAGES["uploading"])
        
        file_size = os.path.getsize(downloaded_file)
        caption = f"🎬 {video_title}\n\n"
        caption += f"📊 کیفیت: {quality_display}\n"
        caption += f"📦 حجم: {human_readable_size(file_size)}"
        
        if is_audio:
            # ارسال فایل صوتی
            await context.bot.send_audio(
                chat_id=user_id,
                audio=open(downloaded_file, 'rb'),
                caption=caption,
                title=video_title
            )
        elif is_video_file(downloaded_file):
            # ارسال ویدیو
            thumb_path = video_info.get('thumbnail')  # اگر در دسترس باشد
            
            await context.bot.send_video(
                chat_id=user_id,
                video=open(downloaded_file, 'rb'),
                caption=caption,
                thumb=open(thumb_path, 'rb') if thumb_path and os.path.exists(thumb_path) else None
            )
        else:
            # ارسال به عنوان فایل معمولی
            await context.bot.send_document(
                chat_id=user_id,
                document=open(downloaded_file, 'rb'),
                caption=caption
            )
        
        # پیام تکمیل دانلود
        await query.edit_message_text(STATUS_MESSAGES["completed"])
        
    except Exception as e:
        logger.error(f"خطا در دانلود یوتیوب: {str(e)}")
        logger.error(f"جزئیات خطا: {traceback.format_exc()}")
        await query.edit_message_text(ERROR_MESSAGES["generic_error"])
        return None

async def download_instagram_with_option(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, option: Dict) -> None:
    """
    دانلود ویدیوی اینستاگرام با گزینه انتخاب شده
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: کانتکست تلگرام
        url: آدرس اینستاگرام
        option: گزینه انتخاب شده برای دانلود (شامل کیفیت و نوع)
    """
    query = update.callback_query
    user_id = update.effective_user.id
    
    try:
        # تنظیم پیام وضعیت
        await query.edit_message_text(STATUS_MESSAGES["downloading"])
        
        # ایجاد دانلودر اینستاگرام
        from telegram_downloader import InstagramDownloader
        downloader = InstagramDownloader()
        
        # تعیین نوع دانلود (ویدیو یا صدا)
        is_audio = option.get('type') == 'audio' or 'audio' in option.get('quality', '').lower()
        
        if is_audio:
            # دانلود صدا
            logger.info(f"درخواست دانلود صدای اینستاگرام: {url}")
            quality = 'audio'
        else:
            # دانلود ویدیو با کیفیت مشخص
            quality = option.get('quality', 'best')
            logger.info(f"درخواست دانلود ویدیوی اینستاگرام با کیفیت {quality}: {url}")
        
        # دانلود پست
        downloaded_file = await downloader.download_post(url, quality)
        
        # بررسی نتیجه دانلود
        if not downloaded_file or not os.path.exists(downloaded_file):
            logger.error(f"دانلود ناموفق بود: {url}")
            await query.edit_message_text(ERROR_MESSAGES["download_failed"])
            return
            
        # ارسال فایل دانلود شده
        await query.edit_message_text(STATUS_MESSAGES["uploading"])
        
        file_size = os.path.getsize(downloaded_file)
        caption = f"🎬 پست اینستاگرام\n\n"
        caption += f"📊 کیفیت: {option.get('display_name', option.get('quality', 'نامشخص'))}\n"
        caption += f"📦 حجم: {human_readable_size(file_size)}"
        
        if is_audio:
            # ارسال فایل صوتی
            await context.bot.send_audio(
                chat_id=user_id,
                audio=open(downloaded_file, 'rb'),
                caption=caption,
                title="صدای پست اینستاگرام"
            )
        elif is_video_file(downloaded_file):
            # ارسال ویدیو
            await context.bot.send_video(
                chat_id=user_id,
                video=open(downloaded_file, 'rb'),
                caption=caption
            )
        else:
            # ارسال به عنوان فایل معمولی
            await context.bot.send_document(
                chat_id=user_id,
                document=open(downloaded_file, 'rb'),
                caption=caption
            )
        
        # پیام تکمیل دانلود
        await query.edit_message_text(STATUS_MESSAGES["completed"])
        
    except Exception as e:
        logger.error(f"خطا در دانلود اینستاگرام: {str(e)}")
        logger.error(f"جزئیات خطا: {traceback.format_exc()}")
        await query.edit_message_text(ERROR_MESSAGES["generic_error"])
        return None

async def download_instagram(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, option_id: str) -> None:
    """
    دانلود ویدیوی اینستاگرام با شناسه گزینه
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: کانتکست تلگرام
        url: آدرس اینستاگرام
        option_id: شناسه گزینه انتخاب شده
    """
    query = update.callback_query
    user_id = update.effective_user.id
    
    try:
        # تنظیم پیام وضعیت
        await query.edit_message_text(STATUS_MESSAGES["downloading"])
        
        # ایجاد دانلودر اینستاگرام
        from telegram_downloader import InstagramDownloader
        downloader = InstagramDownloader()
        
        # تعیین نوع دانلود (ویدیو یا صدا)
        is_audio = option_id == 'audio'
        
        if is_audio:
            # دانلود صدا
            logger.info(f"درخواست دانلود صدای اینستاگرام: {url}")
            quality = 'audio'
            quality_display = "فقط صدا (MP3)"
        else:
            # تعیین کیفیت بر اساس option_id
            try:
                option_num = int(option_id)
                
                # دریافت گزینه‌های دانلود
                options = await downloader.get_download_options(url)
                
                if option_num < len(options):
                    # استفاده از گزینه موجود
                    selected_option = options[option_num]
                    quality = selected_option.get('quality', 'best')
                    quality_display = selected_option.get('display_name', f"کیفیت {quality}")
                else:
                    # استفاده از کیفیت پیش‌فرض
                    quality = 'best'
                    quality_display = "بهترین کیفیت"
            except ValueError:
                quality = option_id
                quality_display = f"کیفیت {option_id}"
            
        # دانلود پست
        logger.info(f"درخواست دانلود اینستاگرام با کیفیت {quality}: {url}")
        downloaded_file = await downloader.download_post(url, quality)
        
        # بررسی نتیجه دانلود
        if not downloaded_file or not os.path.exists(downloaded_file):
            logger.error(f"دانلود ناموفق بود: {url}")
            await query.edit_message_text(ERROR_MESSAGES["download_failed"])
            return
            
        # ارسال فایل دانلود شده
        await query.edit_message_text(STATUS_MESSAGES["uploading"])
        
        file_size = os.path.getsize(downloaded_file)
        caption = f"🎬 پست اینستاگرام\n\n"
        caption += f"📊 کیفیت: {quality_display}\n"
        caption += f"📦 حجم: {human_readable_size(file_size)}"
        
        if is_audio:
            # ارسال فایل صوتی
            await context.bot.send_audio(
                chat_id=user_id,
                audio=open(downloaded_file, 'rb'),
                caption=caption,
                title="صدای پست اینستاگرام"
            )
        elif is_video_file(downloaded_file):
            # ارسال ویدیو
            await context.bot.send_video(
                chat_id=user_id,
                video=open(downloaded_file, 'rb'),
                caption=caption
            )
        else:
            # ارسال به عنوان فایل معمولی
            await context.bot.send_document(
                chat_id=user_id,
                document=open(downloaded_file, 'rb'),
                caption=caption
            )
        
        # پیام تکمیل دانلود
        await query.edit_message_text(STATUS_MESSAGES["completed"])
        
    except Exception as e:
        logger.error(f"خطا در دانلود اینستاگرام: {str(e)}")
        logger.error(f"جزئیات خطا: {traceback.format_exc()}")
        await query.edit_message_text(ERROR_MESSAGES["generic_error"])
        return None
"""
بهبود رابط کاربری ربات تلگرام

این ماژول امکانات پیشرفته رابط کاربری برای ربات تلگرام ارائه می‌دهد.
"""

import os
import re
import time
import logging
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from datetime import datetime
import html

# تنظیم لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

try:
    from telegram import (
        InlineKeyboardButton, InlineKeyboardMarkup, Update, 
        InputMediaPhoto, InputMediaVideo, Bot, ParseMode,
        ChatAction
    )
    from telegram.ext import ContextTypes, CallbackContext
except ImportError:
    logger.error("کتابخانه python-telegram-bot نصب نشده است.")
    
# آیکون‌های یونیکد برای استفاده در پیام‌ها
ICONS = {
    "download": "⬇️",
    "video": "🎬",
    "audio": "🎵",
    "photo": "📷",
    "youtube": "📺",
    "instagram": "📱",
    "settings": "⚙️",
    "help": "❓",
    "info": "ℹ️",
    "warning": "⚠️",
    "error": "❌",
    "success": "✅",
    "wait": "⏳",
    "time": "⏱️",
    "size": "📊",
    "quality": "🔍",
    "like": "👍",
    "view": "👁️",
    "date": "📅",
    "user": "👤",
    "back": "🔙",
    "cancel": "❌",
    "next": "⏩",
    "prev": "⏪",
    "play": "▶️",
    "pause": "⏸️",
    "refresh": "🔄",
    "link": "🔗",
    "file": "📁",
    "progress": "📶",
}

# قالب‌های HTML برای پیام‌های بهتر
HTML_TEMPLATES = {
    "video_info": """
<b>{icon_video} {title}</b>

<b>{icon_user} کانال:</b> {uploader}
<b>{icon_time} مدت زمان:</b> {duration}
<b>{icon_view} بازدید:</b> {view_count}
<b>{icon_like} پسند:</b> {like_count}
<b>{icon_date} تاریخ انتشار:</b> {upload_date}

<b>{icon_info} توضیحات:</b>
{description}

<i>{icon_quality} لطفاً کیفیت مورد نظر را انتخاب کنید:</i>
""",
    
    "download_started": """
<b>{icon_wait} در حال دانلود...</b>

<b>{icon_video} عنوان:</b> {title}
<b>{icon_quality} کیفیت:</b> {quality}

<i>لطفاً صبر کنید...</i>
""",
    
    "download_complete": """
<b>{icon_success} دانلود کامل شد!</b>

<b>{icon_video} عنوان:</b> {title}
<b>{icon_quality} کیفیت:</b> {quality}
<b>{icon_size} حجم فایل:</b> {file_size}
<b>{icon_time} زمان دانلود:</b> {download_time}

<i>فایل در حال ارسال است...</i>
""",
    
    "download_failed": """
<b>{icon_error} خطا در دانلود!</b>

<b>{icon_video} عنوان:</b> {title}
<b>{icon_quality} کیفیت:</b> {quality}
<b>{icon_info} علت خطا:</b> {error_reason}

<i>لطفاً مجدداً تلاش کنید یا کیفیت دیگری را انتخاب کنید.</i>
""",
    
    "progress_bar": """
<b>{icon_download} در حال دانلود... {percent}%</b>
{progress_bar}
<b>{icon_size} حجم:</b> {downloaded}/{total}
<b>{icon_time} سرعت:</b> {speed}/s
<b>{icon_time} زمان باقیمانده:</b> {eta}
""",
    
    "bulk_status": """
<b>{icon_info} وضعیت دانلودهای موازی</b>

<b>{icon_link} شناسه دسته:</b> {batch_id}
<b>{icon_download} تعداد کل:</b> {total_count}
<b>{icon_success} تکمیل شده:</b> {completed_count}
<b>{icon_wait} در انتظار:</b> {pending_count}
<b>{icon_error} خطا:</b> {failed_count}
<b>{icon_progress} پیشرفت کلی:</b> {overall_progress}%

{progress_details}
""",
}

class TelegramUIEnhancer:
    """کلاس بهبود رابط کاربری ربات تلگرام"""
    
    def __init__(self, bot: Optional[Bot] = None):
        """
        مقداردهی اولیه کلاس
        
        Args:
            bot: شیء ربات تلگرام (اختیاری)
        """
        self.bot = bot
        
    def set_bot(self, bot: Bot):
        """
        تنظیم شیء ربات
        
        Args:
            bot: شیء ربات تلگرام
        """
        self.bot = bot
    
    def create_video_quality_keyboard(self, video_id: str, is_instagram: bool = False) -> InlineKeyboardMarkup:
        """
        ایجاد کیبورد انتخاب کیفیت ویدیو
        
        Args:
            video_id: شناسه ویدیو
            is_instagram: آیا ویدیو از اینستاگرام است؟
            
        Returns:
            کیبورد درون‌خطی تلگرام
        """
        source = "instagram" if is_instagram else "youtube"
        
        keyboard = [
            [
                InlineKeyboardButton("1080p 📺", callback_data=f"{source}_{video_id}_1080p"),
                InlineKeyboardButton("720p 📱", callback_data=f"{source}_{video_id}_720p"),
            ],
            [
                InlineKeyboardButton("480p 🔍", callback_data=f"{source}_{video_id}_480p"),
                InlineKeyboardButton("360p 💡", callback_data=f"{source}_{video_id}_360p"),
            ],
            [
                InlineKeyboardButton("240p 🔎", callback_data=f"{source}_{video_id}_240p"),
                InlineKeyboardButton("صدا 🎵", callback_data=f"{source}_{video_id}_mp3"),
            ],
            [
                InlineKeyboardButton("🔄 بروزرسانی", callback_data=f"refresh_{source}_{video_id}"),
                InlineKeyboardButton("❌ لغو", callback_data=f"cancel_{video_id}"),
            ]
        ]
        
        return InlineKeyboardMarkup(keyboard)
    
    def create_bulk_download_keyboard(self, batch_id: str) -> InlineKeyboardMarkup:
        """
        ایجاد کیبورد مدیریت دانلودهای موازی
        
        Args:
            batch_id: شناسه دسته دانلود
            
        Returns:
            کیبورد درون‌خطی تلگرام
        """
        keyboard = [
            [
                InlineKeyboardButton("🔄 بروزرسانی وضعیت", callback_data=f"refresh_batch_{batch_id}"),
            ],
            [
                InlineKeyboardButton("⏸️ توقف موقت", callback_data=f"pause_batch_{batch_id}"),
                InlineKeyboardButton("▶️ ادامه", callback_data=f"resume_batch_{batch_id}"),
            ],
            [
                InlineKeyboardButton("❌ لغو دانلودها", callback_data=f"cancel_batch_{batch_id}"),
            ]
        ]
        
        return InlineKeyboardMarkup(keyboard)
    
    def create_help_keyboard(self) -> InlineKeyboardMarkup:
        """
        ایجاد کیبورد راهنما
        
        Returns:
            کیبورد درون‌خطی تلگرام
        """
        keyboard = [
            [
                InlineKeyboardButton("📱 راهنمای اینستاگرام", callback_data="help_instagram"),
                InlineKeyboardButton("📺 راهنمای یوتیوب", callback_data="help_youtube"),
            ],
            [
                InlineKeyboardButton("📊 دانلود موازی", callback_data="help_bulk"),
                InlineKeyboardButton("🔍 رفع خطاها", callback_data="help_errors"),
            ],
            [
                InlineKeyboardButton("ℹ️ درباره ربات", callback_data="about"),
            ]
        ]
        
        return InlineKeyboardMarkup(keyboard)
    
    def format_message_with_icons(self, template: str, **kwargs) -> str:
        """
        جایگزینی آیکون‌ها در قالب پیام
        
        Args:
            template: قالب پیام
            **kwargs: پارامترهای جایگزینی
            
        Returns:
            پیام فرمت‌شده با آیکون‌ها
        """
        # افزودن آیکون‌ها به پارامترها
        for icon_name, icon in ICONS.items():
            kwargs[f"icon_{icon_name}"] = icon
            
        # جلوگیری از خطا در صورت خالی بودن پارامترها
        for key, value in kwargs.items():
            if value is None:
                kwargs[key] = "-"
                
        # فرمت‌بندی HTML برای متن طولانی مانند توضیحات
        if 'description' in kwargs and kwargs['description']:
            # کوتاه کردن توضیحات طولانی
            desc = kwargs['description']
            if len(desc) > 300:
                desc = desc[:297] + "..."
            # خنثی‌سازی کدهای HTML
            desc = html.escape(desc)
            kwargs['description'] = desc
            
        return template.format(**kwargs)
    
    def format_duration(self, seconds: Optional[int]) -> str:
        """
        فرمت‌بندی مدت زمان به صورت خوانا
        
        Args:
            seconds: مدت زمان به ثانیه
            
        Returns:
            رشته فرمت‌شده
        """
        if seconds is None:
            return "-"
            
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    
    def format_file_size(self, size_bytes: Optional[int]) -> str:
        """
        فرمت‌بندی اندازه فایل به صورت خوانا
        
        Args:
            size_bytes: اندازه فایل به بایت
            
        Returns:
            رشته فرمت‌شده
        """
        if size_bytes is None:
            return "-"
            
        # تبدیل به واحدهای خوانا
        for unit in ['بایت', 'کیلوبایت', 'مگابایت', 'گیگابایت']:
            if size_bytes < 1024.0:
                if unit == 'بایت':
                    return f"{size_bytes} {unit}"
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
            
        return f"{size_bytes:.2f} ترابایت"
    
    def format_date(self, date_str: Optional[str]) -> str:
        """
        فرمت‌بندی تاریخ به صورت خوانا
        
        Args:
            date_str: تاریخ به فرمت YYYYMMDD
            
        Returns:
            رشته فرمت‌شده
        """
        if not date_str or len(date_str) != 8:
            return "-"
            
        try:
            year = date_str[:4]
            month = date_str[4:6]
            day = date_str[6:8]
            
            # تبدیل به تاریخ میلادی قابل فهم
            return f"{year}/{month}/{day}"
        except:
            return date_str
    
    def create_progress_bar(self, percent: float, length: int = 10) -> str:
        """
        ایجاد نوار پیشرفت گرافیکی
        
        Args:
            percent: درصد پیشرفت (0 تا 100)
            length: طول نوار پیشرفت
            
        Returns:
            نوار پیشرفت گرافیکی
        """
        filled_length = int(length * percent / 100)
        bar = '█' * filled_length + '░' * (length - filled_length)
        return bar
    
    async def send_video_info_message(self, 
                                     update: Update, 
                                     context: ContextTypes.DEFAULT_TYPE,
                                     video_info: Dict[str, Any],
                                     is_instagram: bool = False) -> int:
        """
        ارسال پیام اطلاعات ویدیو با پیش‌نمایش و دکمه‌های انتخاب کیفیت
        
        Args:
            update: شیء آپدیت تلگرام
            context: شیء کانتکست تلگرام
            video_info: دیکشنری حاوی اطلاعات ویدیو
            is_instagram: آیا ویدیو از اینستاگرام است؟
            
        Returns:
            شناسه پیام ارسال شده
        """
        chat_id = update.effective_chat.id
        video_id = video_info.get('id', 'unknown')
        
        # ساخت پیام اطلاعات ویدیو
        message_text = self.format_message_with_icons(
            HTML_TEMPLATES["video_info"],
            title=html.escape(video_info.get('title', 'بدون عنوان')),
            uploader=html.escape(video_info.get('uploader', '-')),
            duration=self.format_duration(video_info.get('duration')),
            view_count=format(video_info.get('view_count', 0), ','),
            like_count=format(video_info.get('like_count', 0), ','),
            upload_date=self.format_date(video_info.get('upload_date')),
            description=video_info.get('description', '')
        )
        
        # ایجاد کیبورد انتخاب کیفیت
        reply_markup = self.create_video_quality_keyboard(video_id, is_instagram)
        
        # ارسال پیام همراه با تصویر بندانگشتی اگر موجود است
        thumbnail_url = video_info.get('thumbnail')
        
        if thumbnail_url:
            # نمایش آیکون در حال تایپ برای تجربه کاربری بهتر
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
            
            try:
                # ارسال تصویر بندانگشتی همراه با اطلاعات ویدیو
                message = await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=thumbnail_url,
                    caption=message_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
                return message.message_id
            except Exception as e:
                logger.error(f"خطا در ارسال تصویر بندانگشتی: {e}")
                # در صورت خطا، فقط متن را ارسال می‌کنیم
                message = await context.bot.send_message(
                    chat_id=chat_id,
                    text=message_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
                return message.message_id
        else:
            # ارسال پیام بدون تصویر
            message = await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return message.message_id
    
    async def update_download_progress(self, 
                                     chat_id: int,
                                     message_id: int,
                                     percent: float,
                                     downloaded: str,
                                     total: str,
                                     speed: str,
                                     eta: str):
        """
        به‌روزرسانی پیام پیشرفت دانلود
        
        Args:
            chat_id: شناسه چت
            message_id: شناسه پیام
            percent: درصد پیشرفت
            downloaded: حجم دانلود شده
            total: حجم کل
            speed: سرعت دانلود
            eta: زمان باقیمانده
        """
        if not self.bot:
            logger.error("شیء ربات تنظیم نشده است")
            return
            
        # ایجاد نوار پیشرفت
        progress_bar = self.create_progress_bar(percent)
        
        # ساخت پیام پیشرفت
        message_text = self.format_message_with_icons(
            HTML_TEMPLATES["progress_bar"],
            percent=int(percent),
            progress_bar=progress_bar,
            downloaded=downloaded,
            total=total,
            speed=speed,
            eta=eta
        )
        
        try:
            # به‌روزرسانی پیام موجود
            await self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=message_text,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            # اگر پیام تغییر نکرده باشد، تلگرام خطا می‌دهد که می‌توانیم نادیده بگیریم
            logger.debug(f"خطا در به‌روزرسانی پیشرفت: {e}")
    
    async def send_download_started_message(self, 
                                          update: Update, 
                                          context: ContextTypes.DEFAULT_TYPE,
                                          title: str,
                                          quality: str) -> int:
        """
        ارسال پیام شروع دانلود
        
        Args:
            update: شیء آپدیت تلگرام
            context: شیء کانتکست تلگرام
            title: عنوان ویدیو
            quality: کیفیت انتخاب شده
            
        Returns:
            شناسه پیام ارسال شده
        """
        chat_id = update.effective_chat.id
        
        # نمایش آیکون در حال تایپ برای تجربه کاربری بهتر
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        
        # ساخت پیام شروع دانلود
        message_text = self.format_message_with_icons(
            HTML_TEMPLATES["download_started"],
            title=html.escape(title),
            quality=quality
        )
        
        # ارسال پیام
        message = await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            parse_mode=ParseMode.HTML
        )
        
        return message.message_id
    
    async def send_download_complete_message(self, 
                                           chat_id: int,
                                           message_id: int,
                                           title: str,
                                           quality: str,
                                           file_size: str,
                                           download_time: str):
        """
        به‌روزرسانی پیام به وضعیت تکمیل دانلود
        
        Args:
            chat_id: شناسه چت
            message_id: شناسه پیام
            title: عنوان ویدیو
            quality: کیفیت انتخاب شده
            file_size: حجم فایل
            download_time: زمان دانلود
        """
        if not self.bot:
            logger.error("شیء ربات تنظیم نشده است")
            return
            
        # ساخت پیام تکمیل دانلود
        message_text = self.format_message_with_icons(
            HTML_TEMPLATES["download_complete"],
            title=html.escape(title),
            quality=quality,
            file_size=file_size,
            download_time=download_time
        )
        
        try:
            # به‌روزرسانی پیام موجود
            await self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=message_text,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"خطا در به‌روزرسانی پیام تکمیل دانلود: {e}")
    
    async def send_download_failed_message(self, 
                                         chat_id: int,
                                         message_id: int,
                                         title: str,
                                         quality: str,
                                         error_reason: str):
        """
        به‌روزرسانی پیام به وضعیت خطا در دانلود
        
        Args:
            chat_id: شناسه چت
            message_id: شناسه پیام
            title: عنوان ویدیو
            quality: کیفیت انتخاب شده
            error_reason: دلیل خطا
        """
        if not self.bot:
            logger.error("شیء ربات تنظیم نشده است")
            return
            
        # ساخت پیام خطا
        message_text = self.format_message_with_icons(
            HTML_TEMPLATES["download_failed"],
            title=html.escape(title),
            quality=quality,
            error_reason=html.escape(error_reason)
        )
        
        # ایجاد دکمه تلاش مجدد
        keyboard = [
            [
                InlineKeyboardButton("🔄 تلاش مجدد", callback_data=f"retry_{quality}"),
                InlineKeyboardButton("🔍 انتخاب کیفیت دیگر", callback_data="show_qualities"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            # به‌روزرسانی پیام موجود
            await self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"خطا در به‌روزرسانی پیام خطای دانلود: {e}")
    
    async def send_bulk_status_message(self, 
                                     update: Update, 
                                     context: ContextTypes.DEFAULT_TYPE,
                                     batch_id: str,
                                     total_count: int,
                                     completed_count: int,
                                     pending_count: int,
                                     failed_count: int,
                                     progress_details: str) -> int:
        """
        ارسال پیام وضعیت دانلودهای موازی
        
        Args:
            update: شیء آپدیت تلگرام
            context: شیء کانتکست تلگرام
            batch_id: شناسه دسته دانلود
            total_count: تعداد کل دانلودها
            completed_count: تعداد دانلودهای تکمیل شده
            pending_count: تعداد دانلودهای در انتظار
            failed_count: تعداد دانلودهای ناموفق
            progress_details: جزئیات پیشرفت هر فایل
            
        Returns:
            شناسه پیام ارسال شده
        """
        chat_id = update.effective_chat.id
        
        # محاسبه درصد پیشرفت کلی
        if total_count > 0:
            overall_progress = int((completed_count / total_count) * 100)
        else:
            overall_progress = 0
            
        # ساخت پیام وضعیت دانلودهای موازی
        message_text = self.format_message_with_icons(
            HTML_TEMPLATES["bulk_status"],
            batch_id=batch_id,
            total_count=total_count,
            completed_count=completed_count,
            pending_count=pending_count,
            failed_count=failed_count,
            overall_progress=overall_progress,
            progress_details=html.escape(progress_details)
        )
        
        # ایجاد کیبورد مدیریت دانلودهای موازی
        reply_markup = self.create_bulk_download_keyboard(batch_id)
        
        # ارسال پیام
        message = await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        
        return message.message_id
    
    @staticmethod
    def create_download_progress_callback(chat_id: int, message_id: int, ui_enhancer) -> Callable:
        """
        ایجاد تابع callback برای پیشرفت دانلود
        
        Args:
            chat_id: شناسه چت
            message_id: شناسه پیام
            ui_enhancer: شیء TelegramUIEnhancer
            
        Returns:
            تابع callback
        """
        last_update_time = [time.time()]  # استفاده از لیست برای حفظ مرجع
        
        async def progress_callback(d):
            if d['status'] == 'downloading':
                # به‌روزرسانی حداکثر هر 1 ثانیه برای جلوگیری از خطای محدودیت تلگرام
                current_time = time.time()
                if current_time - last_update_time[0] < 1.0:
                    return
                    
                last_update_time[0] = current_time
                
                try:
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                    
                    if total > 0:
                        percent = (downloaded / total) * 100
                    else:
                        percent = 0
                        
                    speed = d.get('speed', 0)
                    eta = d.get('eta', 0)
                    
                    # فرمت‌بندی مقادیر
                    downloaded_str = ui_enhancer.format_file_size(downloaded)
                    total_str = ui_enhancer.format_file_size(total)
                    speed_str = ui_enhancer.format_file_size(speed)
                    eta_str = ui_enhancer.format_duration(eta)
                    
                    # به‌روزرسانی پیام پیشرفت
                    asyncio.create_task(
                        ui_enhancer.update_download_progress(
                            chat_id, message_id, percent, 
                            downloaded_str, total_str, 
                            speed_str, eta_str
                        )
                    )
                except Exception as e:
                    logger.error(f"خطا در callback پیشرفت: {e}")
                    
        return progress_callback

# افزودن توابع کمکی برای استفاده آسان‌تر
def create_enhanced_keyboard(keyboard_type: str, *args, **kwargs) -> InlineKeyboardMarkup:
    """
    ایجاد کیبورد بهبود یافته
    
    Args:
        keyboard_type: نوع کیبورد ('video_quality', 'bulk_download', 'help')
        *args, **kwargs: پارامترهای اضافی برای تابع مربوطه
        
    Returns:
        کیبورد درون‌خطی تلگرام
    """
    enhancer = TelegramUIEnhancer()
    
    if keyboard_type == "video_quality":
        video_id = kwargs.get('video_id', args[0] if args else None)
        is_instagram = kwargs.get('is_instagram', args[1] if len(args) > 1 else False)
        return enhancer.create_video_quality_keyboard(video_id, is_instagram)
    elif keyboard_type == "bulk_download":
        batch_id = kwargs.get('batch_id', args[0] if args else None)
        return enhancer.create_bulk_download_keyboard(batch_id)
    elif keyboard_type == "help":
        return enhancer.create_help_keyboard()
    else:
        logger.error(f"نوع کیبورد نامعتبر: {keyboard_type}")
        return InlineKeyboardMarkup([])

def format_html_message(template_name: str, **kwargs) -> str:
    """
    فرمت‌بندی پیام HTML با آیکون‌ها
    
    Args:
        template_name: نام قالب در HTML_TEMPLATES
        **kwargs: پارامترهای جایگزینی
        
    Returns:
        پیام فرمت‌شده
    """
    enhancer = TelegramUIEnhancer()
    template = HTML_TEMPLATES.get(template_name)
    
    if not template:
        logger.error(f"قالب نامعتبر: {template_name}")
        return f"خطا: قالب {template_name} یافت نشد."
        
    return enhancer.format_message_with_icons(template, **kwargs)

# نمونه استفاده و تست ماژول در صورت اجرای مستقیم
if __name__ == "__main__":
    print("تست بهبود رابط کاربری ربات تلگرام")
    
    # تست ایجاد کیبورد انتخاب کیفیت
    enhancer = TelegramUIEnhancer()
    keyboard = enhancer.create_video_quality_keyboard("sample_video_id")
    print("کیبورد انتخاب کیفیت:")
    for row in keyboard.inline_keyboard:
        buttons = []
        for button in row:
            buttons.append(f"{button.text} ({button.callback_data})")
        print(" - ".join(buttons))
    
    # تست فرمت‌بندی پیام
    formatted_message = enhancer.format_message_with_icons(
        HTML_TEMPLATES["video_info"],
        title="عنوان تست ویدیو",
        uploader="کانال تست",
        duration=enhancer.format_duration(1234),
        view_count="1,234,567",
        like_count="12,345",
        upload_date=enhancer.format_date("20220130"),
        description="این یک متن تست برای توضیحات ویدیو است."
    )
    print("\nپیام فرمت‌شده:")
    print(formatted_message)
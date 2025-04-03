#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
بهبود رابط کاربری و هندلرهای تلگرام

این ماژول قابلیت‌ها و رابط کاربری تلگرام را بهبود می‌بخشد.
"""

import os
import time
import logging
import asyncio
import threading
from typing import Dict, List, Optional, Union, Any, Callable
from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

# واردسازی ماژول‌های بهینه‌سازی
from cache_optimizer import cleanup_cache, optimize_cache
from youtube_downloader_optimizer import optimize_youtube_downloader

# تنظیم لاگر
logger = logging.getLogger(__name__)

# متغیرهای سراسری
active_downloads = {}  # نگهداری وضعیت دانلودهای فعال
progress_messages = {}  # پیام‌های در حال پیشرفت
user_settings = {}  # تنظیمات کاربران
special_effects = {}  # جلوه‌های ویژه

class TelegramUIEnhancer:
    """کلاس بهبود رابط کاربری تلگرام"""
    
    def __init__(self):
        """مقداردهی اولیه"""
        # تعمیم قالب‌های پیام
        self.message_templates = {
            'welcome': """<b>🎬 خوش آمدید به ربات دانلود ویدیو</b>

از این ربات برای دانلود ویدیوهای <b>یوتیوب</b> و <b>اینستاگرام</b> با کیفیت‌های مختلف استفاده کنید.

<i>🔹 با سرعت بالا
🔹 دانلود همزمان چندین ویدیو
🔹 پشتیبانی از کیفیت‌های مختلف
🔹 استخراج صدا از ویدیو
🔹 بدون محدودیت حجم (برای فایل‌های بزرگ به صورت چند بخشی ارسال می‌شود)</i>

برای شروع، لینک ویدیویی که می‌خواهید دانلود کنید را برای من ارسال کنید 📩
""",
            'downloading': """<b>⏳ در حال دانلود...</b>

🔗 <i>{url}</i>

🔄 <b>وضعیت:</b> {progress}%
⏱ <b>زمان باقی‌مانده:</b> {eta}
🚀 <b>سرعت:</b> {speed} MB/s

<i>لطفاً منتظر بمانید...</i>
""",
            'download_options': """<b>🎞 انتخاب کیفیت دانلود</b>

🔗 <i>{url}</i>

لطفاً یکی از کیفیت‌های زیر را انتخاب کنید:
"""
        }
        
        # ایموجی‌های پیشرفت
        self.progress_emojis = {
            'start': '🔍',
            'downloading': '⏬',
            'processing': '⚙️',
            'uploading': '📤',
            'complete': '✅',
            'error': '❌'
        }
        
        # رنگ‌های دکمه (بر اساس کیفیت)
        self.button_themes = {
            '1080p': 'primary',
            '720p': 'secondary',
            '480p': 'success',
            '360p': 'warning',
            '240p': 'danger',
            'audio': 'info'
        }
        
        logger.info("بهبود دهنده رابط کاربری تلگرام راه‌اندازی شد")
    
    def create_styled_buttons(self, options: List[Dict]) -> List[List[InlineKeyboardButton]]:
        """
        ایجاد دکمه‌های زیبا و استایل دار
        
        Args:
            options: لیست گزینه‌های دانلود
            
        Returns:
            دکمه‌های استایل‌دار
        """
        buttons = []
        current_row = []
        
        for i, option in enumerate(options):
            # دریافت اطلاعات دکمه
            option_id = option.get('id', f"option_{i}")
            label = option.get('label', f"گزینه {i+1}")
            quality = option.get('quality', 'unknown')
            
            # افزودن ایموجی مناسب بر اساس کیفیت
            if 'audio' in option_id.lower() or quality == 'audio':
                emoji = '🎵'
            elif '1080' in quality:
                emoji = '🎬'
            elif '720' in quality:
                emoji = '📹'
            elif '480' in quality:
                emoji = '📱'
            elif '360' in quality:
                emoji = '📲'
            else:
                emoji = '🎞'
            
            # ایجاد متن دکمه با ایموجی
            button_text = f"{emoji} {label}"
            
            # ایجاد دکمه
            button = InlineKeyboardButton(button_text, callback_data=option_id)
            
            # افزودن به سطر فعلی یا ایجاد سطر جدید
            if len(current_row) < 2:  # دو دکمه در هر سطر
                current_row.append(button)
            else:
                buttons.append(current_row)
                current_row = [button]
        
        # افزودن آخرین سطر اگر خالی نباشد
        if current_row:
            buttons.append(current_row)
        
        return buttons
    
    def create_help_buttons(self) -> List[List[InlineKeyboardButton]]:
        """
        ایجاد دکمه‌های راهنما برای منوی اصلی
        
        Returns:
            دکمه‌های راهنما
        """
        return [
            [
                InlineKeyboardButton("📚 راهنما", callback_data="help"),
                InlineKeyboardButton("⚙️ تنظیمات", callback_data="settings")
            ],
            [
                InlineKeyboardButton("📊 وضعیت سرور", callback_data="server_status"),
                InlineKeyboardButton("📥 دانلودهای من", callback_data="my_downloads")
            ]
        ]
    
    def get_animated_progress_bar(self, percent: float, length: int = 10) -> str:
        """
        ایجاد نوار پیشرفت انیمیشنی
        
        Args:
            percent: درصد پیشرفت (0-100)
            length: طول نوار پیشرفت
            
        Returns:
            نوار پیشرفت انیمیشنی با ایموجی
        """
        # اطمینان از محدوده صحیح درصد
        percent = max(0, min(100, percent))
        
        # محاسبه تعداد مربع‌های پر
        filled_length = int(length * percent / 100)
        
        # انتخاب ایموجی مناسب بر اساس درصد پیشرفت
        if percent < 10:
            animation_emoji = "🔄"
        elif percent < 30:
            animation_emoji = "⏳"
        elif percent < 70:
            animation_emoji = "⌛"
        elif percent < 95:
            animation_emoji = "🔋"
        else:
            animation_emoji = "✨"
        
        # ایجاد نوار پیشرفت
        bar = '█' * filled_length + '░' * (length - filled_length)
        
        # اضافه کردن ایموجی به انتهای نوار
        return f"[{bar}] {animation_emoji} {percent:.1f}%"
    
    def format_download_progress_message(self, status: Dict[str, Any]) -> str:
        """
        قالب‌بندی پیام پیشرفت دانلود
        
        Args:
            status: وضعیت دانلود
            
        Returns:
            پیام قالب‌بندی شده
        """
        # استخراج اطلاعات وضعیت
        url = status.get('url', 'نامشخص')
        progress = status.get('progress', 0)
        speed = status.get('speed', 0)
        eta = status.get('eta', 'نامشخص')
        size = status.get('size', 0)
        filename = status.get('filename', 'نامشخص')
        
        # کوتاه کردن URL
        if len(url) > 40:
            url = url[:37] + '...'
        
        # تبدیل سرعت به مگابایت بر ثانیه
        speed_mb = speed / (1024 * 1024) if isinstance(speed, (int, float)) else 0
        
        # ایجاد نوار پیشرفت
        progress_bar = self.get_animated_progress_bar(progress)
        
        # قالب‌بندی پیام
        message = f"""<b>⏬ در حال دانلود ویدیو</b>

🔗 <code>{url}</code>

{progress_bar}
🚀 <b>سرعت:</b> {speed_mb:.2f} MB/s
⏱ <b>زمان باقی‌مانده:</b> {eta}
📦 <b>حجم:</b> {size / (1024*1024):.1f} MB

<i>لطفاً منتظر بمانید...</i>"""
        
        return message
    
    def format_error_message(self, error: str) -> str:
        """
        قالب‌بندی پیام خطا
        
        Args:
            error: متن خطا
            
        Returns:
            پیام خطای قالب‌بندی شده
        """
        return f"""<b>❌ خطا در دانلود ویدیو</b>

<code>{error}</code>

<i>لطفاً لینک دیگری را امتحان کنید یا بعداً دوباره تلاش کنید.</i>"""

    async def update_progress_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                     message_id: int, status: Dict[str, Any]) -> None:
        """
        به‌روزرسانی پیام پیشرفت دانلود
        
        Args:
            update: آبجکت آپدیت تلگرام
            context: کانتکست
            message_id: شناسه پیام
            status: وضعیت دانلود
        """
        try:
            # ایجاد پیام پیشرفت جدید
            new_text = self.format_download_progress_message(status)
            
            # ویرایش پیام موجود
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=message_id,
                text=new_text,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.warning(f"خطا در به‌روزرسانی پیام پیشرفت: {e}")
    
    def create_download_options_keyboard(self, options: List[Dict], url_id: str, 
                                        download_type: str) -> InlineKeyboardMarkup:
        """
        ایجاد کیبورد گزینه‌های دانلود
        
        Args:
            options: لیست گزینه‌های دانلود
            url_id: شناسه URL
            download_type: نوع دانلود (یوتیوب یا اینستاگرام)
            
        Returns:
            کیبورد اینلاین با دکمه‌های زیبا
        """
        keyboard = []
        
        for option in options:
            option_id = option.get('id', '')
            label = option.get('label', 'نامشخص')
            
            # افزودن ایموجی مناسب
            if 'audio' in option_id:
                emoji = '🎵'
            elif '1080' in option_id:
                emoji = '🎬'
            elif '720' in option_id:
                emoji = '📹'
            elif '480' in option_id:
                emoji = '📱'
            elif '360' in option_id:
                emoji = '📲'
            elif '240' in option_id:
                emoji = '📺'
            else:
                emoji = '🎞'
            
            # ایجاد متن دکمه
            button_text = f"{emoji} {label}"
            
            # ایجاد کالبک دیتا
            callback_data = f"dl_{download_type}_{option_id}_{url_id}"
            
            # افزودن دکمه به سطر مناسب
            if 'audio' in option_id:
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            elif len(keyboard) == 0 or len(keyboard[-1]) >= 2:
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            else:
                keyboard[-1].append(InlineKeyboardButton(button_text, callback_data=callback_data))
        
        # افزودن دکمه لغو
        keyboard.append([InlineKeyboardButton("❌ لغو", callback_data=f"cancel_{url_id}")])
        
        return InlineKeyboardMarkup(keyboard)
        
# تابع اصلی برای اعمال بهینه‌سازی‌ها
async def apply_all_enhancements() -> bool:
    """
    اعمال تمام بهبودها و بهینه‌سازی‌ها
    
    Returns:
        موفقیت‌آمیز بودن بهینه‌سازی
    """
    logger.info("در حال اجرای بهینه‌سازی‌های اولیه...")
    
    try:
        # بهینه‌سازی کش
        cleanup_cache()
        
        # بهینه‌سازی دانلودر یوتیوب
        youtube_success = optimize_youtube_downloader()
        
        logger.info("ربات با موفقیت با بهینه‌سازی‌ها و بهبودهای رابط کاربری به‌روزرسانی شد")
        return True
    except Exception as e:
        logger.error(f"خطا در اعمال بهینه‌سازی‌ها: {e}")
        return False

# تابع پیکربندی مجدد رابط کاربری
def configure_ui_enhancements(application) -> TelegramUIEnhancer:
    """
    پیکربندی بهبودهای رابط کاربری برای اپلیکیشن تلگرام
    
    Args:
        application: آبجکت اپلیکیشن تلگرام
        
    Returns:
        نمونه بهبود‌دهنده رابط کاربری
    """
    # ایجاد نمونه از کلاس بهبود‌دهنده
    enhancer = TelegramUIEnhancer()
    
    # ذخیره در کانتکست اپلیکیشن برای دسترسی آسان
    application.bot_data['ui_enhancer'] = enhancer
    
    return enhancer

# فانکشن کمکی برای دریافت بهبود‌دهنده رابط کاربری از کانتکست
def get_ui_enhancer(context: ContextTypes.DEFAULT_TYPE) -> TelegramUIEnhancer:
    """
    دریافت نمونه بهبود‌دهنده رابط کاربری از کانتکست
    
    Args:
        context: کانتکست تلگرام
        
    Returns:
        نمونه بهبود‌دهنده رابط کاربری
    """
    if 'ui_enhancer' not in context.bot_data:
        context.bot_data['ui_enhancer'] = TelegramUIEnhancer()
    
    return context.bot_data['ui_enhancer']

if __name__ == "__main__":
    # تنظیم لاگر
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # تست عملکرد بهبود‌دهنده
    enhancer = TelegramUIEnhancer()
    print("بهبود‌دهنده رابط کاربری با موفقیت راه‌اندازی شد")
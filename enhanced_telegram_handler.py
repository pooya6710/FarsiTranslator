"""
یکپارچه‌سازی بهینه‌سازی‌ها و بهبودهای رابط کاربری برای ربات تلگرام

این ماژول تغییرات لازم برای استفاده از بهینه‌سازی‌ها و بهبودهای رابط کاربری را فراهم می‌کند
"""

import os
import re
import asyncio
import logging
import time
import tempfile
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime

# تنظیم لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# تعریف کلاس‌های مورد نیاز در صورت عدم وجود کتابخانه
class Update:
    class EffectiveChat:
        id = 0
        
    effective_chat = EffectiveChat()
    effective_user = None

class Bot:
    async def send_message(self, *args, **kwargs):
        pass
        
    async def send_chat_action(self, *args, **kwargs):
        pass
        
    async def send_photo(self, *args, **kwargs):
        class Message:
            message_id = 0
        return Message()
        
    async def send_video(self, *args, **kwargs):
        pass
        
    async def send_audio(self, *args, **kwargs):
        pass

class ContextTypes:
    DEFAULT_TYPE = Any

class ChatAction:
    TYPING = "typing"
    UPLOAD_PHOTO = "upload_photo"
    UPLOAD_VIDEO = "upload_video"
    UPLOAD_AUDIO = "upload_audio"

class ParseMode:
    HTML = "HTML"

# وارد کردن ماژول‌های بهینه‌سازی
try:
    # ماژول بهینه‌سازی کش
    from cache_optimizer import run_optimization as optimize_cache
except ImportError:
    logger.warning("ماژول بهینه‌سازی کش یافت نشد!")
    def optimize_cache():
        logger.warning("از تابع optimize_cache جایگزین استفاده می‌شود")
        return

try:
    # ماژول پردازش ویدیو
    from video_processor import (
        convert_video_quality, extract_audio, optimize_for_telegram, get_video_info
    )
except ImportError:
    logger.warning("ماژول پردازش ویدیو یافت نشد!")

try:
    # ماژول بهینه‌سازی یوتیوب
    from youtube_downloader_optimizer import (
        optimize_yt_dlp_for_speed, download_with_optimized_settings, 
        get_youtube_video_info, extract_video_id_from_url
    )
except ImportError:
    logger.warning("ماژول بهینه‌سازی یوتیوب یافت نشد!")

try:
    # ماژول بهبود رابط کاربری
    from telegram_ui_enhancer import (
        TelegramUIEnhancer, create_enhanced_keyboard, format_html_message
    )
except ImportError:
    logger.warning("ماژول بهبود رابط کاربری یافت نشد!")

# استفاده از کتابخانه‌های تلگرام
try:
    from telegram import Update as TGUpdate, Bot as TGBot, ChatAction as TGChatAction, ParseMode as TGParseMode
    from telegram.ext import ContextTypes as TGContextTypes, CallbackContext
    
    # جایگزینی کلاس‌های واقعی
    Update = TGUpdate
    Bot = TGBot
    ContextTypes = TGContextTypes
    ChatAction = TGChatAction
    ParseMode = TGParseMode
except ImportError:
    logger.error("کتابخانه python-telegram-bot نصب نشده است. از نسخه‌های پشتیبان استفاده می‌شود.")

# کلاس اصلی یکپارچه‌سازی
class EnhancedTelegramHandler:
    """کلاس مدیریت بهینه شده ربات تلگرام"""
    
    def __init__(self):
        """مقداردهی اولیه کلاس"""
        self.ui_enhancer = None
        self.downloads_dir = os.path.join(os.getcwd(), "downloads")
        os.makedirs(self.downloads_dir, exist_ok=True)
        
        # بهینه‌سازی اولیه
        self.init_optimizations()
    
    def init_optimizations(self):
        """اجرای بهینه‌سازی‌های اولیه"""
        logger.info("در حال اجرای بهینه‌سازی‌های اولیه...")
        
        # بهینه‌سازی کش
        try:
            optimize_cache()
        except Exception as e:
            logger.error(f"خطا در بهینه‌سازی کش: {e}")
            
        # بهینه‌سازی yt-dlp
        try:
            optimize_yt_dlp_for_speed()
        except Exception as e:
            logger.error(f"خطا در بهینه‌سازی yt-dlp: {e}")
    
    def setup_ui_enhancer(self, bot: Bot):
        """
        راه‌اندازی بهبوددهنده رابط کاربری
        
        Args:
            bot: شیء ربات تلگرام
        """
        try:
            self.ui_enhancer = TelegramUIEnhancer(bot)
        except Exception as e:
            logger.error(f"خطا در راه‌اندازی بهبوددهنده رابط کاربری: {e}")
    
    async def handle_youtube_url(self, 
                               update: Update, 
                               context: ContextTypes.DEFAULT_TYPE, 
                               url: str) -> None:
        """
        مدیریت لینک یوتیوب با رابط کاربری و دانلود بهینه شده
        
        Args:
            update: شیء آپدیت تلگرام
            context: شیء کانتکست تلگرام
            url: آدرس ویدیوی یوتیوب
        """
        chat_id = update.effective_chat.id
        
        try:
            # نمایش آیکون در حال تایپ برای تجربه کاربری بهتر
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            
            # دریافت اطلاعات ویدیو
            video_info = get_youtube_video_info(url)
            
            if not video_info:
                # در صورت عدم دریافت اطلاعات، از تابع قدیمی استفاده می‌شود
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ خطا در دریافت اطلاعات ویدیو. لطفاً مجدداً تلاش کنید."
                )
                return
                
            # نمایش اطلاعات ویدیو و گزینه‌های دانلود
            try:
                if self.ui_enhancer:
                    await self.ui_enhancer.send_video_info_message(update, context, video_info, is_instagram=False)
                else:
                    # در صورت عدم دسترسی به بهبوددهنده رابط کاربری، از رابط قدیمی استفاده می‌کنیم
                    source = "youtube"
                    video_id = video_info.get('id', 'unknown')
                    
                    keyboard = [
                        [
                            InlineKeyboardButton("1080p HD", callback_data=f"{source}_{video_id}_1080p"),
                            InlineKeyboardButton("720p HD", callback_data=f"{source}_{video_id}_720p"),
                        ],
                        [
                            InlineKeyboardButton("480p", callback_data=f"{source}_{video_id}_480p"),
                            InlineKeyboardButton("360p", callback_data=f"{source}_{video_id}_360p"),
                        ],
                        [
                            InlineKeyboardButton("240p", callback_data=f"{source}_{video_id}_240p"),
                            InlineKeyboardButton("فقط صدا", callback_data=f"{source}_{video_id}_mp3"),
                        ],
                    ]
                    
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"📺 ویدیوی یوتیوب: {video_info.get('title')}\n\nلطفاً کیفیت مورد نظر را انتخاب کنید:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
            except Exception as e:
                logger.error(f"خطا در ارسال اطلاعات ویدیو: {str(e)}")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ خطا در نمایش اطلاعات ویدیو: {str(e)}\nلطفاً مجدداً تلاش کنید."
                )
                
            # ذخیره اطلاعات ویدیو در user_data
            if not context.user_data.get('video_info'):
                context.user_data['video_info'] = {}
                
            video_id = video_info.get('id', 'unknown')
            context.user_data['video_info'][video_id] = video_info
            context.user_data['last_url'] = url
            
        except Exception as e:
            logger.error(f"خطا در مدیریت لینک یوتیوب: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ خطا در پردازش لینک یوتیوب: {str(e)}"
            )
    
    async def download_youtube_with_quality(self, 
                                          update: Update, 
                                          context: ContextTypes.DEFAULT_TYPE,
                                          video_id: str,
                                          quality: str) -> None:
        """
        دانلود ویدیوی یوتیوب با کیفیت انتخاب شده با استفاده از روش‌های بهینه
        
        Args:
            update: شیء آپدیت تلگرام
            context: شیء کانتکست تلگرام
            video_id: شناسه ویدیوی یوتیوب
            quality: کیفیت مورد نظر ('1080p', '720p', '480p', '360p', '240p', 'mp3')
        """
        # استفاده از query یا effective_chat بسته به نوع آپدیت
        chat_id = update.effective_chat.id if update.effective_chat else update.callback_query.message.chat_id
        is_audio = quality == 'mp3'
        
        try:
            # بررسی اطلاعات ویدیو
            video_info = context.user_data.get('video_info', {}).get(video_id)
            url = context.user_data.get('last_url')
            
            if not video_info or not url:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ اطلاعات ویدیو یافت نشد. لطفاً دوباره لینک را ارسال کنید."
                )
                return
                
            # ارسال پیام شروع دانلود
            title = video_info.get('title', 'ویدیوی ناشناس')
            
            if self.ui_enhancer:
                message_id = await self.ui_enhancer.send_download_started_message(
                    update, context, title, quality
                )
            else:
                # در صورت عدم دسترسی به بهبوددهنده رابط کاربری
                message = await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⏳ در حال دانلود با کیفیت {quality}... لطفاً صبر کنید."
                )
                message_id = message.message_id
                
            # نمایش آیکون مناسب برای نوع محتوا
            if is_audio:
                await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_AUDIO)
            else:
                await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO)
                
            # ایجاد callback برای پیشرفت دانلود
            progress_callback = None
            if self.ui_enhancer:
                progress_callback = TelegramUIEnhancer.create_download_progress_callback(
                    chat_id, message_id, self.ui_enhancer
                )
                
            # شروع زمان‌سنج دانلود
            start_time = time.time()
            
            # دانلود ویدیو با تنظیمات بهینه
            output_path = os.path.join(self.downloads_dir, f"{video_id}_{quality}.mp4")
            
            if is_audio:
                output_path = os.path.join(self.downloads_dir, f"{video_id}.mp3")
                
            # استفاده از دانلودر بهینه
            file_path = await asyncio.to_thread(
                download_with_optimized_settings, url, quality, output_path
            )
            
            if not file_path or not os.path.exists(file_path):
                # اعلام خطای دانلود
                if self.ui_enhancer:
                    await self.ui_enhancer.send_download_failed_message(
                        chat_id, message_id, title, quality, 
                        "دانلود ناموفق بود. فایل خروجی ایجاد نشد."
                    )
                else:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"❌ خطا در دانلود ویدیو با کیفیت {quality}."
                    )
                return
                
            # محاسبه زمان دانلود
            download_time = time.time() - start_time
            formatted_time = time.strftime("%M:%S", time.gmtime(download_time))
            
            # بهینه‌سازی برای آپلود در تلگرام اگر حجم فایل زیاد است
            file_size = os.path.getsize(file_path)
            if file_size > 50 * 1024 * 1024:  # 50MB
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"⚠️ حجم فایل بیش از حد مجاز تلگرام است. در حال بهینه‌سازی..."
                )
                
                optimized_file = await asyncio.to_thread(
                    optimize_for_telegram, file_path
                )
                
                if optimized_file and os.path.exists(optimized_file):
                    file_path = optimized_file
                    file_size = os.path.getsize(file_path)
                    
            # فرمت‌بندی حجم فایل
            formatted_size = self.format_file_size(file_size)
            
            # ارسال پیام تکمیل دانلود
            if self.ui_enhancer:
                await self.ui_enhancer.send_download_complete_message(
                    chat_id, message_id, title, quality,
                    formatted_size, formatted_time
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"✅ دانلود کامل شد!\nفایل: {title}\nکیفیت: {quality}\nحجم: {formatted_size}\nزمان: {formatted_time}"
                )
                
            # ارسال فایل
            caption = f"🎬 {title}\n💾 {quality} | {formatted_size}"
            
            if is_audio:
                # ارسال فایل صوتی
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=open(file_path, 'rb'),
                    caption=caption,
                    title=title,
                    performer=video_info.get('uploader', 'یوتیوب'),
                    thumb=video_info.get('thumbnail')
                )
            else:
                # ارسال ویدیو
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=open(file_path, 'rb'),
                    caption=caption,
                    supports_streaming=True,
                    width=video_info.get('width', 0),
                    height=video_info.get('height', 0),
                    duration=video_info.get('duration', 0)
                )
                
            # پاکسازی فایل برای صرفه‌جویی در فضا (اختیاری)
            # os.remove(file_path)
            
        except Exception as e:
            logger.error(f"خطا در دانلود یوتیوب: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ خطا در دانلود ویدیو: {str(e)}"
            )
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """
        فرمت‌بندی اندازه فایل به صورت خوانا
        
        Args:
            size_bytes: اندازه فایل به بایت
            
        Returns:
            رشته فرمت‌شده
        """
        # تبدیل به واحدهای خوانا
        for unit in ['بایت', 'کیلوبایت', 'مگابایت', 'گیگابایت']:
            if size_bytes < 1024.0:
                if unit == 'بایت':
                    return f"{size_bytes} {unit}"
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
            
        return f"{size_bytes:.2f} ترابایت"
    
    @staticmethod
    def is_youtube_url(url: str) -> bool:
        """
        بررسی می‌کند که آیا URL از یوتیوب است
        
        Args:
            url: آدرس URL
            
        Returns:
            True اگر URL از یوتیوب باشد، False در غیر این صورت
        """
        youtube_patterns = [
            r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})'
        ]
        
        for pattern in youtube_patterns:
            if re.search(pattern, url):
                return True
                
        return False
    
    @staticmethod
    def is_youtube_shorts(url: str) -> bool:
        """
        بررسی می‌کند که آیا URL از یوتیوب شورتز است
        
        Args:
            url: آدرس URL
            
        Returns:
            True اگر URL از یوتیوب شورتز باشد، False در غیر این صورت
        """
        shorts_pattern = r'youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})'
        return bool(re.search(shorts_pattern, url))
    
    @staticmethod
    def is_youtube_playlist(url: str) -> bool:
        """
        بررسی می‌کند که آیا URL از پلی‌لیست یوتیوب است
        
        Args:
            url: آدرس URL
            
        Returns:
            True اگر URL از پلی‌لیست یوتیوب باشد، False در غیر این صورت
        """
        playlist_pattern = r'youtube\.com\/playlist\?list=([a-zA-Z0-9_-]+)'
        return bool(re.search(playlist_pattern, url))
    
    @staticmethod
    def is_instagram_url(url: str) -> bool:
        """
        بررسی می‌کند که آیا URL از اینستاگرام است
        
        Args:
            url: آدرس URL
            
        Returns:
            True اگر URL از اینستاگرام باشد، False در غیر این صورت
        """
        return 'instagram.com' in url or 'instagr.am' in url

# توابع کمکی برای استفاده آسان‌تر
def get_enhanced_handler() -> EnhancedTelegramHandler:
    """
    دریافت نمونه از کلاس EnhancedTelegramHandler
    
    Returns:
        یک نمونه از کلاس EnhancedTelegramHandler
    """
    handler = EnhancedTelegramHandler()
    return handler

def setup_bot_with_enhancements(bot: Bot) -> EnhancedTelegramHandler:
    """
    راه‌اندازی ربات با بهینه‌سازی‌ها و بهبودهای رابط کاربری
    
    Args:
        bot: شیء ربات تلگرام
        
    Returns:
        یک نمونه از کلاس EnhancedTelegramHandler
    """
    handler = EnhancedTelegramHandler()
    handler.setup_ui_enhancer(bot)
    return handler

def update_telegram_bot(bot: Bot, application) -> None:
    """
    به‌روزرسانی ربات تلگرام برای استفاده از بهینه‌سازی‌ها و بهبودهای رابط کاربری
    
    Args:
        bot: شیء ربات تلگرام
        application: شیء اپلیکیشن تلگرام
    """
    try:
        # راه‌اندازی بهینه‌سازی‌ها
        handler = setup_bot_with_enhancements(bot)
        
        # ذخیره هندلر در اپلیکیشن برای استفاده آسان‌تر
        application.enhanced_handler = handler
        
        logger.info("ربات با موفقیت با بهینه‌سازی‌ها و بهبودهای رابط کاربری به‌روزرسانی شد")
    except Exception as e:
        logger.error(f"خطا در به‌روزرسانی ربات: {e}")

# آزمایش ماژول در صورت اجرای مستقیم
if __name__ == "__main__":
    print("این ماژول برای استفاده به عنوان یک کتابخانه طراحی شده است.")
    print("برای استفاده، آن را از telegram_downloader.py وارد کنید.")
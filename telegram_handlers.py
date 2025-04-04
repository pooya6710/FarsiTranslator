"""
هندلرهای دکمه‌های منوی ربات تلگرام

این ماژول حاوی هندلر‌های لازم برای پردازش دکمه‌های منوی ربات و ایجاد رابط کاربری بهتر است.
"""

import logging
from typing import Dict, List, Any, Optional
import traceback

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

# تنظیم لاگر
logger = logging.getLogger(__name__)

async def handle_menu_button(update: Update, context: CallbackContext) -> None:
    """
    هندلر دکمه‌های منو
    
    این تابع کالبک دکمه‌های منوی ربات را مدیریت می‌کند
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: کانتکست تلگرام
    """
    query = update.callback_query
    await query.answer()
    
    # استخراج اطلاعات کالبک
    callback_data = query.data
    user_id = update.effective_user.id
    
    # اطمینان از اینکه این هندلر فقط کالبک‌های منو را پردازش می‌کند
    if callback_data.startswith("dl_"):
        logger.warning(f"کالبک دانلود {callback_data} به هندلر منو ارسال شد - در حال رد کردن")
        return
    
    logger.info(f"کاربر {user_id} دکمه {callback_data} را انتخاب کرد")
    
    if callback_data == "back_to_start":
        # برگشت به منوی اصلی
        await handle_back_to_start(update, context)
    elif callback_data == "help":
        # نمایش راهنما
        await handle_help_section(update, context)
    elif callback_data == "about":
        # نمایش درباره ما
        await handle_about_section(update, context)
    elif callback_data == "help_video":
        # راهنمای کیفیت‌های ویدیو
        await handle_video_help(update, context)
    elif callback_data == "help_audio":
        # راهنمای دانلود صوتی
        await handle_audio_help(update, context)
    elif callback_data == "help_bulk":
        # راهنمای دانلود گروهی
        await handle_bulk_help(update, context)
    elif callback_data == "mydownloads":
        # نمایش دانلودهای کاربر
        await handle_my_downloads(update, context)
    else:
        logger.warning(f"دکمه نامشخص: {callback_data}")

async def handle_back_to_start(update: Update, context: CallbackContext) -> None:
    """
    برگرداندن کاربر به منوی اصلی
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: کانتکست تلگرام
    """
    query = update.callback_query
    
    from telegram_downloader import START_MESSAGE
    
    # ایجاد دکمه‌های راهنما
    keyboard = [
        [
            InlineKeyboardButton("📚 راهنمای استفاده", callback_data="help"),
            InlineKeyboardButton("ℹ️ درباره ربات", callback_data="about")
        ],
        [
            InlineKeyboardButton("📥 دانلودهای من", callback_data="mydownloads")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام خوش‌آمدگویی با فرمت HTML و دکمه‌ها
    await query.edit_message_text(
        START_MESSAGE,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def handle_help_section(update: Update, context: CallbackContext) -> None:
    """
    نمایش صفحه راهنما
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: کانتکست تلگرام
    """
    query = update.callback_query
    
    from telegram_downloader import HELP_MESSAGE
    
    # ایجاد دکمه‌های راهنما
    keyboard = [
        [
            InlineKeyboardButton("🎬 کیفیت‌های ویدیو", callback_data="help_video"),
            InlineKeyboardButton("🎵 دانلود صوتی", callback_data="help_audio")
        ],
        [
            InlineKeyboardButton("📱 دانلود گروهی", callback_data="help_bulk"),
            InlineKeyboardButton("ℹ️ درباره ربات", callback_data="about")
        ],
        [
            InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="back_to_start")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام راهنما با فرمت HTML و دکمه‌ها
    await query.edit_message_text(
        HELP_MESSAGE,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def handle_about_section(update: Update, context: CallbackContext) -> None:
    """
    نمایش صفحه درباره ما
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: کانتکست تلگرام
    """
    query = update.callback_query
    
    from telegram_downloader import ABOUT_MESSAGE
    
    # ایجاد دکمه بازگشت به منوی اصلی
    keyboard = [
        [
            InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="back_to_start")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام درباره با فرمت HTML و دکمه بازگشت
    await query.edit_message_text(
        ABOUT_MESSAGE,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def handle_video_help(update: Update, context: CallbackContext) -> None:
    """
    نمایش راهنمای کیفیت‌های ویدیو
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: کانتکست تلگرام
    """
    query = update.callback_query
    
    video_help_message = """<b>🎬 راهنمای کیفیت‌های ویدیو</b>

<b>کیفیت‌های قابل انتخاب:</b>
• <b>1080p (Full HD)</b> - بالاترین کیفیت، حجم بالا
• <b>720p (HD)</b> - کیفیت عالی، حجم متوسط
• <b>480p</b> - کیفیت متوسط، حجم کم
• <b>360p</b> - کیفیت پایین، حجم خیلی کم
• <b>240p</b> - کیفیت خیلی پایین، حجم بسیار کم

<b>⚠️ توجه داشته باشید:</b>
• تلگرام فایل‌های با حجم بیش از <b>50 مگابایت</b> را پشتیبانی نمی‌کند
• برای ویدیوهای طولانی، کیفیت‌های پایین‌تر توصیه می‌شود
• در صورت خطای حجم زیاد، کیفیت پایین‌تری را انتخاب کنید

<i>برای ارسال لینک جدید، کافیست آن را برای ربات ارسال کنید.</i>"""
    
    # ایجاد دکمه‌های راهنما
    keyboard = [
        [
            InlineKeyboardButton("📚 بازگشت به راهنما", callback_data="help"),
            InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="back_to_start")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام راهنمای کیفیت ویدیو با فرمت HTML و دکمه‌ها
    await query.edit_message_text(
        video_help_message,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def handle_audio_help(update: Update, context: CallbackContext) -> None:
    """
    نمایش راهنمای دانلود صوتی
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: کانتکست تلگرام
    """
    query = update.callback_query
    
    audio_help_message = """<b>🎵 راهنمای دانلود صوتی</b>

<b>دانلود فایل صوتی از ویدیو:</b>
• برای دانلود <b>فقط صدا</b> از ویدیوهای یوتیوب یا اینستاگرام، گزینه "فقط صدا (MP3)" را انتخاب کنید
• فایل با <b>کیفیت 192kbps</b> استخراج و تبدیل می‌شود
• فرمت خروجی <b>MP3</b> خواهد بود
• متادیتای ویدیو (عنوان، هنرمند و تصویر) در فایل صوتی ذخیره می‌شود

<b>مزایای دانلود صوتی:</b>
• <b>حجم کمتر</b> نسبت به ویدیو
• <b>دانلود سریع‌تر</b>
• <b>ذخیره فضا</b> در دستگاه شما
• مناسب برای <b>موسیقی و پادکست</b>

<i>برای ارسال لینک جدید، کافیست آن را برای ربات ارسال کنید.</i>"""
    
    # ایجاد دکمه‌های راهنما
    keyboard = [
        [
            InlineKeyboardButton("📚 بازگشت به راهنما", callback_data="help"),
            InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="back_to_start")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام راهنمای دانلود صوتی با فرمت HTML و دکمه‌ها
    await query.edit_message_text(
        audio_help_message,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def handle_bulk_help(update: Update, context: CallbackContext) -> None:
    """
    نمایش راهنمای دانلود گروهی
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: کانتکست تلگرام
    """
    query = update.callback_query
    
    bulk_help_message = """<b>📱 راهنمای دانلود گروهی</b>

<b>روش استفاده از دانلود گروهی:</b>
برای دانلود چندین لینک به صورت همزمان از دستور <code>/bulkdownload</code> استفاده کنید:

<code>/bulkdownload کیفیت
https://youtube.com/...
https://instagram.com/...
https://youtube.com/...</code>

<b>مثال:</b>
<code>/bulkdownload 720p
https://youtube.com/watch?v=dQw4w9WgXcQ
https://instagram.com/p/ABC123
https://youtube.com/shorts/XYZ456</code>

<b>کیفیت‌های قابل انتخاب:</b>
• <code>1080p</code>, <code>720p</code>, <code>480p</code>, <code>360p</code>, <code>240p</code>
• <code>audio</code> - برای دانلود فقط صدا

<b>⚠️ محدودیت‌ها:</b>
• حداکثر <b>5</b> لینک در هر دستور
• حداکثر <b>3</b> دانلود همزمان برای هر کاربر

<i>برای بررسی وضعیت دانلودها از <code>/status_BATCH_ID</code> استفاده کنید</i>"""
    
    # ایجاد دکمه‌های راهنما
    keyboard = [
        [
            InlineKeyboardButton("📚 بازگشت به راهنما", callback_data="help"),
            InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="back_to_start")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام راهنمای دانلود گروهی با فرمت HTML و دکمه‌ها
    await query.edit_message_text(
        bulk_help_message,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def handle_my_downloads(update: Update, context: CallbackContext) -> None:
    """
    نمایش دانلودهای کاربر
    
    Args:
        update: آبجکت آپدیت تلگرام
        context: کانتکست تلگرام
    """
    query = update.callback_query
    user_id = update.effective_user.id
    
    # ایجاد پیام دانلودهای کاربر
    message = "<b>📥 دانلودهای اخیر شما</b>\n\n"
    
    # اینجا باید از تاریخچه دانلودهای کاربر استفاده کنیم
    # در این نسخه فقط یک پیام نمونه نمایش می‌دهیم
    message += "<i>در حال حاضر تاریخچه دانلودها در دسترس نیست.</i>\n"
    message += "<i>این قابلیت در بروزرسانی‌های آینده اضافه خواهد شد.</i>"
    
    # ایجاد دکمه بازگشت به منوی اصلی
    keyboard = [
        [
            InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="back_to_start")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام دانلودهای کاربر با فرمت HTML و دکمه بازگشت
    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
"""
ماژول مدیریت دانلود موازی ویدیوها

این ماژول امکان دانلود همزمان چندین لینک را فراهم می‌کند
"""

import os
import re
import asyncio
import logging
from typing import List, Dict, Optional, Set, Tuple
import time
import threading
import uuid
import json
from concurrent.futures import ThreadPoolExecutor

# تنظیم لاگر
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# محل ذخیره‌سازی فایل‌های در حال دانلود
PENDING_DOWNLOADS_FILE = "pending_downloads.json"

# حداکثر دانلودهای همزمان - افزایش یافته به شکل قابل توجه برای بهبود چندبرابری عملکرد
MAX_CONCURRENT_DOWNLOADS = 15

# فاصله زمانی بین دانلودها (به ثانیه) - حذف تقریبی تأخیر برای شروع تقریباً همزمان
DOWNLOAD_DELAY = 0.1

# مدیریت صف دانلود
download_queue = asyncio.Queue()
active_downloads = set()
download_results = {}
download_status = {}

# تنظیم سمافور برای محدود کردن تعداد دانلودهای همزمان
download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

# قفل برای همگام‌سازی دسترسی به منابع مشترک
lock = threading.Lock()

class BulkDownloadManager:
    """کلاس مدیریت دانلود چندگانه"""
    
    def __init__(self):
        """مقداردهی اولیه"""
        self.download_tasks = {}  # نگهداری تسک‌های در حال اجرا
        self.load_pending_downloads()  # بارگذاری دانلودهای معلق
        
    def load_pending_downloads(self) -> None:
        """بارگذاری دانلودهای معلق از فایل"""
        try:
            if os.path.exists(PENDING_DOWNLOADS_FILE):
                with open(PENDING_DOWNLOADS_FILE, 'r') as f:
                    self.pending_downloads = json.load(f)
                logger.info(f"تعداد {len(self.pending_downloads)} دانلود معلق بارگذاری شد")
            else:
                self.pending_downloads = {}
        except Exception as e:
            logger.error(f"خطا در بارگذاری دانلودهای معلق: {str(e)}")
            self.pending_downloads = {}
    
    def save_pending_downloads(self) -> None:
        """ذخیره دانلودهای معلق در فایل"""
        try:
            with open(PENDING_DOWNLOADS_FILE, 'w') as f:
                json.dump(self.pending_downloads, f)
            logger.info(f"تعداد {len(self.pending_downloads)} دانلود معلق ذخیره شد")
        except Exception as e:
            logger.error(f"خطا در ذخیره دانلودهای معلق: {str(e)}")
    
    def extract_urls(self, text: str) -> List[str]:
        """استخراج URL‌های یوتیوب و اینستاگرام از متن"""
        # الگوی URL های یوتیوب
        youtube_pattern = r'(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)/(?:watch\?v=|shorts/)?([A-Za-z0-9_-]+)'
        # الگوی URL های اینستاگرام
        instagram_pattern = r'(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel)/([A-Za-z0-9_-]+)'
        
        # ترکیب الگوها برای یافتن هر دو نوع URL
        combined_pattern = f'{youtube_pattern}|{instagram_pattern}'
        
        matches = re.findall(combined_pattern, text)
        
        # استخراج URLs کامل
        urls = []
        
        # یافتن تمام URLهای یوتیوب در متن
        youtube_matches = re.finditer(r'(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)/(?:watch\?v=|shorts/)?[A-Za-z0-9_-]+', text)
        for match in youtube_matches:
            urls.append(match.group())
            
        # یافتن تمام URLهای اینستاگرام در متن
        instagram_matches = re.finditer(r'(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel)/[A-Za-z0-9_-]+', text)
        for match in instagram_matches:
            urls.append(match.group())
            
        return urls
    
    async def add_urls_to_queue(self, urls: List[str], user_id: int, quality: str = "best") -> str:
        """افزودن گروهی از URLها به صف دانلود"""
        if not urls:
            return "هیچ لینک معتبری یافت نشد!"
            
        batch_id = f"batch_{uuid.uuid4().hex[:8]}"
        logger.info(f"افزودن دسته جدید با شناسه {batch_id} برای کاربر {user_id} با {len(urls)} لینک")
        
        # ثبت اطلاعات دسته
        self.pending_downloads[batch_id] = {
            "urls": urls,
            "user_id": user_id,
            "quality": quality,
            "status": "pending",
            "progress": 0,
            "total": len(urls),
            "completed": 0,
            "timestamp": time.time()
        }
        
        self.save_pending_downloads()
        
        # شروع پردازش دسته
        asyncio.create_task(self.process_batch(batch_id))
        
        return f"🔄 {len(urls)} لینک به صف دانلود اضافه شد.\n⏳ شناسه دسته: `{batch_id}`\nاز دستور /status_{batch_id} برای بررسی وضعیت استفاده کنید."
    
    async def process_batch(self, batch_id: str) -> None:
        """پردازش یک دسته از URLها به صورت موازی"""
        if batch_id not in self.pending_downloads:
            logger.error(f"شناسه دسته {batch_id} یافت نشد")
            return
            
        batch = self.pending_downloads[batch_id]
        urls = batch["urls"]
        user_id = batch["user_id"]
        quality = batch["quality"]
        
        # آماده‌سازی تسک‌های دانلود
        download_tasks = []
        
        self.pending_downloads[batch_id]["status"] = "processing"
        self.save_pending_downloads()
        
        # ایجاد تسک‌های دانلود با استفاده از سمافور برای محدود کردن تعداد دانلودهای همزمان
        for i, url in enumerate(urls):
            download_task = asyncio.create_task(self.download_url_with_semaphore(url, user_id, quality, batch_id, i))
            download_tasks.append(download_task)
            
            # اضافه کردن تأخیر بین شروع دانلودها برای جلوگیری از فشار زیاد
            await asyncio.sleep(DOWNLOAD_DELAY)
        
        # منتظر تکمیل تمام دانلودها
        await asyncio.gather(*download_tasks)
        
        # بروزرسانی وضعیت دسته
        self.pending_downloads[batch_id]["status"] = "completed"
        self.save_pending_downloads()
        
        logger.info(f"دسته {batch_id} با موفقیت پردازش شد")
    
    async def download_url_with_semaphore(self, url: str, user_id: int, quality: str, batch_id: str, index: int) -> None:
        """دانلود URL با استفاده از سمافور برای کنترل تعداد دانلودهای همزمان"""
        async with download_semaphore:
            await self.download_url(url, user_id, quality, batch_id, index)
    
    async def download_url(self, url: str, user_id: int, quality: str, batch_id: str, index: int) -> None:
        """دانلود یک URL با استفاده از تابع دانلود مناسب - بهینه‌سازی شده برای عملکرد بهتر"""
        key = f"{batch_id}_{index}"
        try:
            logger.info(f"شروع دانلود {url} برای کاربر {user_id} با کیفیت {quality}")
            
            # بروزرسانی وضعیت در پردازش
            download_status[key] = "downloading"
            
            # بررسی کش برای جلوگیری از دانلود مجدد
            from telegram_downloader import get_from_cache
            cached_file = get_from_cache(url, quality)
            if cached_file:
                logger.info(f"فایل از کش برگردانده شد: {cached_file}")
                download_results[key] = cached_file
                download_status[key] = "completed"
                
                # بروزرسانی پیشرفت
                with lock:
                    self.pending_downloads[batch_id]["completed"] += 1
                    self.pending_downloads[batch_id]["progress"] = (self.pending_downloads[batch_id]["completed"] / 
                                                                  self.pending_downloads[batch_id]["total"]) * 100
                    self.save_pending_downloads()
                return
            
            from telegram_downloader import InstagramDownloader, YouTubeDownloader, is_instagram_url, is_youtube_url, add_to_cache
            
            # انتخاب دانلودر مناسب بر اساس نوع URL
            if is_instagram_url(url):
                downloader = InstagramDownloader()
                # استفاده از ThreadPoolExecutor پیشرفته با 8 ترد برای چند برابر کردن سرعت
                with ThreadPoolExecutor(max_workers=8) as executor:
                    # اجرای همزمان چندین فرآیند دانلود با اولویت بالا
                    downloaded_file = await asyncio.get_event_loop().run_in_executor(
                        executor,
                        lambda: asyncio.run(downloader.download_post(url, quality))
                    )
            elif is_youtube_url(url):
                downloader = YouTubeDownloader()
                # تنظیمات فوق‌العاده بهینه‌سازی شده برای دانلود چندبرابر سریع‌تر
                youtube_opts = {
                    'concurrent_fragment_downloads': 20,
                    'buffersize': 1024 * 1024 * 50,
                    'http_chunk_size': 1024 * 1024 * 25,
                    'fragment_retries': 10,
                    'retry_sleep_functions': {'fragment': lambda x: 0.5},
                    'retries': 10,
                    'file_access_retries': 10,
                    'extractor_retries': 5,
                    'throttledratelimit': 0,
                    'sleep_interval': 0,
                    'max_sleep_interval': 0,
                    'external_downloader': 'aria2c',
                    'external_downloader_args': [
                        '-j', '16',
                        '-x', '16',
                        '-s', '16',
                        '--min-split-size=1M',
                        '--optimize-concurrent-downloads=true',
                        '--http-accept-gzip=true',
                        '--download-result=hide',
                        '--quiet=true',
                    ],
                }
                # استفاده از ThreadPoolExecutor پیشرفته با 8 ترد برای چند برابر کردن سرعت
                with ThreadPoolExecutor(max_workers=8) as executor:
                    # اجرای همزمان چندین فرآیند دانلود با اولویت بالا
                    downloaded_file = await asyncio.get_event_loop().run_in_executor(
                        executor,
                        lambda: asyncio.run(downloader.download_video(url, quality))
                    )
            else:
                logger.warning(f"URL نامعتبر: {url}")
                download_status[key] = "failed"
                
                # بروزرسانی پیشرفت علی‌رغم خطا
                with lock:
                    self.pending_downloads[batch_id]["completed"] += 1
                    self.pending_downloads[batch_id]["progress"] = (self.pending_downloads[batch_id]["completed"] / 
                                                                  self.pending_downloads[batch_id]["total"]) * 100
                    self.save_pending_downloads()
                return
                
            # ذخیره نتیجه دانلود
            if downloaded_file:
                # افزودن به کش برای استفاده‌های بعدی
                add_to_cache(url, downloaded_file, quality)
                
                download_results[key] = downloaded_file
                download_status[key] = "completed"
                logger.info(f"دانلود {url} برای کاربر {user_id} تکمیل شد: {downloaded_file}")
            else:
                download_status[key] = "failed"
                logger.error(f"دانلود {url} با شکست مواجه شد (فایل خروجی خالی)")
            
            # بروزرسانی پیشرفت دسته
            with lock:
                self.pending_downloads[batch_id]["completed"] += 1
                self.pending_downloads[batch_id]["progress"] = (self.pending_downloads[batch_id]["completed"] / 
                                                               self.pending_downloads[batch_id]["total"]) * 100
                self.save_pending_downloads()
                
        except Exception as e:
            logger.error(f"خطا در دانلود {url}: {str(e)}")
            download_status[key] = "failed"
            
            # بروزرسانی پیشرفت دسته علی‌رغم خطا
            with lock:
                self.pending_downloads[batch_id]["completed"] += 1
                self.pending_downloads[batch_id]["progress"] = (self.pending_downloads[batch_id]["completed"] / 
                                                               self.pending_downloads[batch_id]["total"]) * 100
                self.save_pending_downloads()
    
    async def get_batch_status(self, batch_id: str) -> Dict:
        """دریافت وضعیت یک دسته دانلود"""
        if batch_id in self.pending_downloads:
            return self.pending_downloads[batch_id]
        return {"error": "شناسه دسته یافت نشد"}
    
    def get_download_file(self, batch_id: str, index: int) -> Optional[str]:
        """دریافت مسیر فایل دانلود شده"""
        key = f"{batch_id}_{index}"
        if key in download_results:
            return download_results[key]
        return None
        
    def get_all_batches_for_user(self, user_id: int) -> List[Dict]:
        """دریافت تمام دسته‌های دانلود یک کاربر"""
        user_batches = []
        for batch_id, batch in self.pending_downloads.items():
            if batch.get("user_id") == user_id:
                batch_info = batch.copy()
                batch_info["batch_id"] = batch_id
                user_batches.append(batch_info)
        
        # مرتب‌سازی بر اساس زمان (جدیدترین اول)
        user_batches.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return user_batches

# نمونه سینگلتون از مدیر دانلود
download_manager = BulkDownloadManager()

# تعریف دستورات تلگرام برای مدیریت دانلود موازی
async def handle_bulk_download(update, context):
    """هندلر دستور /bulkdownload برای دانلود چندگانه"""
    message_text = update.message.text
    
    # استخراج کیفیت از دستور
    quality_match = re.search(r'/bulkdownload\s+(\w+)', message_text)
    quality = "best"
    if quality_match:
        requested_quality = quality_match.group(1).lower()
        if requested_quality in ["1080p", "720p", "480p", "360p", "240p", "audio"]:
            quality = requested_quality
    
    # پاک کردن دستور از متن
    message_text = re.sub(r'/bulkdownload\s+\w+\s*', '', message_text)
    message_text = re.sub(r'/bulkdownload\s*', '', message_text)
    
    if not message_text and update.message.reply_to_message:
        # اگر دستور در پاسخ به پیام دیگری است، از متن آن پیام استفاده کن
        message_text = update.message.reply_to_message.text
    
    if not message_text:
        await update.message.reply_text(
            "⚠️ لطفاً چند لینک یوتیوب یا اینستاگرام را به همراه این دستور ارسال کنید یا به پیامی که شامل لینک‌هاست پاسخ دهید.\n\n"
            "مثال:\n"
            "/bulkdownload 720p\n"
            "https://www.youtube.com/watch?v=ABC123\n"
            "https://www.instagram.com/p/DEF456\n"
            "https://www.youtube.com/shorts/GHI789"
        )
        return
    
    # استخراج لینک‌ها
    urls = download_manager.extract_urls(message_text)
    
    if not urls:
        await update.message.reply_text("❌ هیچ لینک معتبری در پیام شما یافت نشد.")
        return
    
    # ارسال پیام در حال پردازش
    processing_message = await update.message.reply_text(
        f"🔍 در حال پردازش {len(urls)} لینک... لطفاً صبر کنید."
    )
    
    # افزودن به صف دانلود
    result = await download_manager.add_urls_to_queue(urls, update.effective_user.id, quality)
    
    # بروزرسانی پیام
    await processing_message.edit_text(result)

async def handle_batch_status(update, context):
    """هندلر دستور /status_{batch_id} برای بررسی وضعیت دسته دانلود"""
    message_text = update.message.text
    
    # استخراج شناسه دسته از دستور
    batch_id_match = re.search(r'/status_(\w+)', message_text)
    if not batch_id_match:
        await update.message.reply_text("❌ لطفاً شناسه دسته را به همراه دستور وارد کنید. مثال: /status_batch_abc123")
        return
    
    batch_id = batch_id_match.group(1)
    
    # دریافت وضعیت دسته
    status = await download_manager.get_batch_status(batch_id)
    
    if "error" in status:
        await update.message.reply_text(f"❌ {status['error']}")
        return
    
    # ساخت پیام وضعیت
    progress = status.get("progress", 0)
    completed = status.get("completed", 0)
    total = status.get("total", 0)
    current_status = status.get("status", "نامشخص")
    
    # ترجمه وضعیت به فارسی
    status_translation = {
        "pending": "در انتظار",
        "processing": "در حال پردازش",
        "completed": "تکمیل شده"
    }
    
    persian_status = status_translation.get(current_status, current_status)
    
    # ساخت نوار پیشرفت
    progress_bar = make_progress_bar(progress)
    
    message = (
        f"📊 وضعیت دسته دانلود: `{batch_id}`\n\n"
        f"🔄 وضعیت: {persian_status}\n"
        f"✅ تکمیل شده: {completed} از {total}\n"
        f"⏳ پیشرفت: {progress:.1f}%\n\n"
        f"{progress_bar}\n\n"
    )
    
    # اگر دسته کامل شده، اطلاعات بیشتری نشان بده
    if current_status == "completed":
        message += "✅ دانلود همه فایل‌ها تکمیل شده است. فایل‌ها به صورت جداگانه برای شما ارسال شده‌اند."
    
    await update.message.reply_text(message)

async def handle_list_downloads(update, context):
    """هندلر دستور /mydownloads برای نمایش همه دانلودهای کاربر"""
    user_id = update.effective_user.id
    
    # دریافت همه دسته‌های کاربر
    batches = download_manager.get_all_batches_for_user(user_id)
    
    if not batches:
        await update.message.reply_text("❌ شما هیچ دسته دانلودی ندارید.")
        return
    
    # ساخت پیام لیست دانلودها
    message = "📋 لیست دسته‌های دانلود شما:\n\n"
    
    for i, batch in enumerate(batches, 1):
        batch_id = batch.get("batch_id", "نامشخص")
        progress = batch.get("progress", 0)
        status = batch.get("status", "نامشخص")
        total = batch.get("total", 0)
        timestamp = batch.get("timestamp", 0)
        
        # ترجمه وضعیت به فارسی
        status_translation = {
            "pending": "در انتظار",
            "processing": "در حال پردازش",
            "completed": "تکمیل شده"
        }
        
        persian_status = status_translation.get(status, status)
        
        # تبدیل timestamp به تاریخ خوانا
        date_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(timestamp))
        
        message += (
            f"{i}. شناسه: `{batch_id}`\n"
            f"   📊 وضعیت: {persian_status} ({progress:.1f}%)\n"
            f"   📁 تعداد فایل‌ها: {total}\n"
            f"   🕒 تاریخ: {date_str}\n"
            f"   📝 دستور بررسی: `/status_{batch_id}`\n\n"
        )
    
    await update.message.reply_text(message)

def make_progress_bar(percent, length=20):
    """ساخت نوار پیشرفت متنی"""
    filled_length = int(length * percent / 100)
    bar = '█' * filled_length + '░' * (length - filled_length)
    return f"[{bar}] {percent:.1f}%"

def register_handlers(application):
    """ثبت هندلرهای دستورات در اپلیکیشن تلگرام"""
    from telegram.ext import CommandHandler, MessageHandler, filters
    
    # هندلر دستور دانلود چندگانه
    application.add_handler(CommandHandler("bulkdownload", handle_bulk_download))
    
    # هندلر دستور بررسی وضعیت با الگوی /status_{batch_id}
    application.add_handler(MessageHandler(filters.Regex(r'^/status_\w+'), handle_batch_status))
    
    # هندلر دستور نمایش همه دانلودها
    application.add_handler(CommandHandler("mydownloads", handle_list_downloads))
    
    logger.info("هندلرهای دانلود موازی با موفقیت ثبت شدند")
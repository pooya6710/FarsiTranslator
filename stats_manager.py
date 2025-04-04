#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ماژول مدیریت آمار

این ماژول توابع لازم برای ذخیره، بروزرسانی و نمایش آمار ربات را ارائه می‌دهد.
"""

import os
import io
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from sqlalchemy import func, desc
import matplotlib.pyplot as plt
import numpy as np

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import ContextTypes
except ImportError:
    from telegram.bot import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.bot.ext import ContextTypes
except Exception as e:
    from python_telegram_bot import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from python_telegram_bot.ext import ContextTypes

from database_models import Session, User, Download, BotStats

# تنظیمات لاگر
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# فهرست کاربران مدیر (از متغیر محیطی)
ADMIN_IDS = []
try:
    admin_id_str = os.environ.get("ADMIN_TELEGRAM_ID", "")
    if admin_id_str:
        # پشتیبانی از چند ادمین با جداکننده کاما
        ADMIN_IDS = [int(admin_id.strip()) for admin_id in admin_id_str.split(',') if admin_id.strip()]
        logger.info(f"شناسه‌های مدیران ربات بارگذاری شدند: {ADMIN_IDS}")
except Exception as e:
    logger.error(f"خطا در بارگذاری شناسه‌های مدیران: {e}")

class StatsManager:
    """مدیریت آمار ربات"""
    
    @staticmethod
    def ensure_user_exists(update: Update) -> User:
        """اطمینان از وجود کاربر در دیتابیس و بروزرسانی آخرین فعالیت"""
        user = update.effective_user
        if not user:
            logger.warning("کاربر در آپدیت یافت نشد")
            return None
            
        try:
            with Session() as session:
                # جستجوی کاربر در دیتابیس
                db_user = session.query(User).filter_by(id=user.id).first()
                
                if db_user:
                    # بروزرسانی اطلاعات کاربر
                    db_user.username = user.username
                    db_user.first_name = user.first_name
                    db_user.last_name = user.last_name
                    db_user.language_code = user.language_code
                    db_user.last_activity = datetime.utcnow()
                    
                    # بررسی دسترسی مدیر
                    if user.id in ADMIN_IDS and not db_user.is_admin:
                        db_user.is_admin = True
                        logger.info(f"کاربر {user.id} به عنوان مدیر ارتقا یافت")
                else:
                    # ایجاد کاربر جدید
                    is_admin = user.id in ADMIN_IDS
                    db_user = User(
                        id=user.id,
                        username=user.username,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        language_code=user.language_code,
                        is_admin=is_admin
                    )
                    session.add(db_user)
                    logger.info(f"کاربر جدید در دیتابیس ثبت شد: {user.id}")
                
                session.commit()
                return db_user
        except Exception as e:
            logger.error(f"خطا در ثبت یا بروزرسانی کاربر: {e}")
            return None
    
    @staticmethod
    def record_download(user_id: int, url: str, source_type: str, quality: str, 
                        is_audio: bool, file_size: float = None, 
                        download_time: float = None, success: bool = True, 
                        error: str = None) -> bool:
        """ثبت اطلاعات یک دانلود جدید"""
        try:
            with Session() as session:
                # افزودن رکورد دانلود
                download = Download(
                    user_id=user_id,
                    url=url,
                    source_type=source_type.lower(),
                    quality=quality,
                    is_audio=is_audio,
                    file_size=file_size,
                    download_time=download_time,
                    success=success,
                    error=error
                )
                session.add(download)
                session.commit()
                
                # بروزرسانی آمار روزانه
                StatsManager._update_daily_stats(session)
                
                logger.info(f"دانلود با موفقیت ثبت شد: کاربر {user_id}, نوع {source_type}")
                return True
        except Exception as e:
            logger.error(f"خطا در ثبت آمار دانلود: {e}")
            return False
            
    @staticmethod
    def add_download_record(user, source_type: str, quality: str, file_size: float = None) -> bool:
        """
        ثبت آمار دانلود با استفاده از آبجکت user تلگرام
        
        Args:
            user: آبجکت کاربر تلگرام
            source_type: نوع منبع (youtube, instagram)
            quality: کیفیت دانلود
            file_size: حجم فایل به بایت
        
        Returns:
            bool: موفقیت‌آمیز بودن ثبت
        """
        try:
            # تبدیل حجم فایل از بایت به مگابایت
            file_size_mb = file_size / (1024 * 1024) if file_size else None
            
            # بررسی اینکه درخواست صوتی است یا خیر
            is_audio = quality == "audio"
            
            # ثبت در دیتابیس
            user_id = user.id
            return StatsManager.record_download(
                user_id=user_id,
                url="",  # URL در این متد ثبت نمی‌شود
                source_type=source_type,
                quality=quality,
                is_audio=is_audio,
                file_size=file_size_mb,
                success=True
            )
        except Exception as e:
            logger.error(f"خطا در ثبت آمار: {e}")
            return False
    
    @staticmethod
    def _update_daily_stats(session) -> None:
        """بروزرسانی آمار روزانه ربات"""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # بررسی آیا آمار امروز قبلاً ایجاد شده است
        stats = session.query(BotStats).filter(func.date(BotStats.date) == func.date(today)).first()
        
        if not stats:
            # ایجاد رکورد جدید برای امروز
            stats = BotStats(date=today)
            session.add(stats)
        
        # محاسبه آمارها
        # تعداد کل کاربران
        stats.total_users = session.query(func.count(User.id)).scalar()
        
        # تعداد کاربران فعال در 7 روز گذشته
        week_ago = datetime.utcnow() - timedelta(days=7)
        stats.active_users = session.query(func.count(User.id)).filter(User.last_activity >= week_ago).scalar()
        
        # آمار دانلودها
        stats.total_downloads = session.query(func.count(Download.id)).scalar()
        stats.youtube_downloads = session.query(func.count(Download.id)).filter(Download.source_type == 'youtube').scalar()
        stats.instagram_downloads = session.query(func.count(Download.id)).filter(Download.source_type == 'instagram').scalar()
        stats.audio_downloads = session.query(func.count(Download.id)).filter(Download.is_audio == True).scalar()
        stats.video_downloads = session.query(func.count(Download.id)).filter(Download.is_audio == False).scalar()
        
        # محاسبه میانگین زمان دانلود و حجم کل
        avg_time_result = session.query(func.avg(Download.download_time)).filter(Download.download_time != None).scalar()
        stats.avg_download_time = float(avg_time_result) if avg_time_result is not None else 0.0
        
        total_size_result = session.query(func.sum(Download.file_size)).filter(Download.file_size != None).scalar()
        stats.total_download_size = float(total_size_result) if total_size_result is not None else 0.0
        
        session.commit()
        logger.info(f"آمار روزانه بروزرسانی شد: {stats.date.strftime('%Y-%m-%d')}")
    
    @staticmethod
    def get_user_stats(user_id: int) -> Dict[str, Any]:
        """دریافت آمار دانلودهای یک کاربر"""
        try:
            with Session() as session:
                # اطلاعات پایه کاربر
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    return {"error": "کاربر یافت نشد"}
                
                # آمار دانلودها
                total_downloads = session.query(func.count(Download.id)).filter(Download.user_id == user_id).scalar()
                youtube_downloads = session.query(func.count(Download.id)).filter(
                    Download.user_id == user_id, Download.source_type == 'youtube').scalar()
                instagram_downloads = session.query(func.count(Download.id)).filter(
                    Download.user_id == user_id, Download.source_type == 'instagram').scalar()
                audio_downloads = session.query(func.count(Download.id)).filter(
                    Download.user_id == user_id, Download.is_audio == True).scalar()
                video_downloads = session.query(func.count(Download.id)).filter(
                    Download.user_id == user_id, Download.is_audio == False).scalar()
                
                # میانگین زمان دانلود
                avg_time_result = session.query(func.avg(Download.download_time)).filter(
                    Download.user_id == user_id, Download.download_time != None).scalar()
                avg_download_time = float(avg_time_result) if avg_time_result is not None else 0.0
                
                # حجم کل دانلودها
                total_size_result = session.query(func.sum(Download.file_size)).filter(
                    Download.user_id == user_id, Download.file_size != None).scalar()
                total_download_size = float(total_size_result) if total_size_result is not None else 0.0
                
                # آمار روزانه
                daily_stats = []
                last_week = datetime.utcnow() - timedelta(days=7)
                daily_data = session.query(
                    func.date(Download.created_at),
                    func.count(Download.id)
                ).filter(
                    Download.user_id == user_id,
                    Download.created_at >= last_week
                ).group_by(
                    func.date(Download.created_at)
                ).order_by(
                    func.date(Download.created_at)
                ).all()
                
                # تبدیل نتایج به دیکشنری
                for date, count in daily_data:
                    daily_stats.append({"date": date, "count": count})
                
                return {
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "created_at": user.created_at,
                        "last_activity": user.last_activity
                    },
                    "downloads": {
                        "total": total_downloads,
                        "youtube": youtube_downloads,
                        "instagram": instagram_downloads,
                        "audio": audio_downloads,
                        "video": video_downloads,
                        "avg_time": avg_download_time,
                        "total_size": total_download_size
                    },
                    "daily_stats": daily_stats
                }
        except Exception as e:
            logger.error(f"خطا در دریافت آمار کاربر: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def get_bot_stats() -> Dict[str, Any]:
        """دریافت آمار کلی ربات"""
        try:
            with Session() as session:
                # آمار کلی
                total_users = session.query(func.count(User.id)).scalar()
                week_ago = datetime.utcnow() - timedelta(days=7)
                active_users = session.query(func.count(User.id)).filter(User.last_activity >= week_ago).scalar()
                
                total_downloads = session.query(func.count(Download.id)).scalar()
                youtube_downloads = session.query(func.count(Download.id)).filter(Download.source_type == 'youtube').scalar()
                instagram_downloads = session.query(func.count(Download.id)).filter(Download.source_type == 'instagram').scalar()
                audio_downloads = session.query(func.count(Download.id)).filter(Download.is_audio == True).scalar()
                video_downloads = session.query(func.count(Download.id)).filter(Download.is_audio == False).scalar()
                
                # میانگین زمان دانلود
                avg_time_result = session.query(func.avg(Download.download_time)).filter(Download.download_time != None).scalar()
                avg_download_time = float(avg_time_result) if avg_time_result is not None else 0.0
                
                # حجم کل دانلودها
                total_size_result = session.query(func.sum(Download.file_size)).filter(Download.file_size != None).scalar()
                total_download_size = float(total_size_result) if total_size_result is not None else 0.0
                
                # آمار روزانه
                daily_stats = []
                last_month = datetime.utcnow() - timedelta(days=30)
                daily_data = session.query(
                    func.date(Download.created_at),
                    func.count(Download.id)
                ).filter(
                    Download.created_at >= last_month
                ).group_by(
                    func.date(Download.created_at)
                ).order_by(
                    func.date(Download.created_at)
                ).all()
                
                # تبدیل نتایج به دیکشنری
                for date, count in daily_data:
                    daily_stats.append({"date": date.strftime("%Y-%m-%d"), "count": count})
                
                # کاربران فعال
                top_users = session.query(
                    Download.user_id,
                    func.count(Download.id).label('download_count')
                ).group_by(
                    Download.user_id
                ).order_by(
                    desc('download_count')
                ).limit(5).all()
                
                # دریافت اطلاعات کاربران برتر
                top_users_data = []
                for user_id, count in top_users:
                    user = session.query(User).filter_by(id=user_id).first()
                    if user:
                        top_users_data.append({
                            "id": user.id,
                            "username": user.username or "بدون نام کاربری",
                            "first_name": user.first_name or "بدون نام",
                            "count": count
                        })
                
                return {
                    "users": {
                        "total": total_users,
                        "active": active_users
                    },
                    "downloads": {
                        "total": total_downloads,
                        "youtube": youtube_downloads,
                        "instagram": instagram_downloads,
                        "audio": audio_downloads,
                        "video": video_downloads,
                        "avg_time": avg_download_time,
                        "total_size": total_download_size
                    },
                    "daily_stats": daily_stats,
                    "top_users": top_users_data
                }
        except Exception as e:
            logger.error(f"خطا در دریافت آمار ربات: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def generate_stats_chart(stats: Dict[str, Any]) -> Optional[io.BytesIO]:
        """تولید نمودار آماری از داده‌ها"""
        try:
            if "error" in stats:
                return None
                
            # تنظیم فونت مناسب فارسی
            plt.rcParams['font.family'] = 'DejaVu Sans'
            
            # ایجاد فیگور و محورها
            plt.figure(figsize=(10, 8))
            
            # نمودار دانلودهای یوتیوب و اینستاگرام
            labels = ['یوتیوب', 'اینستاگرام']
            downloads = [stats['downloads']['youtube'], stats['downloads']['instagram']]
            
            plt.subplot(2, 2, 1)
            plt.pie(downloads, labels=labels, autopct='%1.1f%%', startangle=90, colors=['#FF0000', '#C13584'])
            plt.title('دانلودها بر اساس منبع')
            
            # نمودار دانلودهای صوتی و ویدیویی
            labels = ['ویدیو', 'صدا']
            media_types = [stats['downloads']['video'], stats['downloads']['audio']]
            
            plt.subplot(2, 2, 2)
            plt.pie(media_types, labels=labels, autopct='%1.1f%%', startangle=90, colors=['#4CAF50', '#2196F3'])
            plt.title('نوع فایل‌های دانلود شده')
            
            # نمودار کاربران کل و فعال
            labels = ['کاربران غیرفعال', 'کاربران فعال']
            users = [stats['users']['total'] - stats['users']['active'], stats['users']['active']]
            
            plt.subplot(2, 2, 3)
            plt.pie(users, labels=labels, autopct='%1.1f%%', startangle=90, colors=['#9E9E9E', '#3F51B5'])
            plt.title('وضعیت فعالیت کاربران')
            
            # اطلاعات کلی
            plt.subplot(2, 2, 4)
            plt.axis('off')
            info_text = (
                f"کل کاربران: {stats['users']['total']}\n"
                f"کاربران فعال: {stats['users']['active']}\n"
                f"کل دانلودها: {stats['downloads']['total']}\n"
                f"میانگین زمان دانلود: {stats['downloads']['avg_time']:.2f} ثانیه\n"
                f"حجم کل دانلودها: {stats['downloads']['total_size'] / 1024:.2f} GB"
            )
            plt.text(0.1, 0.5, info_text, fontsize=12, va='center')
            
            # تنظیم عنوان کلی
            plt.suptitle('آمار کلی ربات دانلود', fontsize=16)
            plt.tight_layout()
            
            # ذخیره نمودار در بافر حافظه
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=100)
            buf.seek(0)
            plt.close()
            
            return buf
        except Exception as e:
            logger.error(f"خطا در تولید نمودار آماری: {e}")
            return None
    
    @staticmethod
    def generate_daily_chart(stats: Dict[str, Any]) -> Optional[io.BytesIO]:
        """تولید نمودار آماری روزانه"""
        try:
            if "error" in stats or not stats.get('daily_stats'):
                return None
                
            # تنظیم فونت مناسب فارسی
            plt.rcParams['font.family'] = 'DejaVu Sans'
            
            # استخراج داده‌های روزانه
            dates = []
            counts = []
            
            for item in stats['daily_stats']:
                # تبدیل تاریخ به فرمت نمایشی
                if isinstance(item['date'], str):
                    date_obj = datetime.strptime(item['date'], "%Y-%m-%d")
                    display_date = date_obj.strftime("%m-%d")
                else:
                    display_date = item['date'].strftime("%m-%d")
                
                dates.append(display_date)
                counts.append(item['count'])
            
            # ایجاد نمودار
            plt.figure(figsize=(12, 6))
            
            # نمودار میله‌ای دانلودهای روزانه
            plt.bar(dates, counts, color='#2196F3')
            plt.title('دانلودهای روزانه در ماه گذشته')
            plt.xlabel('تاریخ')
            plt.ylabel('تعداد دانلود')
            plt.xticks(rotation=45)
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            
            # تنظیم نمودار
            plt.tight_layout()
            
            # ذخیره نمودار در بافر حافظه
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=100)
            buf.seek(0)
            plt.close()
            
            return buf
        except Exception as e:
            logger.error(f"خطا در تولید نمودار روزانه: {e}")
            return None
    
    @staticmethod
    def format_stats_message(stats: Dict[str, Any]) -> str:
        """تبدیل آمار به متن قابل نمایش"""
        if "error" in stats:
            return f"❌ خطا در دریافت آمار: {stats['error']}"
        
        # تاریخ فعلی
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        message = f"📊 <b>آمار ربات دانلود</b>\n\n"
        message += f"📅 تاریخ: {current_time}\n\n"
        
        # آمار کاربران
        message += f"👥 <b>کاربران:</b>\n"
        message += f"• تعداد کل: {stats['users']['total']} کاربر\n"
        message += f"• کاربران فعال: {stats['users']['active']} کاربر\n\n"
        
        # آمار دانلودها
        message += f"📥 <b>دانلودها:</b>\n"
        message += f"• تعداد کل: {stats['downloads']['total']} دانلود\n"
        message += f"• یوتیوب: {stats['downloads']['youtube']} ({int(stats['downloads']['youtube'] / max(1, stats['downloads']['total']) * 100)}%)\n"
        message += f"• اینستاگرام: {stats['downloads']['instagram']} ({int(stats['downloads']['instagram'] / max(1, stats['downloads']['total']) * 100)}%)\n"
        message += f"• ویدیو: {stats['downloads']['video']} ({int(stats['downloads']['video'] / max(1, stats['downloads']['total']) * 100)}%)\n"
        message += f"• صدا: {stats['downloads']['audio']} ({int(stats['downloads']['audio'] / max(1, stats['downloads']['total']) * 100)}%)\n\n"
        
        # سایر آمارها
        message += f"⏱ <b>کارایی:</b>\n"
        message += f"• میانگین زمان دانلود: {stats['downloads']['avg_time']:.2f} ثانیه\n"
        message += f"• حجم کل دانلودها: {stats['downloads']['total_size'] / 1024:.2f} GB\n\n"
        
        # کاربران برتر
        message += f"🏆 <b>کاربران برتر:</b>\n"
        
        if stats.get('top_users'):
            for i, user in enumerate(stats['top_users'], 1):
                username = user['username'] if user['username'] else user['first_name']
                message += f"{i}. {username}: {user['count']} دانلود\n"
        else:
            message += "اطلاعاتی موجود نیست\n"
        
        return message

async def stats_command(update: Update, context) -> None:
    """هندلر دستور /stats برای نمایش آمار به مدیر ربات"""
    user_id = update.effective_user.id
    
    # بررسی دسترسی مدیر
    is_admin = False
    
    try:
        with Session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                is_admin = user.is_admin
    except Exception:
        pass
    
    if not is_admin and user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔️ شما دسترسی به این بخش را ندارید.")
        return
    
    # دریافت و نمایش آمار
    await update.message.reply_text("🔄 در حال دریافت آمار...")
    
    stats = StatsManager.get_bot_stats()
    stats_text = StatsManager.format_stats_message(stats)
    
    # ایجاد دکمه‌های آمار
    keyboard = [
        [
            InlineKeyboardButton("📊 نمودار کلی", callback_data="stats_chart"),
            InlineKeyboardButton("📈 نمودار روزانه", callback_data="daily_chart")
        ],
        [
            InlineKeyboardButton("🔄 بروزرسانی", callback_data="refresh_stats")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        stats_text,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def handle_stats_buttons(update: Update, context) -> None:
    """هندلر کالبک دکمه‌های مربوط به آمار"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    # بررسی دسترسی مدیر
    is_admin = False
    
    try:
        with Session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                is_admin = user.is_admin
    except Exception:
        pass
    
    if not is_admin and user_id not in ADMIN_IDS:
        await query.answer("⛔️ شما دسترسی به این بخش را ندارید.")
        return
    
    await query.answer()
    
    if query.data == "stats_chart":
        # نمایش نمودار آماری کلی
        stats = StatsManager.get_bot_stats()
        chart = StatsManager.generate_stats_chart(stats)
        
        if chart:
            await query.message.reply_photo(
                photo=chart,
                caption="📊 نمودار آماری کلی ربات دانلود"
            )
        else:
            await query.message.reply_text("❌ خطا در ایجاد نمودار آماری")
    
    elif query.data == "daily_chart":
        # نمایش نمودار آماری روزانه
        stats = StatsManager.get_bot_stats()
        chart = StatsManager.generate_daily_chart(stats)
        
        if chart:
            await query.message.reply_photo(
                photo=chart,
                caption="📈 نمودار آماری دانلودهای روزانه"
            )
        else:
            await query.message.reply_text("❌ خطا در ایجاد نمودار آماری روزانه")
    
    elif query.data == "refresh_stats":
        # بروزرسانی آمار
        stats = StatsManager.get_bot_stats()
        stats_text = StatsManager.format_stats_message(stats)
        
        # ایجاد دکمه‌های آمار
        keyboard = [
            [
                InlineKeyboardButton("📊 نمودار کلی", callback_data="stats_chart"),
                InlineKeyboardButton("📈 نمودار روزانه", callback_data="daily_chart")
            ],
            [
                InlineKeyboardButton("🔄 بروزرسانی", callback_data="refresh_stats")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            stats_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

class Timer:
    """کلاس ردیاب زمان برای اندازه‌گیری زمان دانلود"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
    
    def start(self):
        """شروع زمان‌سنج"""
        self.start_time = time.time()
        self.end_time = None
    
    def stop(self):
        """توقف زمان‌سنج"""
        self.end_time = time.time()
    
    def get_elapsed(self):
        """محاسبه زمان سپری شده (ثانیه)"""
        if self.start_time is None:
            return 0
            
        end = self.end_time if self.end_time is not None else time.time()
        return end - self.start_time
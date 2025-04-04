#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ماژول مدل‌های پایگاه داده

این ماژول مدل‌های پایگاه داده برای ذخیره آمار و اطلاعات کاربران را تعریف می‌کند.
"""

import os
import logging
from datetime import datetime

import sqlalchemy
from sqlalchemy import Column, Integer, BigInteger, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# تنظیمات لاگر
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# تنظیم موتور پایگاه داده
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    logger.warning("آدرس اتصال به پایگاه داده یافت نشد!")
    DATABASE_URL = "sqlite:///:memory:"  # استفاده از دیتابیس موقت در حافظه

Base = declarative_base()
engine = sqlalchemy.create_engine(DATABASE_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)

class User(Base):
    """مدل کاربر برای ذخیره اطلاعات کاربران ربات"""
    __tablename__ = 'users'
    
    id = Column(BigInteger, primary_key=True)  # آیدی تلگرام کاربر
    username = Column(String(255), nullable=True)  # نام کاربری تلگرام
    first_name = Column(String(255), nullable=True)  # نام کاربر
    last_name = Column(String(255), nullable=True)  # نام خانوادگی کاربر
    language_code = Column(String(10), nullable=True)  # کد زبان کاربر
    is_admin = Column(Boolean, default=False)  # آیا کاربر ادمین است؟
    created_at = Column(DateTime, default=datetime.utcnow)  # تاریخ ایجاد
    last_activity = Column(DateTime, default=datetime.utcnow)  # آخرین فعالیت
    downloads = relationship("Download", back_populates="user")  # رابطه با دانلودها
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username})>"

class Download(Base):
    """مدل دانلود برای ذخیره اطلاعات دانلودهای انجام شده"""
    __tablename__ = 'downloads'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)  # آیدی کاربر
    url = Column(Text, nullable=False)  # آدرس دانلود
    source_type = Column(String(20), nullable=False)  # نوع منبع (youtube, instagram)
    quality = Column(String(10), nullable=True)  # کیفیت دانلود
    is_audio = Column(Boolean, default=False)  # آیا صوتی است؟
    file_size = Column(Float, nullable=True)  # حجم فایل (MB)
    download_time = Column(Float, nullable=True)  # زمان دانلود (ثانیه)
    success = Column(Boolean, default=True)  # آیا دانلود موفق بوده؟
    error = Column(Text, nullable=True)  # خطای احتمالی
    created_at = Column(DateTime, default=datetime.utcnow)  # تاریخ دانلود
    user = relationship("User", back_populates="downloads")  # رابطه با کاربر
    
    def __repr__(self):
        return f"<Download(id={self.id}, user_id={self.user_id}, source_type={self.source_type})>"

class BotStats(Base):
    """مدل آمار کلی ربات"""
    __tablename__ = 'bot_stats'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, default=datetime.utcnow, unique=True)  # تاریخ آمار
    total_users = Column(Integer, default=0)  # تعداد کل کاربران
    active_users = Column(Integer, default=0)  # تعداد کاربران فعال
    total_downloads = Column(Integer, default=0)  # تعداد کل دانلودها
    youtube_downloads = Column(Integer, default=0)  # تعداد دانلودهای یوتیوب
    instagram_downloads = Column(Integer, default=0)  # تعداد دانلودهای اینستاگرام
    audio_downloads = Column(Integer, default=0)  # تعداد دانلودهای صوتی
    video_downloads = Column(Integer, default=0)  # تعداد دانلودهای ویدیویی
    total_download_size = Column(Float, default=0.0)  # حجم کل دانلودها (MB)
    avg_download_time = Column(Float, default=0.0)  # میانگین زمان دانلود (ثانیه)
    
    def __repr__(self):
        return f"<BotStats(id={self.id}, date={self.date}, total_users={self.total_users})>"

def init_db():
    """ایجاد تمام جداول در دیتابیس"""
    try:
        # ایجاد جداول اگر وجود ندارند
        Base.metadata.create_all(engine)
        logger.info("جداول پایگاه داده با موفقیت ایجاد شدند")
        
        # افزودن دسترسی مدیر به کاربر اول (اختیاری)
        # این قسمت می‌تواند براساس نیاز پروژه تغییر کند
        with Session() as session:
            # بررسی وجود کاربر مدیر
            admin_count = session.query(User).filter_by(is_admin=True).count()
            
            # اضافه کردن ادمین اولیه اگر وجود ندارد
            ADMIN_ID = os.environ.get("ADMIN_TELEGRAM_ID")
            if ADMIN_ID and admin_count == 0:
                try:
                    admin_id = int(ADMIN_ID)
                    admin = User(
                        id=admin_id,
                        username="admin",
                        first_name="Admin",
                        is_admin=True
                    )
                    session.add(admin)
                    session.commit()
                    logger.info(f"کاربر مدیر با شناسه {admin_id} اضافه شد")
                except Exception as e:
                    logger.error(f"خطا در افزودن کاربر مدیر: {e}")
                    session.rollback()
        
        return True
    except Exception as e:
        logger.error(f"خطا در ایجاد پایگاه داده: {e}")
        return False

if __name__ == "__main__":
    # اجرای مستقیم برای تست
    init_db()
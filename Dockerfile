FROM python:3.10-slim AS build

# ایجاد دایرکتوری کاری
WORKDIR /app

# کپی فقط فایل requirements 
COPY requirements.txt .

# نصب وابستگی‌های پایتون
RUN pip install --no-cache-dir -r requirements.txt

# فاز دوم: ایجاد تصویر نهایی بدون aria2c
FROM python:3.10-slim

# نصب بسته‌های مورد نیاز (بدون aria2)
RUN apt-get update && apt-get install -y ffmpeg python3-dev && \
    # اطمینان از حذف هرگونه اشاره به aria2
    apt-get remove -y aria2 libaria2-0 || true && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# تنظیم دایرکتوری کاری
WORKDIR /app

# کپی فایل‌های پروژه
COPY . .

# کپی وابستگی‌های پایتون از مرحله قبلی
COPY --from=build /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

# اطمینان از عدم وجود aria2c
RUN echo "Checking for aria2c binary..." && \
    ! command -v aria2c && \
    echo "aria2c is not installed!"

# ایجاد دایرکتوری دانلود
RUN mkdir -p /app/downloads && chmod 777 /app/downloads

# اجرای ربات با غیرفعال‌سازی کامل aria2c
CMD ["sh", "-c", "python yt_dlp_custom_override.py && python disable_aria2c.py && python telegram_downloader.py"]
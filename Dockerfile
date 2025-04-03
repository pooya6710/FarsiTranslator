# استفاده از روش چندمرحله‌ای برای ایجاد تصویر نهایی بدون هیچ اشاره‌ای به aria2
FROM python:3.10-slim AS builder

# نصب ابزارهای مورد نیاز برای ساخت
RUN apt-get update && apt-get install -y \
    ffmpeg \
    python3-dev \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# تنظیم دایرکتوری کاری
WORKDIR /build

# کپی فایل‌های پروژه و نصب وابستگی‌ها
COPY requirements.txt .

# نصب وابستگی‌های پایتون در محیط مجازی
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# مرحله دوم: پاکسازی و ساخت تصویر نهایی
FROM python:3.10-slim

# تنظیم محیط کار
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app" \
    NO_EXTERNAL_DOWNLOADER=1 \
    YTDLP_NO_ARIA2=1 \
    YDL_NO_ARIA2C=1 \
    HTTP_DOWNLOADER=native \
    YTDLP_DOWNLOADER=native

# نصب بسته‌های سیستمی مورد نیاز
RUN apt-get update && apt-get install -y \
    ffmpeg \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ایجاد دایرکتوری کاری
WORKDIR /app

# کپی محیط مجازی از مرحله قبل
COPY --from=builder /opt/venv /opt/venv

# کپی فایل‌های پروژه
COPY . .

# ایجاد دایرکتوری‌های مورد نیاز
RUN mkdir -p /app/downloads && chmod 777 /app/downloads \
    && mkdir -p /tmp/ytdlp_temp && chmod 777 /tmp/ytdlp_temp

# حذف هرگونه اشاره به aria2
RUN python complete_aria2_removal.py || : \
    && python clean_ytdlp_patch.py || : \
    && echo "=== Removing aria2 references ===" \
    && find / -name "aria2c" -type f -delete 2>/dev/null || : \
    && find / -name "*aria2*" -type f -delete 2>/dev/null || :

# اطمینان از عدم وجود دستور aria2c
RUN echo "Checking for aria2c binary..." && \
    ! command -v aria2c &> /dev/null && \
    echo "SUCCESS: aria2c is not installed!"

# فایل اجرایی
CMD bash railway_startup.sh
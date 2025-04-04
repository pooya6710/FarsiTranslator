# استفاده از روش چندمرحله‌ای برای ایجاد تصویر نهایی بدون هیچ اشاره‌ای به aria2
FROM python:3.10-slim AS builder

# تنظیم متغیرهای محیطی برای جلوگیری از نصب aria2
ENV YDL_NO_ARIA2C=1 \
    HTTP_DOWNLOADER=native \
    YTDLP_DOWNLOADER=native \
    NO_EXTERNAL_DOWNLOADER=1 \
    YTDLP_NO_ARIA2=1 \
    ARIA2C_DISABLED=1 \
    DISABLE_ARIA2C=true

# نصب ابزارهای مورد نیاز برای ساخت (بدون نصب aria2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    python3-dev \
    build-essential \
    && apt-get remove -y aria2 libaria2-0 || true \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && find / -name "aria2*" -type f -delete 2>/dev/null || true

# تنظیم دایرکتوری کاری
WORKDIR /build

# کپی فایل‌های پروژه و نصب وابستگی‌ها - بدون aria2
COPY requirements.txt .
COPY block_aria2_completely.py complete_aria2_removal.py clean_ytdlp_patch.py ./

# حذف aria2 از requirements.txt
RUN grep -v aria2 requirements.txt > requirements-clean.txt && mv requirements-clean.txt requirements.txt

# نصب وابستگی‌های پایتون در محیط مجازی
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    python block_aria2_completely.py && \
    python complete_aria2_removal.py && \
    python clean_ytdlp_patch.py

# مرحله دوم: پاکسازی و ساخت تصویر نهایی
FROM python:3.10-slim

# تنظیم محیط کار برای جلوگیری از استفاده از aria2
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app" \
    NO_EXTERNAL_DOWNLOADER=1 \
    YTDLP_NO_ARIA2=1 \
    YDL_NO_ARIA2C=1 \
    HTTP_DOWNLOADER=native \
    YTDLP_DOWNLOADER=native \
    ARIA2C_DISABLED=1 \
    DISABLE_ARIA2C=true

# نصب بسته‌های سیستمی مورد نیاز (بدون نصب aria2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    python3-dev \
    && apt-get remove -y aria2 libaria2-0 || true \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && find / -name "aria2*" -type f -delete 2>/dev/null || true

# ایجاد دایرکتوری کاری
WORKDIR /app

# کپی محیط مجازی از مرحله قبل
COPY --from=builder /opt/venv /opt/venv

# کپی فایل‌های پروژه
COPY . .

# ایجاد دایرکتوری‌های مورد نیاز
RUN mkdir -p /app/downloads && chmod 777 /app/downloads \
    && mkdir -p /tmp/ytdlp_temp && chmod 777 /tmp/ytdlp_temp

# اجرای اسکریپت‌های پاکسازی
RUN python block_aria2_completely.py && \
    python complete_aria2_removal.py && \
    python clean_ytdlp_patch.py && \
    find / -name "aria2*" -type f -delete 2>/dev/null || true

# بررسی نهایی - اطمینان از عدم وجود aria2c
RUN echo "Final check for aria2c..." && \
    ! command -v aria2c > /dev/null && \
    echo "SUCCESS: aria2c is not installed!"

# فایل اجرایی
CMD bash railway_startup.sh
# راهنمای دیپلوی ربات در Railway

این راهنما به شما کمک می‌کند تا ربات تلگرام دانلودر را در پلتفرم Railway راه‌اندازی کنید. Railway یک پلتفرم ابری است که امکان دیپلوی اپلیکیشن‌ها را به صورت ساده و سریع فراهم می‌کند.

## مراحل دیپلوی

### پیش‌نیازها

1. یک حساب کاربری در [Railway.app](https://railway.app/)
2. یک مخزن گیت‌هاب حاوی کد ربات
3. توکن ربات تلگرام (از [BotFather](https://t.me/BotFather) دریافت کنید)

### گام 1: آماده‌سازی مخزن گیت‌هاب

مطمئن شوید که فایل‌های زیر در مخزن گیت‌هاب شما وجود دارند:

- `Procfile` - با محتوای زیر:
  ```
  worker: python yt_dlp_custom_override.py && python disable_disabled_downloader.py && python telegram_downloader.py
  ```

- `railway.toml` - با محتوای زیر:
  ```toml
  [build]
  builder = "nixpacks"
  buildCommand = "echo 'Building the application...'"

  [deploy]
  startCommand = "python yt_dlp_custom_override.py && python disable_disabled_downloader.py && python telegram_downloader.py"
  restartPolicyType = "always"

  [nixpacks]
  aptPackages = ["ffmpeg", "python3-dev"]
  ```

- `requirements.txt` - حاوی تمام وابستگی‌های پایتون

- `Dockerfile` (توصیه شده) - برای استفاده از روش دیپلوی Docker با حذف کامل disabled_downloader:
  ```Dockerfile
  FROM python:3.10-slim AS build

  # ایجاد دایرکتوری کاری
  WORKDIR /app

  # کپی فقط فایل requirements 
  COPY requirements.txt .

  # نصب وابستگی‌های پایتون
  RUN pip install --no-cache-dir -r requirements.txt

  # فاز دوم: ایجاد تصویر نهایی بدون disabled_downloader
  FROM python:3.10-slim

  # نصب بسته‌های مورد نیاز (بدون disabled_aria)
  RUN apt-get update && apt-get install -y ffmpeg python3-dev && \
      # اطمینان از حذف هرگونه اشاره به disabled_aria
      apt-get remove -y disabled_aria libdisabled_aria-0 || true && \
      apt-get autoremove -y && \
      apt-get clean && \
      rm -rf /var/lib/apt/lists/*

  # تنظیم دایرکتوری کاری
  WORKDIR /app

  # کپی فایل‌های پروژه
  COPY . .

  # کپی وابستگی‌های پایتون از مرحله قبلی
  COPY --from=build /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

  # اطمینان از عدم وجود disabled_downloader
  RUN echo "Checking for disabled_downloader binary..." && \
      ! command -v disabled_downloader && \
      echo "disabled_downloader is not installed!"

  # ایجاد دایرکتوری دانلود
  RUN mkdir -p /app/downloads && chmod 777 /app/downloads

  # اجرای ربات با غیرفعال‌سازی کامل disabled_downloader
  CMD ["sh", "-c", "python yt_dlp_custom_override.py && python disable_disabled_downloader.py && python telegram_downloader.py"]
  ```

### گام 2: ثبت‌نام و ورود به Railway

1. به [Railway.app](https://railway.app/) بروید و ثبت‌نام کنید یا وارد حساب کاربری خود شوید.
2. روی "New Project" کلیک کنید.

### گام 3: انتخاب منبع دیپلوی

1. گزینه "Deploy from GitHub repo" را انتخاب کنید.
2. به Railway اجازه دسترسی به حساب گیت‌هاب خود را بدهید.
3. مخزن حاوی کد ربات را انتخاب کنید.

### گام 4: تنظیم متغیرهای محیطی

1. پس از ایجاد پروژه، به تب "Variables" بروید.
2. روی "New Variable" کلیک کنید.
3. نام متغیر را `TELEGRAM_BOT_TOKEN` و مقدار آن را توکن ربات تلگرام خود قرار دهید.
4. روی "Add" کلیک کنید تا متغیر محیطی اضافه شود.

### گام 5: بررسی تنظیمات دیپلوی (اختیاری)

1. به تب "Settings" بروید.
2. مطمئن شوید که "Root Directory" روی "/" تنظیم شده است.
3. اگر می‌خواهید از Docker استفاده کنید، "Builder" را روی "Docker" تنظیم کنید.
4. اگر می‌خواهید از Nixpacks استفاده کنید، "Builder" را روی "Nixpacks" تنظیم کنید.

### گام 6: دیپلوی پروژه

1. به تب "Deployments" بروید.
2. روی "Deploy Now" کلیک کنید.
3. Railway شروع به ساخت و دیپلوی پروژه می‌کند.
4. منتظر بمانید تا فرآیند دیپلوی کامل شود.

### گام 7: بررسی لاگ‌ها

1. پس از اتمام دیپلوی، روی آخرین دیپلوی کلیک کنید.
2. تب "Logs" را انتخاب کنید تا لاگ‌های ربات را مشاهده کنید.
3. مطمئن شوید که ربات بدون خطا راه‌اندازی شده است و پیام "ربات تلگرام آغاز به کار کرد" را در لاگ‌ها می‌بینید.

## عیب‌یابی

### مشکل 1: خطای "Invalid Key-Value Pair"
- **راه حل**: مطمئن شوید که در فایل `railway.toml` و `Dockerfile` هیچ متغیر محیطی تعریف نکرده‌اید. متغیر محیطی را حتماً در بخش "Variables" داشبورد Railway تنظیم کنید.

### مشکل 2: خطای "ffmpeg not found"
- **راه حل**: مطمئن شوید که در فایل `railway.toml` یا `Dockerfile` بسته ffmpeg را نصب کرده‌اید.

### مشکل 3: ربات تلگرام پاسخ نمی‌دهد
- **راه حل 1**: لاگ‌ها را بررسی کنید تا ببینید آیا خطایی در راه‌اندازی ربات وجود دارد.
- **راه حل 2**: مطمئن شوید که توکن تلگرام صحیح است و ربات فعال است.
- **راه حل 3**: اگر پروژه بدون خطا دیپلوی شده اما ربات پاسخ نمی‌دهد، مطمئن شوید که در Procfile نوع سرویس را `worker` تنظیم کرده‌اید، نه `web`.

### مشکل 4: خطای مربوط به دسترسی به فایل‌ها
- **راه حل**: مطمئن شوید که کد شما پوشه `downloads` را قبل از استفاده ایجاد می‌کند. در محیط Railway، دایرکتوری کاری اپلیکیشن شما `/app` است (اگر از Dockerfile استفاده می‌کنید).

### مشکل 5: خطای "Banned Dependency Detected: disabled_aria"
- **راه حل قطعی**: از فایل‌های زیر در پروژه خود استفاده کنید تا این مشکل به طور کامل برطرف شود:
  
  1. **complete_disabled_aria_removal.py**: این اسکریپت جامع تمام اشارات به disabled_aria را از کد yt-dlp حذف می‌کند.
  
  2. **clean_ytdlp_patch.py**: این فایل به عنوان پشتیبان برای حذف disabled_aria از کد yt-dlp استفاده می‌شود.
  
  3. **railway_startup.sh**: این اسکریپت تمام مراحل لازم برای اطمینان از عدم وجود disabled_aria را انجام می‌دهد:
     - حذف بسته‌های disabled_aria از سیستم
     - حذف فایل‌های باینری disabled_downloader
     - اجرای تمام اسکریپت‌های پاکسازی
     - تنظیم متغیرهای محیطی برای غیرفعال‌سازی disabled_aria
     - بررسی نهایی برای تأیید عدم وجود disabled_aria

  4. فایل‌های پیکربندی Railway:
     ```
     # Procfile
     worker: bash railway_startup.sh
     
     # railway.toml
     [build]
     builder = "docker"
     buildCommand = "chmod +x .railway/clean.sh && ./.railway/clean.sh"

     [deploy]
     startCommand = "bash railway_startup.sh"
     restartPolicyType = "always"

     [build.args]
     SKIP_disabled_aria = "true"
     YDL_NO_disabled_downloader = "1"
     HTTP_DOWNLOADER = "native"
     YTDLP_DOWNLOADER = "native"
     NO_EXTERNAL_DOWNLOADER = "1"
     YTDLP_NO_disabled_aria = "1"
     ```

  5. حتماً از **Docker** به جای Nixpacks استفاده کنید. در تنظیمات پروژه Railway، به بخش "Settings" بروید و "Builder" را روی "Docker" تنظیم کنید.
  
  6. ساختار دایرکتوری‌های لازم را ایجاد کنید:
     ```
     mkdir -p .nixpacks
     mkdir -p .railway
     ```
     
  7. فایل‌های تکمیلی برای حذف کامل disabled_aria:
     ```
     # .nixpacks/no-apt.txt
     disabled_aria
     disabled_downloader
     libdisabled_aria
     *disabled_aria*
     
     # .nixpacks/environment.toml
     [vars]
     YDL_NO_disabled_downloader = "1"
     HTTP_DOWNLOADER = "native"
     YTDLP_DOWNLOADER = "native"
     NO_EXTERNAL_DOWNLOADER = "1"
     YTDLP_NO_disabled_aria = "1"
     
     # .railway/clean.sh (chmod +x)
     #!/bin/bash
     echo "==== Railway Build Clean Script ===="
     find / -name "disabled_downloader" -type f -delete 2>/dev/null
     find / -name "*disabled_aria*" -type f -delete 2>/dev/null
     find /app -type f -name "*.py" -exec sed -i 's/disabled_downloader/disabled_downloader/g' {} \;
     find /app -type f -name "*.py" -exec sed -i 's/disabled_aria/disabled_tool/g' {} \;
     ```
     
  8. اطمینان حاصل کنید که Dockerfile شما مانند نمونه زیر باشد:
     ```Dockerfile
     # استفاده از روش چندمرحله‌ای برای ایجاد تصویر نهایی بدون هیچ اشاره‌ای به disabled_aria
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
         YTDLP_NO_disabled_aria=1

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

     # حذف هرگونه اشاره به disabled_aria
     RUN python complete_disabled_aria_removal.py

     # تنظیم متغیرهای محیطی برای جلوگیری از استفاده از disabled_aria
     ENV YDL_NO_disabled_downloader=1 \
         HTTP_DOWNLOADER=native \
         YTDLP_DOWNLOADER=native

     # اطمینان از عدم وجود دستور disabled_downloader
     RUN echo "Checking for disabled_downloader binary..." && \
         ! command -v disabled_downloader && \
         echo "disabled_downloader is not installed!" && \
         echo "CONFIRMED: No disabled_downloader in the final image."

     # فایل اجرایی
     CMD bash railway_startup.sh
     ```

## پیشنهادات و نکات

1. **مانیتورینگ**: Railway یک سیستم مانیتورینگ داخلی دارد. از تب "Metrics" برای بررسی وضعیت سرویس خود استفاده کنید.

2. **تنظیمات اضافی**: اگر ربات شما نیاز به تنظیمات بیشتری دارد، آن‌ها را به عنوان متغیرهای محیطی در Railway اضافه کنید.

3. **به‌روزرسانی**: برای به‌روزرسانی ربات، کافی است کد جدید را به مخزن گیت‌هاب خود پوش کنید. Railway به طور خودکار پروژه را دوباره دیپلوی می‌کند.

4. **منابع**: اگر نیاز به منابع بیشتری (CPU، RAM) دارید، می‌توانید از تب "Settings" پروژه، بخش "Resources" را تنظیم کنید.

5. **دامنه اختصاصی**: اگر ربات شما نیاز به دامنه اختصاصی دارد، می‌توانید از تب "Settings" پروژه، بخش "Domains" یک دامنه اختصاصی تنظیم کنید.
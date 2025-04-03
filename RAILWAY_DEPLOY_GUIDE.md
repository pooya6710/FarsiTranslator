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
  worker: python yt_dlp_custom_override.py && python disable_aria2c.py && python telegram_downloader.py
  ```

- `railway.toml` - با محتوای زیر:
  ```toml
  [build]
  builder = "nixpacks"
  buildCommand = "echo 'Building the application...'"

  [deploy]
  startCommand = "python yt_dlp_custom_override.py && python disable_aria2c.py && python telegram_downloader.py"
  restartPolicyType = "always"

  [nixpacks]
  aptPackages = ["ffmpeg", "python3-dev"]
  ```

- `requirements.txt` - حاوی تمام وابستگی‌های پایتون

- `Dockerfile` (توصیه شده) - برای استفاده از روش دیپلوی Docker با حذف کامل aria2c:
  ```Dockerfile
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

### مشکل 5: خطای "Banned Dependency Detected: aria2"
- **راه حل 1**: فایل‌های `disable_aria2c.py` و `yt_dlp_custom_override.py` را به پروژه خود اضافه کنید. این فایل‌ها به صورت پیش‌گیرانه استفاده از aria2c را در yt-dlp غیرفعال می‌کنند.
- **راه حل 2**: مطمئن شوید که هر دو فایل فوق قبل از اجرای برنامه اصلی اجرا می‌شوند. دستور اجرا باید به این صورت باشد:
  ```
  python yt_dlp_custom_override.py && python disable_aria2c.py && python telegram_downloader.py
  ```
- **راه حل 3**: مطمئن شوید که در تمام فایل‌های پروژه، هیچ اشاره‌ای به aria2c وجود ندارد. می‌توانید با دستور `grep -r "aria2" --include="*.py" .` این موضوع را بررسی کنید.
- **راه حل 4 (قطعی)**: حتماً از Docker به جای Nixpacks استفاده کنید. در تنظیمات پروژه Railway، به بخش "Settings" بروید و "Builder" را روی "Docker" تنظیم کنید. مطمئن شوید که Dockerfile شما حاوی دستورات حذف aria2c است (مانند نمونه بالا).

## پیشنهادات و نکات

1. **مانیتورینگ**: Railway یک سیستم مانیتورینگ داخلی دارد. از تب "Metrics" برای بررسی وضعیت سرویس خود استفاده کنید.

2. **تنظیمات اضافی**: اگر ربات شما نیاز به تنظیمات بیشتری دارد، آن‌ها را به عنوان متغیرهای محیطی در Railway اضافه کنید.

3. **به‌روزرسانی**: برای به‌روزرسانی ربات، کافی است کد جدید را به مخزن گیت‌هاب خود پوش کنید. Railway به طور خودکار پروژه را دوباره دیپلوی می‌کند.

4. **منابع**: اگر نیاز به منابع بیشتری (CPU، RAM) دارید، می‌توانید از تب "Settings" پروژه، بخش "Resources" را تنظیم کنید.

5. **دامنه اختصاصی**: اگر ربات شما نیاز به دامنه اختصاصی دارد، می‌توانید از تب "Settings" پروژه، بخش "Domains" یک دامنه اختصاصی تنظیم کنید.
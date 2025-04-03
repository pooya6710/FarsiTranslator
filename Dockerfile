FROM python:3.10-slim

# نصب بسته‌های مورد نیاز
RUN apt-get update && apt-get install -y ffmpeg python3-dev

# تنظیم دایرکتوری کاری
WORKDIR /app

# کپی فایل‌های پروژه
COPY . .

# نصب وابستگی‌های پایتون
RUN pip install --no-cache-dir -r requirements.txt

# در محیط Railway، متغیرهای محیطی از داشبورد Railway تنظیم می‌شوند
# و به صورت خودکار در دسترس برنامه قرار می‌گیرند

# اجرای ربات با غیرفعال‌سازی aria2c
CMD ["sh", "-c", "python disable_aria2c.py && python telegram_downloader.py"]
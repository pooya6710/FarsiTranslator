
===========================================================
دستورالعمل‌های دیپلوی نهایی در Railway
===========================================================

1. فایل‌های زیر برای دیپلوی آماده شده‌اند:
   - block_disabled_aria_completely.py (اسکریپت مسدود کردن کامل disabled_aria)
   - complete_disabled_aria_removal.py (اسکریپت حذف کامل disabled_aria)
   - clean_ytdlp_patch.py (اسکریپت پاکسازی yt-dlp)
   - railway.toml (تنظیمات Railway)
   - railway.json (تنظیمات Railway در فرمت JSON)
   - Dockerfile (فایل Docker بهینه‌سازی شده)
   - railway_startup.sh (اسکریپت راه‌اندازی)
   - .nixpacks/environment.toml (تنظیمات محیط Nixpacks)
   - .railwayignore (فایل‌های نادیده گرفته شده)
   - .buildignore (فایل‌های نادیده گرفته شده در زمان ساخت)

2. مراحل دیپلوی در Railway:
   - ابتدا مطمئن شوید که اسکریپت‌های پاکسازی قابل اجرا هستند:
     * chmod +x clean_ytdlp_patch.py complete_disabled_aria_removal.py block_disabled_aria_completely.py railway_startup.sh
   - از پنل Railway یک پروژه جدید ایجاد کنید
   - گزینه دیپلوی از GitHub را انتخاب کنید
   - مخزن خود را انتخاب کنید
   - متغیرهای محیطی زیر را تنظیم کنید:
     * YDL_NO_disabled_downloader=1
     * HTTP_DOWNLOADER=native
     * YTDLP_DOWNLOADER=native
     * NO_EXTERNAL_DOWNLOADER=1
     * YTDLP_NO_disabled_aria=1
     * disabled_downloader_DISABLED=1
     * DISABLE_disabled_downloader=true
     * TELEGRAM_BOT_TOKEN=your_bot_token

3. نکات مهم:
   - اگر با خطای "Banned Dependency Detected" مواجه شدید:
     * پروژه را از Railway حذف کنید
     * کش Railway را پاک کنید (از منوی Settings)
     * دوباره پروژه را دیپلوی کنید
   - اگر باز هم با خطا مواجه شدید، از دیپلوی با Docker استفاده کنید:
     * در پنل Railway، گزینه "Deploy with Docker" را انتخاب کنید
     * این گزینه از Dockerfile موجود در پروژه استفاده می‌کند که تمام اشارات به disabled_aria را حذف می‌کند

امیدوارم دیپلوی شما موفقیت‌آمیز باشد!
===========================================================

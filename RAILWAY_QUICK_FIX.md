# راهنمای سریع حل مشکل Railway

با توجه به خطای `build.builder: Invalid input` که در Railway دریافت کردید، موارد زیر را چک کنید:

## گام‌های حل مشکل

### 1. استفاده از تنظیمات ساده railway.toml
فایل `railway.toml` باید بسیار ساده و به شکل زیر باشد:
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "bash railway_startup.sh"
restartPolicyType = "always"

[nixpacks]
aptPackages = ["ffmpeg", "python3-dev"]
dontInstallRecommends = true

[env]
YDL_NO_disabled_downloader = "1"
HTTP_DOWNLOADER = "native"
YTDLP_DOWNLOADER = "native"
NO_EXTERNAL_DOWNLOADER = "1"
YTDLP_NO_disabled_aria = "1"
```

### 2. استفاده از railway.json به جای railway.toml
در برخی موارد، استفاده از `railway.json` به جای `railway.toml` برای تنظیمات کارساز است:
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "bash railway_startup.sh",
    "restartPolicyType": "ALWAYS"
  }
}
```

### 3. تنظیم پروژه از طریق رابط کاربری Railway
گاهی اوقات تنظیم پروژه از طریق رابط کاربری Railway بهتر از فایل کانفیگ عمل می‌کند:

1. به بخش "Settings" پروژه Railway بروید.
2. در بخش "Deploy" این تنظیمات را قرار دهید:
   - Root Directory: `/`
   - Builder: `Nixpacks`
   - Start Command: `bash railway_startup.sh`
   - Restart Policy: `Always`

3. در بخش "Variables" متغیرهای محیطی را اضافه کنید:
   - `TELEGRAM_BOT_TOKEN`: توکن ربات تلگرام شما
   - `YDL_NO_disabled_downloader`: `1`
   - `HTTP_DOWNLOADER`: `native`
   - `YTDLP_DOWNLOADER`: `native`
   - `NO_EXTERNAL_DOWNLOADER`: `1`
   - `YTDLP_NO_disabled_aria`: `1`

### 4. تغییر نوع سرویس
حتماً در تنظیمات Railway نوع سرویس را از `Web Service` به `Worker` تغییر دهید.

## تست لوکال
قبل از دیپلوی در Railway، می‌توانید اسکریپت‌ها را به صورت لوکال تست کنید:

```bash
# تست اسکریپت حذف disabled_aria
python complete_disabled_aria_removal.py

# تست اسکریپت راه‌اندازی
bash railway_startup.sh
```

## مشکلات رایج
1. **خطای Banned Dependency**: مطمئن شوید همه اشارات به disabled_aria با روش‌های ذکر شده در `complete_disabled_aria_removal.py` حذف شده‌اند.
2. **خطای پارس کردن فایل تنظیمات**: فایل‌های `railway.toml` و `railway.json` را با فرمت‌های ساده بالا جایگزین کنید.
3. **مشکل Procfile**: مطمئن شوید Procfile دقیقاً به این شکل است:
   ```
   worker: bash railway_startup.sh
   ```
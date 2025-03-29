
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
اسکریپت استخراج فایل‌ها از telegram_bot_complete.py
"""

import os
import re
import logging

# تنظیم لاگینگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_files():
    """استخراج فایل‌ها از telegram_bot_complete.py"""
    try:
        # خواندن محتوای فایل اصلی
        with open('telegram_bot_complete.py', 'r', encoding='utf-8') as f:
            content = f.read()

        # الگوی فایل‌ها در کامنت‌ها
        file_pattern = re.compile(r'path: ([^\n]+)\n\n```[^\n]*\n(.*?)```', re.DOTALL)
        matches = file_pattern.finditer(content)

        files_created = []
        
        for match in matches:
            file_path = match.group(1).strip()
            file_content = match.group(2)

            # اطمینان از وجود دایرکتوری
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # نوشتن محتوا در فایل
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(file_content)

            logger.info(f"فایل ایجاد شد: {file_path}")
            files_created.append(file_path)

        if files_created:
            logger.info("\nفایل‌های استخراج شده:")
            for file in files_created:
                logger.info(f"- {file}")
        else:
            logger.warning("هیچ فایلی برای استخراج پیدا نشد!")

    except Exception as e:
        logger.error(f"خطا در استخراج فایل‌ها: {str(e)}")

if __name__ == "__main__":
    extract_files()

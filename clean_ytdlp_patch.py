"""
پچ کامل برای yt-dlp: حذف تمام اشارات به aria2

این اسکریپت یک نسخه تمیز از yt-dlp ایجاد می‌کند که هیچ اشاره‌ای به aria2 ندارد.
"""

import os
import sys
import shutil
import tempfile
import logging
import importlib
from pathlib import Path

# تنظیم لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

def find_site_packages():
    """پیدا کردن مسیر site-packages پایتون"""
    # اول در مسیرهای استاندارد جستجو کنیم
    for path in sys.path:
        if path.endswith('site-packages') or path.endswith('pythonlibs/lib/python3.11/site-packages'):
            return path
            
    # اگر پیدا نشد، در مسیرهای خاص Replit بررسی کنیم
    replit_paths = [
        '/home/runner/workspace/.pythonlibs/lib/python3.11/site-packages',
        '/nix/store/ii5bys31iv4q48wbsxp4g8fdnlcw5y5f-python3-3.11.0/lib/python3.11/site-packages',
        '/home/runner/.local/lib/python3.11/site-packages'
    ]
    
    for path in replit_paths:
        if os.path.exists(path):
            return path
            
    return None

def find_ytdlp_path():
    """پیدا کردن مسیر نصب yt-dlp"""
    # روش 1: از مسیر site-packages پیدا کردن
    site_packages = find_site_packages()
    if site_packages:
        ytdlp_path = os.path.join(site_packages, 'yt_dlp')
        if os.path.exists(ytdlp_path):
            return ytdlp_path
            
    # روش 2: با استفاده از سیستم ماژول
    try:
        import yt_dlp
        module_path = os.path.dirname(yt_dlp.__file__)
        if os.path.exists(module_path):
            logger.info(f"مسیر yt-dlp با استفاده از سیستم ماژول پیدا شد: {module_path}")
            return module_path
    except ImportError:
        pass
    
    # روش 3: از مسیرهای خاص Replit بررسی کنیم
    replit_ytdlp_paths = [
        '/home/runner/workspace/.pythonlibs/lib/python3.11/site-packages/yt_dlp',
        '/nix/store/ii5bys31iv4q48wbsxp4g8fdnlcw5y5f-python3-3.11.0/lib/python3.11/site-packages/yt_dlp',
        '/home/runner/.local/lib/python3.11/site-packages/yt_dlp'
    ]
    
    for path in replit_ytdlp_paths:
        if os.path.exists(path):
            logger.info(f"مسیر yt-dlp در مسیر خاص Replit پیدا شد: {path}")
            return path
            
    logger.error("مسیر yt-dlp پیدا نشد")
    return None

def create_clean_ytdlp():
    """ایجاد یک نسخه تمیز از yt-dlp بدون اشاره به aria2"""
    ytdlp_path = find_ytdlp_path()
    if not ytdlp_path:
        logger.error("مسیر yt-dlp یافت نشد.")
        return False

    # مسیر فایلهایی که باید اصلاح شوند
    paths_to_patch = [
        os.path.join(ytdlp_path, 'downloader', 'external.py'),
        os.path.join(ytdlp_path, 'options.py'),
    ]
    
    # نسخه پشتیبان ایجاد کنید
    backup_dir = tempfile.mkdtemp(prefix='ytdlp_backup_')
    for file_path in paths_to_patch:
        if os.path.exists(file_path):
            backup_path = os.path.join(backup_dir, os.path.relpath(file_path, ytdlp_path))
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            shutil.copy2(file_path, backup_path)
            logger.info(f"نسخه پشتیبان از {file_path} در {backup_path} ایجاد شد.")
    
    # 1. پچ کردن external.py: حذف کامل دانلودر aria2c
    external_file = os.path.join(ytdlp_path, 'downloader', 'external.py')
    if os.path.exists(external_file):
        with open(external_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # روش جایگزینی کامل: فایل را با نسخه بدون aria2c جایگزین کنیم
        new_content = """
# coding: utf-8
from __future__ import unicode_literals

import os.path
import re
import subprocess
import sys
import time

from .common import FileDownloader
from ..utils import (
    check_executable,
    encodeFilename,
    encodeArgument,
)


class ExternalFD(FileDownloader):
    \"\"\"Base class for external downloader \"\"\"

    def real_download(self, filename, info_dict):
        self.report_destination(filename)
        tmpfilename = self.temp_name(filename)

        retval = self._call_downloader(tmpfilename, info_dict)
        if retval == 0:
            self.try_rename(tmpfilename, filename)
            return True
        else:
            self.to_screen('\\nERROR: External downloader exited with error code %s' % retval)
            return False

    def _call_downloader(self, tmpfilename, info_dict):
        \"\"\"Either overwrite this or implement _make_cmd\"\"\"
        cmd = [encodeArgument(a) for a in self._make_cmd(tmpfilename, info_dict)]

        self._debug_cmd(cmd)

        p = subprocess.Popen(
            cmd, stderr=subprocess.PIPE)
        _, stderr = p.communicate_or_kill()
        if p.returncode != 0:
            self._debug_cmd_stderr(cmd, stderr)
        return p.returncode


class CurlFD(ExternalFD):
    AVAILABLE_OPT = '-V'

    def _make_cmd(self, tmpfilename, info_dict):
        cmd = [
            'curl', '--location', '--silent', '--show-error', '--output', tmpfilename]
        for key, val in info_dict.get('http_headers', {}).items():
            cmd += ['--header', '%s: %s' % (key, val)]

        # If bandwidth is being throttled, tell curl to limit its download
        # rate to avoid going over the limit
        throttled_bandwidth = info_dict.get('throttled_bandwidth')
        if throttled_bandwidth is not None:
            cmd += ['--limit-rate', throttled_bandwidth]

        cmd += [info_dict['url']]
        return cmd


class WgetFD(ExternalFD):
    AVAILABLE_OPT = '--version'

    def _make_cmd(self, tmpfilename, info_dict):
        cmd = [
            'wget', '-O', tmpfilename, '--no-check-certificate', '--no-verbose']
        for key, val in info_dict.get('http_headers', {}).items():
            cmd += ['--header', '%s: %s' % (key, val)]

        # If bandwidth is being throttled, tell wget to limit its download
        # rate to avoid going over the limit. Support for this feature was
        # added in wget 1.16.
        throttled_bandwidth = info_dict.get('throttled_bandwidth')
        if throttled_bandwidth is not None:
            cmd += ['--limit-rate', throttled_bandwidth]

        cmd += [info_dict['url']]
        return cmd


class Aria2AFD(ExternalFD):
    # This class is completely empty to prevent any use of aria2c
    AVAILABLE_OPT = '--version'
    
    def _make_cmd(self, tmpfilename, info_dict):
        # This method will never be called since aria2c is disabled
        raise ValueError("aria2c is disabled")


_BY_NAME = {
    'curl': CurlFD,
    'wget': WgetFD,
}
# Do not include aria2c in the available downloaders
"""
        
        # نوشتن فایل اصلاح شده
        with open(external_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        logger.info(f"فایل {external_file} با موفقیت پچ شد.")
    
    # 2. پچ کردن options.py: حذف کامل اشارات به aria2c
    options_file = os.path.join(ytdlp_path, 'options.py')
    if os.path.exists(options_file):
        with open(options_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # روش جایگزینی کامل برای _EXTERNAL_DOWNLOADERS
        if '_EXTERNAL_DOWNLOADERS =' in content:
            new_downloaders = """
    _EXTERNAL_DOWNLOADERS = {
        'native': [''],
        'curl': ['curl'],
        'wget': ['wget'],
        'ffmpeg': ['ffmpeg'],
        # aria2c is intentionally removed
    }
"""
            # جایگزینی با الگوی regex
            import re
            content = re.sub(
                r'_EXTERNAL_DOWNLOADERS\s*=\s*\{[^}]*\}',
                new_downloaders.strip(),
                content
            )
            
        # حذف اشارات به aria2c در توضیحات خط فرمان
        content = content.replace("'E.g. --downloader aria2c --downloader \"dash,m3u8:native\" will use '", 
                                "'E.g. --downloader \"dash,m3u8:native\" will use '")
        content = content.replace("'aria2c for http/ftp downloads, and the native downloader for dash/m3u8 downloads '",
                                "'the native downloader for dash/m3u8 downloads '")
        
        # حذف هرگونه منطق استفاده از aria2c
        content = content.replace("cls._EXTERNAL_DOWNLOADERS['aria2c']", 
                                "[]  # aria2c intentionally disabled")
        
        # نوشتن فایل اصلاح شده
        with open(options_file, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"فایل {options_file} با موفقیت پچ شد.")
    
    logger.info("yt-dlp با موفقیت پچ شد تا تمام اشارات به aria2 حذف شوند.")
    return True

def reload_ytdlp():
    """بازخوانی ماژول yt-dlp برای اعمال تغییرات"""
    try:
        if 'yt_dlp' in sys.modules:
            importlib.reload(sys.modules['yt_dlp'])
        logger.info("ماژول yt-dlp با موفقیت بازخوانی شد.")
        return True
    except Exception as e:
        logger.error(f"خطا در بازخوانی ماژول yt-dlp: {e}")
        return False

def cleanup_yt_dlp_temp_files():
    """پاکسازی فایل‌های موقت که ممکن است حاوی اشاره به aria2 باشند"""
    try:
        temp_dir = tempfile.gettempdir()
        count = 0
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if 'ytdl' in file.lower() or 'aria2' in file.lower():
                    try:
                        os.remove(os.path.join(root, file))
                        count += 1
                    except:
                        pass
        logger.info(f"{count} فایل موقت مرتبط با yt-dlp پاکسازی شدند.")
        return True
    except Exception as e:
        logger.error(f"خطا در پاکسازی فایل‌های موقت: {e}")
        return False

def clean_ytdlp_installation():
    """تابع اصلی برای اجرای پچ"""
    logger.info("در حال آغاز فرآیند پچ کردن yt-dlp...")
    
    # 1. ایجاد نسخه تمیز از yt-dlp
    if not create_clean_ytdlp():
        logger.error("خطا در ایجاد نسخه تمیز از yt-dlp.")
        return False
    
    # 2. بازخوانی ماژول yt-dlp
    if not reload_ytdlp():
        logger.error("خطا در بازخوانی ماژول yt-dlp.")
        return False
    
    # 3. پاکسازی فایل‌های موقت
    if not cleanup_yt_dlp_temp_files():
        logger.warning("هشدار: پاکسازی فایل‌های موقت ناموفق بود.")
    
    logger.info("فرآیند پچ کردن yt-dlp با موفقیت انجام شد!")
    return True

def cleanup_temp_files():
    """تابع خارجی برای پاکسازی فایل‌های موقت"""
    return cleanup_yt_dlp_temp_files()

if __name__ == "__main__":
    success = clean_ytdlp_installation()
    sys.exit(0 if success else 1)
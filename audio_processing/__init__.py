"""
ماژول پردازش صدا برای ربات تلگرام

این ماژول شامل توابع استخراج صدا و کار با فایل‌های صوتی است.
"""

from audio_processing import extract_audio, is_video_file, is_audio_file

__all__ = ['extract_audio', 'is_video_file', 'is_audio_file']
"""
پردازشگر موازی برای افزایش سرعت دانلود و پردازش

این ماژول ابزارهای پیشرفته برای پردازش موازی و دانلود همزمان چند فایل ارائه می‌دهد.
"""

import os
import asyncio
import logging
import time
import multiprocessing
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import Dict, List, Tuple, Callable, Any, Optional, Union
from dataclasses import dataclass

# تنظیم لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# کلاس داده وظیفه
@dataclass
class Task:
    """کلاس داده وظیفه"""
    id: str               # شناسه یکتای وظیفه
    func: Callable        # تابع برای اجرا
    args: Tuple = ()      # آرگومان‌های تابع
    kwargs: Dict = None   # پارامترهای کلیدی تابع
    timeout: int = 1800   # حداکثر زمان اجرا (ثانیه)
    priority: int = 1     # اولویت (بالاتر = اولویت بیشتر)
    max_retries: int = 3  # حداکثر تلاش‌های مجدد
    retry_delay: int = 10 # تأخیر بین تلاش‌های مجدد (ثانیه)

# کلاس نتیجه وظیفه
@dataclass
class TaskResult:
    """کلاس نتیجه وظیفه"""
    task_id: str              # شناسه وظیفه
    success: bool = False     # آیا وظیفه با موفقیت انجام شده است؟
    result: Any = None        # نتیجه اجرای وظیفه
    error: Exception = None   # خطای رخ داده
    start_time: float = None  # زمان شروع اجرا
    end_time: float = None    # زمان پایان اجرا
    retries: int = 0          # تعداد تلاش‌های انجام شده
    
    @property
    def execution_time(self) -> float:
        """مدت زمان اجرا به ثانیه"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0

# کلاس مدیریت استخر وظایف
class TaskPoolManager:
    """کلاس مدیریت استخر وظایف"""
    
    def __init__(self, 
                max_workers: int = None, 
                use_processes: bool = False, 
                max_queue_size: int = 100):
        """
        مقداردهی اولیه کلاس
        
        Args:
            max_workers: حداکثر تعداد ترد‌ها یا پروسس‌ها
            use_processes: استفاده از پروسس‌ها به جای ترد‌ها
            max_queue_size: حداکثر اندازه صف وظایف
        """
        # تعیین تعداد ترد‌ها/پروسس‌ها بر اساس CPU
        if max_workers is None:
            max_workers = min(multiprocessing.cpu_count() + 4, 16)
            
        self.max_workers = max_workers
        self.use_processes = use_processes
        self.max_queue_size = max_queue_size
        
        # ایجاد استخر مناسب
        if use_processes:
            self.executor = ProcessPoolExecutor(max_workers=max_workers)
        else:
            self.executor = ThreadPoolExecutor(max_workers=max_workers)
            
        # صف وظایف
        self.task_queue = asyncio.Queue(maxsize=max_queue_size)
        
        # ذخیره نتایج وظایف
        self.results = {}
        
        # وضعیت اجرا
        self.running = False
        self.workers = []
        self.active_tasks = set()
        
        # قفل‌های همگام‌سازی
        self.lock = threading.Lock()
        
        logger.info(f"مدیریت استخر وظایف ایجاد شد: {max_workers} {'پروسس' if use_processes else 'ترد'}")
    
    async def add_task(self, task: Task) -> str:
        """
        افزودن وظیفه به صف
        
        Args:
            task: وظیفه برای افزودن
            
        Returns:
            شناسه وظیفه
        """
        if not task.kwargs:
            task.kwargs = {}
            
        await self.task_queue.put(task)
        logger.debug(f"وظیفه {task.id} به صف اضافه شد (اندازه صف: {self.task_queue.qsize()})")
        return task.id
    
    async def add_tasks(self, tasks: List[Task]) -> List[str]:
        """
        افزودن چندین وظیفه به صف
        
        Args:
            tasks: لیست وظایف برای افزودن
            
        Returns:
            لیست شناسه‌های وظایف
        """
        task_ids = []
        for task in tasks:
            task_id = await self.add_task(task)
            task_ids.append(task_id)
        return task_ids
    
    async def get_result(self, task_id: str, wait: bool = True) -> Optional[TaskResult]:
        """
        دریافت نتیجه وظیفه
        
        Args:
            task_id: شناسه وظیفه
            wait: آیا منتظر تکمیل وظیفه بماند؟
            
        Returns:
            نتیجه وظیفه یا None در صورت عدم وجود
        """
        # بررسی وجود نتیجه
        if task_id in self.results:
            return self.results[task_id]
            
        if not wait:
            return None
            
        # انتظار برای تکمیل وظیفه
        while task_id not in self.results and task_id in self.active_tasks:
            await asyncio.sleep(0.5)
            
        return self.results.get(task_id)
    
    async def get_results(self, task_ids: List[str], wait: bool = True) -> Dict[str, TaskResult]:
        """
        دریافت نتایج چندین وظیفه
        
        Args:
            task_ids: لیست شناسه‌های وظایف
            wait: آیا منتظر تکمیل وظایف بماند؟
            
        Returns:
            دیکشنری از نتایج وظایف
        """
        results = {}
        for task_id in task_ids:
            result = await self.get_result(task_id, wait)
            if result:
                results[task_id] = result
        return results
    
    async def _worker(self):
        """کارگر پردازش وظایف"""
        while self.running:
            try:
                # دریافت وظیفه از صف
                task = await self.task_queue.get()
                
                with self.lock:
                    self.active_tasks.add(task.id)
                
                # ایجاد شیء نتیجه
                result = TaskResult(task_id=task.id)
                result.start_time = time.time()
                
                # اجرای وظیفه با تلاش مجدد
                for retry in range(task.max_retries):
                    result.retries = retry + 1
                    
                    try:
                        # اجرای وظیفه در استخر
                        loop = asyncio.get_event_loop()
                        future = loop.run_in_executor(
                            self.executor,
                            task.func,
                            *task.args,
                            **task.kwargs
                        )
                        
                        # اجرا با محدودیت زمانی
                        task_result = await asyncio.wait_for(future, timeout=task.timeout)
                        
                        # ذخیره نتیجه موفق
                        result.success = True
                        result.result = task_result
                        break
                    except asyncio.TimeoutError:
                        result.error = asyncio.TimeoutError(f"وظیفه {task.id} بیش از {task.timeout} ثانیه طول کشید")
                        logger.warning(f"وظیفه {task.id} به دلیل محدودیت زمانی متوقف شد (تلاش {retry+1}/{task.max_retries})")
                    except Exception as e:
                        result.error = e
                        logger.warning(f"خطا در اجرای وظیفه {task.id}: {e} (تلاش {retry+1}/{task.max_retries})")
                    
                    # تأخیر قبل از تلاش مجدد
                    if retry < task.max_retries - 1:
                        await asyncio.sleep(task.retry_delay)
                
                # ثبت زمان پایان
                result.end_time = time.time()
                
                # ذخیره نتیجه
                with self.lock:
                    self.results[task.id] = result
                    self.active_tasks.remove(task.id)
                
                # اعلام تکمیل وظیفه به صف
                self.task_queue.task_done()
                
                # گزارش نتیجه
                if result.success:
                    logger.debug(f"وظیفه {task.id} با موفقیت انجام شد (زمان: {result.execution_time:.2f}s)")
                else:
                    logger.warning(f"وظیفه {task.id} ناموفق بود پس از {result.retries} تلاش (خطا: {result.error})")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"خطا در کارگر پردازش وظایف: {e}")
    
    async def start(self):
        """شروع پردازش وظایف"""
        if self.running:
            return
            
        self.running = True
        
        # راه‌اندازی کارگران
        self.workers = [
            asyncio.create_task(self._worker())
            for _ in range(self.max_workers)
        ]
        
        logger.info(f"مدیریت استخر وظایف با {self.max_workers} کارگر شروع به کار کرد")
    
    async def stop(self):
        """توقف پردازش وظایف"""
        if not self.running:
            return
            
        self.running = False
        
        # لغو کارگران
        for worker in self.workers:
            worker.cancel()
            
        # انتظار برای تکمیل
        await asyncio.gather(*self.workers, return_exceptions=True)
        
        # بستن استخر
        self.executor.shutdown(wait=False)
        
        logger.info("مدیریت استخر وظایف متوقف شد")
    
    async def wait_completion(self):
        """انتظار برای تکمیل تمام وظایف"""
        await self.task_queue.join()
        logger.info("تمام وظایف با موفقیت تکمیل شدند")
    
    def clear_results(self, max_age: int = 3600):
        """
        پاکسازی نتایج قدیمی
        
        Args:
            max_age: حداکثر سن نتایج به ثانیه
        """
        now = time.time()
        with self.lock:
            to_remove = []
            for task_id, result in self.results.items():
                if result.end_time and now - result.end_time > max_age:
                    to_remove.append(task_id)
                    
            for task_id in to_remove:
                del self.results[task_id]
                
        logger.debug(f"{len(to_remove)} نتیجه قدیمی پاکسازی شد")

# کلاس مدیریت دانلود موازی
class ParallelDownloadManager:
    """کلاس مدیریت دانلود موازی"""
    
    def __init__(self, 
                max_concurrent_downloads: int = 5, 
                download_dir: str = None):
        """
        مقداردهی اولیه کلاس
        
        Args:
            max_concurrent_downloads: حداکثر تعداد دانلودهای همزمان
            download_dir: مسیر دایرکتوری دانلودها
        """
        self.max_concurrent_downloads = max_concurrent_downloads
        
        if download_dir:
            self.download_dir = download_dir
        else:
            self.download_dir = os.path.join(os.getcwd(), "downloads")
            
        os.makedirs(self.download_dir, exist_ok=True)
        
        # ایجاد مدیریت استخر وظایف
        self.task_pool = TaskPoolManager(max_workers=max_concurrent_downloads)
        
        # ذخیره اطلاعات دانلودها
        self.downloads = {}
        
        # گروه‌بندی دانلودها
        self.batch_downloads = {}
        
        # قفل‌های همگام‌سازی
        self.lock = threading.Lock()
        
        logger.info(f"مدیریت دانلود موازی ایجاد شد: {max_concurrent_downloads} دانلود همزمان")
    
    async def start(self):
        """شروع مدیریت دانلود موازی"""
        await self.task_pool.start()
    
    async def stop(self):
        """توقف مدیریت دانلود موازی"""
        await self.task_pool.stop()
    
    async def add_download(self, 
                          url: str, 
                          download_func: Callable, 
                          options: Dict = None,
                          batch_id: str = None) -> str:
        """
        افزودن دانلود به صف
        
        Args:
            url: آدرس URL برای دانلود
            download_func: تابع دانلود
            options: گزینه‌های دانلود
            batch_id: شناسه دسته (اختیاری)
            
        Returns:
            شناسه دانلود
        """
        if options is None:
            options = {}
            
        # ایجاد شناسه دانلود
        download_id = f"dl_{int(time.time())}_{hash(url) % 10000:04d}"
        
        # ذخیره اطلاعات دانلود
        with self.lock:
            self.downloads[download_id] = {
                'url': url,
                'status': 'pending',
                'options': options,
                'start_time': None,
                'end_time': None,
                'result': None,
                'error': None,
                'file_path': None,
                'batch_id': batch_id
            }
            
            # اضافه کردن به دسته
            if batch_id:
                if batch_id not in self.batch_downloads:
                    self.batch_downloads[batch_id] = {
                        'downloads': [],
                        'status': 'pending',
                        'start_time': time.time(),
                        'end_time': None
                    }
                    
                self.batch_downloads[batch_id]['downloads'].append(download_id)
        
        # ایجاد وظیفه دانلود
        task = Task(
            id=download_id,
            func=download_func,
            args=(url,),
            kwargs=options,
            timeout=3600,  # 1 ساعت
            max_retries=3
        )
        
        # افزودن به صف وظایف
        await self.task_pool.add_task(task)
        
        return download_id
    
    async def add_batch_download(self, 
                               urls: List[str], 
                               download_func: Callable,
                               options: Dict = None) -> str:
        """
        افزودن دسته دانلود به صف
        
        Args:
            urls: لیست آدرس‌های URL برای دانلود
            download_func: تابع دانلود
            options: گزینه‌های دانلود
            
        Returns:
            شناسه دسته
        """
        if options is None:
            options = {}
            
        # ایجاد شناسه دسته
        batch_id = f"batch_{int(time.time())}_{hash(''.join(urls)) % 10000:04d}"
        
        # افزودن هر URL به عنوان یک دانلود
        for url in urls:
            await self.add_download(url, download_func, options, batch_id)
            
        return batch_id
    
    async def get_download_status(self, download_id: str) -> Dict:
        """
        دریافت وضعیت دانلود
        
        Args:
            download_id: شناسه دانلود
            
        Returns:
            دیکشنری وضعیت دانلود
        """
        # بررسی وجود دانلود
        if download_id not in self.downloads:
            return {'status': 'not_found', 'error': 'دانلود یافت نشد'}
            
        # دریافت اطلاعات دانلود
        download_info = self.downloads[download_id].copy()
        
        # بررسی وضعیت
        if download_info['status'] == 'pending':
            # دریافت وضعیت از مدیریت وظایف
            result = await self.task_pool.get_result(download_id, wait=False)
            
            if result:
                # به‌روزرسانی وضعیت
                with self.lock:
                    if result.success:
                        self.downloads[download_id]['status'] = 'completed'
                        self.downloads[download_id]['result'] = result.result
                        self.downloads[download_id]['file_path'] = result.result
                    else:
                        self.downloads[download_id]['status'] = 'failed'
                        self.downloads[download_id]['error'] = str(result.error)
                        
                    self.downloads[download_id]['start_time'] = result.start_time
                    self.downloads[download_id]['end_time'] = result.end_time
                    
                # به‌روزرسانی اطلاعات
                download_info = self.downloads[download_id].copy()
        
        return download_info
    
    async def get_batch_status(self, batch_id: str) -> Dict:
        """
        دریافت وضعیت دسته دانلود
        
        Args:
            batch_id: شناسه دسته
            
        Returns:
            دیکشنری وضعیت دسته
        """
        # بررسی وجود دسته
        if batch_id not in self.batch_downloads:
            return {'status': 'not_found', 'error': 'دسته دانلود یافت نشد'}
            
        # دریافت اطلاعات دسته
        batch_info = self.batch_downloads[batch_id].copy()
        download_ids = batch_info['downloads']
        
        # به‌روزرسانی وضعیت تک تک دانلودها
        statuses = {
            'pending': 0,
            'completed': 0,
            'failed': 0,
            'total': len(download_ids)
        }
        
        download_details = []
        
        for download_id in download_ids:
            download_status = await self.get_download_status(download_id)
            status = download_status['status']
            statuses[status] = statuses.get(status, 0) + 1
            
            download_details.append({
                'id': download_id,
                'url': download_status['url'],
                'status': status,
                'file_path': download_status.get('file_path'),
                'error': download_status.get('error')
            })
            
        # به‌روزرسانی وضعیت دسته
        if statuses['pending'] == 0:
            batch_info['status'] = 'completed'
            batch_info['end_time'] = time.time()
            
            # به‌روزرسانی در دیکشنری اصلی
            with self.lock:
                self.batch_downloads[batch_id]['status'] = 'completed'
                self.batch_downloads[batch_id]['end_time'] = batch_info['end_time']
        
        # افزودن اطلاعات تجمیعی
        batch_info['download_count'] = statuses
        batch_info['downloads'] = download_details
        
        # محاسبه پیشرفت
        if statuses['total'] > 0:
            progress = (statuses['completed'] + statuses['failed']) / statuses['total'] * 100
            batch_info['progress'] = round(progress, 1)
        else:
            batch_info['progress'] = 0
            
        # محاسبه زمان
        if batch_info['start_time'] and batch_info['end_time']:
            batch_info['duration'] = batch_info['end_time'] - batch_info['start_time']
        elif batch_info['start_time']:
            batch_info['duration'] = time.time() - batch_info['start_time']
        else:
            batch_info['duration'] = 0
            
        return batch_info
    
    def clear_completed_downloads(self, max_age: int = 3600):
        """
        پاکسازی دانلودهای تکمیل شده قدیمی
        
        Args:
            max_age: حداکثر سن به ثانیه
        """
        now = time.time()
        
        with self.lock:
            # پاکسازی دانلودهای قدیمی
            to_remove = []
            for download_id, info in self.downloads.items():
                if info['status'] in ['completed', 'failed'] and info['end_time'] and now - info['end_time'] > max_age:
                    to_remove.append(download_id)
                    
            for download_id in to_remove:
                batch_id = self.downloads[download_id].get('batch_id')
                del self.downloads[download_id]
                
                # به‌روزرسانی دسته‌ها
                if batch_id and batch_id in self.batch_downloads:
                    if download_id in self.batch_downloads[batch_id]['downloads']:
                        self.batch_downloads[batch_id]['downloads'].remove(download_id)
                        
                    # حذف دسته اگر خالی است
                    if not self.batch_downloads[batch_id]['downloads']:
                        del self.batch_downloads[batch_id]
                        
        # پاکسازی نتایج وظایف
        self.task_pool.clear_results(max_age)
        
        logger.debug(f"{len(to_remove)} دانلود قدیمی پاکسازی شد")

# توابع کمکی برای استفاده آسان‌تر
async def create_parallel_downloader(max_concurrent: int = 5, download_dir: str = None) -> ParallelDownloadManager:
    """
    ایجاد و راه‌اندازی مدیریت دانلود موازی
    
    Args:
        max_concurrent: حداکثر تعداد دانلودهای همزمان
        download_dir: مسیر دایرکتوری دانلودها
        
    Returns:
        مدیریت دانلود موازی
    """
    downloader = ParallelDownloadManager(max_concurrent, download_dir)
    await downloader.start()
    return downloader

def create_task_from_func(func: Callable, *args, **kwargs) -> Task:
    """
    ایجاد وظیفه از تابع
    
    Args:
        func: تابع برای اجرا
        *args: آرگومان‌های تابع
        **kwargs: پارامترهای کلیدی تابع
        
    Returns:
        وظیفه آماده برای افزودن به صف
    """
    task_id = f"task_{int(time.time())}_{hash(func.__name__)%10000:04d}"
    return Task(id=task_id, func=func, args=args, kwargs=kwargs)

# تست و نمونه استفاده
async def test_downloader():
    """تست مدیریت دانلود موازی"""
    # تابع دانلود نمونه
    def download_file(url, quality="720p", output_dir=None):
        print(f"Downloading {url} with quality {quality} to {output_dir}")
        time.sleep(2)  # شبیه‌سازی دانلود
        return f"/path/to/downloaded/{url.split('/')[-1]}"
    
    # ایجاد مدیریت دانلود موازی
    downloader = await create_parallel_downloader(3)
    
    # افزودن چند دانلود
    download_id = await downloader.add_download(
        "https://example.com/video1.mp4",
        download_file,
        {"quality": "1080p"}
    )
    
    # افزودن دسته دانلود
    batch_id = await downloader.add_batch_download(
        [
            "https://example.com/video2.mp4",
            "https://example.com/video3.mp4",
            "https://example.com/video4.mp4"
        ],
        download_file,
        {"quality": "720p"}
    )
    
    # نمایش وضعیت
    print(f"Download ID: {download_id}")
    print(f"Batch ID: {batch_id}")
    
    # انتظار کوتاه
    await asyncio.sleep(1)
    
    # بررسی وضعیت
    status = await downloader.get_download_status(download_id)
    print(f"Download Status: {status}")
    
    batch_status = await downloader.get_batch_status(batch_id)
    print(f"Batch Status: {batch_status}")
    
    # انتظار برای تکمیل
    await asyncio.sleep(5)
    
    # بررسی وضعیت نهایی
    status = await downloader.get_download_status(download_id)
    print(f"Final Download Status: {status}")
    
    batch_status = await downloader.get_batch_status(batch_id)
    print(f"Final Batch Status: {batch_status}")
    
    # توقف مدیریت دانلود
    await downloader.stop()

if __name__ == "__main__":
    # اجرای تست
    asyncio.run(test_downloader())
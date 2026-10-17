# -*- coding: utf-8 -*-

"""
DouyinLiveRecorder 可视化控制台 - 媒体后处理任务队列

合并 / 裁切这类操作虽然多数只要几十秒，但重编码可能要几个小时，
所以不能同步阻塞请求：这里用一条后台线程串行执行任务，
对外提供进度、状态和取消能力，前端轮询 /api/media/jobs 即可。

串行而不是并发，是因为这些任务的瓶颈都在磁盘 I/O，
同时跑多个只会互相拖慢，还容易把机械硬盘拖到卡死。
"""

import collections
import os
import threading
import time
import traceback
import uuid

from media_tools import Cancelled, MediaError  # noqa: F401  (供上层捕获)


class Job:
    """一个后台任务。传给 media_tools 的回调对象。"""

    def __init__(self, kind: str, title: str, payload: dict = None, func=None):
        self.id = uuid.uuid4().hex[:12]
        self.kind = kind
        self.title = title
        self.payload = payload or {}
        self.func = func
        self.output_path = ''           # 任务产出文件，取消时用于清理
        self.status = 'queued'          # queued / running / done / error / cancelled
        self.percent = 0.0
        self.message = ''
        self.error = ''
        self.result = None
        self.created_at = time.time()
        self.started_at = None
        self.finished_at = None
        self.logs = collections.deque(maxlen=60)
        self._cancel = threading.Event()
        self._process = None
        self._lock = threading.RLock()

    # ---------------------------------------------------------- 供任务调用
    def update(self, percent: float = None, message: str = None):
        with self._lock:
            if percent is not None:
                try:
                    self.percent = max(self.percent, min(100.0, float(percent)))
                except (TypeError, ValueError):
                    pass
            if message:
                self.message = message
                self.logs.append(f'[{time.strftime("%H:%M:%S")}] {message}')

    def raise_if_cancelled(self):
        if self._cancel.is_set():
            raise Cancelled()

    def attach_process(self, process):
        """把 ffmpeg 子进程挂上来，取消时直接结束它。"""
        with self._lock:
            self._process = process
        if process is not None and self._cancel.is_set():
            self._kill_process()

    def set_output(self, path: str):
        """登记将要产出的文件，取消时好清理半成品。"""
        with self._lock:
            self.output_path = path or ''

    def _kill_process(self):
        process = self._process
        if process is None:
            return
        try:
            process.terminate()
            try:
                process.wait(timeout=5)
            except Exception:
                process.kill()
        except Exception:
            pass

    def cancel(self) -> bool:
        with self._lock:
            if self.status in ('done', 'error', 'cancelled'):
                return False
            self._cancel.set()
            self.status = 'cancelled'
            self.message = '已请求取消'
            self.finished_at = time.time()
        self._kill_process()
        return True

    # ---------------------------------------------------------- 对外序列化
    def to_dict(self) -> dict:
        with self._lock:
            return {
                'id': self.id,
                'kind': self.kind,
                'title': self.title,
                'status': self.status,
                'running': self.status in ('queued', 'running'),
                'percent': round(self.percent, 1),
                'message': self.message,
                'error': self.error,
                'result': self.result,
                'created_at': self.created_at,
                'started_at': self.started_at,
                'finished_at': self.finished_at,
                'logs': list(self.logs)[-12:],
            }


class MediaJobManager:
    """串行执行媒体任务的后台队列。"""

    def __init__(self, project_root: str, keep: int = 60):
        self.project_root = project_root
        self._jobs = collections.OrderedDict()
        self._keep = keep
        self._queue = collections.deque()
        self._lock = threading.RLock()
        self._wakeup = threading.Condition(self._lock)
        self._worker = threading.Thread(target=self._loop, name='media-jobs', daemon=True)
        self._worker.start()

    # ---------------------------------------------------------- 对外接口
    def start(self, kind: str, title: str, func, payload: dict = None) -> Job:
        job = Job(kind, title, payload, func=func)
        with self._lock:
            self._jobs[job.id] = job
            self._queue.append(job)
            while len(self._jobs) > self._keep:
                oldest_id = next(iter(self._jobs))
                oldest = self._jobs[oldest_id]
                if oldest.status in ('done', 'error', 'cancelled'):
                    self._jobs.pop(oldest_id, None)
                else:
                    break
            self._wakeup.notify_all()
        return job

    def list(self, limit: int = 40) -> list:
        with self._lock:
            jobs = list(self._jobs.values())
        return [job.to_dict() for job in reversed(jobs)][:limit]

    def get(self, job_id: str) -> Job:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job is None:
            return False
        return job.cancel()

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for job in self._jobs.values() if job.status in ('queued', 'running'))

    # ---------------------------------------------------------- 内部
    def _loop(self):
        while True:
            with self._lock:
                while not self._queue:
                    self._wakeup.wait(timeout=5)
                job = self._queue.popleft()
            if job.status == 'cancelled':
                continue
            self._run(job)

    def _run(self, job: Job):
        with job._lock:
            if job.status == 'cancelled':
                return
            job.status = 'running'
            job.started_at = time.time()
            job.message = '开始处理'
        try:
            result = job.func(job)
            with job._lock:
                if job.status != 'cancelled':
                    job.status = 'done'
                    job.percent = 100.0
                    job.result = result
                    job.message = job.message or '完成'
        except Cancelled:
            with job._lock:
                job.status = 'cancelled'
                job.message = '已取消'
                pending = job.output_path
            # 半成品没有价值，顺手删掉，避免用户以为它是完整文件
            if pending and os.path.exists(pending):
                try:
                    os.remove(pending)
                    job.logs.append('已删除未完成的输出文件')
                except OSError:
                    pass
        except MediaError as exc:
            with job._lock:
                job.status = 'error'
                job.error = str(exc)
                job.message = str(exc)
        except Exception as exc:  # noqa: BLE001 - 兜底，别让队列线程死掉
            traceback.print_exc()
            with job._lock:
                job.status = 'error'
                job.error = f'{type(exc).__name__}: {exc}'
                job.message = job.error
        finally:
            with job._lock:
                job.finished_at = time.time()
                job._process = None
            with self._lock:
                self._wakeup.notify_all()

"""内存任务队列：把同步回测请求变成可轮询的异步任务。

要解决的问题：多策略对比 / 组合回测 / 参数网格都是同步阻塞接口，
vn.py 的 load_data 走数据库 IO + GIL，前端一个组合回测 10 标的就是
10 次串行等待，且没有取消机制。

设计约束：
  - 不引入 Redis / Celery——这是单机演示项目，进程内队列足够，
    换来的是零部署成本。
  - 结果只保留一段时间（TTL），过期自动清理，避免内存无限增长。
  - 任务状态/进度/结果都是普通 dict，可直接 JSON 序列化给前端。
"""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

JOB_TTL_SECONDS = 3600        # 结果保留 1 小时
MAX_JOBS = 200                # 进程内最多保留多少个任务记录
MAX_WORKERS = 4


class JobCancelled(Exception):
    """任务协作式取消信号：工作函数在检查点抛出即可提前结束。"""


@dataclass
class Job:
    job_id: str
    kind: str
    status: str = "pending"          # pending / running / done / failed / cancelled
    progress: int = 0                # 0-100
    stage: str = "queued"
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    result: Any = None
    error: str | None = None
    _future: Future | None = field(default=None, repr=False, compare=False)

    def to_dict(self, *, include_result: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "job_id": self.job_id,
            "kind": self.kind,
            "status": self.status,
            "progress": self.progress,
            "stage": self.stage,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "elapsed_ms": int(((self.finished_at or time.time()) - self.created_at) * 1000),
            "error": self.error,
        }
        if include_result and self.status in ("done", "failed"):
            payload["result"] = self.result
            payload["success"] = self.status == "done"
        return payload


class JobManager:
    """线程安全的任务注册表 + 线程池执行器。

    用法：
        manager = JobManager()
        job_id = manager.submit("compare", lambda p: _work(p), progress_hook=...)
        info = manager.get(job_id)
    """

    def __init__(self, max_workers: int = MAX_WORKERS) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="btjob")

    # ---- 生命周期 ----

    def submit(
        self,
        kind: str,
        fn: Callable[[Callable[..., None]], Any],
        total_units: int = 1,
    ) -> str:
        """提交任务。

        fn 会收到 `report(done_units, stage_text)` 与 `cancelled()` 两个回调。
        返回 job_id。
        """
        job_id = uuid.uuid4().hex[:16]
        job = Job(job_id=job_id, kind=kind)
        total = max(1, int(total_units))

        with self._lock:
            self._evict_locked()
            self._jobs[job_id] = job

        done = {"n": 0}

        def report(done_units: int = 0, stage: str | None = None) -> None:
            done["n"] += int(done_units)
            with self._lock:
                if job.status in ("cancelled", "failed"):
                    return
                job.progress = int(min(99, round(done["n"] / total * 100)))
                if stage:
                    job.stage = stage

        def runner() -> None:
            with self._lock:
                if job.status == "cancelled":
                    return
                job.status = "running"
                job.stage = "running"

            def cancelled() -> bool:
                return job.status == "cancelled"

            try:
                result = fn(report, cancelled)
                with self._lock:
                    if job.status == "cancelled":
                        return
                    job.result = result
                    job.progress = 100
                    job.stage = "done"
                    job.status = "done"
                    job.finished_at = time.time()
            except JobCancelled:
                with self._lock:
                    job.status = "cancelled"
                    job.stage = "cancelled"
                    job.finished_at = time.time()
            except Exception as exc:  # noqa: BLE001 - 任务错误统一落库
                with self._lock:
                    job.error = str(exc)
                    job.status = "failed"
                    job.finished_at = time.time()

        job._future = self._pool.submit(runner)
        return job_id

    def get(self, job_id: str, *, include_result: bool = True) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return job.to_dict(include_result=include_result)

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            if job.status in ("done", "failed"):
                return False
            job.status = "cancelled"
            job.stage = "cancelled"
            job.finished_at = time.time()
        fut = job._future
        if fut is not None:
            fut.cancel()
        return True

    def stats(self) -> dict[str, Any]:
        with self._lock:
            running = sum(1 for j in self._jobs.values() if j.status == "running")
            return {
                "total": len(self._jobs),
                "running": running,
                "pending": sum(1 for j in self._jobs.values() if j.status == "pending"),
                "workers": MAX_WORKERS,
            }

    def list(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            items = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
            return [j.to_dict(include_result=False) for j in items[: max(1, min(limit, 100))]]

    # ---- 内部 ----

    def _evict_locked(self) -> None:
        """清理过期/超额任务记录（调用方需持有锁）。"""
        if len(self._jobs) < MAX_JOBS:
            return
        now = time.time()
        expired = [
            jid for jid, j in self._jobs.items()
            if j.status in ("done", "failed", "cancelled")
            and j.finished_at is not None
            and now - j.finished_at > JOB_TTL_SECONDS
        ]
        for jid in expired:
            self._jobs.pop(jid, None)
        if len(self._jobs) < MAX_JOBS:
            return
        # 仍超限：按完成时间从旧到新删除
        finished = sorted(
            (j for j in self._jobs.values() if j.status in ("done", "failed", "cancelled")),
            key=lambda j: j.finished_at or 0,
        )
        for j in finished[: len(self._jobs) - MAX_JOBS // 2]:
            self._jobs.pop(j.job_id, None)

"""异步任务路由：把重活提交到进程内 JobManager，前端轮询进度。

同步接口仍保留在 analytics / research 中（向后兼容），
这里仅提供 job 版本，避免长回测占住一个 HTTP 连接。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from routers import analytics, research

router = APIRouter()


@router.post("/jobs/compare")
def submit_compare_job(body: analytics.CompareRequest):
    def work(report, cancelled):
        return analytics._compare_impl(body, progress=report, cancelled=cancelled)

    job_id = analytics.jobs.submit(
        "compare", work, total_units=max(1, len(body.strategy_ids))
    )
    return {"job_id": job_id, "kind": "compare", "status": "pending"}


@router.post("/jobs/grid")
def submit_grid_job(body: analytics.GridRequest):
    cells = len(body.values) * (len(body.values2) if body.values2 else 1)

    def work(report, cancelled):
        return analytics._grid_impl(body, progress=report, cancelled=cancelled)

    job_id = analytics.jobs.submit("grid", work, total_units=max(1, cells))
    return {"job_id": job_id, "kind": "grid", "status": "pending"}


@router.post("/jobs/portfolio")
def submit_portfolio_job(body: analytics.PortfolioRequest):
    def work(report, cancelled):
        return analytics._portfolio_impl(body, progress=report, cancelled=cancelled)

    job_id = analytics.jobs.submit(
        "portfolio", work, total_units=max(1, len(body.vt_symbols))
    )
    return {"job_id": job_id, "kind": "portfolio", "status": "pending"}


@router.post("/jobs/walk-forward")
def submit_walk_forward_job(body: research.WalkForwardRequest):
    total = max(1, body.n_splits * (len(body.values) + 1))

    def work(report, cancelled):
        return research._walk_forward_impl(body, progress=report, cancelled=cancelled)

    job_id = analytics.jobs.submit("walk-forward", work, total_units=total)
    return {"job_id": job_id, "kind": "walk-forward", "status": "pending"}


@router.get("/jobs")
def list_jobs(limit: int = Query(20, ge=1, le=100)):
    return {"jobs": analytics.jobs.list(limit=limit), "stats": analytics.jobs.stats()}


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    info = analytics.jobs.get(job_id)
    if info is None:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return info


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    ok = analytics.jobs.cancel(job_id)
    if not ok:
        raise HTTPException(status_code=409, detail="任务不存在或已完成，无法取消")
    return {"job_id": job_id, "status": "cancelled"}

"""Server-side paging and aggregate queries for LLM call metadata."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func

from app import db
from app.models.llm import LLMCallLog


def list_logs(user_id: int, params: dict):
    page, per_page = _pagination(params)
    query = _filtered_query(user_id, params)
    return db.paginate(
        query.order_by(LLMCallLog.created_at.desc(), LLMCallLog.id.desc()).statement,
        page=page,
        per_page=per_page,
        error_out=False,
    )


def summary(user_id: int, params: dict) -> dict:
    query = _filtered_query(user_id, params)
    calls, tokens, cost, input_tokens, output_tokens, cached_input_tokens = query.with_entities(
        func.count(LLMCallLog.id),
        func.coalesce(func.sum(LLMCallLog.total_tokens), 0),
        func.coalesce(func.sum(LLMCallLog.cost_amount), 0),
        func.coalesce(func.sum(LLMCallLog.input_tokens), 0),
        func.coalesce(func.sum(LLMCallLog.output_tokens), 0),
        func.coalesce(func.sum(LLMCallLog.cached_input_tokens), 0),
    ).one()
    minutes = _window_minutes(params)
    input_total = int(input_tokens or 0)
    cached_total = int(cached_input_tokens or 0)
    return {
        "total_calls": int(calls or 0),
        "total_tokens": int(tokens or 0),
        "total_cost": float(cost or 0),
        "input_tokens": input_total,
        "output_tokens": int(output_tokens or 0),
        "cached_input_tokens": cached_total,
        "cache_hit_rate": round(cached_total / input_total * 100, 1) if input_total else None,
        "rpm": round(float(calls or 0) / minutes, 2),
        "tpm": round(float(tokens or 0) / minutes, 2),
    }


def analytics(user_id: int, params: dict) -> dict:
    query = _filtered_query(user_id, params)
    overview = summary(user_id, params)
    model_rows = (
        query.with_entities(
            LLMCallLog.model,
            func.count(LLMCallLog.id).label("calls"),
            func.coalesce(func.sum(LLMCallLog.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(LLMCallLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(LLMCallLog.cached_input_tokens), 0).label("cached_input_tokens"),
            func.coalesce(func.sum(LLMCallLog.cost_amount), 0).label("cost"),
        )
        .group_by(LLMCallLog.model)
        .order_by(func.count(LLMCallLog.id).desc())
        .all()
    )
    provider_rows = (
        query.with_entities(
            LLMCallLog.provider_name,
            func.count(LLMCallLog.id).label("calls"),
            func.coalesce(func.sum(LLMCallLog.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(LLMCallLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(LLMCallLog.cached_input_tokens), 0).label("cached_input_tokens"),
            func.coalesce(func.sum(LLMCallLog.cost_amount), 0).label("cost"),
        )
        .group_by(LLMCallLog.provider_name)
        .order_by(func.count(LLMCallLog.id).desc())
        .all()
    )
    bucket = func.date(LLMCallLog.created_at).label("bucket")
    trend_model = LLMCallLog.model.label("model")
    trend_rows = (
        query.with_entities(
            bucket,
            trend_model,
            func.count(LLMCallLog.id).label("calls"),
            func.coalesce(func.sum(LLMCallLog.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(LLMCallLog.cost_amount), 0).label("cost"),
        )
        .group_by(bucket, trend_model)
        .order_by(bucket.asc(), trend_model.asc())
        .all()
    )
    return {
        "summary": overview,
        "models": [_aggregate_row(row, "model") for row in model_rows],
        "providers": [_aggregate_row(row, "provider_name") for row in provider_rows],
        "trend": [
            {
                "bucket": str(row.bucket),
                "model": row.model,
                "calls": int(row.calls or 0),
                "tokens": int(row.tokens or 0),
                "cost": float(row.cost or 0),
            }
            for row in trend_rows
        ],
    }


def _filtered_query(user_id: int, params: dict):
    query = LLMCallLog.query.filter_by(user_id=user_id)
    model = str(params.get("model", "") or "").strip()
    operation = str(params.get("operation", "") or "").strip()
    status = str(params.get("status", "") or "").strip()
    if model:
        query = query.filter(LLMCallLog.model.ilike(f"%{model}%"))
    if operation:
        query = query.filter(LLMCallLog.operation == operation)
    if status:
        query = query.filter(LLMCallLog.status == status)
    if params.get("provider_id"):
        try:
            provider_id = int(params["provider_id"])
        except (TypeError, ValueError) as exc:
            raise ValueError("provider_id 必须是整数") from exc
        query = query.filter(LLMCallLog.provider_config_id == provider_id)
    start = _parse_datetime(params.get("start"))
    end = _parse_datetime(params.get("end"))
    if start:
        query = query.filter(LLMCallLog.created_at >= start)
    if end:
        query = query.filter(LLMCallLog.created_at <= end)
    return query


def _pagination(params: dict) -> tuple[int, int]:
    try:
        page = int(params.get("page", 1))
        per_page = int(params.get("per_page", 20))
    except (TypeError, ValueError) as exc:
        raise ValueError("page 和 per_page 必须是整数") from exc
    if page < 1 or not 1 <= per_page <= 100:
        raise ValueError("page 必须大于 0，per_page 必须在 1 至 100 之间")
    return page, per_page


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    if not isinstance(value, str):
        raise ValueError("日期参数必须是 ISO 字符串")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("日期参数格式无效") from exc
    return parsed.replace(tzinfo=None)


def _window_minutes(params: dict) -> float:
    start = _parse_datetime(params.get("start"))
    end = _parse_datetime(params.get("end"))
    if start and end and end > start:
        return max(1 / 60, (end - start).total_seconds() / 60)
    return 1.0


def _aggregate_row(row, key: str) -> dict:
    input_total = int(row.input_tokens or 0)
    cached_total = int(row.cached_input_tokens or 0)
    return {
        key: getattr(row, key),
        "calls": int(row.calls or 0),
        "tokens": int(row.tokens or 0),
        "input_tokens": input_total,
        "cached_input_tokens": cached_total,
        "cache_hit_rate": round(cached_total / input_total * 100, 1) if input_total else None,
        "cost": float(row.cost or 0),
    }

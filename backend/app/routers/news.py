from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import verify_refresh_token
from app.services import news_service

router = APIRouter()


@router.get("/headlines")
async def headlines(limit: int = Query(15, ge=1, le=50)):
    try:
        return await news_service.get_headlines(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load headlines: {exc}") from exc


@router.get("/calendar")
async def calendar(days_ahead: int = Query(14, ge=1, le=90)):
    try:
        return await news_service.get_upcoming_calendar(days_ahead=days_ahead)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load calendar: {exc}") from exc


@router.post("/refresh", dependencies=[Depends(verify_refresh_token)])
async def refresh():
    return await news_service.refresh_news_data()

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.scheduler import shutdown_scheduler, start_scheduler
from app.routers import (
    ai_decision,
    dxy,
    history,
    ict,
    market_data,
    news,
    notifications,
    performance,
    rates,
    settings as settings_router,
    top_down,
    treasury,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(
    title="Macro Intelligence AI",
    description="Institutional-grade macro intelligence for Gold (XAU/USD) and Nasdaq (NQ).",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(treasury.router, prefix="/api/treasury", tags=["Treasury"])
app.include_router(rates.router, prefix="/api/rates", tags=["Interest Rates"])
app.include_router(news.router, prefix="/api/news", tags=["Economic News"])
app.include_router(dxy.router, prefix="/api/dxy", tags=["DXY"])
app.include_router(market_data.router, prefix="/api/market-data", tags=["Market Data"])
app.include_router(ict.router, prefix="/api/ict", tags=["ICT Analysis"])
app.include_router(ai_decision.router, prefix="/api/ai-decision", tags=["AI Decision"])
app.include_router(history.router, prefix="/api/history", tags=["Historical Learning"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(performance.router, prefix="/api/performance", tags=["Performance"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["Settings"])
app.include_router(top_down.router, prefix="/api/top-down", tags=["Top-Down Analysis"])


@app.get("/api/health", tags=["Health"])
async def health():
    """Also the endpoint GitHub Actions pings to keep the free Render
    instance warm between scheduled refreshes."""
    return {"status": "ok", "service": "macro-intelligence-ai-backend", "env": settings.environment}

"""AI assistant chat service.

Uses Gemini Flash — fast and cheap, chosen deliberately for this since
it's a support/info assistant, not a reasoning-heavy task. Token usage is
kept down two ways: the model calls tools to fetch real, current data
instead of a large system-prompt data dump on every turn, and conversation
history is trimmed server-side regardless of what the frontend sends.

Uses the classic, stable generate_content API rather than Google's newer
Interactions API — the latter is very recently GA (mid-2026) and its
multi-turn tool-result submission shape is still settling across Google's
own docs, whereas generate_content's tool-calling loop is long-established
and explicitly still fully supported.
"""
import json

from google import genai
from google.genai import types

from app.config import get_settings
from app.services import (
    ai_decision_service,
    dxy_service,
    history_service,
    ict_service,
    ipda_service,
    news_service,
    open_float_service,
    performance_service,
    treasury_service,
)

MAX_TOKENS = 700
MAX_HISTORY_MESSAGES = 12
MAX_TOOL_ROUNDS = 4

SYSTEM_PROMPT = (
    "You are the AI assistant embedded in Macro Intelligence AI, a dashboard tracking "
    "Gold (XAU/USD) and Nasdaq (NQ, proxied via QQQ since real futures data requires a "
    "paid feed) using ICT-style technical analysis, macro data (Treasury yields, DXY, "
    "economic calendar), and a rules-based AI decision engine. You help visitors "
    "understand what the dashboard is showing, including its own track record.\n\n"
    "Always use your tools to pull real, current data before answering questions about "
    "live prices, signals, decisions, macro conditions, performance, or upcoming events — "
    "never guess or invent numbers. If a tool returns nothing, say so plainly.\n\n"
    "You are not a financial advisor and this isn't financial advice — say so naturally "
    "if someone asks for a trade recommendation. Keep answers concise."
)

# Individual function declarations, grouped into one Tool below. The
# Gemini SDK's Tool model only accepts specific top-level keys
# (function_declarations, google_search, code_execution, ...) — passing a
# bare {"name": ..., "description": ..., "parameters": ...} dict directly
# in the tools list, as earlier, fails pydantic validation with
# "Extra inputs are not permitted" on each of those keys.
FUNCTION_DECLARATIONS = [
    {
        "name": "get_market_snapshot",
        "description": (
            "The current AI decision (long/short/neutral, confidence, rationale) and the "
            "most recent ICT signal (institutional bias, trend, premium/discount, OTE "
            "zones) for an asset. Use this for any question about current price action, "
            "bias, or what the dashboard currently shows."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "asset": {
                    "type": "string",
                    "enum": ["XAUUSD", "NQ"],
                    "description": "XAUUSD for gold, NQ for Nasdaq",
                },
            },
            "required": ["asset"],
        },
    },
    {
        "name": "get_upcoming_calendar",
        "description": "Upcoming economic calendar releases (CPI, NFP, Fed decisions, etc).",
        "parameters": {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "description": "How many days ahead to look. Default 7."},
            },
        },
    },
    {
        "name": "get_recent_headlines",
        "description": "Recent economic news headlines with sentiment, most recent first.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "How many headlines. Default 8."},
            },
        },
    },
    {
        "name": "get_macro_snapshot",
        "description": (
            "The current Treasury yield curve (2Y/10Y spread, inversion status) and DXY "
            "(dollar index) snapshot with trend forecast. Use for questions about the "
            "macro backdrop, yield curve inversion, or dollar strength."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_performance_stats",
        "description": (
            "The AI decision engine's track record for an asset: win rate and performance "
            "metrics (total return, max drawdown, etc) from historical outcomes. Use when "
            "asked how well the system has performed, its accuracy, or its win rate."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "asset": {
                    "type": "string",
                    "enum": ["XAUUSD", "NQ"],
                    "description": "XAUUSD for gold, NQ for Nasdaq",
                },
            },
            "required": ["asset"],
        },
    },
    {
        "name": "get_open_float_analysis",
        "description": (
            "Quarterly Shift & Open Float analysis for an asset: the current quarterly "
            "structural bias, and where buy-side (above price) and sell-side (below price) "
            "protective liquidity currently sits — short-term swing highs/lows, and 3/6/12-"
            "month highs/lows — each with distance from current price and whether it's "
            "already been swept. Use this for any question about liquidity pools, stop "
            "hunts, where price might be 'reaching for', or which side has more open float."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "asset": {
                    "type": "string",
                    "enum": ["XAUUSD", "NQ"],
                    "description": "XAUUSD for gold, NQ for Nasdaq",
                },
            },
            "required": ["asset"],
        },
    },
    {
        "name": "get_ipda_data_ranges",
        "description": (
            "IPDA (Interbank Price Delivery Algorithm) analysis for an asset: the ~3-4 "
            "month institutional range, smart-money accumulation/distribution patterns "
            "versus a benchmark (DXY for gold, 10Y yield for Nasdaq), quarterly structure "
            "at 20/40/60 trading-day windows, institutional reference points (old highs/"
            "lows, order blocks, fair value gaps), the previous major market shift, "
            "projected 20/40/60-day cast-forward time windows, and Open Float at the same "
            "20/40/60-day windows. Use this for any question about IPDA ranges, smart money "
            "buy/sell programs, benchmark divergence, institutional reference points, or "
            "cast-forward projections."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "asset": {
                    "type": "string",
                    "enum": ["XAUUSD", "NQ"],
                    "description": "XAUUSD for gold, NQ for Nasdaq",
                },
            },
            "required": ["asset"],
        },
    },
]

TOOLS = [{"function_declarations": FUNCTION_DECLARATIONS}]


def _safe_json(value):
    """Round-trips through JSON (stringifying anything non-native, e.g. a
    Decimal or datetime from Supabase) so the result is guaranteed to be
    plain dicts/lists/strings/numbers before the SDK serializes it into
    the request — avoids an obscure serialization error deep in the
    tool-result round trip."""
    return json.loads(json.dumps(value, default=str))


async def _run_tool(name: str, tool_input: dict) -> dict | list:
    """Executes one tool call. Output size directly drives token cost per
    turn, so this stays lean rather than passing whole raw rows through."""
    if name == "get_market_snapshot":
        asset = tool_input.get("asset", "XAUUSD")
        decision = await ai_decision_service.get_latest_decision(asset)
        signals = await ict_service.get_latest_signals(asset, limit=1)
        return _safe_json(
            {"asset": asset, "ai_decision": decision, "latest_ict_signal": signals[0] if signals else None}
        )

    if name == "get_upcoming_calendar":
        days_ahead = tool_input.get("days_ahead", 7)
        events = await news_service.get_upcoming_calendar(days_ahead=days_ahead)
        return _safe_json(events[:15])

    if name == "get_recent_headlines":
        limit = tool_input.get("limit", 8)
        headlines = await news_service.get_headlines(limit=limit)
        return _safe_json(headlines)

    if name == "get_macro_snapshot":
        yield_curve = await treasury_service.get_yield_curve()
        dxy = await dxy_service.get_dxy_snapshot()
        return _safe_json({"yield_curve": yield_curve, "dxy": dxy})

    if name == "get_performance_stats":
        asset = tool_input.get("asset", "XAUUSD")
        performance = await performance_service.get_performance_summary(asset)
        win_rate = await history_service.get_win_rate(asset)
        return _safe_json({"asset": asset, "performance": performance, "win_rate": win_rate})

    if name == "get_open_float_analysis":
        asset = tool_input.get("asset", "XAUUSD")
        return _safe_json(await open_float_service.get_open_float_analysis(asset))

    if name == "get_ipda_data_ranges":
        asset = tool_input.get("asset", "XAUUSD")
        return _safe_json(await ipda_service.get_ipda_data_ranges(asset))

    return {"error": f"unknown tool '{name}'"}


async def get_chat_response(messages: list[dict]) -> str:
    """messages: [{"role": "user" | "assistant", "content": str}, ...] —
    the frontend's running conversation. Returns the assistant's final
    text reply after resolving any tool calls."""
    settings = get_settings()
    if not settings.gemini_api_key:
        return "The AI assistant isn't configured yet — GEMINI_API_KEY is missing on the backend."

    client = genai.Client(api_key=settings.gemini_api_key)

    # Gemini calls the assistant's own turns "model", not "assistant".
    contents = [
        types.Content(
            role="model" if m["role"] == "assistant" else "user",
            parts=[types.Part.from_text(text=m["content"])],
        )
        for m in messages[-MAX_HISTORY_MESSAGES:]
    ]

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        max_output_tokens=MAX_TOKENS,
        tools=TOOLS,
    )

    for _ in range(MAX_TOOL_ROUNDS):
        response = await client.aio.models.generate_content(model=settings.gemini_model, contents=contents, config=config)

        candidate_content = response.candidates[0].content
        function_calls = [p.function_call for p in candidate_content.parts if p.function_call]

        if not function_calls:
            return (response.text or "").strip()

        contents.append(candidate_content)

        result_parts = [
            types.Part.from_function_response(
                name=fc.name, response={"result": await _run_tool(fc.name, dict(fc.args) if fc.args else {})}
            )
            for fc in function_calls
        ]
        contents.append(types.Content(role="user", parts=result_parts))

    return "I wasn't able to finish looking that up — try rephrasing the question."

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SwingPoint:
    index: int
    price: float
    kind: str  # HIGH | LOW


@dataclass
class MarketStructure:
    trend: str
    strength: float
    bos: bool
    choch: bool
    mss: bool
    hh: bool
    hl: bool
    lh: bool
    ll: bool
    last_high: Optional[float]
    last_low: Optional[float]


class MarketStructureEngine:

    def __init__(self, bars: List[dict]):
        self.bars = bars

    def swing_highs(self, lookback: int = 3) -> List[SwingPoint]:
        swings = []

        for i in range(lookback, len(self.bars) - lookback):

            high = float(self.bars[i]["high"])

            if all(
                high > float(self.bars[j]["high"])
                for j in range(i - lookback, i + lookback + 1)
                if j != i
            ):
                swings.append(
                    SwingPoint(
                        index=i,
                        price=high,
                        kind="HIGH",
                    )
                )

        return swings

    def swing_lows(self, lookback: int = 3) -> List[SwingPoint]:
        swings = []

        for i in range(lookback, len(self.bars) - lookback):

            low = float(self.bars[i]["low"])

            if all(
                low < float(self.bars[j]["low"])
                for j in range(i - lookback, i + lookback + 1)
                if j != i
            ):
                swings.append(
                    SwingPoint(
                        index=i,
                        price=low,
                        kind="LOW",
                    )
                )

        return swings

    def analyse(self) -> MarketStructure:

        highs = self.swing_highs()
        lows = self.swing_lows()

        if len(highs) < 2 or len(lows) < 2:
            return MarketStructure(
                trend="UNKNOWN",
                strength=0,
                bos=False,
                choch=False,
                mss=False,
                hh=False,
                hl=False,
                lh=False,
                ll=False,
                last_high=None,
                last_low=None,
            )

        h1 = highs[-2].price
        h2 = highs[-1].price

        l1 = lows[-2].price
        l2 = lows[-1].price

        hh = h2 > h1
        hl = l2 > l1

        lh = h2 < h1
        ll = l2 < l1

        trend = "RANGE"

        if hh and hl:
            trend = "BULLISH"

        elif lh and ll:
            trend = "BEARISH"

        bos = hh or ll

        choch = (
            (hh and ll)
            or
            (lh and hl)
        )

        mss = choch

        strength = 50.0

        if trend != "RANGE":
            strength = 70.0

        if bos:
            strength += 10

        if choch:
            strength += 10

        if hh and hl:
            strength += 10

        if lh and ll:
            strength += 10

        strength = min(100, strength)

        return MarketStructure(
            trend=trend,
            strength=strength,
            bos=bos,
            choch=choch,
            mss=mss,
            hh=hh,
            hl=hl,
            lh=lh,
            ll=ll,
            last_high=h2,
            last_low=l2,
        )

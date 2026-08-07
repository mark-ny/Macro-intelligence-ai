"use client";

import { useEffect, useRef } from "react";
import {
  AreaSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
} from "lightweight-charts";

import type { YieldHistoryPoint } from "@/types";

/**
 * Reads a color token's "R G B" triplet from the live CSS custom property
 * (see src/app/globals.css) rather than hardcoding hex — lightweight-charts
 * renders to a <canvas>, so it can't resolve CSS variables itself the way
 * a bg-* Tailwind class can; this is what makes the chart follow the
 * dark/light theme instead of staying stuck on one palette.
 */
function cssVarTriplet(name: string): string {
  if (typeof window === "undefined") return "0 0 0";
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "0 0 0";
}

function chartColors() {
  const gold = cssVarTriplet("--color-gold").split(" ").join(",");
  return {
    text: `rgb(${cssVarTriplet("--color-muted")})`,
    grid: `rgb(${cssVarTriplet("--color-border")})`,
    lineColor: `rgb(${cssVarTriplet("--color-gold")})`,
    topColor: `rgba(${gold},0.28)`,
    bottomColor: `rgba(${gold},0.0)`,
  };
}

interface Props {
  data: YieldHistoryPoint[];
  height?: number;
}

/**
 * Wraps lightweight-charts v5. Note the v5 API change from v4: series are
 * created with chart.addSeries(SeriesType, options) and the series type
 * (AreaSeries, LineSeries, ...) must be imported explicitly — the old
 * chart.addLineSeries()/addAreaSeries() methods were removed in v5.
 */
export function YieldCurveChart({ data, height = 280 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const colors = chartColors();
    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { color: "transparent" },
        textColor: colors.text,
        fontFamily: "var(--font-mono)",
      },
      grid: {
        vertLines: { color: colors.grid },
        horzLines: { color: colors.grid },
      },
      rightPriceScale: { borderColor: colors.grid },
      timeScale: { borderColor: colors.grid },
    });

    const series = chart.addSeries(AreaSeries, {
      lineColor: colors.lineColor,
      topColor: colors.topColor,
      bottomColor: colors.bottomColor,
      lineWidth: 2,
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const resizeObserver = new ResizeObserver((entries) => {
      const { width } = entries[0].contentRect;
      chart.applyOptions({ width });
    });
    resizeObserver.observe(containerRef.current);

    // Re-applies colors immediately if the user flips the theme (Settings
    // page) while this chart is mounted, instead of only on next load.
    const themeObserver = new MutationObserver(() => {
      const next = chartColors();
      chart.applyOptions({
        layout: { textColor: next.text },
        grid: { vertLines: { color: next.grid }, horzLines: { color: next.grid } },
        rightPriceScale: { borderColor: next.grid },
        timeScale: { borderColor: next.grid },
      });
      series.applyOptions({
        lineColor: next.lineColor,
        topColor: next.topColor,
        bottomColor: next.bottomColor,
      });
    });
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

    return () => {
      resizeObserver.disconnect();
      themeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [height]);

  useEffect(() => {
    if (!seriesRef.current) return;
    seriesRef.current.setData(data.map((point) => ({ time: point.date, value: point.value })));
    chartRef.current?.timeScale().fitContent();
  }, [data]);

  return <div ref={containerRef} className="w-full" />;
}

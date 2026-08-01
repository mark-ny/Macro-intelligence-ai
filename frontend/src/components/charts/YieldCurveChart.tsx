"use client";

import { useEffect, useRef } from "react";
import {
  AreaSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
} from "lightweight-charts";

import type { YieldHistoryPoint } from "@/types";

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

    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { color: "transparent" },
        textColor: "#8B93A7",
        fontFamily: "var(--font-mono)",
      },
      grid: {
        vertLines: { color: "#232838" },
        horzLines: { color: "#232838" },
      },
      rightPriceScale: { borderColor: "#232838" },
      timeScale: { borderColor: "#232838" },
    });

    const series = chart.addSeries(AreaSeries, {
      lineColor: "#C9A227",
      topColor: "rgba(201, 162, 39, 0.28)",
      bottomColor: "rgba(201, 162, 39, 0.0)",
      lineWidth: 2,
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const resizeObserver = new ResizeObserver((entries) => {
      const { width } = entries[0].contentRect;
      chart.applyOptions({ width });
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
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

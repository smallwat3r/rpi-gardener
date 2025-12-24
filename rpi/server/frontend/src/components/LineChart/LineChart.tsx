import { useEffect, useRef, memo } from 'preact/compat';
import * as echarts from 'echarts/core';
import { LineChart as ELineChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsOption, LineSeriesOption } from 'echarts';
import styles from './LineChart.module.css';

echarts.use([ELineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer]);

export interface SeriesConfig {
  name: string;
  dataKey: string;
  color: string;
  yAxisIndex?: number;
}

interface LineChartProps {
  data: Record<string, number>[];
  series: SeriesConfig[];
  yAxes?: {
    min?: number;
    max?: number;
    position?: 'left' | 'right';
  }[];
  showArea?: boolean;
  colorAxis?: boolean;
}

export const LineChart = memo(function LineChart({ data, series, yAxes, showArea = true, colorAxis = true }: LineChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = echarts.init(containerRef.current);
    chartRef.current = chart;

    const handleResize = () => {
      if (chartRef.current && !chartRef.current.isDisposed()) {
        chartRef.current.resize();
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chart && !chart.isDisposed()) {
        chart.dispose();
      }
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || chart.isDisposed() || !data.length) return;

    const yAxisConfigs = yAxes?.map((axis, idx) => ({
      type: 'value' as const,
      position: axis.position || (idx === 0 ? 'left' : 'right'),
      min: axis.min,
      max: axis.max,
      axisLine: {
        show: true,
        lineStyle: { color: colorAxis ? (series[idx]?.color || '#666') : '#4b5563' },
      },
      axisLabel: {
        color: '#9ca3af',
        fontSize: 11,
        formatter: (value: number) => Math.round(value).toString(),
      },
      splitLine: {
        lineStyle: { color: 'rgba(75, 85, 99, 0.3)' },
      },
    })) || [{
      type: 'value' as const,
      axisLine: { show: false },
      axisLabel: { color: '#9ca3af', fontSize: 11 },
      splitLine: { lineStyle: { color: 'rgba(75, 85, 99, 0.3)' } },
    }];

    const seriesData: LineSeriesOption[] = series.map((s) => ({
      name: s.name,
      type: 'line',
      yAxisIndex: s.yAxisIndex ?? 0,
      smooth: 0.4,
      symbol: 'none',
      itemStyle: {
        color: s.color,
      },
      lineStyle: {
        width: 2.5,
        color: s.color,
      },
      ...(showArea && {
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: `${s.color}40` },
            { offset: 1, color: `${s.color}05` },
          ]),
        },
      }),
      data: data.map(d => [d.epoch, d[s.dataKey]]),
    }));

    const option: EChartsOption = {
      animation: true,
      animationDuration: 300,
      animationEasing: 'cubicOut',
      grid: {
        left: 45,
        right: yAxes && yAxes.length > 1 ? 45 : 15,
        top: 20,
        bottom: 25,
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(30, 30, 35, 0.95)',
        borderColor: 'rgba(75, 85, 99, 0.5)',
        borderWidth: 1,
        padding: [10, 14],
        textStyle: {
          color: '#f3f4f6',
          fontSize: 12,
        },
        formatter: (params: unknown) => {
          const items = params as { seriesName: string; value: [number, number]; color: string }[];
          if (!items.length) return '';
          const date = new Date(items[0].value[0]);
          const timeStr = date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
          const dateStr = date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
          let html = `<div style="font-weight:600;margin-bottom:8px;color:#9ca3af">${dateStr} ${timeStr} UTC</div>`;
          items.forEach(item => {
            const value = typeof item.value[1] === 'number' ? item.value[1].toFixed(1) : item.value[1];
            html += `<div style="display:flex;align-items:center;gap:8px;margin:4px 0">
              <span style="width:10px;height:10px;border-radius:50%;background:${item.color}"></span>
              <span style="flex:1">${item.seriesName}</span>
              <span style="font-weight:600">${value}</span>
            </div>`;
          });
          return html;
        },
      },
      xAxis: {
        type: 'time',
        axisLine: { lineStyle: { color: '#4b5563' } },
        axisLabel: {
          color: '#9ca3af',
          fontSize: 11,
          formatter: (value: number) => {
            const date = new Date(value);
            return date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
          },
        },
        splitLine: { show: false },
      },
      yAxis: yAxisConfigs,
      series: seriesData,
    };

    chart.setOption(option, { notMerge: false, lazyUpdate: true });
  }, [data, series, yAxes, showArea, colorAxis]);

  return <div ref={containerRef} class={styles.container} />;
});

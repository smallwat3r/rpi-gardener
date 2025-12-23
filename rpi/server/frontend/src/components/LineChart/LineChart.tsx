import { useEffect, useRef, memo } from 'preact/compat';
import {
  Chart,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  TimeScale,
  Tooltip,
  Filler,
} from 'chart.js';
import 'chartjs-adapter-date-fns';
import styles from './LineChart.module.css';

Chart.register(LineController, LineElement, PointElement, LinearScale, TimeScale, Tooltip, Filler);

Chart.defaults.font.family = 'Inter';
Chart.defaults.color = '#f8f9fa';
Chart.defaults.font.size = 11;

interface Dataset {
  label: string;
  data: Record<string, number>[];
  borderColor: string;
  yAxisID?: string;
  parsing: { yAxisKey: string; xAxisKey: string };
}

interface LineChartProps {
  datasets: Dataset[];
  yAxes?: {
    id: string;
    position: 'left' | 'right';
    min?: number;
    max?: number;
    suggestedMin?: number;
    suggestedMax?: number;
  }[];
}

export const LineChart = memo(function LineChart({ datasets, yAxes }: LineChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const chartRef = useRef<Chart<'line', any[], unknown> | null>(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    const scales: Record<string, object> = {
      x: {
        type: 'time',
        ticks: { stepSize: 2, color: '#f8f9fa' },
        time: {
          unit: 'second',
          displayFormats: { second: 'HH:mm' },
          tooltipFormat: 'yyyy-MM-dd HH:mm',
        },
        grid: { color: '#495057' },
      },
    };

    if (yAxes) {
      yAxes.forEach((axis) => {
        scales[axis.id] = {
          type: 'linear',
          display: true,
          position: axis.position,
          min: axis.min,
          max: axis.max,
          suggestedMin: axis.suggestedMin,
          suggestedMax: axis.suggestedMax,
          ticks: { color: '#f8f9fa' },
          grid: { color: '#495057' },
        };
      });
    } else {
      scales['y'] = {
        type: 'linear',
        display: true,
        suggestedMin: 0,
        suggestedMax: 100,
        ticks: { color: '#f8f9fa' },
        grid: { color: '#495057' },
      };
    }

    chartRef.current = new Chart(canvasRef.current, {
      type: 'line',
      data: {
        datasets: datasets.map((ds) => ({
          ...ds,
          tension: 0.4,
          borderWidth: 2,
          pointStyle: false as const,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 0 },
        scales,
        interaction: { intersect: false, mode: 'index' },
        plugins: {
          legend: { display: false },
        },
      },
    });

    return () => {
      chartRef.current?.destroy();
    };
  }, []);

  useEffect(() => {
    if (!chartRef.current) return;

    datasets.forEach((ds, idx) => {
      if (chartRef.current?.data.datasets[idx]) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        chartRef.current.data.datasets[idx].data = ds.data as any;
      }
    });
    chartRef.current.update('none');
  }, [datasets]);

  return (
    <div class={styles.container}>
      <canvas ref={canvasRef} />
    </div>
  );
});

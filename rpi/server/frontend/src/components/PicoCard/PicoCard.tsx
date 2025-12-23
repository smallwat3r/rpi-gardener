import type { PicoReading, PicoChartDataPoint } from '@/types';
import { LineChart } from '@/components/LineChart';
import styles from './PicoCard.module.css';

const PLANT_COLORS: Record<string, string> = {
  'plant-1': '#9d34a0',
  'plant-2': '#00aaff',
  'plant-3': '#ff00ff',
};

interface PicoCardProps {
  latest: PicoReading[];
  chartData: PicoChartDataPoint[];
}

export function PicoCard({ latest, chartData }: PicoCardProps) {
  const datasets = latest.map((plant, idx) => ({
    label: `${plant.plant_id} %`,
    data: chartData as unknown as Record<string, number>[],
    borderColor: PLANT_COLORS[plant.plant_id] || ['#9d34a0', '#00aaff', '#ff00ff'][idx],
    parsing: { yAxisKey: plant.plant_id, xAxisKey: 'epoch' },
  }));

  const yAxes = [
    { id: 'y', position: 'left' as const, min: 0, suggestedMin: 10, suggestedMax: 90 },
  ];

  return (
    <article class={styles.card} aria-labelledby="pico-card-header">
      <h2 id="pico-card-header" class={styles.header}>RPi Pico Moisture</h2>
      <div class={styles.body}>
        <p class={styles.lastUpdate}>Last update: <time>{latest[0]?.recording_time}</time></p>
        <div class={styles.plants} role="list" aria-label="Plant moisture readings">
          {latest.map((plant) => (
            <div key={plant.plant_id} class={styles.plant} role="listitem">
              <h3
                class={styles.plantName}
                style={{ color: PLANT_COLORS[plant.plant_id] }}
              >
                {plant.plant_id}
              </h3>
              <p
                class={styles.display}
                style={{ color: PLANT_COLORS[plant.plant_id] }}
                aria-live="polite"
              >
                {plant.moisture}%
              </p>
            </div>
          ))}
        </div>
        <LineChart datasets={datasets} yAxes={yAxes} />
      </div>
    </article>
  );
}

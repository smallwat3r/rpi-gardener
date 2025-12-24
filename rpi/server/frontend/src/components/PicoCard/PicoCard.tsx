import { useMemo } from 'preact/hooks';
import type { PicoReading, PicoChartDataPoint } from '@/types';
import { LineChart, type SeriesConfig } from '@/components/LineChart';
import styles from './PicoCard.module.css';

const PLANT_COLORS: Record<string, string> = {
  'plant-1': '#a78bfa',
  'plant-2': '#38bdf8',
  'plant-3': '#fb7185',
};

const Y_AXES = [{ position: 'left' as const, min: 0, max: 100 }];

interface PicoCardProps {
  latest: PicoReading[];
  chartData: PicoChartDataPoint[];
}

export function PicoCard({ latest, chartData }: PicoCardProps) {
  const series = useMemo<SeriesConfig[]>(
    () => latest.map((plant, idx) => ({
      name: plant.plant_id,
      dataKey: plant.plant_id,
      color: PLANT_COLORS[plant.plant_id] || ['#a78bfa', '#38bdf8', '#fb7185'][idx],
      yAxisIndex: 0,
    })),
    [latest]
  );

  const data = useMemo(
    () => chartData as unknown as Record<string, number>[],
    [chartData]
  );

  if (!latest.length) {
    return (
      <article class={styles.card} aria-labelledby="pico-card-header">
        <h2 id="pico-card-header" class={styles.header}>RPi Pico Moisture</h2>
        <div class={styles.body}>
          <p class={styles.noData}>No data available</p>
        </div>
      </article>
    );
  }

  return (
    <article class={styles.card} aria-labelledby="pico-card-header">
      <h2 id="pico-card-header" class={styles.header}>RPi Pico Moisture</h2>
      <div class={styles.body}>
        <div class={styles.content}>
          <p class={styles.lastUpdate}>Last update: <time>{latest[0]?.recording_time}</time> UTC</p>
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
        </div>
        <LineChart data={data} series={series} yAxes={Y_AXES} colorAxis={false} />
      </div>
    </article>
  );
}

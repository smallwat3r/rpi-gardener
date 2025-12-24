import { useMemo } from 'preact/hooks';
import type { DHTReading, DHTStats } from '@/types';
import { LineChart, type SeriesConfig } from '@/components/LineChart';
import { StatDisplay } from '@/components/StatDisplay';
import styles from './DHTCard.module.css';

interface DHTCardProps {
  latest: DHTReading | null;
  stats: DHTStats | null;
  chartData: DHTReading[];
}

const SERIES_CONFIG: SeriesConfig[] = [
  { name: 'Temperature (°C)', dataKey: 'temperature', color: '#f472b6', yAxisIndex: 0 },
  { name: 'Humidity (%)', dataKey: 'humidity', color: '#22d3ee', yAxisIndex: 1 },
];

const Y_AXES = [
  { position: 'left' as const, min: 15, max: 35 },
  { position: 'right' as const, min: 30, max: 80 },
];

export function DHTCard({ latest, stats, chartData }: DHTCardProps) {
  const data = useMemo(
    () => chartData as unknown as Record<string, number>[],
    [chartData]
  );

  if (!latest || !stats) {
    return (
      <article class={styles.card} aria-labelledby="dht-card-header">
        <h2 id="dht-card-header" class={styles.header}>RPi 4 DHT22</h2>
        <div class={styles.body}>
          <p class={styles.noData}>No data available</p>
        </div>
      </article>
    );
  }

  return (
    <article class={styles.card} aria-labelledby="dht-card-header">
      <h2 id="dht-card-header" class={styles.header}>RPi 4 DHT22</h2>
      <div class={styles.body}>
        <div class={styles.content}>
          <p class={styles.lastUpdate}>Last update: <time>{latest.recording_time}</time> UTC</p>
          <div class={styles.readings}>
            <section class={styles.reading} aria-label="Temperature readings">
              <h3 class={styles.temperature}>Temperature</h3>
              <p class={`${styles.display} ${styles.temperature}`} aria-live="polite">{latest.temperature}°C</p>
              <StatDisplay
                avg={stats.avg_temperature}
                min={stats.min_temperature}
                max={stats.max_temperature}
                unit="°C"
              />
            </section>
            <section class={`${styles.reading} ${styles.readingRight}`} aria-label="Humidity readings">
              <h3 class={styles.humidity}>Humidity</h3>
              <p class={`${styles.display} ${styles.humidity}`} aria-live="polite">{latest.humidity}%</p>
              <StatDisplay
                avg={stats.avg_humidity}
                min={stats.min_humidity}
                max={stats.max_humidity}
                unit="%"
              />
            </section>
          </div>
        </div>
        <LineChart data={data} series={SERIES_CONFIG} yAxes={Y_AXES} />
      </div>
    </article>
  );
}

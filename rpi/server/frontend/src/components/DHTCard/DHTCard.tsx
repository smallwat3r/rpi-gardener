import type { DHTReading, DHTStats } from '@/types';
import { LineChart } from '@/components/LineChart';
import { StatDisplay } from '@/components/StatDisplay';
import styles from './DHTCard.module.css';

interface DHTCardProps {
  latest: DHTReading;
  stats: DHTStats;
  chartData: DHTReading[];
}

export function DHTCard({ latest, stats, chartData }: DHTCardProps) {
  const datasets = [
    {
      label: 'Temperature (c)',
      data: chartData as unknown as Record<string, number>[],
      borderColor: '#ff00ff',
      yAxisID: 'y',
      parsing: { yAxisKey: 'temperature', xAxisKey: 'epoch' },
    },
    {
      label: 'Humidity (%)',
      data: chartData as unknown as Record<string, number>[],
      borderColor: '#00ffff',
      yAxisID: 'y1',
      parsing: { yAxisKey: 'humidity', xAxisKey: 'epoch' },
    },
  ];

  const yAxes = [
    { id: 'y', position: 'left' as const, suggestedMin: 20, suggestedMax: 30 },
    { id: 'y1', position: 'right' as const, suggestedMin: 40, suggestedMax: 65 },
  ];

  return (
    <article class={styles.card} aria-labelledby="dht-card-header">
      <h2 id="dht-card-header" class={styles.header}>RPi 4 DHT22</h2>
      <div class={styles.body}>
        <p class={styles.lastUpdate}>Last update: <time>{latest.recording_time}</time></p>
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
        <LineChart datasets={datasets} yAxes={yAxes} />
      </div>
    </article>
  );
}

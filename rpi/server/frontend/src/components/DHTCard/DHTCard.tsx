import { useCallback, useMemo, useState } from 'preact/hooks';
import { LineChart, type SeriesConfig, type ThresholdLine } from '@/components/LineChart';
import { Modal } from '@/components/Modal';
import { StatDisplay } from '@/components/StatDisplay';
import { WarningBadge } from '@/components/WarningBadge';
import type { DHTReading, DHTStats, Thresholds } from '@/types';
import styles from './DHTCard.module.css';

type ModalChart = 'temperature' | 'humidity' | null;

interface DHTCardProps {
  latest: DHTReading | null;
  stats: DHTStats | null;
  chartData: DHTReading[];
  thresholds: Thresholds | null;
}

const TEMP_SERIES: SeriesConfig[] = [
  { name: 'Temperature (°C)', dataKey: 'temperature', color: '#f472b6', yAxisIndex: 0 },
];

const HUMIDITY_SERIES: SeriesConfig[] = [
  { name: 'Humidity (%)', dataKey: 'humidity', color: '#22d3ee', yAxisIndex: 0 },
];

const TEMP_Y_AXES = [{ position: 'left' as const, min: 15, max: 35 }];
const HUMIDITY_Y_AXES = [{ position: 'left' as const, min: 30, max: 80 }];

const ALERT_COLOR = '#ef4444';

type AlertStatus = 'ok' | 'too_low' | 'too_high';

function getValueStatus(value: number, min: number, max: number): AlertStatus {
  if (value < min) return 'too_low';
  if (value > max) return 'too_high';
  return 'ok';
}

export function DHTCard({ latest, stats, chartData, thresholds }: DHTCardProps) {
  const [openModal, setOpenModal] = useState<ModalChart>(null);

  const closeModal = useCallback(() => setOpenModal(null), []);

  const data = useMemo(() => chartData as unknown as Record<string, number>[], [chartData]);

  const tempThresholds = useMemo<ThresholdLine[]>(() => {
    if (!thresholds) return [];
    return [
      {
        value: thresholds.temperature.min,
        label: `Min ${thresholds.temperature.min}°C`,
        color: ALERT_COLOR,
        yAxisIndex: 0,
        type: 'min',
      },
      {
        value: thresholds.temperature.max,
        label: `Max ${thresholds.temperature.max}°C`,
        color: ALERT_COLOR,
        yAxisIndex: 0,
        type: 'max',
      },
    ];
  }, [thresholds]);

  const humidityThresholds = useMemo<ThresholdLine[]>(() => {
    if (!thresholds) return [];
    return [
      {
        value: thresholds.humidity.min,
        label: `Min ${thresholds.humidity.min}%`,
        color: ALERT_COLOR,
        yAxisIndex: 0,
        type: 'min',
      },
      {
        value: thresholds.humidity.max,
        label: `Max ${thresholds.humidity.max}%`,
        color: ALERT_COLOR,
        yAxisIndex: 0,
        type: 'max',
      },
    ];
  }, [thresholds]);

  const tempStatus =
    thresholds && latest
      ? getValueStatus(latest.temperature, thresholds.temperature.min, thresholds.temperature.max)
      : 'ok';
  const humidityStatus =
    thresholds && latest
      ? getValueStatus(latest.humidity, thresholds.humidity.min, thresholds.humidity.max)
      : 'ok';

  if (!latest || !stats) {
    return (
      <article class={styles.card} aria-labelledby="dht-card-header">
        <h2 id="dht-card-header" class={styles.header}>
          Room Climate
        </h2>
        <div class={styles.body}>
          <p class={styles.noData}>No data available</p>
        </div>
      </article>
    );
  }

  return (
    <article class={styles.card} aria-labelledby="dht-card-header">
      <h2 id="dht-card-header" class={styles.header}>
        Room Climate
      </h2>
      <div class={styles.body}>
        <p class={styles.lastUpdate}>
          Last update: <time>{latest.recording_time}</time> UTC
        </p>
        <div class={styles.charts}>
          <section class={styles.chartSection} aria-label="Temperature readings">
            <div class={styles.chartHeader}>
              <h3 class={styles.temperature}>Temperature</h3>
              <p class={`${styles.display} ${styles.temperature}`} aria-live="polite">
                {latest.temperature}°C
              </p>
              {tempStatus === 'too_high' && <WarningBadge>Too hot</WarningBadge>}
              {tempStatus === 'too_low' && <WarningBadge>Too cold</WarningBadge>}
              <StatDisplay
                avg={stats.avg_temperature}
                min={stats.min_temperature}
                max={stats.max_temperature}
                unit="°C"
              />
              <button
                type="button"
                class={styles.expandBtn}
                onClick={() => setOpenModal('temperature')}
                aria-label="Expand temperature chart"
              >
                ⛶
              </button>
            </div>
            <LineChart
              data={data}
              series={TEMP_SERIES}
              yAxes={TEMP_Y_AXES}
              thresholds={tempThresholds}
              colorAxis={false}
              showArea={false}
            />
          </section>
          <section class={styles.chartSection} aria-label="Humidity readings">
            <div class={styles.chartHeader}>
              <h3 class={styles.humidity}>Humidity</h3>
              <p class={`${styles.display} ${styles.humidity}`} aria-live="polite">
                {latest.humidity}%
              </p>
              {humidityStatus === 'too_high' && <WarningBadge>Too humid</WarningBadge>}
              {humidityStatus === 'too_low' && <WarningBadge>Too dry</WarningBadge>}
              <StatDisplay
                avg={stats.avg_humidity}
                min={stats.min_humidity}
                max={stats.max_humidity}
                unit="%"
              />
              <button
                type="button"
                class={styles.expandBtn}
                onClick={() => setOpenModal('humidity')}
                aria-label="Expand humidity chart"
              >
                ⛶
              </button>
            </div>
            <LineChart
              data={data}
              series={HUMIDITY_SERIES}
              yAxes={HUMIDITY_Y_AXES}
              thresholds={humidityThresholds}
              colorAxis={false}
              showArea={false}
            />
          </section>
        </div>
      </div>

      <Modal isOpen={openModal === 'temperature'} onClose={closeModal} title="Temperature">
        <LineChart
          data={data}
          series={TEMP_SERIES}
          yAxes={TEMP_Y_AXES}
          thresholds={tempThresholds}
          colorAxis={false}
          showArea={false}
          height={400}
        />
      </Modal>

      <Modal isOpen={openModal === 'humidity'} onClose={closeModal} title="Humidity">
        <LineChart
          data={data}
          series={HUMIDITY_SERIES}
          yAxes={HUMIDITY_Y_AXES}
          thresholds={humidityThresholds}
          colorAxis={false}
          showArea={false}
          height={400}
        />
      </Modal>
    </article>
  );
}

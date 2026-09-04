import { useCallback, useMemo, useState } from 'preact/hooks';
import { cssVar, LineChart, type SeriesConfig, type ThresholdLine } from '@/components/LineChart';
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
  loading?: boolean;
  humidifierIsOn?: boolean | null;
}

const TEMP_Y_AXES = [{ position: 'left' as const, min: 15, max: 35 }];
const HUMIDITY_Y_AXES = [{ position: 'left' as const, min: 30, max: 80 }];

type AlertStatus = 'ok' | 'too_low' | 'too_high';

function getValueStatus(value: number, min: number, max: number): AlertStatus {
  if (value < min) return 'too_low';
  if (value > max) return 'too_high';
  return 'ok';
}

function SectionHead({ recordingTime }: { recordingTime?: string }) {
  return (
    <div class={styles.sectionHead}>
      <h2 id="dht-card-header" class={styles.heading}>
        Room climate
      </h2>
      <span class={styles.rule} aria-hidden="true" />
      {recordingTime && (
        <p class={styles.lastUpdate}>
          updated <time>{recordingTime}</time> UTC
        </p>
      )}
    </div>
  );
}

function ExpandIcon() {
  return (
    <svg
      class={styles.expandIcon}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <polyline points="15 3 21 3 21 9" />
      <polyline points="9 21 3 21 3 15" />
      <line x1="21" y1="3" x2="14" y2="10" />
      <line x1="3" y1="21" x2="10" y2="14" />
    </svg>
  );
}

export function DHTCard({
  latest,
  stats,
  chartData,
  thresholds,
  loading = false,
  humidifierIsOn,
}: DHTCardProps) {
  const [openModal, setOpenModal] = useState<ModalChart>(null);

  const closeModal = useCallback(() => setOpenModal(null), []);

  const data = useMemo(() => chartData as unknown as Record<string, number>[], [chartData]);

  const tempSeries = useMemo<SeriesConfig[]>(
    () => [
      {
        name: 'Temperature (°C)',
        dataKey: 'temperature',
        color: cssVar('--color-temperature'),
        yAxisIndex: 0,
      },
    ],
    [],
  );

  const humiditySeries = useMemo<SeriesConfig[]>(
    () => [
      {
        name: 'Humidity (%)',
        dataKey: 'humidity',
        color: cssVar('--color-humidity'),
        yAxisIndex: 0,
      },
    ],
    [],
  );

  const alertColor = useMemo(() => `${cssVar('--color-alert')}99`, []);

  const tempThresholds = useMemo<ThresholdLine[]>(() => {
    if (!thresholds) return [];
    return [
      {
        value: thresholds.temperature.min,
        label: `Min ${thresholds.temperature.min}°C`,
        color: alertColor,
        yAxisIndex: 0,
        type: 'min',
      },
      {
        value: thresholds.temperature.max,
        label: `Max ${thresholds.temperature.max}°C`,
        color: alertColor,
        yAxisIndex: 0,
        type: 'max',
      },
    ];
  }, [thresholds, alertColor]);

  const humidityThresholds = useMemo<ThresholdLine[]>(() => {
    if (!thresholds) return [];
    return [
      {
        value: thresholds.humidity.min,
        label: `Min ${thresholds.humidity.min}%`,
        color: alertColor,
        yAxisIndex: 0,
        type: 'min',
      },
      {
        value: thresholds.humidity.max,
        label: `Max ${thresholds.humidity.max}%`,
        color: alertColor,
        yAxisIndex: 0,
        type: 'max',
      },
    ];
  }, [thresholds, alertColor]);

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
      <article class={styles.section} aria-labelledby="dht-card-header">
        <SectionHead />
        <p class={styles.noData}>No data available</p>
      </article>
    );
  }

  return (
    <article class={styles.section} aria-labelledby="dht-card-header">
      <SectionHead recordingTime={latest.recording_time} />
      <div class={styles.metrics}>
        <section class={styles.metric} aria-label="Temperature readings">
          <div class={styles.metricTop}>
            <h3 class={styles.metricLabel}>Temperature</h3>
            {tempStatus === 'too_high' && <WarningBadge>Too hot</WarningBadge>}
            {tempStatus === 'too_low' && <WarningBadge>Too cold</WarningBadge>}
            <div class={styles.metricValue}>
              <p class={`${styles.display} ${styles.temperature}`} aria-live="polite">
                {latest.temperature}
                <span class={styles.unit}>°C</span>
              </p>
              <button
                type="button"
                class={styles.expandBtn}
                onClick={() => setOpenModal('temperature')}
                aria-label="Expand temperature chart"
              >
                <ExpandIcon />
              </button>
            </div>
          </div>
          <StatDisplay
            avg={stats.avg_temperature}
            min={stats.min_temperature}
            max={stats.max_temperature}
            unit="°C"
          />
          <LineChart
            data={data}
            series={tempSeries}
            yAxes={TEMP_Y_AXES}
            thresholds={tempThresholds}
            colorAxis={false}
            showArea={false}
            loading={loading}
          />
        </section>
        <section class={styles.metric} aria-label="Humidity readings">
          <div class={styles.metricTop}>
            <h3 class={styles.metricLabel}>Humidity</h3>
            {humidityStatus === 'too_high' && <WarningBadge>Too humid</WarningBadge>}
            {humidityStatus === 'too_low' && <WarningBadge>Too dry</WarningBadge>}
            {humidifierIsOn && (
              <span class={styles.humidifierBadge}>
                <svg
                  class={styles.humidifierIcon}
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <path d="M12 2c-5.33 4.55-8 8.48-8 11.8 0 4.98 3.8 8.2 8 8.2s8-3.22 8-8.2c0-3.32-2.67-7.25-8-11.8zm0 18c-3.35 0-6-2.57-6-6.2 0-2.34 1.95-5.44 6-9.14 4.05 3.7 6 6.79 6 9.14 0 3.63-2.65 6.2-6 6.2z" />
                </svg>
                <span>ON</span>
              </span>
            )}
            <div class={styles.metricValue}>
              <p class={`${styles.display} ${styles.humidity}`} aria-live="polite">
                {latest.humidity}
                <span class={styles.unit}>%</span>
              </p>
              <button
                type="button"
                class={styles.expandBtn}
                onClick={() => setOpenModal('humidity')}
                aria-label="Expand humidity chart"
              >
                <ExpandIcon />
              </button>
            </div>
          </div>
          <StatDisplay
            avg={stats.avg_humidity}
            min={stats.min_humidity}
            max={stats.max_humidity}
            unit="%"
          />
          <LineChart
            data={data}
            series={humiditySeries}
            yAxes={HUMIDITY_Y_AXES}
            thresholds={humidityThresholds}
            colorAxis={false}
            showArea={false}
            loading={loading}
          />
        </section>
      </div>

      <Modal
        isOpen={openModal === 'temperature'}
        onClose={closeModal}
        title="Temperature"
        scrollable
      >
        <LineChart
          data={data}
          series={tempSeries}
          yAxes={TEMP_Y_AXES}
          thresholds={tempThresholds}
          colorAxis={false}
          showArea={false}
          height={350}
        />
      </Modal>

      <Modal isOpen={openModal === 'humidity'} onClose={closeModal} title="Humidity" scrollable>
        <LineChart
          data={data}
          series={humiditySeries}
          yAxes={HUMIDITY_Y_AXES}
          thresholds={humidityThresholds}
          colorAxis={false}
          showArea={false}
          height={350}
        />
      </Modal>
    </article>
  );
}

import { useCallback, useMemo, useState } from 'preact/hooks';
import { cssVar, LineChart, type SeriesConfig, type ThresholdLine } from '@/components/LineChart';
import { Modal } from '@/components/Modal';
import { WarningBadge } from '@/components/WarningBadge';
import type { PicoChartDataPoint, PicoReading, Thresholds } from '@/types';
import styles from './PicoCard.module.css';

const Y_AXES = [{ position: 'left' as const, min: 0, max: 100 }];

const formatPlantLabel = (plantId: number | string): string => `Plant ${plantId}`;

interface PicoCardProps {
  latest: PicoReading[];
  chartData: PicoChartDataPoint[];
  thresholds: Thresholds | null;
  loading?: boolean;
}

function SectionHead({ recordingTime }: { recordingTime?: string }) {
  return (
    <div class={styles.sectionHead}>
      <h2 id="pico-card-header" class={styles.heading}>
        Soil moisture
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

export function PicoCard({ latest, chartData, thresholds, loading = false }: PicoCardProps) {
  const [openPlantId, setOpenPlantId] = useState<number | string | null>(null);

  const closeModal = useCallback(() => setOpenPlantId(null), []);

  const data = useMemo(() => chartData as unknown as Record<string, number>[], [chartData]);

  const plantColor = useMemo(() => cssVar('--color-moisture'), []);
  const alertColor = useMemo(() => `${cssVar('--color-alert')}99`, []);

  const sortedLatest = useMemo(
    () => [...latest].sort((a, b) => Number(a.plant_id) - Number(b.plant_id)),
    [latest],
  );

  const getMoistureStatus = (plantId: number | string, moisture: number): 'ok' | 'alert' => {
    if (!thresholds) return 'ok';
    const minThreshold = thresholds.moisture[plantId] ?? 30;
    return moisture < minThreshold ? 'alert' : 'ok';
  };

  const getPlantThresholds = (plantId: number | string): ThresholdLine[] => {
    if (!thresholds) return [];
    const minThreshold = thresholds.moisture[plantId] ?? 30;
    return [
      {
        value: minThreshold,
        label: `Min ${minThreshold}%`,
        color: alertColor,
        yAxisIndex: 0,
        type: 'min',
      },
    ];
  };

  const getPlantSeries = (plantId: number | string): SeriesConfig[] => [
    {
      name: formatPlantLabel(plantId),
      dataKey: String(plantId),
      color: plantColor,
      yAxisIndex: 0,
    },
  ];

  if (!latest.length) {
    return (
      <article class={styles.section} aria-labelledby="pico-card-header">
        <SectionHead />
        <p class={styles.noData}>No data available</p>
      </article>
    );
  }

  const openPlant = latest.find((p) => p.plant_id === openPlantId);

  return (
    <article class={styles.section} aria-labelledby="pico-card-header">
      <SectionHead recordingTime={latest[0]?.recording_time} />
      <div class={styles.metrics}>
        {sortedLatest.map((plant) => {
          const status = getMoistureStatus(plant.plant_id, plant.moisture);
          const label = formatPlantLabel(plant.plant_id);
          return (
            <section key={plant.plant_id} class={styles.metric} aria-label={`${label} moisture`}>
              <div class={styles.metricTop}>
                <h3 class={styles.metricLabel}>{label}</h3>
                {status === 'alert' && <WarningBadge>Thirsty</WarningBadge>}
                <div class={styles.metricValue}>
                  <p class={`${styles.display} ${styles.moisture}`} aria-live="polite">
                    {plant.moisture}
                    <span class={styles.unit}>%</span>
                  </p>
                  <button
                    type="button"
                    class={styles.expandBtn}
                    onClick={() => setOpenPlantId(plant.plant_id)}
                    aria-label={`Expand ${label} chart`}
                  >
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
                  </button>
                </div>
              </div>
              <LineChart
                data={data}
                series={getPlantSeries(plant.plant_id)}
                yAxes={Y_AXES}
                thresholds={getPlantThresholds(plant.plant_id)}
                colorAxis={false}
                showArea={false}
                height={140}
                loading={loading}
              />
            </section>
          );
        })}
      </div>

      {openPlant && (
        <Modal
          isOpen={true}
          onClose={closeModal}
          title={formatPlantLabel(openPlant.plant_id)}
          scrollable
        >
          <LineChart
            data={data}
            series={getPlantSeries(openPlant.plant_id)}
            yAxes={Y_AXES}
            thresholds={getPlantThresholds(openPlant.plant_id)}
            colorAxis={false}
            showArea={false}
            height={350}
          />
        </Modal>
      )}
    </article>
  );
}

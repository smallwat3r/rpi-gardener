import { useMemo } from 'preact/hooks';
import type { PicoReading, PicoChartDataPoint, Thresholds } from '@/types';
import { LineChart, type SeriesConfig, type ThresholdLine } from '@/components/LineChart';
import { WarningBadge } from '@/components/WarningBadge';
import styles from './PicoCard.module.css';

const PLANT_COLOR = '#a78bfa';

const Y_AXES = [{ position: 'left' as const, min: 0, max: 100 }];

const ALERT_COLOR = '#ef4444';

const formatPlantLabel = (plantId: number | string): string => `Plant ${plantId}`;

interface PicoCardProps {
  latest: PicoReading[];
  chartData: PicoChartDataPoint[];
  thresholds: Thresholds | null;
}

export function PicoCard({ latest, chartData, thresholds }: PicoCardProps) {
  const data = useMemo(
    () => chartData as unknown as Record<string, number>[],
    [chartData]
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
      { value: minThreshold, label: `Min ${minThreshold}%`, color: ALERT_COLOR, yAxisIndex: 0, type: 'min' },
    ];
  };

  const getPlantSeries = (plantId: number | string): SeriesConfig[] => [
    {
      name: formatPlantLabel(plantId),
      dataKey: String(plantId),
      color: PLANT_COLOR,
      yAxisIndex: 0,
    },
  ];

  if (!latest.length) {
    return (
      <article class={styles.card} aria-labelledby="pico-card-header">
        <h2 id="pico-card-header" class={styles.header}>Soil Moisture</h2>
        <div class={styles.body}>
          <p class={styles.noData}>No data available</p>
        </div>
      </article>
    );
  }

  return (
    <article class={styles.card} aria-labelledby="pico-card-header">
      <h2 id="pico-card-header" class={styles.header}>Soil Moisture</h2>
      <div class={styles.body}>
        <p class={styles.lastUpdate}>Last update: <time>{latest[0]?.recording_time}</time> UTC</p>
        <div class={styles.charts}>
          {latest.map((plant) => {
            const status = getMoistureStatus(plant.plant_id, plant.moisture);
            const label = formatPlantLabel(plant.plant_id);
            return (
              <section key={plant.plant_id} class={styles.chartSection} aria-label={`${label} moisture`}>
                <div class={styles.chartHeader}>
                  <h3 style={{ color: PLANT_COLOR }}>{label}</h3>
                  <p class={styles.display} style={{ color: PLANT_COLOR }} aria-live="polite">
                    {plant.moisture}%
                  </p>
                  {status === 'alert' && <WarningBadge>Needs water</WarningBadge>}
                </div>
                <LineChart
                  data={data}
                  series={getPlantSeries(plant.plant_id)}
                  yAxes={Y_AXES}
                  thresholds={getPlantThresholds(plant.plant_id)}
                  colorAxis={false}
                  showArea={false}
                  height={110}
                />
              </section>
            );
          })}
        </div>
      </div>
    </article>
  );
}

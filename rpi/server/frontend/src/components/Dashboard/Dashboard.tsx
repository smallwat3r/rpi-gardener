import { useDashboard } from '@/hooks/useDashboard';
import { DHTCard } from '@/components/DHTCard';
import { PicoCard } from '@/components/PicoCard';
import { HoursFilter } from '@/components/HoursFilter';
import styles from './Dashboard.module.css';

export function Dashboard() {
  const { data, thresholds, loading, error, hours, setHours } = useDashboard();

  if (loading && !data) {
    return <div class={styles.loading}>Loading...</div>;
  }

  if (error) {
    return <div class={styles.error}>Error: {error}</div>;
  }

  if (!data) {
    return null;
  }

  return (
    <div class={styles.container}>
      <header class={styles.header}>
        <h1>Dashboard</h1>
      </header>

      <HoursFilter value={hours} onChange={setHours} />

      <div class={styles.grid}>
        <DHTCard
          latest={data.latest}
          stats={data.stats}
          chartData={data.data}
          thresholds={thresholds}
        />
        <PicoCard
          latest={data.pico_latest}
          chartData={data.pico_data}
          thresholds={thresholds}
        />
      </div>
    </div>
  );
}

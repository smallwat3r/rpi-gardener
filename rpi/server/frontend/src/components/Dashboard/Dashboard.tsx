import { useEffect, useRef } from 'preact/hooks';
import { DHTCard } from '@/components/DHTCard';
import { HoursFilter } from '@/components/HoursFilter';
import { PicoCard } from '@/components/PicoCard';
import { useDashboard } from '@/hooks/useDashboard';
import { useHumidifierStatus } from '@/hooks/useHumidifierStatus';
import styles from './Dashboard.module.css';

interface DashboardProps {
  onSettingsClick?: () => void;
  thresholdVersion?: number;
}

export function Dashboard({ onSettingsClick, thresholdVersion }: DashboardProps) {
  const { data, thresholds, loading, error, hours, setHours, refreshThresholds } = useDashboard();
  const { isOn: humidifierIsOn } = useHumidifierStatus();
  const isFirstRender = useRef(true);

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    refreshThresholds();
  }, [thresholdVersion, refreshThresholds]);

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
        <HoursFilter value={hours} onChange={setHours} disabled={loading} />
        {onSettingsClick && (
          <button
            type="button"
            class={styles.settingsButton}
            onClick={onSettingsClick}
            aria-label="Settings"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              role="img"
              aria-hidden="true"
            >
              <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          </button>
        )}
      </header>

      <div class={styles.grid}>
        <DHTCard
          latest={data.latest}
          stats={data.stats}
          chartData={data.data}
          thresholds={thresholds}
          loading={loading}
          humidifierIsOn={humidifierIsOn}
        />
        <PicoCard
          latest={data.pico_latest}
          chartData={data.pico_data}
          thresholds={thresholds}
          loading={loading}
        />
      </div>
    </div>
  );
}

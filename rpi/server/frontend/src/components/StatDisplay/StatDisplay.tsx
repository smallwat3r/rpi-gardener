import { memo } from 'preact/compat';
import styles from './StatDisplay.module.css';

interface StatDisplayProps {
  avg: number;
  min: number;
  max: number;
  unit: string;
}

export const StatDisplay = memo(function StatDisplay({ avg, min, max, unit }: StatDisplayProps) {
  return (
    <div class={styles.stats} role="group" aria-label="Statistics">
      <span class={styles.stat}>
        <span class={styles.statLabel}>avg</span> {avg}
        {unit}
      </span>
      <span class={styles.stat}>
        <span class={styles.statLabel}>min</span> {min}
      </span>
      <span class={styles.stat}>
        <span class={styles.statLabel}>max</span> {max}
      </span>
    </div>
  );
});

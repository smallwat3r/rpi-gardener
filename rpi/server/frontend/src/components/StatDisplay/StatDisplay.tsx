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
      <span class={styles.stat}>{avg}{unit}</span>
      <span class={styles.sep}>/</span>
      <span class={styles.stat}>{min}</span>
      <span class={styles.sep}>–</span>
      <span class={styles.stat}>{max}</span>
    </div>
  );
});

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
      <div>Avg: {avg}{unit}</div>
      <div>Min: {min}{unit}</div>
      <div>Max: {max}{unit}</div>
    </div>
  );
});

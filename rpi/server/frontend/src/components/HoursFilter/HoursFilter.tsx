import styles from './HoursFilter.module.css';

interface HoursFilterProps {
  value: number;
  onChange: (hours: number) => void;
}

const TIMEFRAMES = [
  { hours: 1, label: '1h' },
  { hours: 3, label: '3h' },
  { hours: 6, label: '6h' },
  { hours: 12, label: '12h' },
  { hours: 24, label: '24h' },
  { hours: 72, label: '3d' },
];

export function HoursFilter({ value, onChange }: HoursFilterProps) {
  return (
    <div class={styles.container}>
      {TIMEFRAMES.map(({ hours, label }) => (
        <button
          key={hours}
          type="button"
          class={`${styles.button} ${value === hours ? styles.active : ''}`}
          onClick={() => onChange(hours)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

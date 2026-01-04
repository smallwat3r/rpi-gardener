import styles from './HoursFilter.module.css';

interface HoursFilterProps {
  value: number;
  onChange: (hours: number) => void;
  disabled?: boolean;
}

const TIMEFRAMES = [
  { hours: 1, label: '1h' },
  { hours: 6, label: '6h' },
  { hours: 12, label: '12h' },
  { hours: 24, label: '24h' },
  { hours: 72, label: '3d' },
  { hours: 168, label: '7d' },
];

export function HoursFilter({ value, onChange, disabled = false }: HoursFilterProps) {
  return (
    <div class={`${styles.container} ${disabled ? styles.disabled : ''}`}>
      {TIMEFRAMES.map(({ hours, label }) => (
        <button
          key={hours}
          type="button"
          class={`${styles.button} ${value === hours ? styles.active : ''}`}
          onClick={() => onChange(hours)}
          disabled={disabled}
          aria-disabled={disabled}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

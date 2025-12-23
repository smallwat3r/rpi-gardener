import { useState } from 'preact/hooks';
import styles from './HoursFilter.module.css';

interface HoursFilterProps {
  value: number;
  onChange: (hours: number) => void;
}

export function HoursFilter({ value, onChange }: HoursFilterProps) {
  const [inputValue, setInputValue] = useState(value.toString());

  const handleSubmit = (e: Event) => {
    e.preventDefault();
    const hours = Math.min(24, Math.max(1, parseInt(inputValue) || 3));
    setInputValue(hours.toString());
    onChange(hours);
  };

  return (
    <form class={styles.form} onSubmit={handleSubmit}>
      <label class={styles.label} htmlFor="hours">Hours ago</label>
      <input
        type="number"
        id="hours"
        min="1"
        max="24"
        class={styles.input}
        value={inputValue}
        onInput={(e) => setInputValue((e.target as HTMLInputElement).value)}
      />
      <button type="submit" class={styles.button}>Update</button>
    </form>
  );
}

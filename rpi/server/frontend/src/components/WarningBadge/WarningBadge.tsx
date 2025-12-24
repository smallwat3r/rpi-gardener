import styles from './WarningBadge.module.css';

interface WarningBadgeProps {
  children: string;
}

export function WarningBadge({ children }: WarningBadgeProps) {
  return (
    <span class={styles.badge}>
      <svg class={styles.icon} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M12 2L1 21h22L12 2zm0 3.5L19.5 19h-15L12 5.5zM11 10v4h2v-4h-2zm0 6v2h2v-2h-2z" />
      </svg>
      <span>{children}</span>
    </span>
  );
}

import { useCallback, useEffect, useRef, useState } from 'preact/hooks';
import { getAdminSettings, updateAdminSettings } from '@/api/admin';
import type { AdminSettings as AdminSettingsType } from '@/types';
import styles from './AdminSettings.module.css';

interface AdminSettingsProps {
  onClose: () => void;
  onSave: () => void;
}

const defaultSettings: AdminSettingsType = {
  thresholds: {
    temperature: { min: 18, max: 25 },
    humidity: { min: 40, max: 65 },
    moisture: { default: 30, 1: 30, 2: 30, 3: 30 },
  },
  notifications: {
    enabled: false,
    backends: [],
  },
  cleanup: {
    retentionDays: 3,
  },
};

export function AdminSettings({ onClose, onSave }: AdminSettingsProps) {
  const [settings, setSettings] = useState<AdminSettingsType>(defaultSettings);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notConfigured, setNotConfigured] = useState(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    getAdminSettings()
      .then((data) => {
        if (mountedRef.current) {
          setSettings(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (mountedRef.current) {
          if (err.message === 'Unauthorized') {
            // Auth failed or was cancelled - close modal
            onClose();
          } else if (err.message === 'Admin not configured') {
            setNotConfigured(true);
            setLoading(false);
          } else {
            setError(err.message);
            setLoading(false);
          }
        }
      });
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError(null);
    try {
      await updateAdminSettings(settings);
      if (!mountedRef.current) return;
      onSave();
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err.message : 'Failed to save settings');
    } finally {
      if (mountedRef.current) setSaving(false);
    }
  }, [settings, onSave]);

  const updateThreshold = useCallback(
    (category: 'temperature' | 'humidity', field: 'min' | 'max', value: string) => {
      const numValue = Number.parseInt(value, 10);
      if (Number.isNaN(numValue)) return;
      setSettings((prev) => ({
        ...prev,
        thresholds: {
          ...prev.thresholds,
          [category]: {
            ...prev.thresholds[category],
            [field]: numValue,
          },
        },
      }));
    },
    [],
  );

  const updateMoisture = useCallback((key: 'default' | '1' | '2' | '3', value: string) => {
    const numValue = Number.parseInt(value, 10);
    if (Number.isNaN(numValue)) return;
    setSettings((prev) => ({
      ...prev,
      thresholds: {
        ...prev.thresholds,
        moisture: {
          ...prev.thresholds.moisture,
          [key]: numValue,
        },
      },
    }));
  }, []);

  const updateNotificationEnabled = useCallback((enabled: boolean) => {
    setSettings((prev) => ({
      ...prev,
      notifications: {
        ...prev.notifications,
        enabled,
      },
    }));
  }, []);

  const updateBackend = useCallback((backend: string, enabled: boolean) => {
    setSettings((prev) => ({
      ...prev,
      notifications: {
        ...prev.notifications,
        backends: enabled
          ? [...prev.notifications.backends, backend]
          : prev.notifications.backends.filter((b) => b !== backend),
      },
    }));
  }, []);

  const updateRetention = useCallback((value: string) => {
    const numValue = Number.parseInt(value, 10);
    if (Number.isNaN(numValue)) return;
    setSettings((prev) => ({
      ...prev,
      cleanup: {
        retentionDays: numValue,
      },
    }));
  }, []);

  if (loading) {
    return <div class={styles.loading}>Loading settings...</div>;
  }

  if (notConfigured) {
    return <div class={styles.notConfigured}>Admin not configured. Set ADMIN_PASSWORD in .env</div>;
  }

  return (
    <div class={styles.container}>
      <section class={styles.section}>
        <h3 class={styles.sectionTitle}>Temperature Thresholds</h3>
        <div class={styles.row}>
          <label class={styles.field}>
            <span class={styles.label}>Min</span>
            <input
              type="number"
              class={styles.input}
              value={settings.thresholds.temperature.min}
              onInput={(e) =>
                updateThreshold('temperature', 'min', (e.target as HTMLInputElement).value)
              }
              min={-40}
              max={80}
            />
          </label>
          <label class={styles.field}>
            <span class={styles.label}>Max</span>
            <input
              type="number"
              class={styles.input}
              value={settings.thresholds.temperature.max}
              onInput={(e) =>
                updateThreshold('temperature', 'max', (e.target as HTMLInputElement).value)
              }
              min={-40}
              max={80}
            />
          </label>
        </div>
      </section>

      <section class={styles.section}>
        <h3 class={styles.sectionTitle}>Humidity Thresholds</h3>
        <div class={styles.row}>
          <label class={styles.field}>
            <span class={styles.label}>Min (%)</span>
            <input
              type="number"
              class={styles.input}
              value={settings.thresholds.humidity.min}
              onInput={(e) =>
                updateThreshold('humidity', 'min', (e.target as HTMLInputElement).value)
              }
              min={0}
              max={100}
            />
          </label>
          <label class={styles.field}>
            <span class={styles.label}>Max (%)</span>
            <input
              type="number"
              class={styles.input}
              value={settings.thresholds.humidity.max}
              onInput={(e) =>
                updateThreshold('humidity', 'max', (e.target as HTMLInputElement).value)
              }
              min={0}
              max={100}
            />
          </label>
        </div>
      </section>

      <section class={styles.section}>
        <h3 class={styles.sectionTitle}>Moisture Thresholds (%)</h3>
        <div class={styles.grid}>
          <label class={styles.field}>
            <span class={styles.label}>Default</span>
            <input
              type="number"
              class={styles.input}
              value={settings.thresholds.moisture.default}
              onInput={(e) => updateMoisture('default', (e.target as HTMLInputElement).value)}
              min={0}
              max={100}
            />
          </label>
          <label class={styles.field}>
            <span class={styles.label}>Plant 1</span>
            <input
              type="number"
              class={styles.input}
              value={settings.thresholds.moisture[1]}
              onInput={(e) => updateMoisture('1', (e.target as HTMLInputElement).value)}
              min={0}
              max={100}
            />
          </label>
          <label class={styles.field}>
            <span class={styles.label}>Plant 2</span>
            <input
              type="number"
              class={styles.input}
              value={settings.thresholds.moisture[2]}
              onInput={(e) => updateMoisture('2', (e.target as HTMLInputElement).value)}
              min={0}
              max={100}
            />
          </label>
          <label class={styles.field}>
            <span class={styles.label}>Plant 3</span>
            <input
              type="number"
              class={styles.input}
              value={settings.thresholds.moisture[3]}
              onInput={(e) => updateMoisture('3', (e.target as HTMLInputElement).value)}
              min={0}
              max={100}
            />
          </label>
        </div>
      </section>

      <section class={styles.section}>
        <h3 class={styles.sectionTitle}>Notifications</h3>
        <div class={styles.toggle}>
          <label class={styles.toggleLabel}>
            <input
              type="checkbox"
              checked={settings.notifications.enabled}
              onChange={(e) => updateNotificationEnabled((e.target as HTMLInputElement).checked)}
            />
            <span>Enable notifications</span>
          </label>
        </div>
        <div class={styles.checkboxGroup}>
          <label class={styles.checkbox}>
            <input
              type="checkbox"
              checked={settings.notifications.backends.includes('gmail')}
              onChange={(e) => updateBackend('gmail', (e.target as HTMLInputElement).checked)}
              disabled={!settings.notifications.enabled}
            />
            <span>Gmail</span>
          </label>
          <label class={styles.checkbox}>
            <input
              type="checkbox"
              checked={settings.notifications.backends.includes('slack')}
              onChange={(e) => updateBackend('slack', (e.target as HTMLInputElement).checked)}
              disabled={!settings.notifications.enabled}
            />
            <span>Slack</span>
          </label>
        </div>
      </section>

      <section class={styles.section}>
        <h3 class={styles.sectionTitle}>Data Retention</h3>
        <label class={styles.field}>
          <span class={styles.label}>Keep data for (days)</span>
          <input
            type="number"
            class={styles.input}
            value={settings.cleanup.retentionDays}
            onInput={(e) => updateRetention((e.target as HTMLInputElement).value)}
            min={1}
            max={365}
          />
        </label>
      </section>

      {error && <div class={styles.error}>{error}</div>}

      <div class={styles.actions}>
        <button type="button" class={styles.saveButton} onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
      </div>
    </div>
  );
}

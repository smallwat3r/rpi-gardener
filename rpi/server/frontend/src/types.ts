export interface DHTReading {
  temperature: number;
  humidity: number;
  recording_time: string;
  epoch: number;
}

export interface DHTStats {
  avg_temperature: number;
  min_temperature: number;
  max_temperature: number;
  avg_humidity: number;
  min_humidity: number;
  max_humidity: number;
}

export interface PicoReading {
  plant_id: number;
  moisture: number;
  recording_time: string;
  epoch: number;
}

export interface PicoChartDataPoint {
  epoch: number;
  [plantId: string]: number;
}

/** Shape of /api/dashboard. Chart arrays are bucketed to ~500 points. */
export interface DashboardData {
  hours: number;
  bucket_sec: number;
  data: DHTReading[];
  latest: DHTReading | null;
  pico_data: PicoChartDataPoint[];
  pico_latest: PicoReading[];
}

/** Dashboard data plus stats derived client side from the chart data. */
export interface DashboardView extends DashboardData {
  stats: DHTStats | null;
}

export interface Thresholds {
  temperature: { min: number; max: number };
  humidity: { min: number; max: number };
  moisture: Record<string, number>;
}

export interface HumidifierState {
  type: string;
  is_on: boolean;
  recording_time: string;
}

export interface AdminSettings {
  thresholds: {
    temperature: { min: number; max: number };
    humidity: { min: number; max: number };
    moisture: { default: number; 1: number; 2: number; 3: number };
  };
  notifications: {
    enabled: boolean;
    backends: string[];
  };
  cleanup: {
    retentionDays: number;
  };
}

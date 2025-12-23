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
  plant_id: string;
  moisture: number;
  recording_time: string;
  epoch: number;
}

export interface PicoChartDataPoint {
  epoch: number;
  [plantId: string]: number;
}

export interface DashboardData {
  hours: number;
  data: DHTReading[];
  stats: DHTStats;
  latest: DHTReading;
  pico_data: PicoChartDataPoint[];
  pico_latest: PicoReading[];
}

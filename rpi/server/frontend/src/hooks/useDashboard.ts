import { useCallback, useEffect, useMemo, useRef, useState } from 'preact/hooks';
import { fetchDashboardData, fetchThresholds } from '@/api/dashboard';
import type {
  DashboardData,
  DHTReading,
  DHTStats,
  PicoChartDataPoint,
  PicoReading,
  Thresholds,
} from '@/types';
import { useWebSocket } from './useWebSocket';

export function useDashboard(initialHours: number = 3) {
  const [hours, setHours] = useState(initialHours);
  const [data, setData] = useState<DashboardData | null>(null);
  const [thresholds, setThresholds] = useState<Thresholds | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const lastDhtEpoch = useRef<number | null>(null);
  const lastPicoEpoch = useRef<number | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    fetchThresholds()
      .then((t) => {
        if (mountedRef.current) setThresholds(t);
      })
      .catch(() => {});
  }, []);

  const loadData = useCallback(async () => {
    if (!mountedRef.current) return;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchDashboardData(hours);
      if (!mountedRef.current) return;
      setData(result);
      lastDhtEpoch.current = result.latest?.epoch ?? null;
      lastPicoEpoch.current = result.pico_latest[0]?.epoch ?? null;
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [hours]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleDhtLatest = useCallback(
    (reading: DHTReading | null) => {
      if (!reading || reading.epoch === lastDhtEpoch.current) return;
      lastDhtEpoch.current = reading.epoch;
      setData((prev) => {
        if (!prev) return prev;
        const cutoff = Date.now() - hours * 60 * 60 * 1000;
        const newChartData = [...prev.data.filter((r) => r.epoch >= cutoff), reading];
        return { ...prev, latest: reading, data: newChartData };
      });
    },
    [hours],
  );

  const handlePicoLatest = useCallback((picoReadings: PicoReading[] | null) => {
    if (!picoReadings?.length || picoReadings[0].epoch === lastPicoEpoch.current) return;
    lastPicoEpoch.current = picoReadings[0].epoch;
    setData((prev) => {
      if (!prev) return prev;

      const newPicoChartPoint: PicoChartDataPoint = { epoch: picoReadings[0].epoch };
      picoReadings.forEach((r) => {
        newPicoChartPoint[r.plant_id] = r.moisture;
      });

      const newPicoData: PicoChartDataPoint[] = [newPicoChartPoint, ...prev.pico_data.slice(0, -1)];
      return { ...prev, pico_latest: picoReadings, pico_data: newPicoData };
    });
  }, []);

  const stats = useMemo<DHTStats | null>(() => {
    if (!data?.data.length) return null;
    const cutoff = Date.now() - hours * 60 * 60 * 1000;
    const readings = data.data.filter((r) => r.epoch >= cutoff);
    if (!readings.length) return null;

    const temps = readings.map((r) => r.temperature);
    const hums = readings.map((r) => r.humidity);
    const sum = (arr: number[]) => arr.reduce((a, b) => a + b, 0);
    const round = (n: number, d: number) => Math.round(n * 10 ** d) / 10 ** d;

    return {
      avg_temperature: round(sum(temps) / temps.length, 2),
      min_temperature: Math.min(...temps),
      max_temperature: Math.max(...temps),
      avg_humidity: round(sum(hums) / hums.length, 2),
      min_humidity: Math.min(...hums),
      max_humidity: Math.max(...hums),
    };
  }, [data?.data, hours]);

  useWebSocket<DHTReading>({
    url: '/dht/latest',
    onMessage: handleDhtLatest,
  });

  useWebSocket<PicoReading[]>({
    url: '/pico/latest',
    onMessage: handlePicoLatest,
  });

  const dashboardData = useMemo<DashboardData | null>(() => {
    if (!data) return null;
    return { ...data, stats };
  }, [data, stats]);

  return { data: dashboardData, thresholds, loading, error, hours, setHours, refresh: loadData };
}

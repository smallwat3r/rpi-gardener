import { useState, useEffect, useCallback, useRef } from 'preact/hooks';
import { fetchDashboardData } from '@/api/dashboard';
import { useWebSocket } from './useWebSocket';
import type { DashboardData, DHTReading, DHTStats, PicoChartDataPoint, PicoReading } from '@/types';

export function useDashboard(initialHours: number = 3) {
  const [hours, setHours] = useState(initialHours);
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const lastDhtEpoch = useRef<number | null>(null);
  const lastPicoEpoch = useRef<number | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
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

  const handleDhtLatest = useCallback((reading: DHTReading | null) => {
    if (!reading || reading.epoch === lastDhtEpoch.current) return;
    lastDhtEpoch.current = reading.epoch;
    setData((prev) => {
      if (!prev) return prev;
      const newChartData = [reading, ...prev.data.slice(0, -1)];
      return { ...prev, latest: reading, data: newChartData };
    });
  }, []);

  const handleDhtStats = useCallback((stats: DHTStats | null) => {
    if (!stats) return;
    setData((prev) => (prev ? { ...prev, stats } : prev));
  }, []);

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

  useWebSocket<DHTReading>({
    url: '/dht/latest',
    onMessage: handleDhtLatest,
  });

  useWebSocket<DHTStats>({
    url: `/dht/stats?hours=${hours}`,
    onMessage: handleDhtStats,
  });

  useWebSocket<PicoReading[]>({
    url: '/pico/latest',
    onMessage: handlePicoLatest,
  });

  return { data, loading, error, hours, setHours, refresh: loadData };
}

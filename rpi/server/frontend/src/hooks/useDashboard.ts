import { useCallback, useEffect, useMemo, useRef, useState } from 'preact/hooks';
import { fetchDashboardData, fetchThresholds } from '@/api/dashboard';
import type {
  DashboardData,
  DashboardView,
  DHTReading,
  DHTStats,
  PicoChartDataPoint,
  PicoReading,
  Thresholds,
} from '@/types';
import { useSSE } from './useSSE';

/**
 * Merge a live reading into bucketed chart data. Within the current bucket
 * the head point is replaced, so the array stays at ~500 points however
 * long the page is open. A new bucket prepends.
 */
function mergeLive<T extends { epoch: number }>(
  points: T[],
  point: T,
  bucketSec: number,
  hours: number,
): T[] {
  const bucketMs = bucketSec * 1000;
  const head = points[0];
  const sameBucket =
    head && Math.floor(head.epoch / bucketMs) === Math.floor(point.epoch / bucketMs);
  const rest = sameBucket ? points.slice(1) : points;
  const cutoff = Date.now() - hours * 60 * 60 * 1000;
  return [point, ...rest.filter((p) => p.epoch >= cutoff)];
}

function computeStats(readings: DHTReading[]): DHTStats | null {
  if (!readings.length) return null;
  let tSum = 0;
  let tMin = Number.POSITIVE_INFINITY;
  let tMax = Number.NEGATIVE_INFINITY;
  let hSum = 0;
  let hMin = Number.POSITIVE_INFINITY;
  let hMax = Number.NEGATIVE_INFINITY;
  for (const r of readings) {
    tSum += r.temperature;
    tMin = Math.min(tMin, r.temperature);
    tMax = Math.max(tMax, r.temperature);
    hSum += r.humidity;
    hMin = Math.min(hMin, r.humidity);
    hMax = Math.max(hMax, r.humidity);
  }
  const round1 = (n: number) => Math.round(n * 10) / 10;
  return {
    avg_temperature: round1(tSum / readings.length),
    min_temperature: tMin,
    max_temperature: tMax,
    avg_humidity: round1(hSum / readings.length),
    min_humidity: hMin,
    max_humidity: hMax,
  };
}

export function useDashboard(initialHours: number = 24) {
  const [hours, setHours] = useState(initialHours);
  const [data, setData] = useState<DashboardData | null>(null);
  const [thresholds, setThresholds] = useState<Thresholds | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const lastDhtEpoch = useRef<number | null>(null);
  const lastPicoEpoch = useRef<number | null>(null);
  const mountedRef = useRef(true);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      abortControllerRef.current?.abort();
    };
  }, []);

  const refreshThresholds = useCallback(() => {
    fetchThresholds()
      .then((t) => {
        if (mountedRef.current) setThresholds(t);
      })
      .catch(() => {
        // Ignore errors - thresholds are non-critical
      });
  }, []);

  useEffect(() => {
    refreshThresholds();
  }, [refreshThresholds]);

  const loadData = useCallback(async () => {
    if (!mountedRef.current) return;

    // Cancel any in-flight request
    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();

    setLoading(true);
    setError(null);
    try {
      const result = await fetchDashboardData(hours, abortControllerRef.current.signal);
      if (!mountedRef.current) return;
      setData(result);
      lastDhtEpoch.current = result.latest?.epoch ?? null;
      lastPicoEpoch.current = result.pico_latest[0]?.epoch ?? null;
    } catch (err) {
      if (!mountedRef.current) return;
      // Ignore abort errors
      if (err instanceof Error && err.name === 'AbortError') return;
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

  // Retry while the API is down, so a page opened mid-deploy recovers by itself
  useEffect(() => {
    if (!error) return;
    const timer = window.setTimeout(loadData, 5000);
    return () => clearTimeout(timer);
  }, [error, loadData]);

  const handleDhtLatest = useCallback(
    (reading: DHTReading | null) => {
      if (!reading || reading.epoch === lastDhtEpoch.current) return;
      lastDhtEpoch.current = reading.epoch;
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          latest: reading,
          data: mergeLive(prev.data, reading, prev.bucket_sec, hours),
        };
      });
    },
    [hours],
  );

  const handlePicoLatest = useCallback(
    (picoReadings: PicoReading[] | null) => {
      if (!picoReadings?.length || picoReadings[0].epoch === lastPicoEpoch.current) return;
      lastPicoEpoch.current = picoReadings[0].epoch;
      setData((prev) => {
        if (!prev) return prev;
        const point: PicoChartDataPoint = { epoch: picoReadings[0].epoch };
        for (const r of picoReadings) {
          point[r.plant_id] = r.moisture;
        }
        return {
          ...prev,
          pico_latest: picoReadings,
          pico_data: mergeLive(prev.pico_data, point, prev.bucket_sec, hours),
        };
      });
    },
    [hours],
  );

  const stats = useMemo(() => computeStats(data?.data ?? []), [data?.data]);

  useSSE<DHTReading>({
    url: '/sse/dht/latest',
    onMessage: handleDhtLatest,
  });

  useSSE<PicoReading[]>({
    url: '/sse/pico/latest',
    onMessage: handlePicoLatest,
  });

  const dashboardData = useMemo<DashboardView | null>(() => {
    if (!data) return null;
    return { ...data, stats };
  }, [data, stats]);

  return {
    data: dashboardData,
    thresholds,
    loading,
    error,
    hours,
    setHours,
    refresh: loadData,
    refreshThresholds,
  };
}

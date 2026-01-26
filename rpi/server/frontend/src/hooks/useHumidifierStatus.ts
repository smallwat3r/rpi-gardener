import { useCallback, useState } from 'preact/hooks';
import type { HumidifierState } from '../types';
import { useSSE } from './useSSE';

export function useHumidifierStatus() {
  const [state, setState] = useState<HumidifierState | null>(null);

  const handleMessage = useCallback((data: HumidifierState) => {
    setState(data);
  }, []);

  useSSE<HumidifierState>({
    url: '/sse/humidifier/state',
    onMessage: handleMessage,
  });

  return {
    isOn: state?.is_on ?? null,
    lastUpdate: state?.recording_time ?? null,
  };
}

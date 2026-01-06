import { useCallback, useState } from 'preact/hooks';
import type { HumidifierState } from '../types';
import { useWebSocket } from './useWebSocket';

type HumidifierMessage = HumidifierState | { type: 'ping' };

function isHumidifierState(msg: HumidifierMessage): msg is HumidifierState {
  return 'is_on' in msg;
}

export function useHumidifierStatus() {
  const [state, setState] = useState<HumidifierState | null>(null);

  const handleMessage = useCallback((data: HumidifierMessage) => {
    if (isHumidifierState(data)) {
      setState(data);
    }
  }, []);

  useWebSocket<HumidifierMessage>({
    url: '/humidifier/state',
    onMessage: handleMessage,
  });

  return {
    isOn: state?.is_on ?? null,
    lastUpdate: state?.recording_time ?? null,
  };
}

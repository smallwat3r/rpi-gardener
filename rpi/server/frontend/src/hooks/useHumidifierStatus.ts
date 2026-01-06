import type { HumidifierState } from '../types';
import { useWebSocket } from './useWebSocket';

export function useHumidifierStatus() {
  const { lastMessage } = useWebSocket<HumidifierState>({
    url: '/humidifier/state',
  });

  return {
    isOn: lastMessage?.is_on ?? null,
    lastUpdate: lastMessage?.recording_time ?? null,
  };
}

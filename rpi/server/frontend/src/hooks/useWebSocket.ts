import { useEffect, useRef, useState } from 'preact/hooks';

interface UseWebSocketOptions<T> {
  url: string;
  onMessage?: (data: T) => void;
  initialReconnectDelay?: number;
  maxReconnectDelay?: number;
}

const DEFAULT_INITIAL_DELAY = 1000;
const DEFAULT_MAX_DELAY = 30000;

export function useWebSocket<T>({
  url,
  onMessage,
  initialReconnectDelay = DEFAULT_INITIAL_DELAY,
  maxReconnectDelay = DEFAULT_MAX_DELAY,
}: UseWebSocketOptions<T>) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<T | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectDelayRef = useRef(initialReconnectDelay);
  const onMessageRef = useRef(onMessage);
  const mountedRef = useRef(true);

  onMessageRef.current = onMessage;

  useEffect(() => {
    mountedRef.current = true;
    reconnectDelayRef.current = initialReconnectDelay;

    const connect = () => {
      if (!mountedRef.current) return;

      const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(`${protocol}//${location.host}${url}`);

      ws.onopen = () => {
        if (mountedRef.current) {
          setIsConnected(true);
          // Reset delay on successful connection
          reconnectDelayRef.current = initialReconnectDelay;
        }
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;
        const data = JSON.parse(event.data) as T;
        setLastMessage(data);
        onMessageRef.current?.(data);
      };

      ws.onclose = () => {
        if (mountedRef.current) {
          setIsConnected(false);
          // Exponential backoff: double delay up to max
          const delay = reconnectDelayRef.current;
          reconnectDelayRef.current = Math.min(delay * 2, maxReconnectDelay);
          reconnectTimeoutRef.current = window.setTimeout(connect, delay);
        }
      };

      ws.onerror = () => {
        ws.close();
      };

      wsRef.current = ws;
    };

    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.onopen = null;
        wsRef.current.onmessage = null;
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [url, initialReconnectDelay, maxReconnectDelay]);

  return { isConnected, lastMessage };
}

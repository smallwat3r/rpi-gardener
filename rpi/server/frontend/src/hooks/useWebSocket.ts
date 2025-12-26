import { useEffect, useRef, useState } from 'preact/hooks';

interface UseWebSocketOptions<T> {
  url: string;
  onMessage?: (data: T) => void;
  reconnectInterval?: number;
}

export function useWebSocket<T>({
  url,
  onMessage,
  reconnectInterval = 3000,
}: UseWebSocketOptions<T>) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<T | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const onMessageRef = useRef(onMessage);
  const mountedRef = useRef(true);

  onMessageRef.current = onMessage;

  useEffect(() => {
    mountedRef.current = true;

    const connect = () => {
      if (!mountedRef.current) return;

      const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(`${protocol}//${location.host}${url}`);

      ws.onopen = () => {
        if (mountedRef.current) {
          setIsConnected(true);
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
          reconnectTimeoutRef.current = window.setTimeout(connect, reconnectInterval);
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
  }, [url, reconnectInterval]);

  return { isConnected, lastMessage };
}

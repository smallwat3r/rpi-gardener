import { useEffect, useRef, useState } from 'preact/hooks';

interface UseSSEOptions<T> {
  url: string;
  onMessage?: (data: T) => void;
}

export function useSSE<T>({ url, onMessage }: UseSSEOptions<T>) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<T | null>(null);
  const onMessageRef = useRef(onMessage);
  const mountedRef = useRef(true);

  onMessageRef.current = onMessage;

  useEffect(() => {
    mountedRef.current = true;
    const eventSource = new EventSource(url);

    eventSource.onopen = () => {
      if (mountedRef.current) {
        setIsConnected(true);
      }
    };

    eventSource.onmessage = (event) => {
      if (!mountedRef.current) return;
      const data = JSON.parse(event.data) as T;
      setLastMessage(data);
      onMessageRef.current?.(data);
    };

    eventSource.onerror = () => {
      if (mountedRef.current) {
        setIsConnected(false);
      }
    };

    return () => {
      mountedRef.current = false;
      eventSource.close();
    };
  }, [url]);

  return { isConnected, lastMessage };
}

import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react';
import {
  resolveWsLiveUrlCandidates,
  resolveWsLiveUrl,
  wsFeatureEnabled,
} from '../utils';

type UseRunWebSocketArgs = {
  activeRunId: string | null;
  activeRunKey: string | null;
  onMessage: (payload: any) => void;
  setRuntimeNotice: Dispatch<SetStateAction<string>>;
  fallbackNotice: string;
  reconnectBaseMs: number;
  reconnectMaxMs: number;
  maxHandshakeAttempts: number;
};

export const useRunWebSocket = ({
  activeRunId,
  activeRunKey,
  onMessage,
  setRuntimeNotice,
  fallbackNotice,
  reconnectBaseMs,
  reconnectMaxMs,
  maxHandshakeAttempts,
}: UseRunWebSocketArgs) => {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onMessageRef = useRef(onMessage);
  const activeRunIdRef = useRef(activeRunId);
  const activeRunKeyRef = useRef(activeRunKey);
  const pollingFallbackRef = useRef(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isPollingFallback, setIsPollingFallback] = useState(false);

  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    activeRunIdRef.current = activeRunId;
    activeRunKeyRef.current = activeRunKey;
  }, [activeRunId, activeRunKey]);

  useEffect(() => {
    const sendSubscribe = (socket: WebSocket | null) => {
      if (!socket || socket.readyState !== WebSocket.OPEN) return;
      const runId = String(activeRunIdRef.current || '').trim();
      if (!runId) return;
      console.log(`Subscribing to run: ${runId}`);
      socket.send(
        JSON.stringify({
          type: 'subscribe',
          run_id: runId,
          run_key: activeRunKeyRef.current || null,
        }),
      );
    };

    let disposed = false;
    let connectAttempts = 0;
    const wsCandidates = resolveWsLiveUrlCandidates();

    if (!wsFeatureEnabled) {
      pollingFallbackRef.current = true;
      setIsPollingFallback(true);
      setIsConnected(true);
      return () => {};
    }

    const connectWs = () => {
      if (disposed || pollingFallbackRef.current) return;
      if (
        wsRef.current &&
        (wsRef.current.readyState === WebSocket.OPEN ||
          wsRef.current.readyState === WebSocket.CONNECTING)
      ) {
        return;
      }

      const wsUrl =
        wsCandidates[Math.min(connectAttempts, Math.max(0, wsCandidates.length - 1))] ||
        resolveWsLiveUrl();

      console.log('Connecting WebSocket...', wsUrl);
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch (_error) {
          // Ignore close errors during reconnect path.
        }
        wsRef.current = null;
      }

      const ws = new WebSocket(wsUrl);
      let openedOnce = false;
      wsRef.current = ws;

      ws.onopen = () => {
        if (disposed) {
          ws.close();
          return;
        }
        openedOnce = true;
        connectAttempts = 0;
        setIsConnected(true);
        setRuntimeNotice((prev) => (prev === fallbackNotice ? '' : prev));
        sendSubscribe(ws);
      };

      ws.onmessage = (event) => {
        if (disposed) return;
        try {
          const data = JSON.parse(event.data);
          onMessageRef.current(data);
        } catch (error) {
          console.error('Failed to parse WS message:', error);
        }
      };

      ws.onclose = () => {
        if (disposed) return;
        if (!openedOnce) {
          connectAttempts += 1;
          if (connectAttempts >= maxHandshakeAttempts) {
            pollingFallbackRef.current = true;
            setIsPollingFallback(true);
            setIsConnected(true);
            setRuntimeNotice((prev) => (prev ? prev : fallbackNotice));
            wsRef.current = null;
            return;
          }
          setIsConnected(false);
          const backoffMs = Math.min(
            reconnectMaxMs,
            reconnectBaseMs * 2 ** Math.max(0, connectAttempts - 1),
          );
          if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = setTimeout(connectWs, backoffMs);
          wsRef.current = null;
          return;
        }
        setIsConnected(false);
        wsRef.current = null;
        if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = setTimeout(connectWs, reconnectBaseMs);
      };

      ws.onerror = (error) => {
        if (!openedOnce) {
          console.warn(
            `WebSocket handshake failed for ${wsUrl}; retrying/falling back.`,
            error,
          );
          return;
        }
        console.warn('WebSocket error:', error);
      };
    };

    connectWs();

    return () => {
      disposed = true;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch (error) {
          console.debug('WS close during cleanup failed:', error);
        }
        wsRef.current = null;
      }
    };
  }, [
    fallbackNotice,
    maxHandshakeAttempts,
    reconnectBaseMs,
    reconnectMaxMs,
    setRuntimeNotice,
  ]);

  useEffect(() => {
    if (isPollingFallback || !isConnected) return;
    if (!activeRunId) return;
    if (wsRef.current?.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(
      JSON.stringify({
        type: 'subscribe',
        run_id: activeRunId,
        run_key: activeRunKey || null,
      }),
    );
  }, [activeRunId, activeRunKey, isConnected, isPollingFallback]);

  return {
    isConnected,
    isPollingFallback,
  };
};

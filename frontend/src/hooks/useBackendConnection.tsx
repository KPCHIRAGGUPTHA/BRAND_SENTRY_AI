import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
  ReactNode,
} from 'react';
import { fetchHealth } from '../services/api';
import { HealthResponse } from '../types/api';

export type ConnectionStatus =
  | 'connecting'
  | 'waking'
  | 'connected'
  | 'temporarily unavailable';

export interface BackendConnectionState {
  status: ConnectionStatus;
  data: HealthResponse | null;
  error: string | null;
  lastChecked: string | null;
  retryCount: number;
  isChecking: boolean;
  checkHealth: (isManual?: boolean) => Promise<void>;
}

export interface BackendConnectionConfig {
  maxWakingRetries?: number;
  initialRetryDelayMs?: number;
  maxRetryDelayMs?: number;
  connectedPollIntervalMs?: number;
  healthTimeoutMs?: number;
  fetchFn?: (signal?: AbortSignal, timeoutMs?: number) => Promise<HealthResponse>;
}

const DEFAULT_CONFIG: Required<BackendConnectionConfig> = {
  maxWakingRetries: 5,
  initialRetryDelayMs: 1000,
  maxRetryDelayMs: 15000,
  connectedPollIntervalMs: 60000,
  healthTimeoutMs: 10000,
  fetchFn: fetchHealth,
};

const BackendConnectionContext = createContext<BackendConnectionState | null>(null);

export function computeBackoffDelay(
  retryCount: number,
  initialDelay: number = 1000,
  maxDelay: number = 15000
): number {
  if (retryCount <= 0) return initialDelay;
  const delay = initialDelay * Math.pow(2, retryCount - 1);
  return Math.min(delay, maxDelay);
}

export const BackendConnectionProvider: React.FC<{
  children: ReactNode;
  config?: BackendConnectionConfig;
}> = ({ children, config: customConfig }) => {
  const config = useMemo(
    () => ({ ...DEFAULT_CONFIG, ...customConfig }),
    [
      customConfig?.maxWakingRetries,
      customConfig?.initialRetryDelayMs,
      customConfig?.maxRetryDelayMs,
      customConfig?.connectedPollIntervalMs,
      customConfig?.healthTimeoutMs,
      customConfig?.fetchFn,
    ]
  );

  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const [data, setData] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState<number>(0);
  const [isChecking, setIsChecking] = useState<boolean>(false);

  // References to handle unmounting, in-flight checks, and timers
  const isMountedRef = useRef<boolean>(true);
  const inFlightRef = useRef<boolean>(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const retryCountRef = useRef<number>(0);
  const statusRef = useRef<ConnectionStatus>('connecting');
  const executeHealthCheckRef = useRef<(isManual?: boolean) => Promise<void>>(
    async () => {}
  );

  useEffect(() => {
    retryCountRef.current = retryCount;
  }, [retryCount]);

  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  const clearScheduledTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const scheduleNextCheck = useCallback(
    (delayMs: number, _reason?: 'retry' | 'heartbeat') => {
      clearScheduledTimer();
      // If tab is currently hidden, pause polling
      if (typeof document !== 'undefined' && document.hidden) {
        return;
      }
      timerRef.current = setTimeout(() => {
        if (isMountedRef.current) {
          executeHealthCheckRef.current(false);
        }
      }, delayMs);
    },
    [clearScheduledTimer]
  );

  const executeHealthCheck = useCallback(
    async (isManual: boolean = false) => {
      // Prevent overlapping concurrent health checks
      if (inFlightRef.current) {
        return;
      }

      clearScheduledTimer();
      inFlightRef.current = true;
      if (isMountedRef.current) {
        setIsChecking(true);
      }

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const result = await config.fetchFn(
          controller.signal,
          config.healthTimeoutMs
        );

        if (!isMountedRef.current) return;

        // Health check succeeded
        setData(result);
        setError(null);
        setStatus('connected');
        setRetryCount(0);
        retryCountRef.current = 0;
        setLastChecked(new Date().toLocaleTimeString());

        // Schedule next relaxed heartbeat check
        scheduleNextCheck(config.connectedPollIntervalMs, 'heartbeat');
      } catch (err: unknown) {
        if (!isMountedRef.current) return;

        // Ignore aborted requests caused by unmount
        if (controller.signal.aborted && !isManual) {
          return;
        }

        const newRetries = retryCountRef.current + 1;
        retryCountRef.current = newRetries;
        setRetryCount(newRetries);

        const errorMessage =
          err instanceof Error ? err.message : 'Unable to connect to backend';
        setError(errorMessage);
        setData(null);
        setLastChecked(new Date().toLocaleTimeString());

        // Determine status: waking during cold start, temporarily unavailable after threshold
        if (newRetries <= config.maxWakingRetries) {
          setStatus('waking');
        } else {
          setStatus('temporarily unavailable');
        }

        // Bounded exponential backoff
        const backoffDelay = computeBackoffDelay(
          newRetries,
          config.initialRetryDelayMs,
          config.maxRetryDelayMs
        );
        scheduleNextCheck(backoffDelay, 'retry');
      } finally {
        inFlightRef.current = false;
        abortControllerRef.current = null;
        if (isMountedRef.current) {
          setIsChecking(false);
        }
      }
    },
    [config, clearScheduledTimer, scheduleNextCheck]
  );

  useEffect(() => {
    executeHealthCheckRef.current = executeHealthCheck;
  }, [executeHealthCheck]);

  const checkHealth = useCallback(
    async (isManual: boolean = false) => {
      if (inFlightRef.current && abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      clearScheduledTimer();
      if (isManual) {
        if (statusRef.current !== 'connected') {
          // Maintain waking/connecting state
          setStatus((prev) => (prev === 'connected' ? 'connecting' : prev));
        }
      }
      await executeHealthCheck(isManual);
    },
    [clearScheduledTimer, executeHealthCheck]
  );

  // Tab visibility management: pause when hidden, resume/check immediately when visible
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        clearScheduledTimer();
      } else {
        if (!inFlightRef.current) {
          executeHealthCheckRef.current(false);
        }
      }
    };

    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', handleVisibilityChange);
    }

    return () => {
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', handleVisibilityChange);
      }
    };
  }, [clearScheduledTimer]);

  // Initial connection on mount & unmount cleanup
  useEffect(() => {
    isMountedRef.current = true;
    executeHealthCheckRef.current(false);

    return () => {
      isMountedRef.current = false;
      clearScheduledTimer();
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [clearScheduledTimer]);

  const value = useMemo<BackendConnectionState>(
    () => ({
      status,
      data,
      error,
      lastChecked,
      retryCount,
      isChecking,
      checkHealth,
    }),
    [status, data, error, lastChecked, retryCount, isChecking, checkHealth]
  );

  return (
    <BackendConnectionContext.Provider value={value}>
      {children}
    </BackendConnectionContext.Provider>
  );
};

export function useBackendConnection(): BackendConnectionState {
  const context = useContext(BackendConnectionContext);
  if (!context) {
    throw new Error(
      'useBackendConnection must be used within a BackendConnectionProvider'
    );
  }
  return context;
}

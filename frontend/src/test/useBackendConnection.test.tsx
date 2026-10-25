import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, act } from '@testing-library/react';
import {
  BackendConnectionProvider,
  useBackendConnection,
  computeBackoffDelay,
} from '../hooks/useBackendConnection';
import { HealthResponse } from '../types/api';

const mockHealthResponse: HealthResponse = {
  status: 'ok',
  service: 'BrandSentry AI',
  version: '0.3.0',
  environment: 'production',
};

// Helper component that consumes the hook and displays state
const TestConsumer: React.FC = () => {
  const { status, data, error, retryCount, isChecking, checkHealth } =
    useBackendConnection();

  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="retry-count">{retryCount}</span>
      <span data-testid="service">{data?.service || ''}</span>
      <span data-testid="error">{error || ''}</span>
      <span data-testid="is-checking">{String(isChecking)}</span>
      <button data-testid="btn-recheck" onClick={() => checkHealth(true)}>
        Re-check
      </button>
    </div>
  );
};

describe('computeBackoffDelay', () => {
  it('calculates bounded exponential backoff up to maxDelay', () => {
    expect(computeBackoffDelay(0, 1000, 15000)).toBe(1000);
    expect(computeBackoffDelay(1, 1000, 15000)).toBe(1000); // 1000 * 2^0
    expect(computeBackoffDelay(2, 1000, 15000)).toBe(2000); // 1000 * 2^1
    expect(computeBackoffDelay(3, 1000, 15000)).toBe(4000); // 1000 * 2^2
    expect(computeBackoffDelay(4, 1000, 15000)).toBe(8000); // 1000 * 2^3
    expect(computeBackoffDelay(5, 1000, 15000)).toBe(15000); // capped at 15000
    expect(computeBackoffDelay(10, 1000, 15000)).toBe(15000); // capped at 15000
  });
});

describe('useBackendConnection and BackendConnectionProvider', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    Object.defineProperty(document, 'hidden', {
      value: false,
      writable: true,
      configurable: true,
    });
    Object.defineProperty(document, 'visibilityState', {
      value: 'visible',
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  // a. Initial successful health check
  it('a. Initial successful health check sets status to connected', async () => {
    const fetchFn = vi.fn().mockResolvedValue(mockHealthResponse);

    let getByTestId: any;
    await act(async () => {
      const rendered = render(
        <BackendConnectionProvider config={{ fetchFn }}>
          <TestConsumer />
        </BackendConnectionProvider>
      );
      getByTestId = rendered.getByTestId;
      await vi.advanceTimersByTimeAsync(10);
    });

    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(getByTestId('status').textContent).toBe('connected');
    expect(getByTestId('service').textContent).toBe('BrandSentry AI');
    expect(getByTestId('retry-count').textContent).toBe('0');
    expect(getByTestId('error').textContent).toBe('');
  });

  // b. First health check fails but a later retry succeeds
  it('b. First health check fails with waking state, but later retry succeeds and restores connected state', async () => {
    const fetchFn = vi
      .fn()
      .mockRejectedValueOnce(new Error('Render cold start: gateway timeout'))
      .mockResolvedValueOnce(mockHealthResponse);

    let getByTestId: any;
    await act(async () => {
      const rendered = render(
        <BackendConnectionProvider
          config={{
            fetchFn,
            initialRetryDelayMs: 1000,
            maxRetryDelayMs: 15000,
            maxWakingRetries: 3,
          }}
        >
          <TestConsumer />
        </BackendConnectionProvider>
      );
      getByTestId = rendered.getByTestId;
      await vi.advanceTimersByTimeAsync(10);
    });

    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(getByTestId('status').textContent).toBe('waking');
    expect(getByTestId('retry-count').textContent).toBe('1');
    expect(getByTestId('error').textContent).toContain('Render cold start');

    // Advance time by 1000ms backoff
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(fetchFn).toHaveBeenCalledTimes(2);
    expect(getByTestId('status').textContent).toBe('connected');
    expect(getByTestId('retry-count').textContent).toBe('0');
    expect(getByTestId('error').textContent).toBe('');
    expect(getByTestId('service').textContent).toBe('BrandSentry AI');
  });

  // c. Backend is unavailable for several checks
  it('c. Backend stays unavailable for several checks, transitioning from waking to temporarily unavailable', async () => {
    const fetchFn = vi.fn().mockRejectedValue(new Error('Connection refused'));

    let getByTestId: any;
    await act(async () => {
      const rendered = render(
        <BackendConnectionProvider
          config={{
            fetchFn,
            initialRetryDelayMs: 1000,
            maxRetryDelayMs: 15000,
            maxWakingRetries: 3,
          }}
        >
          <TestConsumer />
        </BackendConnectionProvider>
      );
      getByTestId = rendered.getByTestId;
      await vi.advanceTimersByTimeAsync(10);
    });

    // Attempt 1 fails -> waking (retry 1)
    expect(getByTestId('status').textContent).toBe('waking');
    expect(getByTestId('retry-count').textContent).toBe('1');

    // Attempt 2 after 1000ms backoff -> waking (retry 2)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(getByTestId('status').textContent).toBe('waking');
    expect(getByTestId('retry-count').textContent).toBe('2');

    // Attempt 3 after 2000ms backoff -> waking (retry 3)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(getByTestId('status').textContent).toBe('waking');
    expect(getByTestId('retry-count').textContent).toBe('3');

    // Attempt 4 after 4000ms backoff -> exceeds maxWakingRetries(3) -> temporarily unavailable
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(getByTestId('status').textContent).toBe('temporarily unavailable');
    expect(getByTestId('retry-count').textContent).toBe('4');
  });

  // d. Browser tab becomes visible after being hidden
  it('d. Browser tab pauses retries when hidden and checks immediately when visible again', async () => {
    const fetchFn = vi
      .fn()
      .mockRejectedValueOnce(new Error('Offline'))
      .mockResolvedValue(mockHealthResponse);

    let getByTestId: any;
    await act(async () => {
      const rendered = render(
        <BackendConnectionProvider
          config={{
            fetchFn,
            initialRetryDelayMs: 5000,
          }}
        >
          <TestConsumer />
        </BackendConnectionProvider>
      );
      getByTestId = rendered.getByTestId;
      await vi.advanceTimersByTimeAsync(10);
    });

    expect(fetchFn).toHaveBeenCalledTimes(1);

    // Simulate tab becoming hidden
    act(() => {
      Object.defineProperty(document, 'hidden', { value: true, configurable: true });
      Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
      document.dispatchEvent(new Event('visibilitychange'));
    });

    // Advance timer while hidden - no check should fire
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    expect(fetchFn).toHaveBeenCalledTimes(1);

    // Simulate tab becoming visible again -> immediately triggers health check
    await act(async () => {
      Object.defineProperty(document, 'hidden', { value: false, configurable: true });
      Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
      document.dispatchEvent(new Event('visibilitychange'));
      await vi.advanceTimersByTimeAsync(10);
    });

    expect(fetchFn).toHaveBeenCalledTimes(2);
    expect(getByTestId('status').textContent).toBe('connected');
  });

  // e. Component unmounts without leaving timers running
  it('e. Component unmounts cleanly without leaving pending timers or active controllers', async () => {
    const abortSpy = vi.fn();
    const fetchFn = vi.fn().mockImplementation((signal?: AbortSignal) => {
      if (signal) {
        signal.addEventListener('abort', abortSpy);
      }
      return new Promise((resolve) => setTimeout(() => resolve(mockHealthResponse), 5000));
    });

    let unmount: () => void = () => {};
    await act(async () => {
      const rendered = render(
        <BackendConnectionProvider
          config={{
            fetchFn,
            initialRetryDelayMs: 1000,
          }}
        >
          <TestConsumer />
        </BackendConnectionProvider>
      );
      unmount = rendered.unmount;
      await vi.advanceTimersByTimeAsync(10);
    });

    expect(fetchFn).toHaveBeenCalledTimes(1);

    // Unmount while request or timer is active
    await act(async () => {
      unmount();
    });

    // Verify abort signal was sent
    expect(abortSpy).toHaveBeenCalled();

    // Advancing timers should not cause any further calls or errors
    await act(async () => {
      await vi.advanceTimersByTimeAsync(20000);
    });

    expect(fetchFn).toHaveBeenCalledTimes(1);
  });
});

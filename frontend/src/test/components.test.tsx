import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, fireEvent } from '@testing-library/react';
import { BackendConnectionProvider } from '../hooks/useBackendConnection';
import { HealthStatus } from '../components/HealthStatus';
import { ClaimReview } from '../components/ClaimReview';
import * as api from '../services/api';

const mockHealthResponse = {
  status: 'ok',
  service: 'BrandSentry AI',
  version: '0.3.0',
  environment: 'production',
};

describe('HealthStatus Component Integration', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('renders "Connecting to backend..." badge initially', async () => {
    const fetchFn = vi.fn().mockImplementation(() => new Promise(() => {}));
    await act(async () => {
      render(
        <BackendConnectionProvider config={{ fetchFn }}>
          <HealthStatus />
        </BackendConnectionProvider>
      );
    });

    expect(screen.getByText('Connecting to backend...')).toBeDefined();
  });

  it('renders "Waking up backend..." badge and informative alert during Render cold start', async () => {
    const fetchFn = vi.fn().mockRejectedValue(new Error('503 Service Unavailable'));
    await act(async () => {
      render(
        <BackendConnectionProvider config={{ fetchFn, maxWakingRetries: 3 }}>
          <HealthStatus />
        </BackendConnectionProvider>
      );
      await vi.advanceTimersByTimeAsync(10);
    });

    expect(screen.getByText('Waking up backend...')).toBeDefined();
    expect(screen.getByText('Waking Up Backend Service')).toBeDefined();
    expect(screen.getByText(/Render free tier services spin down/)).toBeDefined();
  });

  it('renders "Connected" badge and operational message upon success', async () => {
    const fetchFn = vi.fn().mockResolvedValue(mockHealthResponse);
    await act(async () => {
      render(
        <BackendConnectionProvider config={{ fetchFn }}>
          <HealthStatus />
        </BackendConnectionProvider>
      );
      await vi.advanceTimersByTimeAsync(10);
    });

    expect(screen.getByText('Connected')).toBeDefined();
    expect(screen.getByText('FastAPI backend is operational and accepting vector retrieval requests.')).toBeDefined();
  });

  it('renders "Temporarily Unavailable" badge when retry threshold is exceeded', async () => {
    const fetchFn = vi.fn().mockRejectedValue(new Error('Connection refused'));
    await act(async () => {
      render(
        <BackendConnectionProvider
          config={{
            fetchFn,
            maxWakingRetries: 2,
            initialRetryDelayMs: 100,
            maxRetryDelayMs: 500,
          }}
        >
          <HealthStatus />
        </BackendConnectionProvider>
      );
      await vi.advanceTimersByTimeAsync(10);
    });

    // Attempt 2 -> waking (2)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    // Attempt 3 -> temporarily unavailable (3 > maxWakingRetries)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200);
    });

    expect(screen.getByText('Temporarily Unavailable')).toBeDefined();
    expect(screen.getByText('Backend Service Temporarily Unavailable')).toBeDefined();
  });
});

describe('ClaimReview Component Reliability', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(api, 'fetchGuidelines').mockResolvedValue({
      total: 1,
      documents: [
        {
          document_id: 'doc-1',
          filename: 'compliance_guide.pdf',
          status: 'indexed',
          page_count: 1,
          character_count: 500,
          chunk_count: 5,
          created_at: '2026-10-25T00:00:00',
        },
      ],
    });
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('prevents submission when backend is waking up and preserves entered claim copy', async () => {
    const fetchFn = vi.fn().mockRejectedValue(new Error('Render cold start'));
    const reviewSpy = vi.spyOn(api, 'reviewMarketingContent');

    await act(async () => {
      render(
        <BackendConnectionProvider config={{ fetchFn }}>
          <ClaimReview />
        </BackendConnectionProvider>
      );
      await vi.advanceTimersByTimeAsync(10);
    });

    const textarea = screen.getByPlaceholderText(/Enter marketing copy here/) as HTMLTextAreaElement;
    await act(async () => {
      fireEvent.change(textarea, { target: { value: 'Our 100% compliant claim.' } });
    });

    const submitBtn = screen.getByRole('button', { name: /Review Compliance/ });
    await act(async () => {
      fireEvent.click(submitBtn);
      await vi.advanceTimersByTimeAsync(10);
    });

    // Review API must NOT be called
    expect(reviewSpy).not.toHaveBeenCalled();

    // User's text must be preserved
    expect(textarea.value).toBe('Our 100% compliant claim.');

    // Helpful error message displayed with check button
    expect(screen.getByText(/Backend service is currently waking up from standby/)).toBeDefined();
    expect(screen.getByRole('button', { name: /Check Status/ })).toBeDefined();
  });

  it('preserves claim text if reviewMarketingContent fails', async () => {
    const fetchFn = vi.fn().mockResolvedValue(mockHealthResponse);
    vi.spyOn(api, 'reviewMarketingContent').mockRejectedValue(new Error('Internal evaluation timeout'));

    await act(async () => {
      render(
        <BackendConnectionProvider config={{ fetchFn }}>
          <ClaimReview />
        </BackendConnectionProvider>
      );
      await vi.advanceTimersByTimeAsync(10);
    });

    const textarea = screen.getByPlaceholderText(/Enter marketing copy here/) as HTMLTextAreaElement;
    await act(async () => {
      fireEvent.change(textarea, { target: { value: 'Important marketing claim copy that must not be lost.' } });
    });

    const submitBtn = screen.getByRole('button', { name: /Review Compliance/ });
    
    await act(async () => {
      fireEvent.click(submitBtn);
      await vi.advanceTimersByTimeAsync(10);
    });

    // Content is preserved
    expect(textarea.value).toBe('Important marketing claim copy that must not be lost.');
    expect(screen.getByText('Internal evaluation timeout')).toBeDefined();
  });
});

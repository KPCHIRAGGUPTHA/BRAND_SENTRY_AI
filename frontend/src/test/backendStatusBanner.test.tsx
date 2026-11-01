import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BackendConnectionProvider } from '../hooks/useBackendConnection';
import { BackendStatusBanner } from '../components/BackendStatusBanner';

const healthy = { status: 'ok', service: 'BrandSentry AI', version: '0.3.0', environment: 'production' };

const renderWith = (fetchFn: () => Promise<any>) =>
  render(
    <BackendConnectionProvider config={{ fetchFn, initialRetryDelayMs: 100000 }}>
      <BackendStatusBanner />
    </BackendConnectionProvider>
  );

describe('BackendStatusBanner', () => {
  it('tells the visitor the server is waking up and that retrying is automatic', async () => {
    renderWith(vi.fn().mockRejectedValue(new Error('timed out')));
    await waitFor(() => {
      expect(screen.getByText(/Server is waking up \(free tier\), ~1 min/)).toBeDefined();
    });
    expect(screen.getByText(/Retrying automatically/)).toBeDefined();
    expect(screen.getByRole('button', { name: /Retry now/ })).toBeDefined();
  });

  it('explains when the server is up but still loading', async () => {
    renderWith(vi.fn().mockResolvedValue({ ...healthy, readiness: 'warming' }));
    await waitFor(() => {
      expect(screen.getByText(/loading the AI model and sample guideline/)).toBeDefined();
    });
  });

  it('is hidden once the backend is ready', async () => {
    const { container } = renderWith(vi.fn().mockResolvedValue({ ...healthy, readiness: 'ready' }));
    await waitFor(() => {
      expect(container.querySelector('#backend-wake-banner')).toBeNull();
    });
  });
});

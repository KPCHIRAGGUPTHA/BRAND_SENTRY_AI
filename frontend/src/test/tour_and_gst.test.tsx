import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, fireEvent } from '@testing-library/react';
import { Tour } from '../components/Tour';
import { BackendConnectionProvider } from '../hooks/useBackendConnection';
import { ClaimReview } from '../components/ClaimReview';
import * as api from '../services/api';
import { DEMO_EVENTS, SAMPLE_INVOICE_TEXT, GST_RULES_FILENAME, isGstRulesFile } from '../samples/gstSample';

describe('Guided tour', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.localStorage.clear();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('starts by itself on a first visit and can be skipped', () => {
    render(<Tour />);
    expect(screen.queryByText('Check an invoice in 60 seconds')).toBeNull();
    act(() => { vi.advanceTimersByTime(1300); });
    expect(screen.getByText('Check an invoice in 60 seconds')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Skip' }));
    expect(screen.queryByText('Check an invoice in 60 seconds')).toBeNull();
    expect(window.localStorage.getItem('shreshti_tour_done_v1')).toBe('1');
  });

  it('does not start by itself after it has been seen, but opens on request', () => {
    window.localStorage.setItem('shreshti_tour_done_v1', '1');
    render(<Tour />);
    act(() => { vi.advanceTimersByTime(2000); });
    expect(screen.queryByRole('dialog')).toBeNull();
    act(() => { window.dispatchEvent(new Event(DEMO_EVENTS.startTour)); });
    expect(screen.getByRole('dialog')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: /Start the tour/ }));
    expect(screen.getByText('Load the GST rule book')).toBeDefined();
  });

  it('asks the page to load the GST rules from step 1', () => {
    window.localStorage.setItem('shreshti_tour_done_v1', '1');
    const fired = vi.fn();
    window.addEventListener(DEMO_EVENTS.loadGst, fired);
    render(
      <>
        <section id="guidelines">Rule library</section>
        <Tour />
      </>
    );
    act(() => { window.dispatchEvent(new Event(DEMO_EVENTS.startTour)); });
    fireEvent.click(screen.getByRole('button', { name: /Start the tour/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Load sample GST rules' }));
    expect(fired).toHaveBeenCalledTimes(1);
    window.removeEventListener(DEMO_EVENTS.loadGst, fired);
  });
});

describe('Sample GST invoice', () => {
  afterEach(() => vi.restoreAllMocks());

  it('recognises the sample rules file by name', () => {
    expect(isGstRulesFile(GST_RULES_FILENAME)).toBe(true);
    expect(isGstRulesFile('Brand_Guide.pdf')).toBe(false);
  });

  it('fills the sample invoice into the check box', async () => {
    vi.spyOn(api, 'fetchGuidelines').mockResolvedValue({ total: 0, documents: [] });
    vi.spyOn(api, 'fetchPolicyVersions').mockResolvedValue([]);
    await act(async () => {
      render(
        <BackendConnectionProvider>
          <ClaimReview />
        </BackendConnectionProvider>
      );
    });
    fireEvent.click(screen.getByRole('button', { name: /Fill Sample Invoice/ }));
    const box = screen.getByPlaceholderText(/Enter marketing copy here/) as HTMLTextAreaElement;
    expect(box.value).toBe(SAMPLE_INVOICE_TEXT);
  });
});

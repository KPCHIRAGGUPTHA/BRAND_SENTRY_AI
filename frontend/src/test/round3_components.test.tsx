import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, fireEvent } from '@testing-library/react';
import { BackendConnectionProvider } from '../hooks/useBackendConnection';
import { Dashboard } from '../components/Dashboard';
import { AuditHistory } from '../components/AuditHistory';
import { ClaimReview } from '../components/ClaimReview';
import * as api from '../services/api';

describe('Round 3 Frontend Components', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders Dashboard with live stats and recent reviews', async () => {
    vi.spyOn(api, 'fetchDashboardStats').mockResolvedValue({
      total_reviews: 42,
      text_reviews: 30,
      image_reviews: 12,
      total_claims_evaluated: 120,
      supported_claims: 65,
      contradicted_claims: 35,
      insufficient_claims: 20,
      unique_guidelines_used: 3,
    });

    vi.spyOn(api, 'fetchReviewHistory').mockResolvedValue({
      total: 1,
      offset: 0,
      limit: 5,
      reviews: [
        {
          review_id: 'rev-uuid-12345678',
          created_at: new Date().toISOString(),
          content_preview: 'Sample promo text for testing dashboard',
          review_source: 'image',
          total_claims: 3,
          supported: 1,
          contradicted: 1,
          insufficient: 1,
          policy_versions_used: ['v1.0'],
        },
      ],
    });

    await act(async () => {
      render(
        <BackendConnectionProvider>
          <Dashboard />
        </BackendConnectionProvider>
      );
    });

    expect(screen.getByText('Brand Compliance Analytics Dashboard')).toBeDefined();
    expect(screen.getByText('42')).toBeDefined();
    expect(screen.getByText('65')).toBeDefined();
    expect(screen.getByText('35')).toBeDefined();
    expect(screen.getByText('20')).toBeDefined();
    expect(screen.getByText('Sample promo text for testing dashboard')).toBeDefined();
    expect(screen.getByText('Image OCR')).toBeDefined();
  });

  it('renders AuditHistory with filtering and export buttons', async () => {
    vi.spyOn(api, 'fetchReviewHistory').mockResolvedValue({
      total: 2,
      offset: 0,
      limit: 10,
      reviews: [
        {
          review_id: 'rev-abc-1111',
          created_at: new Date().toISOString(),
          content_preview: 'Text review content 1',
          review_source: 'text',
          total_claims: 2,
          supported: 2,
          contradicted: 0,
          insufficient: 0,
          policy_versions_used: ['v1.0'],
        },
        {
          review_id: 'rev-def-2222',
          created_at: new Date().toISOString(),
          content_preview: 'Image review content 2',
          review_source: 'image',
          total_claims: 1,
          supported: 0,
          contradicted: 1,
          insufficient: 0,
          policy_versions_used: ['v1.0'],
        },
      ],
    });

    await act(async () => {
      render(
        <BackendConnectionProvider>
          <AuditHistory />
        </BackendConnectionProvider>
      );
    });

    expect(screen.getByText('Compliance Review Audit Trail')).toBeDefined();
    expect(screen.getByText('Text review content 1')).toBeDefined();
    expect(screen.getByText('Image review content 2')).toBeDefined();
    expect(screen.getAllByTitle('Export PDF').length).toBe(2);
    expect(screen.getAllByTitle('Export CSV').length).toBe(2);
  });

  it('allows ClaimReview to toggle between Text and Image modes', async () => {
    vi.spyOn(api, 'fetchGuidelines').mockResolvedValue({
      total: 1,
      documents: [
        {
          document_id: 'doc-1',
          filename: 'Brand_Guide.pdf',
          status: 'indexed',
          page_count: 5,
          character_count: 1200,
          chunk_count: 8,
          created_at: new Date().toISOString(),
        },
      ],
    });

    await act(async () => {
      render(
        <BackendConnectionProvider>
          <ClaimReview />
        </BackendConnectionProvider>
      );
    });

    expect(screen.getByText('Compliance Review Workspace')).toBeDefined();
    expect(screen.getByText('Marketing Copy to Analyze:')).toBeDefined();

    // Switch to Image OCR mode
    const imageModeBtn = screen.getByRole('button', { name: /Image OCR Review/i });
    await act(async () => {
      fireEvent.click(imageModeBtn);
    });

    expect(screen.getByText(/Select or drop promotional ad image/i)).toBeDefined();

    // Switch back to Text mode
    const textModeBtn = screen.getByRole('button', { name: /Text Copy Review/i });
    await act(async () => {
      fireEvent.click(textModeBtn);
    });

    expect(screen.getByText('Marketing Copy to Analyze:')).toBeDefined();
  });
});

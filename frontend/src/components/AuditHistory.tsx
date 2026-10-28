import React, { useState, useEffect } from 'react';
import {
  History,
  RefreshCw,
  Download,
  Eye,
  X,
} from 'lucide-react';
import { fetchReviewHistory, fetchReviewById, getExportUrl } from '../services/api';
import { AuditReviewSummaryItem } from '../types/api';

export const AuditHistory: React.FC = () => {
  const [reviews, setReviews] = useState<AuditReviewSummaryItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<string>('all');
  const [page, setPage] = useState<number>(0);
  const limit = 10;

  // Selected review for modal inspection
  const [selectedReview, setSelectedReview] = useState<any | null>(null);
  const [, setLoadingDetail] = useState<boolean>(false);

  const loadReviews = async () => {
    setLoading(true);
    setError(null);
    try {
      const src = sourceFilter === 'all' ? undefined : sourceFilter;
      const res = await fetchReviewHistory(limit, page * limit, src);
      setReviews(res.reviews);
      setTotal(res.total);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to load audit history.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReviews();
  }, [page, sourceFilter]);

  const handleViewDetail = async (reviewId: string) => {
    setLoadingDetail(true);
    try {
      const detail = await fetchReviewById(reviewId);
      setSelectedReview(detail);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to load review details');
    } finally {
      setLoadingDetail(false);
    }
  };

  return (
    <section className="card" id="audit-history" style={{ marginBottom: '32px' }}>
      <div className="card-header">
        <div className="card-title-group">
          <h3 className="card-title">
            <History size={20} style={{ color: 'var(--color-primary)' }} />
            Compliance Review Audit Trail
          </h3>
          <p className="card-description">
            Complete, immutable historical audit logs of all text and image promotional compliance evaluations.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <select
            value={sourceFilter}
            onChange={(e) => {
              setSourceFilter(e.target.value);
              setPage(0);
            }}
            style={{
              padding: '4px 10px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--color-border)',
              fontSize: '0.8rem',
            }}
          >
            <option value="all">All Sources</option>
            <option value="text">Text Reviews</option>
            <option value="image">Image Reviews (OCR)</option>
          </select>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={loadReviews}
            disabled={loading}
            style={{ fontSize: '0.8rem', padding: '4px 10px' }}
          >
            <RefreshCw size={13} className={loading ? 'spinning' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert-warning" style={{ marginTop: '12px' }}>
          <span>{error}</span>
        </div>
      )}

      {/* Audit Table */}
      <div style={{ marginTop: '16px', overflowX: 'auto' }}>
        {reviews.length === 0 && !loading ? (
          <div style={{ padding: '24px', textAlign: 'center', color: 'var(--color-text-secondary)' }}>
            No audit records matching filter criteria.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--color-border)', textAlign: 'left', color: 'var(--color-text-secondary)' }}>
                <th style={{ padding: '8px 12px' }}>Review ID</th>
                <th style={{ padding: '8px 12px' }}>Source</th>
                <th style={{ padding: '8px 12px' }}>Marketing Content Preview</th>
                <th style={{ padding: '8px 12px' }}>Verdicts</th>
                <th style={{ padding: '8px 12px' }}>Timestamp</th>
                <th style={{ padding: '8px 12px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {reviews.map((rev: AuditReviewSummaryItem) => (
                <tr key={rev.review_id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '10px 12px', fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>
                    {rev.review_id.slice(0, 8)}...
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <span className={`badge ${rev.review_source === 'image' ? 'badge-primary' : 'badge-neutral'}`} style={{ fontSize: '0.72rem' }}>
                      {rev.review_source === 'image' ? 'Image OCR' : 'Text'}
                    </span>
                  </td>
                  <td style={{ padding: '10px 12px', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {rev.content_preview}
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <span style={{ color: '#1B6A3B', fontWeight: 600 }}>{rev.supported} Supp</span> •{' '}
                    <span style={{ color: '#A91B2E', fontWeight: 600 }}>{rev.contradicted} Cont</span> •{' '}
                    <span style={{ color: '#B7791F', fontWeight: 600 }}>{rev.insufficient} Incon</span>
                  </td>
                  <td style={{ padding: '10px 12px', color: 'var(--color-text-secondary)', fontSize: '0.78rem' }}>
                    {new Date(rev.created_at).toLocaleString()}
                  </td>
                  <td style={{ padding: '10px 12px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                      <button
                        type="button"
                        onClick={() => handleViewDetail(rev.review_id)}
                        className="btn btn-secondary"
                        style={{ fontSize: '0.72rem', padding: '3px 8px', height: 'auto' }}
                        title="View Full Audit Record"
                      >
                        <Eye size={12} />
                        <span>Inspect</span>
                      </button>
                      <a
                        href={getExportUrl(rev.review_id, 'pdf')}
                        target="_blank"
                        rel="noreferrer"
                        className="btn btn-secondary"
                        style={{ fontSize: '0.72rem', padding: '3px 8px', height: 'auto' }}
                        title="Export PDF"
                      >
                        PDF
                      </a>
                      <a
                        href={getExportUrl(rev.review_id, 'csv')}
                        target="_blank"
                        rel="noreferrer"
                        className="btn btn-secondary"
                        style={{ fontSize: '0.72rem', padding: '3px 8px', height: 'auto' }}
                        title="Export CSV"
                      >
                        CSV
                      </a>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {total > limit && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '16px' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)' }}>
            Showing {page * limit + 1} - {Math.min((page + 1) * limit, total)} of {total} reviews
          </span>
          <div style={{ display: 'flex', gap: '6px' }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setPage(page - 1)}
              disabled={page === 0}
              style={{ fontSize: '0.75rem', padding: '4px 10px' }}
            >
              Previous
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setPage(page + 1)}
              disabled={(page + 1) * limit >= total}
              style={{ fontSize: '0.75rem', padding: '4px 10px' }}
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Audit Detail Modal */}
      {selectedReview && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 1000,
            padding: '20px',
          }}
        >
          <div
            style={{
              background: '#FFFFFF',
              borderRadius: 'var(--radius-lg)',
              maxWidth: '800px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              padding: '24px',
              boxShadow: '0 10px 25px rgba(0,0,0,0.2)',
              position: 'relative',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--color-border)', paddingBottom: '12px' }}>
              <div>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--color-deep-aubergine)' }}>
                  Audit Record: {selectedReview.review_id}
                </h3>
                <span style={{ fontSize: '0.78rem', color: 'var(--color-text-secondary)' }}>
                  Created {new Date(selectedReview.created_at).toLocaleString()} • Source: {selectedReview.review_source.toUpperCase()}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setSelectedReview(null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px' }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Export Toolbar */}
            <div style={{ display: 'flex', gap: '8px', marginTop: '14px', alignItems: 'center' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-secondary)' }}>
                Export Report:
              </span>
              <a
                href={getExportUrl(selectedReview.review_id, 'pdf')}
                target="_blank"
                rel="noreferrer"
                className="btn btn-primary"
                style={{ fontSize: '0.75rem', padding: '4px 12px' }}
              >
                <Download size={13} />
                Download PDF
              </a>
              <a
                href={getExportUrl(selectedReview.review_id, 'csv')}
                target="_blank"
                rel="noreferrer"
                className="btn btn-secondary"
                style={{ fontSize: '0.75rem', padding: '4px 12px' }}
              >
                Download CSV
              </a>
              <a
                href={getExportUrl(selectedReview.review_id, 'json')}
                target="_blank"
                rel="noreferrer"
                className="btn btn-secondary"
                style={{ fontSize: '0.75rem', padding: '4px 12px' }}
              >
                Download JSON
              </a>
            </div>

            {/* Submitted Copy */}
            <div style={{ marginTop: '16px' }}>
              <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-secondary)', marginBottom: '6px' }}>
                SUBMITTED MARKETING CONTENT
              </h4>
              <div
                style={{
                  background: 'var(--color-surface-muted)',
                  padding: '12px',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '0.88rem',
                  lineHeight: 1.5,
                }}
              >
                {selectedReview.submitted_content}
              </div>
            </div>

            {/* OCR Raw and Corrected if Image */}
            {selectedReview.review_source === 'image' && (
              <div style={{ marginTop: '12px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <h5 style={{ fontSize: '0.78rem', color: 'var(--color-text-secondary)', marginBottom: '4px' }}>
                    RAW OCR OUTPUT
                  </h5>
                  <div style={{ background: '#f5f5f5', padding: '8px', fontSize: '0.8rem', borderRadius: '4px' }}>
                    {selectedReview.ocr_raw_text || 'None'}
                  </div>
                </div>
                <div>
                  <h5 style={{ fontSize: '0.78rem', color: 'var(--color-text-secondary)', marginBottom: '4px' }}>
                    USER-CORRECTED TEXT
                  </h5>
                  <div style={{ background: '#f5f5f5', padding: '8px', fontSize: '0.8rem', borderRadius: '4px' }}>
                    {selectedReview.ocr_corrected_text || 'None'}
                  </div>
                </div>
              </div>
            )}

            {/* Policy Versions Used */}
            <div style={{ marginTop: '14px' }}>
              <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-secondary)', marginBottom: '6px' }}>
                POLICY VERSIONS ENFORCED
              </h4>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {selectedReview.policy_versions_used && selectedReview.policy_versions_used.length > 0 ? (
                  selectedReview.policy_versions_used.map((pv: string) => (
                    <span key={pv} className="badge badge-primary" style={{ fontSize: '0.75rem' }}>
                      {pv}
                    </span>
                  ))
                ) : (
                  <span style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)' }}>
                    All active policy versions
                  </span>
                )}
              </div>
            </div>

            {/* Claims */}
            <div style={{ marginTop: '20px' }}>
              <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--color-deep-aubergine)', marginBottom: '10px' }}>
                Claims &amp; Grounded Evidence ({selectedReview.claims?.length || 0})
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {selectedReview.claims?.map((cl: any, idx: number) => (
                  <div
                    key={idx}
                    style={{
                      border: '1px solid var(--color-border)',
                      borderRadius: 'var(--radius-sm)',
                      padding: '12px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <strong style={{ fontSize: '0.88rem' }}>{cl.claim_id}: {cl.claim_text}</strong>
                      <span
                        className={`badge ${
                          cl.verdict === 'SUPPORTED'
                            ? 'badge-success'
                            : cl.verdict === 'CONTRADICTED'
                            ? 'badge-error'
                            : 'badge-warning'
                        }`}
                        style={{ fontSize: '0.75rem' }}
                      >
                        {cl.verdict}
                      </span>
                    </div>
                    <p style={{ fontSize: '0.82rem', color: 'var(--color-text-secondary)', margin: '4px 0' }}>
                      {cl.explanation}
                    </p>
                    {cl.evidence && cl.evidence.length > 0 && (
                      <div style={{ marginTop: '6px', fontSize: '0.78rem', background: 'var(--color-surface-muted)', padding: '6px 8px', borderRadius: '4px' }}>
                        <em>&ldquo;{cl.evidence[0].quote}&rdquo;</em> — {cl.evidence[0].source_filename} (p. {cl.evidence[0].page_number})
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div style={{ marginTop: '20px', textAlign: 'right' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setSelectedReview(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};

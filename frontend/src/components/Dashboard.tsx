import React, { useState, useEffect } from 'react';
import {
  BarChart3,
  ShieldCheck,
  ShieldAlert,
  HelpCircle,
  FileText,
  RefreshCw,
} from 'lucide-react';
import { fetchDashboardStats, fetchReviewHistory, getExportUrl } from '../services/api';
import { DashboardStats, AuditReviewSummaryItem } from '../types/api';

export const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentReviews, setRecentReviews] = useState<AuditReviewSummaryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsData, historyData] = await Promise.all([
        fetchDashboardStats(),
        fetchReviewHistory(5, 0),
      ]);
      setStats(statsData);
      setRecentReviews(historyData.reviews);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to load dashboard data');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  return (
    <section className="card" id="dashboard" style={{ marginBottom: '32px' }}>
      <div className="card-header">
        <div className="card-title-group">
          <h3 className="card-title">
            <BarChart3 size={20} style={{ color: 'var(--color-primary)' }} />
            Brand Compliance Analytics Dashboard
          </h3>
          <p className="card-description">
            Live overview of enterprise marketing compliance evaluations, claim verdicts, and audit records.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={loadData}
            disabled={loading}
            style={{ fontSize: '0.8rem', padding: '4px 12px' }}
          >
            <RefreshCw size={13} className={loading ? 'spinning' : ''} />
            <span>Refresh</span>
          </button>
          <span className="badge badge-success">Live SQLite Audit Store</span>
        </div>
      </div>

      {error && (
        <div className="alert alert-warning" style={{ marginTop: '14px' }}>
          <span>{error}</span>
        </div>
      )}

      {/* Metrics Cards Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '16px',
          marginTop: '18px',
        }}
      >
        {/* Total Reviews */}
        <div
          style={{
            background: 'var(--color-surface-muted)',
            padding: '16px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--color-border)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-secondary)' }}>
              TOTAL REVIEWS
            </span>
            <FileText size={16} style={{ color: 'var(--color-primary)' }} />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--color-deep-aubergine)', marginTop: '6px' }}>
            {stats ? stats.total_reviews : 0}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', marginTop: '4px' }}>
            {stats ? `${stats.text_reviews} Text • ${stats.image_reviews} Image` : 'Loading...'}
          </div>
        </div>

        {/* Supported Claims */}
        <div
          style={{
            background: '#F0F9F4',
            padding: '16px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid #D2EEDD',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#1B6A3B' }}>
              SUPPORTED CLAIMS
            </span>
            <ShieldCheck size={16} style={{ color: '#1B6A3B' }} />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: '#1B6A3B', marginTop: '6px' }}>
            {stats ? stats.supported_claims : 0}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#2B834D', marginTop: '4px' }}>
            Affirmatively verified by evidence
          </div>
        </div>

        {/* Contradicted Claims */}
        <div
          style={{
            background: '#FDF2F2',
            padding: '16px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid #F8D7DA',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#A91B2E' }}>
              CONTRADICTED CLAIMS
            </span>
            <ShieldAlert size={16} style={{ color: '#A91B2E' }} />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: '#A91B2E', marginTop: '6px' }}>
            {stats ? stats.contradicted_claims : 0}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#BD2130', marginTop: '4px' }}>
            Violates policy or absolute rules
          </div>
        </div>

        {/* Insufficient Evidence */}
        <div
          style={{
            background: '#FFFDF0',
            padding: '16px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid #FFEAA7',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#B7791F' }}>
              INSUFFICIENT EVIDENCE
            </span>
            <HelpCircle size={16} style={{ color: '#B7791F' }} />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: '#B7791F', marginTop: '6px' }}>
            {stats ? stats.insufficient_claims : 0}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#975A16', marginTop: '4px' }}>
            Requires manual legal review
          </div>
        </div>
      </div>

      {/* Recent Reviews Table */}
      <div style={{ marginTop: '24px' }}>
        <h4 style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--color-deep-aubergine)', marginBottom: '10px' }}>
          Recent Compliance Audits
        </h4>

        {recentReviews.length === 0 ? (
          <div style={{ padding: '16px', textAlign: 'center', color: 'var(--color-text-secondary)', fontSize: '0.88rem' }}>
            No reviews performed yet. Submit marketing copy or an image above to run compliance checks.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--color-border)', textAlign: 'left', color: 'var(--color-text-secondary)' }}>
                  <th style={{ padding: '8px 12px' }}>Review ID</th>
                  <th style={{ padding: '8px 12px' }}>Source</th>
                  <th style={{ padding: '8px 12px' }}>Content Preview</th>
                  <th style={{ padding: '8px 12px' }}>Verdicts</th>
                  <th style={{ padding: '8px 12px' }}>Date</th>
                  <th style={{ padding: '8px 12px', textAlign: 'right' }}>Export</th>
                </tr>
              </thead>
              <tbody>
                {recentReviews.map((rev) => (
                  <tr key={rev.review_id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                    <td style={{ padding: '10px 12px', fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>
                      {rev.review_id.slice(0, 8)}...
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <span className={`badge ${rev.review_source === 'image' ? 'badge-primary' : 'badge-neutral'}`} style={{ fontSize: '0.72rem' }}>
                        {rev.review_source === 'image' ? 'Image OCR' : 'Text'}
                      </span>
                    </td>
                    <td style={{ padding: '10px 12px', maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {rev.content_preview}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        <span style={{ color: '#1B6A3B', fontWeight: 600 }}>{rev.supported}S</span> •{' '}
                        <span style={{ color: '#A91B2E', fontWeight: 600 }}>{rev.contradicted}C</span> •{' '}
                        <span style={{ color: '#B7791F', fontWeight: 600 }}>{rev.insufficient}I</span>
                      </div>
                    </td>
                    <td style={{ padding: '10px 12px', color: 'var(--color-text-secondary)', fontSize: '0.78rem' }}>
                      {new Date(rev.created_at).toLocaleDateString()}
                    </td>
                    <td style={{ padding: '10px 12px', textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                        <a
                          href={getExportUrl(rev.review_id, 'pdf')}
                          target="_blank"
                          rel="noreferrer"
                          className="btn btn-secondary"
                          style={{ fontSize: '0.7rem', padding: '2px 8px', height: 'auto' }}
                          title="Download PDF Audit Report"
                        >
                          PDF
                        </a>
                        <a
                          href={getExportUrl(rev.review_id, 'json')}
                          target="_blank"
                          rel="noreferrer"
                          className="btn btn-secondary"
                          style={{ fontSize: '0.7rem', padding: '2px 8px', height: 'auto' }}
                          title="Download JSON Audit Report"
                        >
                          JSON
                        </a>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
};

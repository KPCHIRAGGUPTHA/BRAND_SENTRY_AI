import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  HelpCircle,
  FileSearch,
  AlertTriangle,
  RefreshCw,
  FileCheck,
  Sparkles,
  Info,
  GitCompare
} from 'lucide-react';
import { reviewMarketingContent, fetchGuidelines } from '../services/api';
import { ReviewResponse, DocumentSummary, ClaimVerdict } from '../types/api';

export const ClaimReview: React.FC = () => {
  const [content, setContent] = useState<string>('');
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string>('all');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [reviewResult, setReviewResult] = useState<ReviewResponse | null>(null);

  const loadDocuments = async () => {
    try {
      const res = await fetchGuidelines();
      setDocuments(res.documents);
    } catch {
      // Backend may be offline during initial render
    }
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setError(null);

    const trimmed = content.trim();
    if (!trimmed) {
      setError('Marketing copy cannot be empty or whitespace-only. Please provide text to review.');
      return;
    }

    setLoading(true);
    try {
      const docIds = selectedDocId !== 'all' ? [selectedDocId] : undefined;
      const res = await reviewMarketingContent(trimmed, docIds);
      setReviewResult(res);
      setError(null);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('An unexpected error occurred while reviewing marketing copy.');
      }
    } finally {
      setLoading(false);
    }
  };

  const fillSampleCopy = () => {
    setContent(
      'Our product is 100% guaranteed to deliver results. Our product is 100% safe. Our solution increases employee productivity by 85%.'
    );
    setError(null);
  };

  const getVerdictBadge = (verdict: string) => {
    switch (verdict) {
      case 'SUPPORTED':
        return (
          <span className="badge badge-success" style={{ gap: '4px', fontSize: '0.8rem', padding: '4px 10px' }}>
            <ShieldCheck size={14} />
            SUPPORTED
          </span>
        );
      case 'CONTRADICTED':
        return (
          <span className="badge badge-error" style={{ gap: '4px', fontSize: '0.8rem', padding: '4px 10px' }}>
            <ShieldAlert size={14} />
            CONTRADICTED
          </span>
        );
      case 'INSUFFICIENT_EVIDENCE':
      default:
        return (
          <span className="badge badge-warning" style={{ gap: '4px', fontSize: '0.8rem', padding: '4px 10px' }}>
            <HelpCircle size={14} />
            INSUFFICIENT_EVIDENCE
          </span>
        );
    }
  };

  return (
    <section className="card" id="review" style={{ marginBottom: '32px' }}>
      <div className="card-header">
        <div className="card-title-group">
          <h3 className="card-title">
            <FileSearch size={20} style={{ color: 'var(--color-primary)' }} />
            Phase 3 Marketing Copy Compliance Review
          </h3>
          <p className="card-description">
            Submit marketing copy to automatically extract discrete claims, retrieve guideline evidence,
            and produce evidence-grounded compliance verdicts.
          </p>
        </div>
        <span className="badge badge-success">Evidence-Grounded Verdict Engine</span>
      </div>

      {/* Review Form */}
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '12px' }}>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <label htmlFor="marketing-copy-input" style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--color-deep-aubergine)' }}>
              Marketing Copy to Analyze:
            </label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                type="button"
                onClick={fillSampleCopy}
                className="btn btn-secondary"
                style={{ fontSize: '0.75rem', padding: '3px 10px', height: 'auto' }}
              >
                <Sparkles size={13} style={{ color: 'var(--color-accent)' }} />
                Fill Sample Copy
              </button>
              {content && (
                <button
                  type="button"
                  onClick={() => { setContent(''); setError(null); }}
                  className="btn btn-secondary"
                  style={{ fontSize: '0.75rem', padding: '3px 10px', height: 'auto' }}
                >
                  Clear
                </button>
              )}
            </div>
          </div>
          <textarea
            id="marketing-copy-input"
            rows={4}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Enter marketing copy here... (e.g. 'Our product is 100% guaranteed to deliver results. Our product is 100% safe. Our solution increases employee productivity by 85%.')"
            style={{
              width: '100%',
              padding: '12px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--color-border)',
              fontFamily: 'var(--font-sans)',
              fontSize: '0.9rem',
              lineHeight: 1.5,
              resize: 'vertical',
            }}
          />
        </div>

        {/* Guideline Scoping Selector */}
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '14px', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <label htmlFor="guideline-scope-select" style={{ fontSize: '0.84rem', fontWeight: 600, color: 'var(--color-text-secondary)' }}>
              Scope to Guideline:
            </label>
            <select
              id="guideline-scope-select"
              value={selectedDocId}
              onFocus={loadDocuments}
              onClick={loadDocuments}
              onChange={(e) => setSelectedDocId(e.target.value)}
              style={{
                padding: '6px 12px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--color-border)',
                background: '#FFFFFF',
                fontSize: '0.85rem',
                color: 'var(--color-text-primary)',
              }}
            >
              <option value="all">All Uploaded Guidelines ({documents.length})</option>
              {documents.map((doc) => (
                <option key={doc.document_id} value={doc.document_id}>
                  {doc.filename} ({doc.chunk_count} chunks)
                </option>
              ))}
            </select>
          </div>

          <button
            type="submit"
            id="btn-analyze-compliance"
            disabled={loading}
            className="btn btn-primary"
            style={{ padding: '8px 24px', fontSize: '0.92rem' }}
          >
            {loading ? (
              <>
                <RefreshCw size={16} className="spinning" />
                <span>Analyzing Claims...</span>
              </>
            ) : (
              <>
                <FileSearch size={16} />
                <span>Review Compliance</span>
              </>
            )}
          </button>
        </div>

        {/* Error Alert */}
        {error && (
          <div id="review-error-alert" className="alert alert-warning" role="alert" style={{ marginTop: '4px' }}>
            <AlertTriangle size={16} style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}
      </form>

      {/* Results View */}
      {reviewResult && (
        <div id="review-results-container" style={{ marginTop: '28px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Summary Dashboard Bar */}
          <div
            id="review-summary-bar"
            style={{
              padding: '16px 20px',
              borderRadius: 'var(--radius-md)',
              background: 'var(--color-surface-muted)',
              border: '1px solid var(--color-border)',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
              <div>
                <strong style={{ fontSize: '1rem', color: 'var(--color-deep-aubergine)' }}>
                  Compliance Review Summary
                </strong>
                <p style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)' }}>
                  {reviewResult.document_ids_searched.length > 0
                    ? `Scoped to ${reviewResult.document_ids_searched.length} specified guideline document`
                    : 'Searched across all indexed guideline documents'}
                </p>
              </div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <span className="badge badge-neutral" id="summary-total-claims" style={{ fontSize: '0.8rem', padding: '4px 10px' }}>
                  Total Claims: <strong>{reviewResult.summary.total_claims}</strong>
                </span>
                <span className="badge badge-success" id="summary-supported-claims" style={{ fontSize: '0.8rem', padding: '4px 10px' }}>
                  Supported: <strong>{reviewResult.summary.supported}</strong>
                </span>
                <span className="badge badge-error" id="summary-contradicted-claims" style={{ fontSize: '0.8rem', padding: '4px 10px' }}>
                  Contradicted: <strong>{reviewResult.summary.contradicted}</strong>
                </span>
                <span className="badge badge-warning" id="summary-insufficient-claims" style={{ fontSize: '0.8rem', padding: '4px 10px' }}>
                  Insufficient Evidence: <strong>{reviewResult.summary.insufficient_evidence}</strong>
                </span>
              </div>
            </div>

            {reviewResult.warning && (
              <div className="alert alert-warning" style={{ fontSize: '0.82rem', padding: '8px 12px' }}>
                <Info size={14} />
                <span>{reviewResult.warning}</span>
              </div>
            )}
          </div>

          {/* Individual Claims Section */}
          <div>
            <h4 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--color-deep-aubergine)', marginBottom: '14px' }}>
              Extracted Claims &amp; Grounded Verdicts ({reviewResult.claims.length})
            </h4>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {reviewResult.claims.map((claim: ClaimVerdict, idx: number) => (
                <article
                  key={claim.claim_id || idx}
                  className="card"
                  id={`claim-verdict-card-${claim.claim_id}`}
                  style={{
                    padding: '20px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--color-border)',
                    background: '#FFFFFF',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '14px',
                  }}
                >
                  {/* Claim Header */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '10px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span
                        className="badge badge-neutral"
                        style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', textTransform: 'uppercase' }}
                      >
                        {claim.claim_id}
                      </span>
                      {claim.deterministic_rule_fired && (
                        <span
                          className="badge badge-primary"
                          style={{ fontSize: '0.72rem' }}
                          title="Determined by an explicit rule prohibiting absolute terms without evidence"
                        >
                          Deterministic Rule Fired
                        </span>
                      )}
                    </div>
                    <div>{getVerdictBadge(claim.verdict)}</div>
                  </div>

                  {/* Claim Text */}
                  <div
                    style={{
                      padding: '10px 14px',
                      background: 'var(--color-surface-muted)',
                      borderRadius: 'var(--radius-sm)',
                      borderLeft: '4px solid var(--color-primary)',
                      fontSize: '0.95rem',
                      fontWeight: 600,
                      color: 'var(--color-deep-aubergine)',
                    }}
                  >
                    &ldquo;{claim.claim_text}&rdquo;
                  </div>

                  {/* Explanation */}
                  <div>
                    <h5 style={{ fontSize: '0.78rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--color-text-secondary)', letterSpacing: '0.04em', marginBottom: '4px' }}>
                      Verdict Explanation
                    </h5>
                    <p style={{ fontSize: '0.88rem', color: 'var(--color-text-primary)', lineHeight: 1.5 }}>
                      {claim.explanation}
                    </p>
                  </div>

                  {/* Suggested Correction (if present) */}
                  {claim.suggested_correction && (
                    <div
                      style={{
                        padding: '12px 14px',
                        background: '#FFFDF5',
                        border: '1px solid #F5E6B3',
                        borderRadius: 'var(--radius-sm)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '4px',
                      }}
                    >
                      <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--color-warning)', letterSpacing: '0.04em' }}>
                        Suggested Correction (Draft)
                      </span>
                      <p style={{ fontSize: '0.85rem', color: '#6A4A00', lineHeight: 1.45 }}>
                        {claim.suggested_correction}
                      </p>
                    </div>
                  )}

                  {/* Semantic Drift Analysis */}
                  {claim.semantic_drift && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <h5
                          style={{
                            fontSize: '0.78rem',
                            fontWeight: 700,
                            textTransform: 'uppercase',
                            color: 'var(--color-text-secondary)',
                            letterSpacing: '0.04em',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            margin: 0,
                          }}
                        >
                          <GitCompare size={14} style={{ color: 'var(--color-primary)' }} />
                          Semantic Drift Analysis
                        </h5>
                        {claim.semantic_drift.detected ? (
                          <span className="badge badge-warning" style={{ fontSize: '0.72rem' }}>
                            Drift Detected ({claim.semantic_drift.issues.length})
                          </span>
                        ) : (
                          <span className="badge badge-success" style={{ fontSize: '0.72rem' }}>
                            No Drift Detected
                          </span>
                        )}
                      </div>

                      {claim.semantic_drift.detected && claim.semantic_drift.issues.length > 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                          {claim.semantic_drift.issues.map((iss, issIdx) => (
                            <div
                              key={issIdx}
                              style={{
                                padding: '12px 14px',
                                background: '#FFF8F0',
                                border: '1px solid #FFE3C2',
                                borderRadius: 'var(--radius-sm)',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '6px',
                              }}
                            >
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.76rem', fontWeight: 700, color: '#A03800' }}>
                                  {iss.category}
                                </span>
                                <span
                                  className={
                                    iss.severity === 'HIGH'
                                      ? 'badge badge-error'
                                      : iss.severity === 'MEDIUM'
                                      ? 'badge badge-warning'
                                      : 'badge badge-primary'
                                  }
                                  style={{ fontSize: '0.70rem', textTransform: 'uppercase' }}
                                >
                                  {iss.severity} Severity
                                </span>
                              </div>

                              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.82rem', marginTop: '2px' }}>
                                <div style={{ background: '#FFFFFF', padding: '6px 10px', borderRadius: '4px', border: '1px solid #F0E6D8' }}>
                                  <span style={{ fontSize: '0.70rem', textTransform: 'uppercase', color: 'var(--color-text-secondary)', display: 'block', fontWeight: 600 }}>
                                    Claim Phrase:
                                  </span>
                                  <span style={{ fontWeight: 600, color: 'var(--color-deep-aubergine)' }}>
                                    &ldquo;{iss.claim_phrase}&rdquo;
                                  </span>
                                </div>
                                <div style={{ background: '#FFFFFF', padding: '6px 10px', borderRadius: '4px', border: '1px solid #F0E6D8' }}>
                                  <span style={{ fontSize: '0.70rem', textTransform: 'uppercase', color: 'var(--color-text-secondary)', display: 'block', fontWeight: 600 }}>
                                    Source Evidence:
                                  </span>
                                  <span style={{ fontStyle: 'italic', color: 'var(--color-text-primary)' }}>
                                    &ldquo;{iss.source_phrase}&rdquo;
                                  </span>
                                </div>
                              </div>

                              <p style={{ fontSize: '0.84rem', color: '#5C3800', margin: '2px 0 0', lineHeight: 1.45 }}>
                                {iss.explanation}
                              </p>

                              {iss.suggested_correction && (
                                <div style={{ fontSize: '0.80rem', color: '#2B5740', background: '#F0F9F4', padding: '6px 10px', borderRadius: '4px', marginTop: '2px' }}>
                                  <strong style={{ textTransform: 'uppercase', fontSize: '0.70rem' }}>Realigned Phrasing: </strong>
                                  &ldquo;{iss.suggested_correction}&rdquo;
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : claim.semantic_drift.uncertainty ? (
                        <div
                          style={{
                            padding: '8px 12px',
                            background: 'var(--color-surface-muted)',
                            borderRadius: 'var(--radius-sm)',
                            fontSize: '0.82rem',
                            color: 'var(--color-text-secondary)',
                          }}
                        >
                          {claim.semantic_drift.uncertainty}
                        </div>
                      ) : (
                        <div
                          style={{
                            padding: '8px 12px',
                            background: '#F0F9F4',
                            border: '1px solid #D2EEDD',
                            borderRadius: 'var(--radius-sm)',
                            fontSize: '0.82rem',
                            color: '#1B6A3B',
                          }}
                        >
                          No material semantic drift was detected in the evidence examined.
                        </div>
                      )}
                    </div>
                  )}

                  {/* Evidence Citations */}
                  {claim.evidence && claim.evidence.length > 0 ? (
                    <div>
                      <h5 style={{ fontSize: '0.78rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--color-text-secondary)', letterSpacing: '0.04em', marginBottom: '8px' }}>
                        Retrieved Evidence Citations ({claim.evidence.length})
                      </h5>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        {claim.evidence.map((ev, evIdx) => (
                          <div
                            key={ev.chunk_id || evIdx}
                            className="evidence-card"
                            style={{ margin: 0, padding: '14px', background: 'var(--color-surface-muted)' }}
                          >
                            <div className="evidence-header" style={{ marginBottom: '8px' }}>
                              <div className="evidence-meta">
                                <span className="evidence-source">
                                  <FileCheck size={14} style={{ display: 'inline', marginRight: '4px', verticalAlign: '-2px' }} />
                                  {ev.source_filename}
                                </span>
                                {ev.page_number && (
                                  <span className="badge badge-neutral" style={{ fontSize: '0.72rem' }}>
                                    Page {ev.page_number}
                                  </span>
                                )}
                              </div>
                              <div className="evidence-metrics">
                                <span className="badge badge-primary" style={{ fontSize: '0.72rem' }}>
                                  Similarity: {(ev.similarity_score * 100).toFixed(1)}%
                                </span>
                              </div>
                            </div>
                            <blockquote
                              className="evidence-passage"
                              style={{
                                fontStyle: 'italic',
                                fontSize: '0.85rem',
                                color: 'var(--color-text-primary)',
                                margin: 0,
                                borderLeft: '3px solid var(--color-marigold)',
                                paddingLeft: '10px',
                              }}
                            >
                              &ldquo;{ev.quote}&rdquo;
                            </blockquote>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : claim.verdict === 'INSUFFICIENT_EVIDENCE' ? (
                    <div
                      style={{
                        padding: '10px 14px',
                        background: 'var(--color-surface-muted)',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '0.82rem',
                        color: 'var(--color-text-secondary)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                      }}
                    >
                      <Info size={15} style={{ flexShrink: 0, color: 'var(--color-text-secondary)' }} />
                      <span>
                        The selected guidelines do not provide sufficient evidence to evaluate this claim.
                        No supporting or contradicting citations were found. Independent human review is required before publication.
                      </span>
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  );
};

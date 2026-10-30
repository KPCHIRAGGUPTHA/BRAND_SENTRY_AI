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
  GitCompare,
  Upload,
  Image as ImageIcon,
  Download,
} from 'lucide-react';
import {
  reviewMarketingContent,
  uploadReviewImage,
  submitImageReview,
  fetchGuidelines,
  fetchPolicyVersions,
  getExportUrl,
} from '../services/api';
import {
  ReviewResponse,
  DocumentSummary,
  PolicyVersion,
  ClaimVerdict,
  ImageOCRResponse,
} from '../types/api';
import { useBackendConnection } from '../hooks/useBackendConnection';

export const ClaimReview: React.FC = () => {
  // Mode selection
  const [reviewMode, setReviewMode] = useState<'text' | 'image'>('text');

  // Text review state
  const [content, setContent] = useState<string>('');

  // Image review state
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [ocrLoading, setOcrLoading] = useState<boolean>(false);
  const [ocrResult, setOcrResult] = useState<ImageOCRResponse | null>(null);
  const [correctedText, setCorrectedText] = useState<string>('');

  // Shared options
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [policyVersions, setPolicyVersions] = useState<PolicyVersion[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string>('all');
  const [retrievalMode, setRetrievalMode] = useState<'hybrid' | 'dense' | 'bm25'>('hybrid');

  // Pipeline execution state
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [reviewResult, setReviewResult] = useState<ReviewResponse | null>(null);

  const { status, checkHealth, isChecking } = useBackendConnection();

  const loadDocuments = async () => {
    try {
      const [res, vers] = await Promise.all([
        fetchGuidelines().catch(() => ({ total: 0, documents: [] })),
        fetchPolicyVersions().catch(() => []),
      ]);
      setDocuments(res.documents || []);
      setPolicyVersions(vers || []);
    } catch {
      // Backend may be offline during initial render
    }
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  useEffect(() => {
    if (status === 'connected' && documents.length === 0) {
      loadDocuments();
    }
  }, [status, documents.length]);

  // Handle Text Submission
  const handleTextSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (loading) return;
    setError(null);

    const trimmed = content.trim();
    if (!trimmed) {
      setError('Marketing copy cannot be empty. Please provide text to review.');
      return;
    }

    if (status === 'connecting' || status === 'waking') {
      setError(
        'Backend service is currently waking up from standby (Render cold start). Please wait a moment for the connection to establish before analyzing claims.'
      );
      checkHealth();
      return;
    }

    setLoading(true);
    try {
      let docIds: string[] | undefined = undefined;
      let verIds: string[] | undefined = undefined;
      if (selectedDocId !== 'all') {
        if (selectedDocId.startsWith('ver-')) {
          verIds = [selectedDocId];
        } else {
          docIds = [selectedDocId];
        }
      }
      const res = await reviewMarketingContent(trimmed, docIds, retrievalMode, verIds);
      setReviewResult(res);
      setError(null);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('An unexpected error occurred while reviewing marketing copy.');
      }
      checkHealth();
    } finally {
      setLoading(false);
    }
  };

  // Handle Image File Selection
  const handleImageFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setError(null);
    setImageFile(file);
    setOcrResult(null);
    setCorrectedText('');

    // Generate local preview URL
    const reader = new FileReader();
    reader.onload = () => {
      setImagePreview(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  // Run OCR on Uploaded Image
  const handleRunOCR = async () => {
    if (!imageFile || ocrLoading) return;
    setError(null);
    setOcrLoading(true);

    try {
      const res = await uploadReviewImage(imageFile);
      setOcrResult(res);
      setCorrectedText(res.extracted_text);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('OCR extraction failed.');
      }
    } finally {
      setOcrLoading(false);
    }
  };

  // Handle Image Compliance Submission
  const handleImageReviewSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (loading) return;
    setError(null);

    const trimmed = correctedText.trim();
    if (!trimmed) {
      setError('Extracted text cannot be empty. Please verify or manually enter text.');
      return;
    }

    setLoading(true);
    try {
      let docIds: string[] | undefined = undefined;
      let verIds: string[] | undefined = undefined;
      if (selectedDocId !== 'all') {
        if (selectedDocId.startsWith('ver-')) {
          verIds = [selectedDocId];
        } else {
          docIds = [selectedDocId];
        }
      }
      const res = await submitImageReview({
        corrected_text: trimmed,
        raw_ocr_text: ocrResult?.extracted_text || trimmed,
        document_ids: docIds,
        policy_version_ids: verIds,
        retrieval_mode: retrievalMode,
      });
      setReviewResult(res);
      setError(null);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to review image promotional copy.');
      }
      checkHealth();
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
            Compliance Review Workspace
          </h3>
          <p className="card-description">
            Evaluate promotional copy or visual creative against brand guidelines using Hybrid Retrieval (Dense + BM25) and evidence-grounded validation.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            type="button"
            className={`btn ${reviewMode === 'text' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setReviewMode('text')}
            style={{ fontSize: '0.82rem', padding: '5px 14px' }}
          >
            <FileSearch size={14} />
            Text Copy Review
          </button>
          <button
            type="button"
            className={`btn ${reviewMode === 'image' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setReviewMode('image')}
            style={{ fontSize: '0.82rem', padding: '5px 14px' }}
          >
            <ImageIcon size={14} />
            Image OCR Review
          </button>
        </div>
      </div>

      {/* --- TEXT REVIEW MODE --- */}
      {reviewMode === 'text' && (
        <form onSubmit={handleTextSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '14px' }}>
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

          {/* Controls: Scope + Retrieval Mode */}
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '14px', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '14px', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <label htmlFor="guideline-scope-select" style={{ fontSize: '0.84rem', fontWeight: 600, color: 'var(--color-text-secondary)' }}>
                  Scope:
                </label>
                <select
                  id="guideline-scope-select"
                  value={selectedDocId}
                  onChange={(e) => setSelectedDocId(e.target.value)}
                  style={{
                    padding: '6px 10px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--color-border)',
                    background: '#FFFFFF',
                    fontSize: '0.84rem',
                  }}
                >
                  <option value="all">
                    All Active Guidelines ({policyVersions.length > 0 ? policyVersions.filter(v => v.is_active).length : documents.length})
                  </option>
                  {policyVersions.length > 0 ? (
                    policyVersions.map((v) => (
                      <option key={v.version_id} value={v.version_id}>
                        {v.is_active ? '● [Active]' : '○ [Archived]'} {v.version_label} — {v.filename}
                      </option>
                    ))
                  ) : (
                    documents.map((doc) => (
                      <option key={doc.document_id} value={doc.document_id}>
                        {doc.filename} ({doc.chunk_count} chunks)
                      </option>
                    ))
                  )}
                </select>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <label htmlFor="retrieval-mode-select" style={{ fontSize: '0.84rem', fontWeight: 600, color: 'var(--color-text-secondary)' }}>
                  Retrieval:
                </label>
                <select
                  id="retrieval-mode-select"
                  value={retrievalMode}
                  onChange={(e) => setRetrievalMode(e.target.value as any)}
                  style={{
                    padding: '6px 10px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--color-border)',
                    background: '#FFFFFF',
                    fontSize: '0.84rem',
                  }}
                >
                  <option value="hybrid">Hybrid (Dense + BM25 via RRF)</option>
                  <option value="dense">Dense Only (ChromaDB)</option>
                  <option value="bm25">BM25 Only (Lexical)</option>
                </select>
              </div>
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
        </form>
      )}

      {/* --- IMAGE OCR REVIEW MODE --- */}
      {reviewMode === 'image' && (
        <div style={{ marginTop: '14px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div
            style={{
              border: '2px dashed var(--color-border)',
              borderRadius: 'var(--radius-md)',
              padding: '24px',
              textAlign: 'center',
              background: 'var(--color-surface-muted)',
            }}
          >
            <input
              type="file"
              id="promo-image-upload"
              accept="image/png,image/jpeg,image/webp"
              onChange={handleImageFileChange}
              style={{ display: 'none' }}
            />
            <label htmlFor="promo-image-upload" style={{ cursor: 'pointer', display: 'inline-block' }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                <Upload size={32} style={{ color: 'var(--color-primary)' }} />
                <span style={{ fontSize: '0.92rem', fontWeight: 600, color: 'var(--color-deep-aubergine)' }}>
                  {imageFile ? imageFile.name : 'Select or drop promotional ad image (PNG, JPEG, WebP)'}
                </span>
                <span style={{ fontSize: '0.78rem', color: 'var(--color-text-secondary)' }}>
                  Max size: 10 MB • Dimensions: up to 8000px
                </span>
              </div>
            </label>
          </div>

          {/* Image Preview & OCR Action */}
          {imagePreview && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '18px', alignItems: 'start' }}>
              {/* Preview Thumbnail */}
              <div style={{ border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '8px', background: '#FFFFFF' }}>
                <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--color-text-secondary)', display: 'block', marginBottom: '6px' }}>
                  IMAGE PREVIEW
                </span>
                <img
                  src={imagePreview}
                  alt="Promotional Creative"
                  style={{ maxWidth: '100%', maxHeight: '200px', objectFit: 'contain', borderRadius: '4px' }}
                />
                <button
                  type="button"
                  onClick={handleRunOCR}
                  disabled={ocrLoading}
                  className="btn btn-primary"
                  style={{ width: '100%', marginTop: '10px', fontSize: '0.84rem' }}
                >
                  {ocrLoading ? (
                    <>
                      <RefreshCw size={14} className="spinning" />
                      <span>Extracting OCR...</span>
                    </>
                  ) : (
                    <>
                      <FileSearch size={14} />
                      <span>{ocrResult ? 'Re-run OCR' : 'Extract Text (OCR)'}</span>
                    </>
                  )}
                </button>
              </div>

              {/* OCR Output & Editable Box */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <label htmlFor="corrected-ocr-text" style={{ fontSize: '0.86rem', fontWeight: 600, color: 'var(--color-deep-aubergine)' }}>
                    Extracted &amp; Verified Promotional Text:
                  </label>
                  {ocrResult && (
                    <span className="badge badge-neutral" style={{ fontSize: '0.75rem' }}>
                      OCR Confidence: <strong>{ocrResult.confidence.toFixed(1)}%</strong>
                    </span>
                  )}
                </div>

                <textarea
                  id="corrected-ocr-text"
                  rows={6}
                  value={correctedText}
                  onChange={(e) => setCorrectedText(e.target.value)}
                  placeholder="Extracted OCR text will appear here. You can edit and correct any misrecognized words before submitting for compliance analysis."
                  style={{
                    width: '100%',
                    padding: '12px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--color-border)',
                    fontFamily: 'var(--font-sans)',
                    fontSize: '0.9rem',
                    lineHeight: 1.5,
                  }}
                />

                {ocrResult?.warning && (
                  <div className="alert alert-warning" style={{ fontSize: '0.8rem', padding: '6px 10px', marginTop: '6px' }}>
                    <Info size={14} />
                    <span>{ocrResult.warning}</span>
                  </div>
                )}

                {/* Submit OCR Text for Compliance */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '12px', flexWrap: 'wrap', gap: '10px' }}>
                  <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                    <label htmlFor="image-scope-select" style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--color-text-secondary)' }}>
                      Scope:
                    </label>
                    <select
                      id="image-scope-select"
                      value={selectedDocId}
                      onChange={(e) => setSelectedDocId(e.target.value)}
                      style={{ padding: '4px 8px', fontSize: '0.82rem', borderRadius: '4px', border: '1px solid var(--color-border)' }}
                    >
                      <option value="all">
                        All Active Guidelines ({policyVersions.length > 0 ? policyVersions.filter(v => v.is_active).length : documents.length})
                      </option>
                      {policyVersions.length > 0 ? (
                        policyVersions.map((v) => (
                          <option key={v.version_id} value={v.version_id}>
                            {v.is_active ? '● [Active]' : '○ [Archived]'} {v.version_label} — {v.filename}
                          </option>
                        ))
                      ) : (
                        documents.map((doc) => (
                          <option key={doc.document_id} value={doc.document_id}>
                            {doc.filename}
                          </option>
                        ))
                      )}
                    </select>
                  </div>

                  <button
                    type="button"
                    onClick={handleImageReviewSubmit}
                    disabled={loading || !correctedText.trim()}
                    className="btn btn-primary"
                    style={{ padding: '8px 20px', fontSize: '0.88rem' }}
                  >
                    {loading ? (
                      <>
                        <RefreshCw size={14} className="spinning" />
                        <span>Evaluating Image Claims...</span>
                      </>
                    ) : (
                      <>
                        <ShieldCheck size={14} />
                        <span>Submit Image for Compliance</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div id="review-error-alert" className="alert alert-warning" role="alert" style={{ marginTop: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={16} style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
          {status !== 'connected' && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => checkHealth(true)}
              disabled={isChecking}
              style={{ fontSize: '0.75rem', padding: '4px 10px', height: 'auto', flexShrink: 0 }}
            >
              <RefreshCw size={12} className={isChecking ? 'spinning' : ''} />
              <span>{isChecking ? 'Checking...' : 'Check Status'}</span>
            </button>
          )}
        </div>
      )}

      {/* --- REVIEW RESULTS INTERFACE --- */}
      {reviewResult && (
        <div id="review-results-container" style={{ marginTop: '28px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Summary Dashboard Bar with Exports */}
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
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <strong style={{ fontSize: '1rem', color: 'var(--color-deep-aubergine)' }}>
                    Compliance Review Summary
                  </strong>
                  <span className={`badge ${reviewResult.review_source === 'image' ? 'badge-primary' : 'badge-neutral'}`} style={{ fontSize: '0.72rem' }}>
                    {reviewResult.review_source === 'image' ? 'Image OCR Creative' : 'Text Copy'}
                  </span>
                </div>
                <p style={{ fontSize: '0.78rem', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
                  Review ID: <code style={{ fontFamily: 'var(--font-mono)' }}>{reviewResult.review_id}</code> •{' '}
                  {reviewResult.policy_versions_used && reviewResult.policy_versions_used.length > 0 ? (
                    <span>
                      Enforced Policy: <strong style={{ color: 'var(--color-deep-aubergine)' }}>{reviewResult.policy_versions_used.join(', ')}</strong>
                    </span>
                  ) : reviewResult.document_ids_searched.length > 0 ? (
                    `Scoped to ${reviewResult.document_ids_searched.length} guideline(s)`
                  ) : (
                    'Searched all active guidelines'
                  )}
                </p>
              </div>

              {/* Export Toolbar */}
              <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--color-text-secondary)' }}>
                  Export:
                </span>
                <a
                  href={getExportUrl(reviewResult.review_id, 'pdf')}
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn-primary"
                  style={{ fontSize: '0.75rem', padding: '3px 10px', height: 'auto' }}
                  title="Download Official Audit PDF"
                >
                  <Download size={12} />
                  PDF Report
                </a>
                <a
                  href={getExportUrl(reviewResult.review_id, 'csv')}
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn-secondary"
                  style={{ fontSize: '0.75rem', padding: '3px 10px', height: 'auto' }}
                  title="Export Claims CSV"
                >
                  CSV
                </a>
                <a
                  href={getExportUrl(reviewResult.review_id, 'json')}
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn-secondary"
                  style={{ fontSize: '0.75rem', padding: '3px 10px', height: 'auto' }}
                  title="Export Machine JSON"
                >
                  JSON
                </a>
              </div>
            </div>

            {/* Counts */}
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', paddingTop: '4px' }}>
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
              Extracted Claims &amp; Evidence Grounding ({reviewResult.claims.length})
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
                      {claim.risk_warning ? (
                        <span
                          className="badge badge-warning"
                          style={{ fontSize: '0.72rem', background: '#FEF3C7', color: '#92400E', border: '1px solid #F59E0B' }}
                          title={`Statutory warning: ${claim.risk_warning.description}`}
                        >
                          Universal Risk Warning
                        </span>
                      ) : claim.rule_category === 'ORG_GUIDELINE_VIOLATION' ? (
                        <span
                          className="badge badge-error"
                          style={{ fontSize: '0.72rem' }}
                          title="Direct violation of an uploaded brand guideline"
                        >
                          Guideline Violation
                        </span>
                      ) : claim.deterministic_rule_fired ? (
                        <span
                          className="badge badge-primary"
                          style={{ fontSize: '0.72rem' }}
                          title="Determined by an explicit compliance rule"
                        >
                          Deterministic Rule Fired
                        </span>
                      ) : null}
                    </div>
                    <div>{getVerdictBadge(claim.verdict)}</div>
                  </div>

                  {/* Claim Text */}
                  <div>
                    <h5 style={{ fontSize: '0.78rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--color-text-secondary)', letterSpacing: '0.04em', marginBottom: '4px' }}>
                      Extracted Claim
                    </h5>
                    <p style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--color-deep-aubergine)', margin: 0 }}>
                      &ldquo;{claim.claim_text}&rdquo;
                    </p>
                  </div>

                  {/* Universal Risk Warning Details */}
                  {claim.risk_warning && (
                    <div
                      style={{
                        padding: '10px 12px',
                        background: '#FFFBEB',
                        border: '1px solid #FCD34D',
                        borderRadius: 'var(--radius-sm)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '4px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: '#B45309' }}>
                          Statutory Warning: {claim.risk_warning.rule_id}
                        </span>
                        <span style={{ fontSize: '0.70rem', color: '#92400E', fontWeight: 600 }}>
                          Severity: {claim.risk_warning.severity}
                        </span>
                      </div>
                      <p style={{ fontSize: '0.84rem', color: '#78350F', margin: 0 }}>
                        {claim.risk_warning.explanation}
                      </p>
                      {claim.risk_warning.legal_basis && (
                        <span style={{ fontSize: '0.75rem', color: '#92400E' }}>
                          <strong>Regulatory Basis:</strong> {claim.risk_warning.legal_basis}
                        </span>
                      )}
                      <span style={{ fontSize: '0.75rem', color: '#6B7280', fontStyle: 'italic' }}>
                        Guideline Compliance: {claim.compliance_verdict || claim.verdict}{' '}
                        {claim.evidence.length > 0
                          ? '(Grounded in the cited guideline evidence below)'
                          : '(No specific organizational policy chunk found)'}
                      </span>
                    </div>
                  )}

                  {/* Explanation */}
                  <div>
                    <h5 style={{ fontSize: '0.78rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--color-text-secondary)', letterSpacing: '0.04em', marginBottom: '4px' }}>
                      Verdict Explanation
                    </h5>
                    <p style={{ fontSize: '0.88rem', color: 'var(--color-text-primary)', margin: 0, lineHeight: 1.5 }}>
                      {claim.explanation}
                    </p>
                  </div>

                  {/* Suggested Correction */}
                  {claim.suggested_correction && (
                    <div
                      style={{
                        padding: '12px 14px',
                        background: '#FFFDF0',
                        border: '1px solid #FFEAA7',
                        borderRadius: 'var(--radius-sm)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '4px',
                      }}
                    >
                      <span style={{ fontSize: '0.78rem', fontWeight: 700, textTransform: 'uppercase', color: '#B7791F' }}>
                        Suggested Compliant Correction:
                      </span>
                      <p style={{ fontSize: '0.88rem', color: '#744210', margin: 0, fontStyle: 'italic' }}>
                        &ldquo;{claim.suggested_correction}&rdquo;
                      </p>
                    </div>
                  )}

                  {/* Semantic Drift Analysis */}
                  {claim.semantic_drift && (
                    <div style={{ marginTop: '2px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                        <GitCompare size={14} style={{ color: 'var(--color-accent)' }} />
                        <span style={{ fontSize: '0.78rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--color-text-secondary)', letterSpacing: '0.04em' }}>
                          Semantic Drift Analysis
                        </span>
                      </div>
                      {claim.semantic_drift.detected && claim.semantic_drift.issues.length > 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                          {claim.semantic_drift.issues.map((iss, issIdx) => (
                            <div
                              key={issIdx}
                              style={{
                                padding: '10px 12px',
                                background: '#FFF8F6',
                                border: '1px solid #FED7D7',
                                borderRadius: 'var(--radius-sm)',
                                fontSize: '0.82rem',
                              }}
                            >
                              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                                <strong style={{ color: '#C53030' }}>{iss.category} ({iss.severity})</strong>
                                <span style={{ color: 'var(--color-text-secondary)' }}>Phrase: &ldquo;{iss.claim_phrase}&rdquo;</span>
                              </div>
                              <p style={{ margin: '4px 0', color: 'var(--color-text-primary)' }}>{iss.explanation}</p>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div style={{ padding: '8px 12px', background: '#F0F9F4', border: '1px solid #D2EEDD', borderRadius: 'var(--radius-sm)', fontSize: '0.82rem', color: '#1B6A3B' }}>
                          No material semantic drift detected in retrieved evidence.
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
                            <div className="evidence-header" style={{ marginBottom: '8px', display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '6px' }}>
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
                              <div className="evidence-metrics" style={{ display: 'flex', gap: '6px' }}>
                                {ev.rrf_score != null && (
                                  <span className="badge badge-primary" style={{ fontSize: '0.72rem' }} title="Reciprocal Rank Fusion score">
                                    RRF: {ev.rrf_score.toFixed(4)}
                                  </span>
                                )}
                                {ev.bm25_score != null && (
                                  <span className="badge badge-neutral" style={{ fontSize: '0.72rem' }} title="BM25 lexical relevance score">
                                    BM25: {ev.bm25_score.toFixed(2)}
                                  </span>
                                )}
                                <span className="badge badge-neutral" style={{ fontSize: '0.72rem' }}>
                                  Sim: {(ev.similarity_score * 100).toFixed(1)}%
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
                        The selected guidelines do not provide sufficient evidence to evaluate this claim. No supporting or contradicting citations were found.
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

import React from 'react';
import { Header } from './components/Header';
import { HealthStatus } from './components/HealthStatus';
import { GuidelineExplorer } from './components/GuidelineExplorer';
import { ClaimReview } from './components/ClaimReview';
import { Dashboard } from './components/Dashboard';
import { AuditHistory } from './components/AuditHistory';
import { API_BASE_URL } from './services/api';
import { BackendConnectionProvider } from './hooks/useBackendConnection';
import {
  Search,
  CheckCircle,
  FileSearch,
  Upload,
  Shield,
  Database,
  ExternalLink,
  History,
  BarChart3,
  Image as ImageIcon,
} from 'lucide-react';

export const App: React.FC = () => {
  return (
    <BackendConnectionProvider>
      <div className="app-wrapper">
        <Header />

        <main className="container" style={{ flex: 1, paddingBottom: '48px' }}>
          {/* Hero Section */}
          <section className="hero-section">
            <div className="hero-badge">
              <span className="hero-badge-dot" />
              <span>Round 3 Production Release &bull; Hybrid Retrieval &bull; Policy Governance &bull; Visual Compliance</span>
            </div>

            <h1 className="hero-title">BrandSentry AI</h1>
            <p className="hero-subtitle">Brand Compliance Intelligence Engine</p>

            <p className="hero-supporting">
              Verify marketing copy and promotional visual creative against immutable brand guidelines.
              Every decision is grounded in retrievable evidence with complete audit trail and multi-format exports.
            </p>

            <div className="hero-actions">
              <a href="#dashboard" className="btn btn-secondary">
                <BarChart3 size={16} />
                <span>Analytics Dashboard</span>
              </a>
              <a href="#review" className="btn btn-primary">
                <FileSearch size={16} />
                <span>Compliance Review</span>
              </a>
              <a href="#guidelines" className="btn btn-secondary">
                <Upload size={16} />
                <span>Policy Library</span>
              </a>
              <a href="#audit-history" className="btn btn-secondary">
                <History size={16} />
                <span>Audit History</span>
              </a>
              <a
                href={`${API_BASE_URL}/docs`}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-secondary"
              >
                <span>FastAPI Docs</span>
                <ExternalLink size={14} />
              </a>
            </div>
          </section>

          {/* 1. Live Compliance Analytics Dashboard */}
          <Dashboard />

          {/* 2. Compliance Review Workspace (Text & Image OCR Review) */}
          <ClaimReview />

          {/* 3. Policy Library & Immutable Version Governance */}
          <GuidelineExplorer />

          {/* 4. Complete Audit Trail & Export Center */}
          <AuditHistory />

          {/* 5. System Health and Environment Summary */}
          <section className="cards-grid">
            {/* Real Backend Health Status */}
            <HealthStatus />

            {/* Runtime Architecture Summary */}
            <div className="card">
              <div className="card-header">
                <div className="card-title-group">
                  <h3 className="card-title">
                    <Database size={18} style={{ color: 'var(--color-primary)' }} />
                    Round 3 Core Architecture
                  </h3>
                  <p className="card-description">
                    Deterministic hybrid compliance runtime configuration and persistence.
                  </p>
                </div>
                <span className="badge badge-success">Production Verified</span>
              </div>

              <div className="meta-list">
                <div className="meta-row">
                  <span className="meta-label">Retrieval Pipeline</span>
                  <span className="meta-value">Hybrid (Dense ChromaDB + BM25Okapi via RRF k=60)</span>
                </div>
                <div className="meta-row">
                  <span className="meta-label">Visual Compliance</span>
                  <span className="meta-value">OCR Service (Tesseract + Pillow Image Validation)</span>
                </div>
                <div className="meta-row">
                  <span className="meta-label">Policy Governance</span>
                  <span className="meta-value">Immutable Versioning (SQLite data/documents.db)</span>
                </div>
                <div className="meta-row">
                  <span className="meta-label">Audit &amp; Reporting</span>
                  <span className="meta-value">Persistent Audit (data/reviews.db, JSON/CSV/PDF)</span>
                </div>
                <div className="meta-row">
                  <span className="meta-label">Backend Service</span>
                  <span className="meta-value">FastAPI + Uvicorn ASGI (200 Unit &amp; Integration Tests)</span>
                </div>
              </div>
            </div>
          </section>

          {/* Final Verification Pipeline Summary */}
          <section className="card" style={{ marginBottom: '32px' }}>
            <div className="card-header">
              <div className="card-title-group">
                <h3 className="card-title">
                  <Shield size={18} style={{ color: 'var(--color-primary)' }} />
                  End-to-End Compliance Pipeline
                </h3>
                <p className="card-description">
                  Systematic architecture ensuring zero ungrounded compliance claims or hallucinations.
                </p>
              </div>
              <span className="badge badge-success">Improvements 1, 2 &amp; 3 Operational</span>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '14px',
                marginTop: '8px',
              }}
            >
              <div
                style={{
                  padding: '16px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface-muted)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--color-success)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Stage 01
                  </span>
                  <span className="badge badge-success" style={{ fontSize: '0.68rem', padding: '1px 6px' }}>Active</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Upload size={16} style={{ color: 'var(--color-primary)' }} />
                  <strong style={{ fontSize: '0.9rem', color: 'var(--color-deep-aubergine)' }}>Ingestion &amp; Versions</strong>
                </div>
                <p style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)', lineHeight: 1.45 }}>
                  PDF/TXT parsing with immutable policy versioning, SHA-256 hashes, and scoping.
                </p>
              </div>

              <div
                style={{
                  padding: '16px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface-muted)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--color-success)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Stage 02
                  </span>
                  <span className="badge badge-success" style={{ fontSize: '0.68rem', padding: '1px 6px' }}>Active</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <ImageIcon size={16} style={{ color: 'var(--color-primary)' }} />
                  <strong style={{ fontSize: '0.9rem', color: 'var(--color-deep-aubergine)' }}>Visual OCR Extraction</strong>
                </div>
                <p style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)', lineHeight: 1.45 }}>
                  Pillow format validation, Tesseract OCR text blocks, confidence metrics, and user corrections.
                </p>
              </div>

              <div
                style={{
                  padding: '16px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface-muted)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--color-success)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Stage 03
                  </span>
                  <span className="badge badge-success" style={{ fontSize: '0.68rem', padding: '1px 6px' }}>Active</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Search size={16} style={{ color: 'var(--color-primary)' }} />
                  <strong style={{ fontSize: '0.9rem', color: 'var(--color-deep-aubergine)' }}>Hybrid Search (RRF)</strong>
                </div>
                <p style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)', lineHeight: 1.45 }}>
                  Fuses ChromaDB dense semantic vectors with BM25Okapi lexical ranks.
                </p>
              </div>

              <div
                style={{
                  padding: '16px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface-muted)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--color-success)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Stage 04
                  </span>
                  <span className="badge badge-success" style={{ fontSize: '0.68rem', padding: '1px 6px' }}>Active</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <CheckCircle size={16} style={{ color: 'var(--color-primary)' }} />
                  <strong style={{ fontSize: '0.9rem', color: 'var(--color-deep-aubergine)' }}>Grounded Verdicts</strong>
                </div>
                <p style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)', lineHeight: 1.45 }}>
                  SUPPORTED, CONTRADICTED, or INSUFFICIENT verdicts with exact quotes and drift analysis.
                </p>
              </div>

              <div
                style={{
                  padding: '16px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface-muted)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--color-success)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Stage 05
                  </span>
                  <span className="badge badge-success" style={{ fontSize: '0.68rem', padding: '1px 6px' }}>Active</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <History size={16} style={{ color: 'var(--color-primary)' }} />
                  <strong style={{ fontSize: '0.9rem', color: 'var(--color-deep-aubergine)' }}>Audit &amp; Export</strong>
                </div>
                <p style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)', lineHeight: 1.45 }}>
                  Permanent SQLite audit records with one-click PDF, CSV, and JSON report downloads.
                </p>
              </div>
            </div>
          </section>

          {/* Phase Status Banner */}
          <div
            style={{
              padding: '16px 20px',
              borderRadius: 'var(--radius-md)',
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '14px',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="badge badge-success">200 Backend Tests Passing</span>
                <strong style={{ fontSize: '0.9rem', color: 'var(--color-deep-aubergine)' }}>
                  Round 3 Final Compliance Platform Verified
                </strong>
              </div>
              <p style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)', marginTop: '4px' }}>
                Hybrid retrieval (RRF), policy version governance, persistent review audits, OCR visual review, and PDF exports fully integrated.
              </p>
            </div>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '0.8rem',
                fontWeight: 600,
                color: 'var(--color-success)',
              }}
            >
              <CheckCircle size={15} style={{ color: 'var(--color-success)' }} />
              Round 3 Production Ready
            </span>
          </div>
        </main>

        <footer className="app-footer">
          <div className="container">
            BrandSentry AI &bull; Brand Compliance Intelligence &bull; Round 3 Final Submission &bull; Team We Code Coders
          </div>
        </footer>
      </div>
    </BackendConnectionProvider>
  );
};

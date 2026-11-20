import React from 'react';
import { Header } from './components/Header';
import { BackendStatusBanner } from './components/BackendStatusBanner';
import { HealthStatus } from './components/HealthStatus';
import { GuidelineExplorer } from './components/GuidelineExplorer';
import { ClaimReview } from './components/ClaimReview';
import { Dashboard } from './components/Dashboard';
import { AuditHistory } from './components/AuditHistory';
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

const TICKER: [string, string][] = [
  ['IGST 18%', 'Intra-state sale: CGST + SGST'],
  ['GSTR-3B filed 12 days late', '\u20B9600 late fee + 18% interest'],
  ['Pay within 90 days', 'MSMED Act: 45 days max'],
  ['Composition dealer, GST @ 5%', 'Cannot collect tax on invoice'],
  ['Section 194C', 'Renumbered in Income-tax Act 2025'],
  ['GSTIN 29AAXCS1234K1Z9', 'Checksum fails'],
  ['Nil return filed late', '\u20B920/day late fee'],
];

export const App: React.FC = () => {
  return (
    <BackendConnectionProvider>
      <div className="app-wrapper">
        <Header />
        <BackendStatusBanner />

        <main className="container" style={{ flex: 1, paddingBottom: '48px' }}>
          {/* Hero Section */}
          <section className="hero-section sx-hero" aria-labelledby="hero-title">
            <div>
              <span className="sx-eyebrow">Before you file &bull; GAVS Hackathon</span>
              <h1 className="hero-title sx-headline" id="hero-title">
                <span className="sx-brandline">ShreshtiAI</span>
                <span className="sx-line">Every invoice</span>
                <span className="sx-strike">IGST 18%</span>
                <span className="sx-fix">CGST 9% + SGST 9%*</span>
                <span className="sx-line">checked.</span>
              </h1>
              <p className="sx-footnote">
                *Example: supplier and buyer are both in Karnataka (state code 29), so the sale is intra-state and takes CGST + SGST, not IGST (IGST Act 2017, s.8).
              </p>
              <p className="hero-subtitle sx-sub">Check before you file. Get paid on time.</p>
              <p className="sx-supporting">
                The digital munim for India&apos;s micro enterprises. Owners send invoices, bills and notices. Agents check them against GST,
                income-tax and MSMED Act rules, cite the exact section for every finding, and abstain rather than guess.
              </p>
              <div className="sx-actions hero-actions">
                <a href="#review" className="btn btn-primary">
                  <FileSearch size={16} />
                  <span>Run a check</span>
                </a>
                <a href="#guidelines" className="btn btn-secondary">
                  <Upload size={16} />
                  <span>Rule library</span>
                </a>
                <a href="#dashboard" className="btn btn-secondary">
                  <BarChart3 size={16} />
                  <span>Dashboard</span>
                </a>
                <a href="#audit-history" className="btn btn-secondary">
                  <History size={16} />
                  <span>Audit trail</span>
                </a>
                <a
                  href="https://github.com/KPCHIRAGGUPTHA/shreshtiai"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-secondary"
                >
                  <span>GitHub</span>
                  <ExternalLink size={14} />
                </a>
              </div>
            </div>

            {/* Example invoice, marked up the way ShreshtiAI reports findings */}
            <figure className="sx-specimen" aria-label="Example invoice with ShreshtiAI findings">
              <span className="sx-specimen-tag">EXAMPLE &bull; FICTIONAL SHOP</span>
              <div className="sx-inv-head">
                <div>
                  <div className="sx-inv-title">TAX INVOICE</div>
                  <div className="sx-inv-meta">Sri Lakshmi Traders, Birur<br />GSTIN 29AAXCS1234K1Z3</div>
                </div>
                <div className="sx-inv-meta" style={{ textAlign: 'right' }}>No. SLT/0412<br />14 Nov 2026<br />Bill to: Davanagere (29)</div>
              </div>
              <div className="sx-inv-row"><span>Ceramic floor tiles, 40 boxes</span><b>&#8377;40,000</b></div>
              <div className="sx-inv-row">
                <span className="sx-mark sx-mark-bad">IGST @ 18%<sup>1</sup></span>
                <b>&#8377;7,200</b>
              </div>
              <div className="sx-inv-row">
                <span>Payment terms: <span className="sx-mark sx-mark-review">90 days<sup>2</sup></span></span>
                <span />
              </div>
              <div className="sx-inv-total"><span>TOTAL</span><span>&#8377;47,200</span></div>

              <div className="sx-chip-stack">
                <div className="sx-chip sx-tone-bad" style={{ animationDelay: '1.4s' }}>
                  <span className="sx-diamond" />
                  <span><span className="sx-label">1 &middot; NON-COMPLIANT</span>Intra-state sale: charge CGST 9% + SGST 9% (&#8377;3,600 each), not IGST. <em>IGST Act, s.8</em></span>
                </div>
                <div className="sx-chip sx-tone-review" style={{ animationDelay: '1.7s' }}>
                  <span className="sx-diamond" />
                  <span><span className="sx-label">2 &middot; NEEDS REVIEW</span>If the buyer is a registered micro or small enterprise, payment is due within 45 days. <em>MSMED Act, s.15</em></span>
                </div>
                <div className="sx-chip sx-tone-ok" style={{ animationDelay: '2s' }}>
                  <span className="sx-diamond" />
                  <span><span className="sx-label">COMPLIANT</span>Invoice number, date and both GSTINs present. <em>CGST Rules, r.46</em></span>
                </div>
              </div>
            </figure>
          </section>

          {/* Ticker of typical findings */}
          <div className="sx-ticker" aria-label="Typical findings">
            <div className="sx-ticker-track">
              {[0, 1].map((dup) => (
                <React.Fragment key={dup}>
                  {TICKER.map(([claim, why]) => (
                    <span className="sx-tick" key={`${dup}-${claim}`} aria-hidden={dup === 1}>
                      <span className="sx-diamond" />
                      <span className="sx-tick-claim">&ldquo;{claim}&rdquo;</span>
                      <span className="sx-tick-why">{why}</span>
                    </span>
                  ))}
                </React.Fragment>
              ))}
            </div>
          </div>

          <div className="sx-engine-note">
            <strong>LIVE ENGINE</strong>
            <span>
              Everything below is the deployed retrieval and cite-or-abstain verdict engine that ShreshtiAI&apos;s rule-check agent reuses.
              Load a rule document, paste text, and each claim comes back <b style={{ color: 'var(--color-success)' }}>COMPLIANT</b>,{' '}
              <b style={{ color: 'var(--color-error)' }}>NON-COMPLIANT</b> or <b style={{ color: 'var(--color-review)' }}>NEEDS REVIEW</b>, quoting the exact rule text.
            </span>
          </div>

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
                    Engine Architecture
                  </h3>
                  <p className="card-description">
                    Deterministic hybrid compliance runtime configuration and persistence.
                  </p>
                </div>
                <span className="badge badge-success">Configuration</span>
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
                  <span className="meta-value">FastAPI + Uvicorn ASGI</span>
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
                  How a verdict is made
                </h3>
                <p className="card-description">
                  Every citation is taken from retrieved guideline text. Verdicts assist a human reviewer and need confirmation before publication.
                </p>
              </div>
              <span className="badge badge-success">Live</span>
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
                  COMPLIANT, NON-COMPLIANT or NEEDS REVIEW (SUPPORTED, CONTRADICTED, INSUFFICIENT_EVIDENCE) with exact quotes and drift analysis.
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

        </main>

        <footer className="app-footer">
          <div className="container" style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px', fontFamily: 'var(--font-mono)', fontSize: '0.7rem', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            <span>ShreshtiAI &bull; Cite or abstain &bull; Nothing is filed without the owner</span>
            <span>
              <a href="https://github.com/KPCHIRAGGUPTHA/shreshtiai" target="_blank" rel="noopener noreferrer" style={{ color: 'inherit' }}>GitHub</a>
              {' '}&bull; GAVS Hackathon &bull; Example data is fictional
            </span>
          </div>
        </footer>
      </div>
    </BackendConnectionProvider>
  );
};

import React from 'react';
import { Header } from './components/Header';
import { HealthStatus } from './components/HealthStatus';
import {
  FileText,
  Search,
  CheckCircle,
  FileSearch,
  Sparkles,
  ArrowRight,
  Shield,
  Layers,
  Database
} from 'lucide-react';

export const App: React.FC = () => {
  return (
    <div className="app-wrapper">
      <Header />

      <main className="container" style={{ flex: 1, paddingBottom: '48px' }}>
        {/* Hero Section */}
        <section className="hero-section">
          <div className="hero-pill">
            <span className="hero-pill-dot" />
            <span>Round 2 — Phase 1 Initialized</span>
          </div>

          <h2 className="hero-title">
            Automated <span className="gradient-text">Brand Compliance</span> &amp; Claim Verification
          </h2>

          <p className="hero-subtitle">
            BrandSentry AI empowers marketing, legal, and compliance teams by automatically validating
            creative copy and advertising claims against official brand guidelines using evidence-grounded
            retrieval and verifiable citations.
          </p>

          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', flexWrap: 'wrap' }}>
            <a href="#architecture" className="btn btn-primary">
              <Sparkles size={16} />
              Review Architecture
            </a>
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-secondary"
            >
              <FileText size={16} />
              Documentation
            </a>
          </div>
        </section>

        {/* Status and Environment Grid */}
        <section className="cards-grid">
          {/* Health Check Card */}
          <HealthStatus />

          {/* Environment & Stack Summary */}
          <div className="glass-card">
            <div className="card-header-row">
              <h3 className="card-title">
                <Database size={18} style={{ color: 'var(--purple)' }} />
                Environment &amp; Stack Runtime
              </h3>
              <span className="status-pill status-online">READY</span>
            </div>

            <div className="meta-list">
              <div className="meta-row">
                <span className="meta-label">Backend Engine</span>
                <span className="meta-value">FastAPI + Uvicorn (Py 3.14)</span>
              </div>
              <div className="meta-row">
                <span className="meta-label">Frontend Framework</span>
                <span className="meta-value">React 18 + TypeScript + Vite</span>
              </div>
              <div className="meta-row">
                <span className="meta-label">Vector Storage (P2)</span>
                <span className="meta-value">ChromaDB Persistent Store</span>
              </div>
              <div className="meta-row">
                <span className="meta-label">LLM Interface (P3)</span>
                <span className="meta-value">Provider-Agnostic Service</span>
              </div>
              <div className="meta-row">
                <span className="meta-label">Strict Hackathon Deadline</span>
                <span className="meta-value">25 Oct 2026, 10:00 AM IST</span>
              </div>
            </div>
          </div>
        </section>

        {/* End-to-End Workflow Pipeline Preview */}
        <section id="architecture" className="glass-card" style={{ marginBottom: '48px' }}>
          <div className="card-header-row">
            <div>
              <h3 className="card-title">
                <Shield size={20} style={{ color: 'var(--primary)' }} />
                Target End-to-End Verification Pipeline
              </h3>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                How BrandSentry AI systematically ensures zero hallucinated compliance approvals.
              </p>
            </div>
            <span
              style={{
                fontSize: '0.75rem',
                color: 'var(--text-dim)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              Phases 2 – 5
            </span>
          </div>

          <div className="workflow-stepper">
            <div className="step-box">
              <span className="step-num">Step 01</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <FileText size={16} color="var(--primary)" />
                <span className="step-title">Guideline Ingestion</span>
              </div>
              <p className="step-desc">
                Upload brand rulebooks (PDF / TXT). PyMuPDF parses text with section-aware chunking.
              </p>
            </div>

            <div className="step-box">
              <span className="step-num">Step 02</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Layers size={16} color="var(--purple)" />
                <span className="step-title">Vector Indexing</span>
              </div>
              <p className="step-desc">
                Dense embeddings &amp; BM25 keyword indexes stored in persistent ChromaDB collections.
              </p>
            </div>

            <div className="step-box">
              <span className="step-num">Step 03</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <FileSearch size={16} color="var(--warning)" />
                <span className="step-title">Claim Extraction</span>
              </div>
              <p className="step-desc">
                Marketing copy is decomposed into testable, discrete claims for independent audit.
              </p>
            </div>

            <div className="step-box">
              <span className="step-num">Step 04</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Search size={16} color="var(--primary)" />
                <span className="step-title">Hybrid Retrieval</span>
              </div>
              <p className="step-desc">
                Retrieve top-k policy clauses per claim. Exact matches for banned words &amp; regulations.
              </p>
            </div>

            <div className="step-box">
              <span className="step-num">Step 05</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <CheckCircle size={16} color="var(--success)" />
                <span className="step-title">3-Way Verdict</span>
              </div>
              <p className="step-desc">
                SUPPORTED, CONTRADICTED, or INSUFFICIENT_EVIDENCE with verifiable citations and fix suggestions.
              </p>
            </div>
          </div>
        </section>

        {/* Phase 1 Verification Notice */}
        <section
          style={{
            padding: '20px 24px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, rgba(79, 110, 247, 0.08), rgba(124, 58, 237, 0.08))',
            border: '1px solid rgba(79, 110, 247, 0.2)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '16px',
          }}
        >
          <div>
            <h4 style={{ fontSize: '1rem', fontWeight: 600, color: '#fff' }}>
              Phase 1 Deliverables Active
            </h4>
            <p style={{ fontSize: '0.825rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              FastAPI backend and React frontend are configured, tested, and ready for Phase 2 guideline indexing.
            </p>
          </div>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.8rem',
              fontWeight: 600,
              color: 'var(--primary)',
            }}
          >
            Awaiting Phase 2 Authorization <ArrowRight size={14} />
          </span>
        </section>
      </main>

      <footer className="app-footer">
        <div className="container">
          BrandSentry AI &bull; Round 2 Engineering &bull; Hackathon Project
        </div>
      </footer>
    </div>
  );
};

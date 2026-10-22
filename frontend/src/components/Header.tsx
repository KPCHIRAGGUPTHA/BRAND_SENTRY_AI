import React from 'react';
import { ShieldCheck, ExternalLink } from 'lucide-react';

export const Header: React.FC = () => {
  return (
    <header className="app-header">
      <div className="container header-content">
        <a href="#" className="logo-group" aria-label="BrandSentry AI Home">
          <div className="logo-icon" aria-hidden="true">
            <ShieldCheck size={22} strokeWidth={2.4} />
          </div>
          <div className="brand-text">
            <span className="brand-title">BrandSentry AI</span>
            <span className="brand-tagline">Brand Compliance Intelligence</span>
          </div>
        </a>

        <nav className="header-nav" aria-label="Main Navigation">
          <a href="#guidelines" className="nav-link active">
            Guidelines
          </a>
          <a href="#search" className="nav-link">
            Semantic Search
          </a>
          <a href="#status" className="nav-link">
            System Status
          </a>
          <a
            href="http://127.0.0.1:8000/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-secondary"
            style={{ fontSize: '0.78rem', padding: '5px 12px', gap: '6px' }}
          >
            <span>API Docs</span>
            <ExternalLink size={12} />
          </a>
        </nav>
      </div>
    </header>
  );
};

import React from 'react';
import { ShieldCheck } from 'lucide-react';

export const Header: React.FC = () => {
  return (
    <header className="app-header">
      <div className="container header-content">
        <div className="logo-group">
          <div className="logo-icon" aria-label="BrandSentry Shield">
            <ShieldCheck size={24} />
          </div>
          <div className="brand-text">
            <h1>BrandSentry AI</h1>
          </div>
          <span className="brand-badge">Phase 1 Foundation</span>
        </div>
        <div>
          <a
            href="http://127.0.0.1:8000/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-secondary"
            style={{ fontSize: '0.78rem', padding: '6px 14px' }}
          >
            API Docs
          </a>
        </div>
      </div>
    </header>
  );
};

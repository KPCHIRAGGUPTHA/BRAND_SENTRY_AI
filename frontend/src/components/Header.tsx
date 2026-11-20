import React from 'react';
import { ExternalLink } from 'lucide-react';
import { API_BASE_URL } from '../services/api';
import { DEMO_EVENTS } from '../samples/gstSample';

export const Header: React.FC = () => {
  return (
    <header className="app-header">
      <div className="container header-content">
        <a href="#" className="logo-group" aria-label="ShreshtiAI Home">
          <div className="logo-icon" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M10 1v7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              <path d="M4 1h12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              <rect x="10" y="9" width="7" height="7" transform="rotate(45 10 9)" fill="currentColor" />
            </svg>
          </div>
          <div className="brand-text">
            <span className="brand-title">ShreshtiAI</span>
            <span className="brand-tagline">The digital munim</span>
          </div>
        </a>

        <nav className="header-nav" aria-label="Main Navigation">
          <a href="#review" className="nav-link active">
            Check
          </a>
          <a href="#guidelines" className="nav-link">
            Rule Library
          </a>
          <a href="#search" className="nav-link">
            Search Rules
          </a>
          <a href="#status" className="nav-link">
            Status
          </a>
          <button
            type="button"
            className="btn btn-primary tour-launch"
            id="start-tour"
            onClick={() => window.dispatchEvent(new Event(DEMO_EVENTS.startTour))}
            style={{ padding: '5px 12px' }}
          >
            Tour
          </button>
          <a
            href={`${API_BASE_URL}/docs`}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-secondary"
            style={{ fontSize: '0.72rem', padding: '5px 12px', gap: '6px', textTransform: 'uppercase', letterSpacing: '0.08em' }}
          >
            <span>API</span>
            <ExternalLink size={12} />
          </a>
        </nav>
      </div>
    </header>
  );
};

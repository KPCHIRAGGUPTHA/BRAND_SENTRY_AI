import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Server, AlertCircle, CheckCircle2 } from 'lucide-react';
import { fetchHealth } from '../services/api';
import { HealthResponse } from '../types/api';

export const HealthStatus: React.FC = () => {
  const [data, setData] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<string | null>(null);

  const checkHealth = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchHealth();
      setData(result);
      setError(null);
    } catch (err: unknown) {
      setData(null);
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Unable to establish connection to backend service');
      }
    } finally {
      setLoading(false);
      setLastChecked(new Date().toLocaleTimeString());
    }
  }, []);

  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  const isOnline = !loading && !error && data?.status === 'ok';

  return (
    <div className="glass-card">
      <div className="card-header-row">
        <h3 className="card-title">
          <Server size={18} style={{ color: 'var(--primary)' }} />
          Backend Service Status
        </h3>
        <div>
          {loading ? (
            <span className="status-pill status-checking">
              <span className="pulse-dot" /> CHECKING
            </span>
          ) : isOnline ? (
            <span className="status-pill status-online">
              <span className="pulse-dot" /> ONLINE
            </span>
          ) : (
            <span className="status-pill status-offline">
              <span className="pulse-dot" /> DISCONNECTED
            </span>
          )}
        </div>
      </div>

      <div className="meta-list">
        <div className="meta-row">
          <span className="meta-label">Target URL</span>
          <span className="meta-value">http://127.0.0.1:8000/health</span>
        </div>

        {isOnline && data && (
          <>
            <div className="meta-row">
              <span className="meta-label">Service</span>
              <span className="meta-value">{data.service}</span>
            </div>
            <div className="meta-row">
              <span className="meta-label">Version</span>
              <span className="meta-value">{data.version}</span>
            </div>
            <div className="meta-row">
              <span className="meta-label">Environment</span>
              <span className="meta-value">{data.environment}</span>
            </div>
          </>
        )}

        <div className="meta-row">
          <span className="meta-label">Last Polled</span>
          <span className="meta-value">{lastChecked || 'Never'}</span>
        </div>
      </div>

      {error && (
        <div
          style={{
            marginTop: '16px',
            padding: '12px',
            borderRadius: '8px',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '10px',
            fontSize: '0.825rem',
            color: '#FCA5A5',
          }}
        >
          <AlertCircle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>
            <strong>Backend Connection Offline</strong>
            <p style={{ marginTop: '4px', color: 'var(--text-muted)' }}>{error}</p>
            <p style={{ marginTop: '6px', fontSize: '0.75rem', color: 'var(--text-dim)' }}>
              Tip: Start the backend with: <code>uvicorn backend.app.main:app --port 8000 --reload</code>
            </p>
          </div>
        </div>
      )}

      {isOnline && (
        <div
          style={{
            marginTop: '16px',
            padding: '10px 12px',
            borderRadius: '8px',
            backgroundColor: 'rgba(16, 185, 129, 0.08)',
            border: '1px solid rgba(16, 185, 129, 0.25)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '0.8rem',
            color: '#86EFAC',
          }}
        >
          <CheckCircle2 size={16} />
          FastAPI ASGI service is healthy and accepting requests.
        </div>
      )}

      <div style={{ marginTop: '16px', display: 'flex', justifyContent: 'flex-end' }}>
        <button
          className="btn btn-secondary"
          onClick={checkHealth}
          disabled={loading}
          style={{ fontSize: '0.8rem', padding: '6px 14px' }}
        >
          <RefreshCw size={14} className={loading ? 'pulse-dot' : ''} />
          {loading ? 'Polling...' : 'Re-check Connection'}
        </button>
      </div>
    </div>
  );
};

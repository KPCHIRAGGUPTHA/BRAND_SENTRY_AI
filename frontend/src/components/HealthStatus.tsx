import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Server, AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';
import { fetchHealth, API_BASE_URL } from '../services/api';
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
  const isError = !loading && (error !== null || (data && data.status !== 'ok'));

  return (
    <div className="card" id="status">
      <div className="card-header">
        <div className="card-title-group">
          <h3 className="card-title">
            <Server size={18} style={{ color: 'var(--color-primary)' }} />
            Backend Service Status
          </h3>
          <p className="card-description">
            Live health verification with the FastAPI ASGI compliance backend.
          </p>
        </div>
        <div>
          {loading ? (
            <span className="badge badge-warning">
              <span className="pulse-indicator" />
              <span>Checking...</span>
            </span>
          ) : isOnline ? (
            <span className="badge badge-success">
              <CheckCircle2 size={13} />
              <span>Connected</span>
            </span>
          ) : (
            <span className="badge badge-error">
              <XCircle size={13} />
              <span>Unavailable</span>
            </span>
          )}
        </div>
      </div>

      <div className="meta-list">
        <div className="meta-row">
          <span className="meta-label">Endpoint</span>
          <span className="meta-value">{API_BASE_URL}/health</span>
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

      {isError && (
        <div className="alert alert-error" role="alert">
          <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>
            <strong style={{ display: 'block', marginBottom: '2px' }}>Backend Service Offline</strong>
            <span>{error || 'Service responded with non-ok status.'}</span>
            <div style={{ marginTop: '6px', fontSize: '0.78rem', color: 'var(--color-text-secondary)' }}>
              Start backend: <code style={{ fontFamily: 'var(--font-mono)', background: '#F4F6F8', padding: '2px 5px', borderRadius: '4px' }}>uvicorn backend.app.main:app --port 8000</code>
            </div>
          </div>
        </div>
      )}

      {isOnline && (
        <div className="alert alert-success" role="status">
          <CheckCircle2 size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
          <span>FastAPI backend is operational and accepting vector retrieval requests.</span>
        </div>
      )}

      <div style={{ marginTop: '16px', display: 'flex', justifyContent: 'flex-end' }}>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={checkHealth}
          disabled={loading}
          style={{ fontSize: '0.8rem', padding: '6px 14px' }}
        >
          <RefreshCw size={14} className={loading ? 'pulse-indicator' : ''} />
          <span>{loading ? 'Polling...' : 'Re-check Connection'}</span>
        </button>
      </div>
    </div>
  );
};

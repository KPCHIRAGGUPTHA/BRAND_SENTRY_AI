import React from 'react';
import { RefreshCw, Server, AlertTriangle, CheckCircle2, XCircle, Clock } from 'lucide-react';
import { API_BASE_URL } from '../services/api';
import { useBackendConnection } from '../hooks/useBackendConnection';

export const HealthStatus: React.FC = () => {
  const {
    status,
    data,
    error,
    lastChecked,
    retryCount,
    isChecking,
    checkHealth,
  } = useBackendConnection();

  const isOnline = status === 'connected' && data?.status === 'ok';

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
          {status === 'connecting' && (
            <span className="badge badge-warning" id="status-badge-connecting">
              <span className="pulse-indicator" />
              <span>Connecting to backend...</span>
            </span>
          )}
          {status === 'waking' && (
            <span className="badge badge-warning" id="status-badge-waking">
              <span className="pulse-indicator" />
              <span>Waking up backend...</span>
            </span>
          )}
          {status === 'connected' && (
            <span className="badge badge-success" id="status-badge-connected">
              <CheckCircle2 size={13} />
              <span>Connected</span>
            </span>
          )}
          {status === 'temporarily unavailable' && (
            <span className="badge badge-error" id="status-badge-unavailable">
              <XCircle size={13} />
              <span>Temporarily Unavailable</span>
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

        {(status === 'waking' || status === 'temporarily unavailable') && retryCount > 0 && (
          <div className="meta-row">
            <span className="meta-label">Retry Attempts</span>
            <span className="meta-value">{retryCount}</span>
          </div>
        )}

        <div className="meta-row">
          <span className="meta-label">Last Polled</span>
          <span className="meta-value">{lastChecked || 'Never'}</span>
        </div>
      </div>

      {status === 'connecting' && (
        <div className="alert alert-warning" role="status">
          <Clock size={16} className="spinning" style={{ flexShrink: 0, marginTop: '2px' }} />
          <span>Verifying connection to FastAPI backend...</span>
        </div>
      )}

      {status === 'waking' && (
        <div className="alert alert-warning" role="status" id="alert-waking">
          <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>
            <strong style={{ display: 'block', marginBottom: '2px' }}>
              Waking Up Backend Service
            </strong>
            <span>
              Render free tier services spin down after inactivity and may take 30–60 seconds to complete cold start.
              Automatic reconnection is in progress (Attempt #{retryCount}).
            </span>
            {error && (
              <div style={{ marginTop: '4px', fontSize: '0.78rem', color: 'var(--color-text-secondary)' }}>
                Latest response: {error}
              </div>
            )}
          </div>
        </div>
      )}

      {status === 'temporarily unavailable' && (
        <div className="alert alert-error" role="alert" id="alert-unavailable">
          <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>
            <strong style={{ display: 'block', marginBottom: '2px' }}>
              Backend Service Temporarily Unavailable
            </strong>
            <span>
              The backend service could not be reached after multiple retry attempts.
              Reconnection attempts continue with bounded backoff in the background.
            </span>
            {error && (
              <div style={{ marginTop: '4px', fontSize: '0.78rem', color: 'var(--color-error)' }}>
                Error detail: {error}
              </div>
            )}
            <div style={{ marginTop: '6px', fontSize: '0.78rem', color: 'var(--color-text-secondary)' }}>
              Local verification: <code style={{ fontFamily: 'var(--font-mono)', background: '#F4F6F8', padding: '2px 5px', borderRadius: '4px' }}>uvicorn backend.app.main:app --port 8000</code>
            </div>
          </div>
        </div>
      )}

      {status === 'connected' && (
        <div className="alert alert-success" role="status" id="alert-connected">
          <CheckCircle2 size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
          <span>FastAPI backend is operational and accepting vector retrieval requests.</span>
        </div>
      )}

      <div style={{ marginTop: '16px', display: 'flex', justifyContent: 'flex-end' }}>
        <button
          type="button"
          id="btn-recheck-health"
          className="btn btn-secondary"
          onClick={() => checkHealth(true)}
          disabled={isChecking}
          style={{ fontSize: '0.8rem', padding: '6px 14px' }}
        >
          <RefreshCw size={14} className={isChecking ? 'spinning' : ''} />
          <span>{isChecking ? 'Checking...' : 'Re-check Connection'}</span>
        </button>
      </div>
    </div>
  );
};

import React from 'react';
import { Clock, RefreshCw } from 'lucide-react';
import { useBackendConnection } from '../hooks/useBackendConnection';

/**
 * Shown at the top of the page whenever the backend is not ready, so a visitor arriving during a
 * free-tier cold start sees what is happening and that retrying is automatic.
 */
export const BackendStatusBanner: React.FC = () => {
  const { status, data, checkHealth, isChecking } = useBackendConnection();

  const warming = status === 'connected' && data?.readiness === 'warming';
  if (status === 'connected' && !warming) return null;

  const message = warming
    ? 'Server is up and loading the AI model and sample guideline. This takes under a minute.'
    : status === 'temporarily unavailable'
      ? 'Server is taking longer than usual to wake up (free tier). Still retrying automatically.'
      : 'Server is waking up (free tier), ~1 min. Retrying automatically, no need to refresh.';

  return (
    <div className="container" style={{ paddingTop: '12px' }}>
      <div className="alert alert-warning" role="status" id="backend-wake-banner">
        <Clock size={16} className="spinning" style={{ flexShrink: 0, marginTop: '2px' }} />
        <span style={{ flex: 1 }}>{message}</span>
        {!warming && (
          <button
            type="button"
            className="btn btn-secondary"
            id="backend-wake-retry"
            onClick={() => checkHealth(true)}
            disabled={isChecking}
          >
            <RefreshCw size={14} />
            <span>Retry now</span>
          </button>
        )}
      </div>
    </div>
  );
};

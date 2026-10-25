import {
  HealthResponse,
  GuidelineUploadResponse,
  GuidelineSearchResponse,
  DocumentListResponse,
  ReviewResponse,
} from '../types/api';

/**
 * Resolves the backend API base URL with safeguards:
 * 1. Checks VITE_API_BASE_URL and VITE_API_URL.
 * 2. If Render's blueprint injected a bare service name (e.g. "brandsentry-api" or "brandsentry-api:8000"),
 *    maps it to the full HTTPS public domain "https://brandsentry-api.onrender.com".
 * 3. If a naked domain without protocol was provided (e.g. "brandsentry-api.onrender.com"),
 *    prefixes "https://".
 * 4. In production deployed on *.onrender.com without env vars, infers "https://brandsentry-api.onrender.com".
 * 5. In local development, falls back to "http://127.0.0.1:8000".
 * 6. Strips any trailing slashes to prevent malformed double slashes.
 */
export function resolveApiBaseUrl(): string {
  let url = (
    import.meta.env.VITE_API_BASE_URL ||
    import.meta.env.VITE_API_URL ||
    ''
  ).trim();

  // If unset, detect if running on Render public domain
  if (!url) {
    if (typeof window !== 'undefined' && window.location.hostname.endsWith('.onrender.com')) {
      return 'https://brandsentry-api.onrender.com';
    }
    return 'http://127.0.0.1:8000';
  }

  // Handle Render internal service names from Blueprint `property: host`
  if (url === 'brandsentry-api' || url.startsWith('brandsentry-api:')) {
    return 'https://brandsentry-api.onrender.com';
  }

  // If domain provided without protocol
  if (!url.startsWith('http://') && !url.startsWith('https://') && !url.startsWith('/')) {
    url = `https://${url}`;
  }

  return url.replace(/\/+$/, '');
}

export const API_BASE_URL = resolveApiBaseUrl();

/**
 * Safely parses response JSON with robust diagnostics for HTML (SPA redirects)
 * and empty responses.
 */
export async function safeParseJson<T>(response: Response, context: string): Promise<T> {
  const text = await response.text();
  const trimmed = (text || '').trim();

  if (!trimmed) {
    throw new Error(`${context}: Empty response received from server (HTTP ${response.status})`);
  }

  if (trimmed.startsWith('<!doctype') || trimmed.startsWith('<html') || trimmed.startsWith('<?xml')) {
    throw new Error(
      `${context}: Server returned HTML instead of JSON (HTTP ${response.status}). Verify that the API URL '${response.url}' points to the backend server rather than the static frontend.`
    );
  }

  try {
    return JSON.parse(trimmed) as T;
  } catch {
    const snippet = trimmed.slice(0, 120);
    throw new Error(`${context}: Invalid JSON payload (HTTP ${response.status}): ${snippet}`);
  }
}

export async function fetchHealth(signal?: AbortSignal, timeoutMs: number = 10000): Promise<HealthResponse> {
  const controller = new AbortController();
  let timedOut = false;
  const timeoutId = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  const onExternalAbort = () => {
    controller.abort();
  };

  if (signal) {
    if (signal.aborted) {
      clearTimeout(timeoutId);
      controller.abort();
    } else {
      signal.addEventListener('abort', onExternalAbort, { once: true });
    }
  }

  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    if (signal) {
      signal.removeEventListener('abort', onExternalAbort);
    }

    if (!response.ok) {
      throw new Error(`Backend responded with HTTP status ${response.status} (${response.statusText})`);
    }

    return await safeParseJson<HealthResponse>(response, 'Health check');
  } catch (error: unknown) {
    clearTimeout(timeoutId);
    if (signal) {
      signal.removeEventListener('abort', onExternalAbort);
    }
    if (timedOut) {
      throw new Error('Connection timed out while reaching backend service');
    }
    if (error instanceof Error) {
      if (error.name === 'AbortError') {
        throw new Error('Health check aborted');
      }
      throw error;
    }
    throw new Error('An unknown error occurred while connecting to the backend');
  }
}

export async function uploadGuideline(file: File): Promise<GuidelineUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const url = `${API_BASE_URL}/api/guidelines/upload`;
  const response = await fetch(url, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => '');
    let errorDetail = `Upload failed with HTTP ${response.status}`;
    try {
      const parsed = JSON.parse(errorText);
      if (parsed.detail) {
        errorDetail = typeof parsed.detail === 'string' ? parsed.detail : JSON.stringify(parsed.detail);
      }
    } catch {
      const trimmed = errorText.trim();
      if (trimmed.startsWith('<!doctype') || trimmed.startsWith('<html')) {
        errorDetail = `Upload failed: Request reached static frontend (${url}) instead of backend API. Verify VITE_API_BASE_URL.`;
      } else if (trimmed) {
        errorDetail = `Upload failed (HTTP ${response.status}): ${trimmed.slice(0, 120)}`;
      }
    }
    throw new Error(errorDetail);
  }

  return await safeParseJson<GuidelineUploadResponse>(response, 'Guideline upload');
}

export async function searchGuidelines(
  query: string,
  documentId?: string,
  topK: number = 5
): Promise<GuidelineSearchResponse> {
  const payload: { query: string; document_id?: string; top_k: number } = {
    query,
    top_k: topK,
  };
  if (documentId) {
    payload.document_id = documentId;
  }

  const url = `${API_BASE_URL}/api/guidelines/search`;
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => '');
    let errorDetail = `Search failed with HTTP ${response.status}`;
    try {
      const parsed = JSON.parse(errorText);
      if (parsed.detail) {
        errorDetail = typeof parsed.detail === 'string' ? parsed.detail : JSON.stringify(parsed.detail);
      }
    } catch {
      if (errorText.trim()) {
        errorDetail = `Search failed: ${errorText.trim().slice(0, 120)}`;
      }
    }
    throw new Error(errorDetail);
  }

  return await safeParseJson<GuidelineSearchResponse>(response, 'Guideline search');
}

export async function fetchGuidelines(): Promise<DocumentListResponse> {
  const url = `${API_BASE_URL}/api/guidelines`;
  const response = await fetch(url, {
    method: 'GET',
    headers: { Accept: 'application/json' },
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => '');
    let errorDetail = `Fetching guidelines failed with HTTP ${response.status}`;
    try {
      const parsed = JSON.parse(errorText);
      if (parsed.detail) {
        errorDetail = typeof parsed.detail === 'string' ? parsed.detail : JSON.stringify(parsed.detail);
      }
    } catch {
      if (errorText.trim()) {
        errorDetail = `Fetching guidelines failed: ${errorText.trim().slice(0, 120)}`;
      }
    }
    throw new Error(errorDetail);
  }

  return await safeParseJson<DocumentListResponse>(response, 'Fetch guidelines');
}

export async function reviewMarketingContent(
  content: string,
  documentIds?: string[]
): Promise<ReviewResponse> {
  const payload: { content: string; document_ids?: string[] } = {
    content,
  };
  if (documentIds && documentIds.length > 0) {
    payload.document_ids = documentIds;
  }

  const url = `${API_BASE_URL}/api/review`;
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => '');
    let errorDetail = `Review request failed with HTTP ${response.status}`;
    try {
      const parsed = JSON.parse(errorText);
      if (parsed.detail) {
        if (Array.isArray(parsed.detail)) {
          errorDetail = parsed.detail.map((d: any) => d.msg || JSON.stringify(d)).join(', ');
        } else {
          errorDetail = typeof parsed.detail === 'string' ? parsed.detail : JSON.stringify(parsed.detail);
        }
      }
    } catch {
      if (errorText.trim()) {
        errorDetail = `Review request failed: ${errorText.trim().slice(0, 120)}`;
      }
    }
    throw new Error(errorDetail);
  }

  return await safeParseJson<ReviewResponse>(response, 'Claim review');
}

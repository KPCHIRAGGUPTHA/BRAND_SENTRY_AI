import {
  HealthResponse,
  GuidelineUploadResponse,
  GuidelineSearchResponse,
  DocumentListResponse,
  ReviewResponse,
} from '../types/api';

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_URL ||
  'http://127.0.0.1:8000';

export async function fetchHealth(): Promise<HealthResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 4000);

  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error(`Backend responded with HTTP status ${response.status} (${response.statusText})`);
    }

    return await response.json();
  } catch (error: unknown) {
    clearTimeout(timeoutId);
    if (error instanceof Error) {
      if (error.name === 'AbortError') {
        throw new Error('Connection timed out while reaching backend service');
      }
      throw error;
    }
    throw new Error('An unknown error occurred while connecting to the backend');
  }
}

export async function uploadGuideline(file: File): Promise<GuidelineUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/api/guidelines/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Upload failed with HTTP ${response.status}`);
  }

  return await response.json();
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

  const response = await fetch(`${API_BASE_URL}/api/guidelines/search`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Search failed with HTTP ${response.status}`);
  }

  return await response.json();
}

export async function fetchGuidelines(): Promise<DocumentListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/guidelines`, {
    method: 'GET',
    headers: { Accept: 'application/json' },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Fetching guidelines failed with HTTP ${response.status}`);
  }

  return await response.json();
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

  const response = await fetch(`${API_BASE_URL}/api/review`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    // FastAPI validation errors may return an array in `detail`
    if (Array.isArray(errorData.detail)) {
      const msg = errorData.detail.map((d: any) => d.msg || JSON.stringify(d)).join(', ');
      throw new Error(msg);
    }
    throw new Error(errorData.detail || `Review request failed with HTTP ${response.status}`);
  }

  return await response.json();
}

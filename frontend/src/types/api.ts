export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
}

export interface GuidelineUploadResponse {
  document_id: string;
  filename: string;
  status: string;
  page_count: number | null;
  extracted_characters: number;
  chunk_count: number;
  message?: string;
}

export interface GuidelineChunkMatch {
  chunk_id: string;
  document_id: string;
  source_filename: string;
  page_number: number | null;
  chunk_index: number;
  text: string;
  distance: number;
  similarity_score: number;
}

export interface GuidelineSearchResponse {
  query: string;
  document_id: string | null;
  total_matches: number;
  results: GuidelineChunkMatch[];
}

export interface DocumentSummary {
  document_id: string;
  filename: string;
  status: string;
  page_count: number | null;
  character_count: number;
  chunk_count: number;
  created_at: string;
  error_message?: string;
}

export interface DocumentListResponse {
  total: number;
  documents: DocumentSummary[];
}

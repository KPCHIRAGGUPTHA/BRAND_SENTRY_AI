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

export interface EvidenceItem {
  chunk_id: string;
  document_id: string;
  source_filename: string;
  page_number: number | null;
  quote: string;
  similarity_score: number;
  distance: number;
}

export interface SemanticDriftIssue {
  category: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | string;
  claim_phrase: string;
  source_phrase: string;
  explanation: string;
  suggested_correction?: string | null;
}

export interface SemanticDriftResult {
  detected: boolean;
  issues: SemanticDriftIssue[];
  uncertainty?: string | null;
}

export interface ClaimVerdict {
  claim_id: string;
  claim_text: string;
  verdict: 'SUPPORTED' | 'CONTRADICTED' | 'INSUFFICIENT_EVIDENCE' | string;
  explanation: string;
  evidence: EvidenceItem[];
  suggested_correction?: string | null;
  deterministic_rule_fired?: boolean;
  semantic_drift?: SemanticDriftResult | null;
}

export interface ReviewSummary {
  total_claims: number;
  supported: number;
  contradicted: number;
  insufficient_evidence: number;
}

export interface ReviewResponse {
  review_id: string;
  content_preview: string;
  document_ids_searched: string[];
  claims: ClaimVerdict[];
  summary: ReviewSummary;
  created_at: string;
  warning?: string | null;
}

export interface ReviewRequest {
  content: string;
  document_ids?: string[];
}

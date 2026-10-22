import React, { useState, useEffect } from 'react';
import { Upload, Search, FileText, CheckCircle2, AlertCircle, FileCheck } from 'lucide-react';
import { uploadGuideline, searchGuidelines, fetchGuidelines } from '../services/api';
import { GuidelineChunkMatch, DocumentSummary } from '../types/api';

export const GuidelineExplorer: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [query, setQuery] = useState<string>('');
  const [searching, setSearching] = useState<boolean>(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<GuidelineChunkMatch[]>([]);

  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string>('');

  const loadDocuments = async () => {
    try {
      const res = await fetchGuidelines();
      setDocuments(res.documents);
      if (res.documents.length > 0 && !selectedDocId) {
        setSelectedDocId(res.documents[0].document_id);
      }
    } catch {
      // Backend may be offline during initial render
    }
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    try {
      const result = await uploadGuideline(file);
      setUploadSuccess(
        `Successfully indexed '${result.filename}' (${result.chunk_count} chunks, ${result.extracted_characters} characters).`
      );
      setFile(null);
      await loadDocuments();
      setSelectedDocId(result.document_id);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setUploadError(err.message);
      } else {
        setUploadError('Failed to upload and index document.');
      }
    } finally {
      setUploading(false);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setSearching(true);
    setSearchError(null);

    try {
      const res = await searchGuidelines(query.trim(), selectedDocId || undefined, 5);
      setSearchResults(res.results);
      if (res.results.length === 0) {
        setSearchError('No matching guideline passages found for this query.');
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setSearchError(err.message);
      } else {
        setSearchError('Search failed.');
      }
    } finally {
      setSearching(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', marginBottom: '48px' }}>
      {/* Upload Box */}
      <div className="glass-card">
        <div className="card-header-row">
          <h3 className="card-title">
            <Upload size={18} style={{ color: 'var(--primary)' }} />
            Phase 2: Guideline Ingestion (PDF / TXT)
          </h3>
          <span className="status-pill status-online">REAL INGESTION</span>
        </div>

        <form onSubmit={handleUpload} style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            type="file"
            accept=".pdf,.txt"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            style={{
              padding: '8px 12px',
              borderRadius: '8px',
              border: '1px solid var(--border)',
              background: 'rgba(0,0,0,0.3)',
              color: 'var(--text-main)',
              fontSize: '0.85rem',
              flex: 1,
            }}
          />
          <button
            type="submit"
            disabled={!file || uploading}
            className="btn btn-primary"
            style={{ fontSize: '0.85rem', padding: '8px 18px' }}
          >
            <FileText size={16} />
            {uploading ? 'Extracting & Indexing...' : 'Upload & Index'}
          </button>
        </form>

        {uploadSuccess && (
          <div
            style={{
              marginTop: '14px',
              padding: '10px 14px',
              borderRadius: '8px',
              backgroundColor: 'rgba(16, 185, 129, 0.1)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              color: '#86EFAC',
              fontSize: '0.825rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <CheckCircle2 size={16} />
            {uploadSuccess}
          </div>
        )}

        {uploadError && (
          <div
            style={{
              marginTop: '14px',
              padding: '10px 14px',
              borderRadius: '8px',
              backgroundColor: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              color: '#FCA5A5',
              fontSize: '0.825rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <AlertCircle size={16} />
            {uploadError}
          </div>
        )}
      </div>

      {/* Semantic Retrieval Search Box */}
      <div className="glass-card">
        <div className="card-header-row">
          <h3 className="card-title">
            <Search size={18} style={{ color: 'var(--purple)' }} />
            Phase 2: Semantic Vector Retrieval (ChromaDB + all-MiniLM-L6-v2)
          </h3>
          <span className="status-pill status-online">ONNX CPU RETRIEVAL</span>
        </div>

        <form onSubmit={handleSearch} style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '16px' }}>
          {documents.length > 0 && (
            <select
              value={selectedDocId}
              onChange={(e) => setSelectedDocId(e.target.value)}
              style={{
                padding: '8px 12px',
                borderRadius: '8px',
                border: '1px solid var(--border)',
                background: '#1E293B',
                color: '#fff',
                fontSize: '0.85rem',
              }}
            >
              <option value="">All Uploaded Guidelines</option>
              {documents.map((d) => (
                <option key={d.document_id} value={d.document_id}>
                  {d.filename} ({d.chunk_count} chunks)
                </option>
              ))}
            </select>
          )}

          <input
            type="text"
            placeholder="Enter a compliance query or claim (e.g., 'What are the rules for comparative claims?')..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{
              padding: '8px 14px',
              borderRadius: '8px',
              border: '1px solid var(--border)',
              background: 'rgba(0,0,0,0.3)',
              color: 'var(--text-main)',
              fontSize: '0.85rem',
              flex: 1,
              minWidth: '260px',
            }}
          />

          <button
            type="submit"
            disabled={!query.trim() || searching}
            className="btn btn-secondary"
            style={{ fontSize: '0.85rem', padding: '8px 18px' }}
          >
            <Search size={16} />
            {searching ? 'Querying...' : 'Search Passages'}
          </button>
        </form>

        {searchError && (
          <div
            style={{
              padding: '10px 14px',
              borderRadius: '8px',
              backgroundColor: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              color: '#FCA5A5',
              fontSize: '0.825rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '16px',
            }}
          >
            <AlertCircle size={16} />
            {searchError}
          </div>
        )}

        {/* Results */}
        {searchResults.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <h4 style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
              Retrieved Guideline Passages ({searchResults.length})
            </h4>
            {searchResults.map((match) => (
              <div
                key={match.chunk_id}
                style={{
                  padding: '14px',
                  borderRadius: '8px',
                  backgroundColor: 'rgba(0,0,0,0.25)',
                  border: '1px solid var(--border)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                    <FileCheck size={14} color="var(--primary)" />
                    <span><strong>Source:</strong> {match.source_filename}</span>
                    {match.page_number && <span>&bull; <strong>Page:</strong> {match.page_number}</span>}
                    <span>&bull; <strong>Chunk:</strong> {match.chunk_id}</span>
                  </div>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <span className="status-pill status-online" style={{ fontSize: '0.7rem' }}>
                      Similarity: {(match.similarity_score * 100).toFixed(1)}%
                    </span>
                    <span className="status-pill" style={{ fontSize: '0.7rem', background: 'rgba(255,255,255,0.06)' }}>
                      Dist: {match.distance.toFixed(3)}
                    </span>
                  </div>
                </div>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-main)', lineHeight: 1.5, fontStyle: 'italic', background: 'rgba(255,255,255,0.02)', padding: '8px 10px', borderRadius: '6px' }}>
                  "{match.text}"
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

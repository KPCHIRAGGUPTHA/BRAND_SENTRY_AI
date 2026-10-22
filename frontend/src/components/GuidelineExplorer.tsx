import React, { useState, useEffect, useRef } from 'react';
import {
  Upload,
  Search,
  FileText,
  CheckCircle2,
  AlertCircle,
  FileCheck,
  RefreshCw,
  FolderOpen,
  Layers,
  Database,
  X,
  FileCode,
  SlidersHorizontal
} from 'lucide-react';
import { uploadGuideline, searchGuidelines, fetchGuidelines } from '../services/api';
import { GuidelineChunkMatch, DocumentSummary } from '../types/api';

export const GuidelineExplorer: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);

  const [query, setQuery] = useState<string>('');
  const [searching, setSearching] = useState<boolean>(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<GuidelineChunkMatch[]>([]);
  const [hasSearched, setHasSearched] = useState<boolean>(false);

  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [loadingDocs, setLoadingDocs] = useState<boolean>(false);
  const [selectedDocId, setSelectedDocId] = useState<string>('');

  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadDocuments = async () => {
    setLoadingDocs(true);
    try {
      const res = await fetchGuidelines();
      setDocuments(res.documents);
      if (res.documents.length > 0 && !selectedDocId) {
        setSelectedDocId(res.documents[0].document_id);
      }
    } catch {
      // Backend may be offline during initial render
    } finally {
      setLoadingDocs(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  const handleFileSelection = (selectedFile: File | null) => {
    setUploadError(null);
    setUploadSuccess(null);

    if (!selectedFile) {
      setFile(null);
      return;
    }

    const lowerName = selectedFile.name.toLowerCase();
    if (!lowerName.endsWith('.pdf') && !lowerName.endsWith('.txt')) {
      setUploadError('Invalid file type. Please select an official brand guideline in PDF (.pdf) or Plain Text (.txt) format.');
      setFile(null);
      return;
    }

    setFile(selectedFile);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelection(e.dataTransfer.files[0]);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || uploading) return;

    setUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    try {
      const result = await uploadGuideline(file);
      setUploadSuccess(
        `Successfully indexed "${result.filename}". Parsed ${result.chunk_count} semantic chunks (${result.extracted_characters.toLocaleString()} characters) into ChromaDB.`
      );
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
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
    if (!query.trim() || searching) return;

    setSearching(true);
    setSearchError(null);
    setHasSearched(true);

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
        setSearchError('Search failed while connecting to backend.');
      }
    } finally {
      setSearching(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px', marginBottom: '40px' }}>
      {/* 1. Guideline Upload Card */}
      <section className="card" id="guidelines">
        <div className="card-header">
          <div className="card-title-group">
            <h3 className="card-title">
              <Upload size={18} style={{ color: 'var(--color-primary)' }} />
              Brand Guidelines Ingestion
            </h3>
            <p className="card-description">
              Upload official corporate brand rulebooks, policy PDF manuals, or compliance TXT files for automated text extraction, page-preserving chunking, and dense vector indexing.
            </p>
          </div>
          <span className="badge badge-primary">
            <FileCode size={12} />
            PDF &bull; TXT
          </span>
        </div>

        <form onSubmit={handleUpload}>
          <div
            className={`upload-dropzone ${isDragOver ? 'drag-active' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                fileInputRef.current?.click();
              }
            }}
            aria-label="Upload guideline file dropzone"
          >
            <div className="upload-icon-wrapper">
              <Upload size={22} />
            </div>
            <div>
              <p style={{ fontWeight: 600, fontSize: '0.95rem', color: 'var(--color-text-primary)' }}>
                Click to browse or drag and drop guideline document
              </p>
              <p style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
                Accepts PDF or TXT files up to 25MB (PyMuPDF page-preserving parser)
              </p>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.txt"
              style={{ display: 'none' }}
              onChange={(e) => handleFileSelection(e.target.files?.[0] || null)}
            />
          </div>

          {file && (
            <div className="upload-selected-file">
              <div className="file-info">
                <FileText size={18} style={{ color: 'var(--color-primary)', flexShrink: 0 }} />
                <span className="file-name" title={file.name}>{file.name}</span>
                <span className="file-size">({formatFileSize(file.size)})</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                  onClick={(e) => {
                    e.stopPropagation();
                    setFile(null);
                    if (fileInputRef.current) fileInputRef.current.value = '';
                  }}
                  aria-label="Remove selected file"
                >
                  <X size={14} />
                  <span>Remove</span>
                </button>
                <button
                  type="submit"
                  disabled={uploading}
                  className="btn btn-primary"
                  style={{ padding: '6px 16px', fontSize: '0.85rem' }}
                >
                  <FileCheck size={16} />
                  <span>{uploading ? 'Extracting & Indexing...' : 'Upload & Index'}</span>
                </button>
              </div>
            </div>
          )}
        </form>

        {uploadSuccess && (
          <div className="alert alert-success" role="status">
            <CheckCircle2 size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
            <span>{uploadSuccess}</span>
          </div>
        )}

        {uploadError && (
          <div className="alert alert-error" role="alert">
            <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
            <span>{uploadError}</span>
          </div>
        )}
      </section>

      {/* 2. Uploaded Guidelines List */}
      <section className="card">
        <div className="card-header">
          <div className="card-title-group">
            <h3 className="card-title">
              <Database size={18} style={{ color: 'var(--color-primary)' }} />
              Active Brand Guideline Registry
            </h3>
            <p className="card-description">
              Indexed compliance manuals stored in persistent vector collections. Click a guideline to scope semantic queries.
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="badge badge-neutral">
              {documents.length} {documents.length === 1 ? 'Document' : 'Documents'}
            </span>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={loadDocuments}
              disabled={loadingDocs}
              style={{ padding: '5px 10px', fontSize: '0.78rem' }}
              title="Refresh document registry"
            >
              <RefreshCw size={13} className={loadingDocs ? 'pulse-indicator' : ''} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {documents.length === 0 ? (
          <div className="empty-state">
            <FolderOpen className="empty-state-icon" strokeWidth={1.5} />
            <h4 className="empty-state-title">No brand guidelines uploaded yet</h4>
            <p className="empty-state-text">
              Upload your company's official brand guidelines or regulatory advertising rules above to populate the compliance registry.
            </p>
          </div>
        ) : (
          <div className="table-container">
            <table className="document-table" aria-label="Brand guidelines registry table">
              <thead>
                <tr>
                  <th>Guideline Document</th>
                  <th>Format</th>
                  <th>Pages</th>
                  <th>Semantic Chunks</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => {
                  const isSelected = selectedDocId === doc.document_id;
                  const isPdf = doc.filename.toLowerCase().endsWith('.pdf');
                  return (
                    <tr
                      key={doc.document_id}
                      className={isSelected ? 'selected-row' : ''}
                      onClick={() => setSelectedDocId(doc.document_id)}
                    >
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <FileText
                            size={16}
                            style={{
                              color: isSelected ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                              flexShrink: 0,
                            }}
                          />
                          <span style={{ fontWeight: isSelected ? 600 : 500 }}>{doc.filename}</span>
                        </div>
                      </td>
                      <td>
                        <span className="badge badge-neutral" style={{ fontSize: '0.7rem' }}>
                          {isPdf ? 'PDF' : 'TXT'}
                        </span>
                      </td>
                      <td>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                          {doc.page_count !== null && doc.page_count !== undefined ? doc.page_count : '—'}
                        </span>
                      </td>
                      <td>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                          {doc.chunk_count} chunks
                        </span>
                      </td>
                      <td>
                        <span className="badge badge-success" style={{ fontSize: '0.7rem' }}>
                          <CheckCircle2 size={11} />
                          Indexed
                        </span>
                      </td>
                      <td>
                        <button
                          type="button"
                          className={`btn ${isSelected ? 'btn-primary' : 'btn-secondary'}`}
                          style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedDocId(doc.document_id);
                          }}
                        >
                          {isSelected ? 'Selected' : 'Select'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* 3. Semantic Search Interface */}
      <section className="card" id="search">
        <div className="card-header">
          <div className="card-title-group">
            <h3 className="card-title">
              <Search size={18} style={{ color: 'var(--color-primary)' }} />
              Semantic Evidence Retrieval
            </h3>
            <p className="card-description">
              Query the vector collection to retrieve exact guideline clauses grounding compliance assessments.
            </p>
          </div>
          <span className="badge badge-neutral">
            <Layers size={12} />
            all-MiniLM-L6-v2 Embeddings
          </span>
        </div>

        <form onSubmit={handleSearch} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '12px' }}>
            <div>
              <label htmlFor="guideline-select" className="form-label">
                Scope Guideline Document
              </label>
              <div style={{ position: 'relative' }}>
                <select
                  id="guideline-select"
                  className="form-select"
                  value={selectedDocId}
                  onChange={(e) => setSelectedDocId(e.target.value)}
                  disabled={documents.length === 0}
                >
                  <option value="">All Uploaded Guidelines ({documents.length})</option>
                  {documents.map((d) => (
                    <option key={d.document_id} value={d.document_id}>
                      {d.filename} ({d.chunk_count} chunks)
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <label htmlFor="query-input" className="form-label">
                Compliance Query or Copy Claim
              </label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  id="query-input"
                  type="text"
                  className="form-input"
                  placeholder="e.g. 'Can we claim our product is 100% natural and eco-friendly?'"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                <button
                  type="submit"
                  disabled={!query.trim() || searching}
                  className="btn btn-primary"
                  style={{ whiteSpace: 'nowrap', padding: '9px 18px', flexShrink: 0 }}
                >
                  <Search size={16} />
                  <span>{searching ? 'Retrieving...' : 'Search Evidence'}</span>
                </button>
              </div>
            </div>
          </div>
        </form>

        {searchError && (
          <div className="alert alert-warning" role="alert" style={{ marginTop: '16px' }}>
            <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
            <span>{searchError}</span>
          </div>
        )}

        {/* 4. Retrieved Evidence Cards */}
        {searchResults.length > 0 && (
          <div style={{ marginTop: '24px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--color-deep-aubergine)' }}>
                Retrieved Policy Evidence ({searchResults.length} {searchResults.length === 1 ? 'Passage' : 'Passages'})
              </h4>
              <span style={{ fontSize: '0.78rem', color: 'var(--color-text-secondary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <SlidersHorizontal size={13} />
                Ranked by dense vector similarity
              </span>
            </div>

            {searchResults.map((match) => (
              <article key={match.chunk_id} className="evidence-card">
                <div className="evidence-header">
                  <div className="evidence-meta">
                    <span className="evidence-source">
                      <FileCheck size={14} style={{ display: 'inline', marginRight: '4px', verticalAlign: '-2px' }} />
                      {match.source_filename}
                    </span>
                    {match.page_number && (
                      <span className="badge badge-neutral" style={{ fontSize: '0.72rem' }}>
                        Page {match.page_number}
                      </span>
                    )}
                    <span className="badge badge-neutral" style={{ fontSize: '0.72rem', fontFamily: 'var(--font-mono)' }}>
                      Chunk #{match.chunk_index + 1}
                    </span>
                  </div>

                  <div className="evidence-metrics">
                    <span
                      className="badge badge-primary"
                      title="Cosine-derived vector similarity to search query"
                      style={{ fontSize: '0.72rem' }}
                    >
                      Vector Similarity: {(match.similarity_score * 100).toFixed(1)}%
                    </span>
                    <span
                      className="badge badge-neutral"
                      title="L2 vector distance metric"
                      style={{ fontSize: '0.72rem', fontFamily: 'var(--font-mono)' }}
                    >
                      Distance: {match.distance.toFixed(3)}
                    </span>
                  </div>
                </div>

                <div className="evidence-passage">
                  &ldquo;{match.text}&rdquo;
                </div>
              </article>
            ))}
          </div>
        )}

        {hasSearched && !searching && searchResults.length === 0 && !searchError && (
          <div className="empty-state" style={{ marginTop: '16px' }}>
            <Search className="empty-state-icon" strokeWidth={1.5} />
            <h4 className="empty-state-title">No matching passages found</h4>
            <p className="empty-state-text">
              Try rephrasing your search query or selecting "All Uploaded Guidelines" to expand coverage.
            </p>
          </div>
        )}
      </section>
    </div>
  );
};

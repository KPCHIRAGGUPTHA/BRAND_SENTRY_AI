"""
Document Registry Service for BrandSentry AI.
Lightweight SQLite-backed metadata tracking for uploaded guidelines.
"""
import hashlib
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from backend.app.core.config import settings


class DocumentRegistry:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            self.db_path = os.path.abspath(settings.documents_db_path)
        else:
            self.db_path = os.path.abspath(db_path)
            
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    stored_path TEXT NOT NULL,
                    page_count INTEGER,
                    character_count INTEGER DEFAULT 0,
                    chunk_count INTEGER DEFAULT 0,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    error_message TEXT,
                    content_hash TEXT
                )
                """
            )
            # Check if content_hash column exists (for pre-existing tables)
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(documents)")
            columns = [col[1] for col in cur.fetchall()]
            if "content_hash" not in columns:
                conn.execute("ALTER TABLE documents ADD COLUMN content_hash TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(content_hash)")

            # Safe backfill: compute content_hash for legacy records without content_hash
            cur.execute("SELECT document_id, stored_path, filename, file_type, file_size FROM documents WHERE content_hash IS NULL")
            rows_to_backfill = cur.fetchall()
            for row in rows_to_backfill:
                doc_id = row[0]
                stored_path = row[1]
                h = hashlib.sha256()
                if stored_path and os.path.exists(stored_path):
                    try:
                        with open(stored_path, "rb") as f:
                            while chunk := f.read(65536):
                                h.update(chunk)
                        c_hash = h.hexdigest()
                    except Exception:
                        fallback = f"{row[2]}_{row[3]}_{row[4]}".encode("utf-8")
                        c_hash = hashlib.sha256(fallback).hexdigest()
                else:
                    fallback = f"{row[2]}_{row[3]}_{row[4]}".encode("utf-8")
                    c_hash = hashlib.sha256(fallback).hexdigest()
                conn.execute("UPDATE documents SET content_hash = ? WHERE document_id = ?", (c_hash, doc_id))
            conn.commit()

    def register_document(
        self,
        document_id: str,
        filename: str,
        file_type: str,
        file_size: int,
        stored_path: str,
        status: str = "uploaded",
        content_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        created_at = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    document_id, filename, file_type, file_size, stored_path, status, created_at, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (document_id, filename, file_type, file_size, stored_path, status, created_at, content_hash),
            )
            conn.commit()
        return self.get_document(document_id) or {}

    def update_status(
        self,
        document_id: str,
        status: str,
        page_count: Optional[int] = None,
        character_count: Optional[int] = None,
        chunk_count: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        with self._get_connection() as conn:
            updates = ["status = ?"]
            params: List[Any] = [status]

            if page_count is not None:
                updates.append("page_count = ?")
                params.append(page_count)
            if character_count is not None:
                updates.append("character_count = ?")
                params.append(character_count)
            if chunk_count is not None:
                updates.append("chunk_count = ?")
                params.append(chunk_count)
            if error_message is not None:
                updates.append("error_message = ?")
                params.append(error_message)

            params.append(document_id)
            query = f"UPDATE documents SET {', '.join(updates)} WHERE document_id = ?"
            conn.execute(query, tuple(params))
            conn.commit()

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM documents WHERE document_id = ?", (document_id,))
            row = cur.fetchone()
            if row:
                return dict(row)
        return None

    def get_document_by_content_hash(self, content_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve existing indexed document matching content SHA-256 hash."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM documents WHERE content_hash = ? AND status = 'indexed' ORDER BY created_at DESC LIMIT 1",
                (content_hash,),
            )
            row = cur.fetchone()
            if row:
                return dict(row)
        return None

    def list_documents(self, deduplicate: bool = True) -> List[Dict[str, Any]]:
        """
        Lists registered documents.
        When deduplicate=True (default), groups identical uploads by content_hash,
        returning the most recent record per unique file content while keeping all records in SQLite.
        Preserves different documents even if their filenames match.
        """
        with self._get_connection() as conn:
            cur = conn.cursor()
            if deduplicate:
                cur.execute(
                    """
                    SELECT document_id, filename, file_type, file_size, stored_path,
                           page_count, character_count, chunk_count, status, created_at,
                           error_message, content_hash
                    FROM (
                        SELECT *, ROW_NUMBER() OVER (
                            PARTITION BY COALESCE(content_hash, document_id)
                            ORDER BY created_at DESC
                        ) as rn
                        FROM documents
                    )
                    WHERE rn = 1
                    ORDER BY created_at DESC
                    """
                )
            else:
                cur.execute("SELECT * FROM documents ORDER BY created_at DESC")
            rows = cur.fetchall()
            return [dict(row) for row in rows]

    def delete_document(self, document_id: str) -> bool:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))
            conn.commit()
            return cur.rowcount > 0


document_registry = DocumentRegistry()

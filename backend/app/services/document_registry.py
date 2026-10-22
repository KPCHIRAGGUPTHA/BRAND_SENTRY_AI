"""
Document Registry Service for BrandSentry AI.
Lightweight SQLite-backed metadata tracking for uploaded guidelines.
"""
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from backend.app.core.config import settings


class DocumentRegistry:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.db_path = os.path.abspath(os.path.join(base_dir, "data", "documents.db"))
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
                    error_message TEXT
                )
                """
            )
            conn.commit()

    def register_document(
        self,
        document_id: str,
        filename: str,
        file_type: str,
        file_size: int,
        stored_path: str,
        status: str = "uploaded",
    ) -> Dict[str, Any]:
        created_at = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    document_id, filename, file_type, file_size, stored_path, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (document_id, filename, file_type, file_size, stored_path, status, created_at),
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

    def list_documents(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
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

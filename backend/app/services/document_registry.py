"""
Document Registry Service for BrandSentry AI.
Lightweight SQLite-backed metadata tracking for uploaded guidelines.
"""
import hashlib
import os
import re
import uuid
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS policy_versions (
                    version_id TEXT PRIMARY KEY,
                    policy_id TEXT NOT NULL,
                    version_label TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'indexed',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    notes TEXT,
                    FOREIGN KEY(document_id) REFERENCES documents(document_id)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_policy_versions_policy_id ON policy_versions(policy_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_policy_versions_content_hash ON policy_versions(content_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_policy_versions_active ON policy_versions(is_active)")

            # Backfill policy_versions for existing indexed documents if any
            cur.execute("SELECT d.document_id, d.filename, d.content_hash, d.created_at, d.status FROM documents d LEFT JOIN policy_versions pv ON d.document_id = pv.document_id WHERE pv.version_id IS NULL AND d.status = 'indexed'")
            docs_to_backfill = cur.fetchall()
            for doc in docs_to_backfill:
                base_name = os.path.splitext(doc[1])[0]
                pol_id = f"pol-{re.sub(r'[^a-zA-Z0-9]', '-', base_name).lower().strip('-')}" or "pol-guideline"
                ver_id = f"ver-{uuid.uuid4().hex[:12]}"
                conn.execute(
                    """
                    INSERT OR IGNORE INTO policy_versions (
                        version_id, policy_id, version_label, document_id, filename, content_hash, created_at, status, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (ver_id, pol_id, "v1.0", doc[0], doc[1], doc[2] or "legacy", doc[3], doc[4]),
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

    def register_policy_version(
        self,
        document_id: str,
        filename: str,
        content_hash: str,
        policy_id: Optional[str] = None,
        notes: Optional[str] = None,
        status: str = "indexed",
    ) -> Dict[str, Any]:
        """
        Creates an immutable policy version record.
        If identical content_hash already exists under this policy_id, reuses that version.
        Otherwise, archives previous versions of this policy and sets this new version active.
        """
        if not policy_id:
            base_name = os.path.splitext(filename)[0]
            clean_slug = re.sub(r"[^a-zA-Z0-9]+", "-", base_name).lower().strip("-")
            policy_id = f"pol-{clean_slug}" if clean_slug else "pol-guideline"

        with self._get_connection() as conn:
            cur = conn.cursor()

            # Check if this exact content_hash is already registered for this policy
            cur.execute(
                "SELECT * FROM policy_versions WHERE policy_id = ? AND content_hash = ?",
                (policy_id, content_hash),
            )
            existing = cur.fetchone()
            if existing:
                return dict(existing)

            # Count existing versions for this policy to generate incremental label (v1.0, v2.0, etc.)
            cur.execute("SELECT COUNT(*) FROM policy_versions WHERE policy_id = ?", (policy_id,))
            version_count = cur.fetchone()[0]
            version_label = f"v{version_count + 1}.0"

            version_id = f"ver-{uuid.uuid4().hex[:12]}"
            created_at = datetime.now(timezone.utc).isoformat()

            # Deactivate previous versions
            conn.execute(
                "UPDATE policy_versions SET is_active = 0 WHERE policy_id = ?",
                (policy_id,),
            )

            # Insert new immutable version
            conn.execute(
                """
                INSERT INTO policy_versions (
                    version_id, policy_id, version_label, document_id, filename,
                    content_hash, created_at, status, is_active, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    version_id,
                    policy_id,
                    version_label,
                    document_id,
                    filename,
                    content_hash,
                    created_at,
                    status,
                    notes or f"Uploaded guideline version {version_label}",
                ),
            )
            conn.commit()

        return self.get_policy_version(version_id) or {}

    def get_policy_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM policy_versions WHERE version_id = ?", (version_id,))
            row = cur.fetchone()
            if row:
                return dict(row)
        return None

    def list_policy_versions(
        self,
        policy_id: Optional[str] = None,
        active_only: bool = False,
    ) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT * FROM policy_versions WHERE 1=1"
            params: List[Any] = []
            if policy_id:
                query += " AND policy_id = ?"
                params.append(policy_id)
            if active_only:
                query += " AND is_active = 1"
            query += " ORDER BY created_at DESC"
            cur.execute(query, tuple(params))
            return [dict(row) for row in cur.fetchall()]

    def activate_policy_version(self, version_id: str) -> bool:
        """Sets target version as active and marks other versions of the same policy as inactive."""
        target = self.get_policy_version(version_id)
        if not target:
            return False

        policy_id = target["policy_id"]
        with self._get_connection() as conn:
            conn.execute("UPDATE policy_versions SET is_active = 0 WHERE policy_id = ?", (policy_id,))
            conn.execute("UPDATE policy_versions SET is_active = 1 WHERE version_id = ?", (version_id,))
            conn.commit()
        return True

    def resolve_version_to_document_id(self, identifier: str) -> Optional[str]:
        """
        Resolves an identifier (either version_id or document_id) to the underlying indexed document_id.
        """
        with self._get_connection() as conn:
            cur = conn.cursor()
            # 1. Check if it's a version_id
            cur.execute("SELECT document_id FROM policy_versions WHERE version_id = ?", (identifier,))
            row = cur.fetchone()
            if row:
                return row[0]
            # 2. Check if it's directly a document_id
            cur.execute("SELECT document_id FROM documents WHERE document_id = ?", (identifier,))
            row = cur.fetchone()
            if row:
                return row[0]
        return None

    def get_version_id_for_document(self, document_id: str) -> Optional[str]:
        """Returns the version_id corresponding to a document_id, prioritizing active versions."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT version_id FROM policy_versions WHERE document_id = ? ORDER BY is_active DESC, created_at DESC",
                (document_id,)
            )
            row = cur.fetchone()
            if row:
                return row[0]
        return None

    def get_active_document_ids(self) -> List[str]:
        """
        Returns document_ids of all currently active policy versions.
        Prevents archived historical guideline versions from leaking into un-scoped reviews.
        Fallback to all indexed documents if no policy versions are registered yet.
        """
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT DISTINCT pv.document_id 
                FROM policy_versions pv
                JOIN documents d ON pv.document_id = d.document_id
                WHERE pv.is_active = 1 AND d.status = 'indexed'
                """
            )
            rows = cur.fetchall()
            if rows:
                return [r[0] for r in rows]

            # Fallback for fresh/legacy DB without policy_versions
            cur.execute("SELECT document_id FROM documents WHERE status = 'indexed'")
            return [r[0] for r in cur.fetchall()]

    def delete_document(self, document_id: str) -> bool:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))
            cur.execute("DELETE FROM policy_versions WHERE document_id = ?", (document_id,))
            conn.commit()
            return cur.rowcount > 0


document_registry = DocumentRegistry()

"""
Audit and Review History Service for BrandSentry AI.
Provides persistent SQLite storage for compliance reviews, policy version tracking,
dashboard analytics, and multi-format report exports (JSON, CSV, PDF).
"""
import os
import io
import csv
import json
import hashlib
import sqlite3
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from backend.app.core.config import settings
from backend.app.services.document_registry import document_registry

logger = logging.getLogger(__name__)


class AuditService:
    """
    Manages immutable audit records for completed brand compliance reviews.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            self.db_path = os.path.abspath(settings.reviews_db_path)
        else:
            self.db_path = os.path.abspath(db_path)

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initializes reviews database schema and indexes."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reviews (
                    review_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    submitted_content TEXT NOT NULL,
                    content_preview TEXT NOT NULL,
                    review_source TEXT NOT NULL DEFAULT 'text',
                    policy_versions TEXT NOT NULL,
                    app_version TEXT NOT NULL,
                    retrieval_mode TEXT NOT NULL DEFAULT 'hybrid',
                    total_claims INTEGER NOT NULL,
                    supported_count INTEGER NOT NULL,
                    contradicted_count INTEGER NOT NULL,
                    insufficient_count INTEGER NOT NULL,
                    claims_json TEXT NOT NULL,
                    warning TEXT,
                    content_hash TEXT NOT NULL,
                    ocr_raw_text TEXT,
                    ocr_corrected_text TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_created ON reviews(created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_source ON reviews(review_source)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_hash ON reviews(content_hash)")
            conn.commit()

    def save_review(
        self,
        review_id: str,
        submitted_content: str,
        claims: List[Dict[str, Any]],
        summary: Dict[str, Any],
        document_ids: Optional[List[str]] = None,
        review_source: str = "text",
        retrieval_mode: Optional[str] = None,
        created_at: Optional[str] = None,
        warning: Optional[str] = None,
        ocr_raw_text: Optional[str] = None,
        ocr_corrected_text: Optional[str] = None,
        policy_versions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Atomically saves a completed compliance review audit record.
        """
        timestamp = created_at or datetime.now(timezone.utc).isoformat()
        content_hash = hashlib.sha256(submitted_content.encode("utf-8")).hexdigest()
        preview = submitted_content[:120] + ("…" if len(submitted_content) > 120 else "")

        # Resolve policy versions used
        policy_version_records = []
        if policy_versions:
            policy_version_records = list(policy_versions)
        elif document_ids:
            for doc_id in document_ids:
                versions = document_registry.list_policy_versions()
                matched = [v for v in versions if v.get("document_id") == doc_id and v.get("is_active") == 1]
                if matched:
                    policy_version_records.append(matched[0]["version_id"])
                else:
                    policy_version_records.append(doc_id)
        else:
            active_versions = document_registry.list_policy_versions(active_only=True)
            policy_version_records = [v["version_id"] for v in active_versions]

        claims_json = json.dumps(claims, ensure_ascii=False)
        policies_json = json.dumps(policy_version_records, ensure_ascii=False)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO reviews (
                    review_id, created_at, submitted_content, content_preview, review_source,
                    policy_versions, app_version, retrieval_mode, total_claims, supported_count,
                    contradicted_count, insufficient_count, claims_json, warning, content_hash,
                    ocr_raw_text, ocr_corrected_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    timestamp,
                    submitted_content,
                    preview,
                    review_source,
                    policies_json,
                    settings.VERSION,
                    retrieval_mode or settings.RETRIEVAL_MODE,
                    summary.get("total_claims", len(claims)),
                    summary.get("supported", 0),
                    summary.get("contradicted", 0),
                    summary.get("insufficient_evidence", 0),
                    claims_json,
                    warning,
                    content_hash,
                    ocr_raw_text,
                    ocr_corrected_text,
                ),
            )
            conn.commit()

        logger.info("Persisted audit review record %s (%d claims, source: %s).", review_id, len(claims), review_source)
        return self.get_review(review_id) or {}

    def get_review(self, review_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves single audit record with parsed structured fields."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM reviews WHERE review_id = ?", (review_id,))
            row = cur.fetchone()
            if not row:
                return None

            data = dict(row)
            try:
                data["claims"] = json.loads(data["claims_json"])
            except Exception:
                data["claims"] = []

            try:
                data["policy_versions"] = json.loads(data["policy_versions"])
            except Exception:
                data["policy_versions"] = []

            data["summary"] = {
                "total_claims": data["total_claims"],
                "supported": data["supported_count"],
                "contradicted": data["contradicted_count"],
                "insufficient_evidence": data["insufficient_count"],
            }
            return data

    def list_reviews(
        self,
        limit: int = 50,
        offset: int = 0,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Lists historical reviews with pagination and optional source filtering."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            where_clause = ""
            params: List[Any] = []
            if source:
                where_clause = "WHERE review_source = ?"
                params.append(source)

            cur.execute(f"SELECT COUNT(*) FROM reviews {where_clause}", tuple(params))
            total = cur.fetchone()[0]

            query = f"""
                SELECT review_id, created_at, content_preview, review_source,
                       policy_versions, app_version, retrieval_mode, total_claims,
                       supported_count, contradicted_count, insufficient_count, content_hash
                FROM reviews {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            cur.execute(query, tuple(params + [limit, offset]))
            rows = cur.fetchall()

            reviews_list = []
            for r in rows:
                item = dict(r)
                try:
                    item["policy_versions"] = json.loads(item["policy_versions"])
                except Exception:
                    item["policy_versions"] = []
                item["summary"] = {
                    "total_claims": item["total_claims"],
                    "supported": item["supported_count"],
                    "contradicted": item["contradicted_count"],
                    "insufficient_evidence": item["insufficient_count"],
                }
                reviews_list.append(item)

            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "reviews": reviews_list,
            }

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Computes aggregate analytics for dashboard."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COUNT(*),
                       COALESCE(SUM(total_claims), 0),
                       COALESCE(SUM(supported_count), 0),
                       COALESCE(SUM(contradicted_count), 0),
                       COALESCE(SUM(insufficient_count), 0),
                       SUM(CASE WHEN review_source = 'text' THEN 1 ELSE 0 END),
                       SUM(CASE WHEN review_source = 'image' THEN 1 ELSE 0 END)
                FROM reviews
                """
            )
            row = cur.fetchone()

        guidelines_count = len(document_registry.list_documents())
        policy_versions_count = len(document_registry.list_policy_versions())

        return {
            "total_reviews": row[0] or 0,
            "total_claims_reviewed": row[1] or 0,
            "total_supported": row[2] or 0,
            "total_contradicted": row[3] or 0,
            "total_insufficient": row[4] or 0,
            "text_reviews_count": row[5] or 0,
            "image_reviews_count": row[6] or 0,
            "indexed_guidelines_count": guidelines_count,
            "policy_versions_count": policy_versions_count,
        }

    def export_csv(self, review_id: str) -> Optional[str]:
        """Generates formatted CSV report for a given review."""
        review = self.get_review(review_id)
        if not review:
            return None

        output = io.StringIO()
        writer = csv.writer(output)

        # Header metadata
        writer.writerow(["BrandSentry AI — Compliance Review Audit Report"])
        writer.writerow(["Review ID", review["review_id"]])
        writer.writerow(["Timestamp (UTC)", review["created_at"]])
        writer.writerow(["Source", review["review_source"]])
        writer.writerow(["App Version", review["app_version"]])
        writer.writerow(["Retrieval Mode", review["retrieval_mode"]])
        writer.writerow(["Content Hash (SHA-256)", review["content_hash"]])
        writer.writerow(["Policy Versions Used", ", ".join(review.get("policy_versions", []))])
        writer.writerow([])

        # Summary
        s = review["summary"]
        writer.writerow(["SUMMARY METRICS"])
        writer.writerow(["Total Claims", s["total_claims"]])
        writer.writerow(["SUPPORTED", s["supported"]])
        writer.writerow(["CONTRADICTED", s["contradicted"]])
        writer.writerow(["INSUFFICIENT_EVIDENCE", s["insufficient_evidence"]])
        writer.writerow([])

        # Claim Details
        writer.writerow([
            "Claim ID",
            "Claim Text",
            "Verdict",
            "Explanation",
            "Suggested Correction",
            "Evidence Citations",
            "Source Filenames",
            "Page Numbers",
        ])

        for c in review.get("claims", []):
            evidence_quotes = " | ".join(e.get("quote", "") for e in c.get("evidence", []))
            sources = ", ".join(set(e.get("source_filename", "") for e in c.get("evidence", [])))
            pages = ", ".join(str(e.get("page_number", "")) for e in c.get("evidence", []))
            writer.writerow([
                c.get("claim_id", ""),
                c.get("claim_text", ""),
                c.get("verdict", ""),
                c.get("explanation", ""),
                c.get("suggested_correction", "") or "None",
                evidence_quotes or "No evidence cited",
                sources or "N/A",
                pages or "N/A",
            ])

        return output.getvalue()

    def export_pdf(self, review_id: str) -> Optional[bytes]:
        """
        Generates a professional PDF audit report using reportlab.
        """
        review = self.get_review(review_id)
        if not review:
            return None

        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            HRFlowable,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=42,
            leftMargin=42,
            topMargin=42,
            bottomMargin=42,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#0f172a"),
            fontName="Helvetica-Bold",
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=styles["Normal"],
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#475569"),
        )
        h2_style = ParagraphStyle(
            "H2Style",
            parent=styles["Heading2"],
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#1e293b"),
            fontName="Helvetica-Bold",
        )
        body_style = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#334155"),
        )
        bold_body = ParagraphStyle(
            "BoldBody",
            parent=body_style,
            fontName="Helvetica-Bold",
        )

        elements = []

        # Title
        elements.append(Paragraph("BrandSentry AI — Compliance Audit Report", title_style))
        elements.append(Paragraph(f"Review ID: {review['review_id']} | Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}", subtitle_style))
        elements.append(Spacer(1, 10))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3b82f6"), spaceAfter=15))

        p_vers = review.get("policy_versions", [])
        if len(p_vers) > 3:
            policy_display = f"{len(p_vers)} Policies ({', '.join(p_vers[:2])}…)"
        elif p_vers:
            policy_display = ", ".join(p_vers)
        else:
            policy_display = "Active Corpus"

        # Metadata Table (total 480 pt)
        meta_data = [
            [
                Paragraph("<b>Review Source:</b>", body_style),
                Paragraph(review.get("review_source", "text").upper(), body_style),
                Paragraph("<b>Date of Review:</b>", body_style),
                Paragraph(review.get("created_at", "")[:19].replace("T", " "), body_style),
            ],
            [
                Paragraph("<b>Engine Version:</b>", body_style),
                Paragraph(review.get("app_version", "0.3.0"), body_style),
                Paragraph("<b>Retrieval Mode:</b>", body_style),
                Paragraph(review.get("retrieval_mode", "hybrid").title(), body_style),
            ],
            [
                Paragraph("<b>Content Hash:</b>", body_style),
                Paragraph(review.get("content_hash", "")[:16] + "…", body_style),
                Paragraph("<b>Policy Versions:</b>", body_style),
                Paragraph(policy_display, body_style),
            ],
        ]
        meta_table = Table(meta_data, colWidths=[90, 150, 90, 150])
        meta_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ])
        )
        elements.append(meta_table)
        elements.append(Spacer(1, 15))

        # Summary Metrics (total 480 pt)
        s = review["summary"]
        elements.append(Paragraph("Compliance Verdict Summary", h2_style))
        elements.append(Spacer(1, 6))

        metric_data = [
            [
                Paragraph("<b>Total Claims</b>", bold_body),
                Paragraph("<b>SUPPORTED</b>", bold_body),
                Paragraph("<b>CONTRADICTED</b>", bold_body),
                Paragraph("<b>INSUFFICIENT</b>", bold_body),
            ],
            [
                Paragraph(str(s["total_claims"]), bold_body),
                Paragraph(f"<font color='#16a34a'>{s['supported']}</font>", bold_body),
                Paragraph(f"<font color='#dc2626'>{s['contradicted']}</font>", bold_body),
                Paragraph(f"<font color='#d97706'>{s['insufficient_evidence']}</font>", bold_body),
            ],
        ]
        metric_table = Table(metric_data, colWidths=[120, 120, 120, 120])
        metric_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("BACKGROUND", (0, 1), (-1, 1), colors.white),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ])
        )
        elements.append(metric_table)
        elements.append(Spacer(1, 15))

        # Marketing Content Excerpt (480 pt)
        elements.append(Paragraph("Submitted Marketing Copy", h2_style))
        elements.append(Spacer(1, 4))
        content_box = Table(
            [[Paragraph(f"<i>\"{review.get('submitted_content', '')}\"</i>", body_style)]],
            colWidths=[480],
        )
        content_box.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ])
        )
        elements.append(content_box)
        elements.append(Spacer(1, 15))

        # Individual Claims & Evidence (total 480 pt)
        elements.append(Paragraph("Detailed Claim Analysis & Verified Evidence", h2_style))
        elements.append(Spacer(1, 6))

        for idx, claim in enumerate(review.get("claims", []), start=1):
            verdict = claim.get("verdict", "INSUFFICIENT_EVIDENCE")
            verdict_color = "#16a34a" if verdict == "SUPPORTED" else ("#dc2626" if verdict == "CONTRADICTED" else "#d97706")

            claim_header = [
                Paragraph(f"<b>Claim #{idx}:</b> {claim.get('claim_text', '')}", bold_body),
                Paragraph(f"<b>Verdict: <font color='{verdict_color}'>{verdict}</font></b>", bold_body),
            ]

            evidence_rows = []
            for ev in claim.get("evidence", []):
                evidence_rows.append(
                    f"• <b>Quote:</b> \"{ev.get('quote', '')}\"<br/>"
                    f"  <i>Source:</i> {ev.get('source_filename', 'N/A')} (Page {ev.get('page_number', '1')}) | "
                    f"  <i>Similarity:</i> {ev.get('similarity_score', 0.0):.4f}"
                )
            evidence_text = "<br/><br/>".join(evidence_rows) if evidence_rows else "<i>No direct guideline passage cited.</i>"

            correction_text = claim.get("suggested_correction") or "None required."

            claim_body = [
                [Paragraph("<b>Explanation:</b>", bold_body), Paragraph(claim.get("explanation", ""), body_style)],
                [Paragraph("<b>Evidence Citation:</b>", bold_body), Paragraph(evidence_text, body_style)],
                [Paragraph("<b>Suggested Revision:</b>", bold_body), Paragraph(correction_text, body_style)],
            ]

            claim_table = Table(
                [[claim_header[0], claim_header[1]]] + claim_body,
                colWidths=[110, 370],
            )
            claim_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ])
            )
            elements.append(claim_table)
            elements.append(Spacer(1, 10))

        # Legal Disclaimer
        elements.append(Spacer(1, 10))
        disclaimer = (
            "<b>Disclaimer:</b> BrandSentry AI compliance verdicts are evidence-grounded recommendations "
            "derived automatically from ingested brand policies. They do not constitute formal legal counsel. "
            "All suggested revisions and critical contradictions should be validated by authorized compliance personnel."
        )
        elements.append(Paragraph(disclaimer, ParagraphStyle("Disc", parent=body_style, fontSize=8, leading=10, textColor=colors.HexColor("#64748b"))))

        doc.build(elements)
        return buffer.getvalue()


audit_service = AuditService()

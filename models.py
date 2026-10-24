"""
Database Models (PRD Section 10: Database Design).
Defines Users, Analyses, and ChatMessages using SQLAlchemy ORM.
Compatible with MySQL 8.0+, PostgreSQL (via psycopg2), and SQLite.

Cloud note: uploaded image bytes are stored in the database
(original_image_bytes / processed_image_bytes) so the app stays
fully portable on hosted platforms whose disk storage is ephemeral.
"""
import json
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


def utc_now():
    return datetime.now(timezone.utc)


class User(db.Model):
    """
    PRD Section 10.1: Users Table
    Columns: user_id (PK), name, email (unique), password_hash, created_at
    """
    __tablename__ = "Users"

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    # One-to-many relationship with Analyses
    analyses = db.relationship(
        "Analysis",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="desc(Analysis.created_at)",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "name": self.name,
            "email": self.email,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M UTC") if self.created_at else "",
        }


class Analysis(db.Model):
    """
    PRD Section 10.2: Analyses Table
    Columns: analysis_id (PK), user_id (FK -> Users.user_id), image_path,
             generated_report, status, model_version, created_at
    Additional helper columns: processed_image_path, case_label, structured_metadata,
             original_image_bytes, processed_image_bytes (cloud storage)
    """
    __tablename__ = "Analyses"

    analysis_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("Users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_path = db.Column(db.String(512), nullable=False)
    processed_image_path = db.Column(db.String(512), nullable=True)
    # Image bytes stored in the database so hosted deployments (ephemeral
    # disk) never lose uploaded radiographs. NULL for built-in samples,
    # which are served from the deployed static/samples/ folder.
    original_image_bytes = db.Column(db.LargeBinary, nullable=True)
    processed_image_bytes = db.Column(db.LargeBinary, nullable=True)
    case_label = db.Column(db.String(180), nullable=False, default="Chest Radiograph (PA View)")
    generated_report = db.Column(db.Text, nullable=False)
    structured_metadata = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="completed")  # processing | completed | failed
    model_version = db.Column(
        db.String(120),
        nullable=False,
        default="ThoraxVLM-RadDraft-v2.4 (DenseNet121-CXR + BioBART)",
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now, index=True)

    # One-to-many relationship with ChatMessages
    messages = db.relationship(
        "ChatMessage",
        backref="analysis",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="asc(ChatMessage.created_at), asc(ChatMessage.message_id)",
    )

    def get_metadata(self) -> dict:
        if not self.structured_metadata:
            return {}
        try:
            return json.loads(self.structured_metadata)
        except Exception:
            return {}

    def set_metadata(self, data: dict) -> None:
        self.structured_metadata = json.dumps(data)

    def to_dict(self, include_messages=True):
        meta = self.get_metadata()
        result = {
            "analysis_id": self.analysis_id,
            "accession_number": f"CXR-{self.created_at.strftime('%Y%m%d') if self.created_at else '20261013'}-{self.analysis_id:04d}",
            "user_id": self.user_id,
            "image_path": self.image_path,
            "processed_image_path": self.processed_image_path or self.image_path,
            "case_label": self.case_label,
            "generated_report": self.generated_report,
            "status": self.status,
            "model_version": self.model_version,
            "created_at": self.created_at.strftime("%b %d, %Y · %H:%M UTC") if self.created_at else "",
            "created_iso": self.created_at.isoformat() if self.created_at else "",
            "metadata": meta,
            "message_count": len(self.messages),
        }
        if include_messages:
            result["messages"] = [m.to_dict() for m in self.messages]
        return result


class ChatMessage(db.Model):
    """
    PRD Section 10.3: ChatMessages Table
    Columns: message_id (PK), analysis_id (FK -> Analyses.analysis_id),
             role ('user' | 'assistant'), message_text, created_at
    """
    __tablename__ = "ChatMessages"

    message_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    analysis_id = db.Column(
        db.Integer,
        db.ForeignKey("Analyses.analysis_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = db.Column(db.String(32), nullable=False)  # 'user' or 'assistant'
    message_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    def to_dict(self):
        return {
            "message_id": self.message_id,
            "analysis_id": self.analysis_id,
            "role": self.role,
            "message_text": self.message_text,
            "created_at": self.created_at.strftime("%H:%M:%S UTC") if self.created_at else "",
        }

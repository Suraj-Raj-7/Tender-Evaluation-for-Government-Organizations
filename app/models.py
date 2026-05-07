# DB Models (Tender, Bidder, Evidence, AuditLog)
from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON, Enum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum
from app.db import Base

class Role(str, enum.Enum):
    UPLOADER = "UPLOADER"
    EVALUATOR = "EVALUATOR"
    AUDITOR = "AUDITOR"
    BIDDER = "BIDDER"


class Tender(Base):
    __tablename__ = "tenders"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="PUBLISHED")
    estimated_value: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship to Criterion
    criteria: Mapped[list["Criterion"]] = relationship("Criterion", back_populates="tender")
    bidders: Mapped[list["Bidder"]] = relationship("Bidder", back_populates="tender")

class Criterion(Base):
    __tablename__ = "criteria"
    id: Mapped[int] = mapped_column(primary_key=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id"))
    code: Mapped[str] = mapped_column(String(50))
    category: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    evidence_type: Mapped[str] = mapped_column(String(50), default="DOCUMENT")
    operator: Mapped[str] = mapped_column(String(20))
    threshold_json: Mapped[dict] = mapped_column(JSON)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationship back to Tender
    tender: Mapped["Tender"] = relationship("Tender", back_populates="criteria")

class Bidder(Base):
    __tablename__ = "bidders"
    id: Mapped[int] = mapped_column(primary_key=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id"))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50), default="GENERAL") # MSME, STARTUP
    overall_verdict: Mapped[str] = mapped_column(String(50), default="PENDING") # ELIGIBLE, NOT ELIGIBLE
    
    tender: Mapped[Tender] = relationship(back_populates="bidders")
    evidence: Mapped[list["Evidence"]] = relationship(back_populates="bidder")

class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    bidder_id: Mapped[int] = mapped_column(ForeignKey("bidders.id"))
    criterion_code: Mapped[str] = mapped_column(String(20)) # e.g., C1, C2
    raw_value: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    rationale: Mapped[str] = mapped_column(Text)
    doc_refs: Mapped[dict] = mapped_column(JSON) # Supports multi-doc info
    udin: Mapped[str] = mapped_column(String(50), nullable=True) # Real regulatory requirement
    projects_json: Mapped[dict] = mapped_column(JSON, nullable=True) # For 80/60/40 table
    
    bidder: Mapped[Bidder] = relationship(back_populates="evidence")
    
    issued_date: Mapped[str] = mapped_column(String(50), nullable=True)
    expiry_date: Mapped[str] = mapped_column(String(50), nullable=True)



class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    username: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100)) # e.g., MANUAL_OVERRIDE
    details: Mapped[dict] = mapped_column(JSON)
    

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.EVALUATOR)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime] = mapped_column(DateTime, nullable=True)

class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    ip_address: Mapped[str] = mapped_column(String(45))
    
    

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id"))
    bidder_id: Mapped[int] = mapped_column(ForeignKey("bidders.id"), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(100))
    is_scanned: Mapped[bool] = mapped_column(Boolean)
    page_count: Mapped[int] = mapped_column(Integer)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[float] = mapped_column(Float, default=1.0)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    
    

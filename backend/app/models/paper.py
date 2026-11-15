from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base, JSONVariant, TimestampMixin, generate_uuid


class Paper(Base, TimestampMixin):
    """Research paper metadata. `id` is the stable paper_id shared with RAG,
    ChromaDB metadata, Neo4j and the frontend — never regenerated per subsystem."""

    __tablename__ = "papers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    abstract: Mapped[Optional[str]] = mapped_column(Text)
    authors: Mapped[Optional[list]] = mapped_column(JSONVariant)
    publication_year: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    doi: Mapped[Optional[str]] = mapped_column(String(255))
    source_url: Mapped[Optional[str]] = mapped_column(String(1000))
    venue: Mapped[Optional[str]] = mapped_column(String(255))

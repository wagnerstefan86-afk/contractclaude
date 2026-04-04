from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ContractPackage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "contract_packages"

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    documents: Mapped[list["Document"]] = relationship(
        back_populates="package", cascade="all, delete-orphan"
    )
    precedence_rules: Mapped[list["DocumentPrecedenceRule"]] = relationship(
        back_populates="package", cascade="all, delete-orphan"
    )


class Document(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "documents"

    package_id: Mapped[str] = mapped_column(
        ForeignKey("contract_packages.id"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    doc_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    package: Mapped["ContractPackage"] = relationship(back_populates="documents")


class DocumentPrecedenceRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "document_precedence_rules"

    package_id: Mapped[str] = mapped_column(
        ForeignKey("contract_packages.id"), nullable=False, index=True
    )
    higher_doc_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id"), nullable=False
    )
    lower_doc_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    package: Mapped["ContractPackage"] = relationship(back_populates="precedence_rules")

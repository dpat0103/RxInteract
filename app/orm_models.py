from sqlalchemy import (
    Column, Integer, String, Text, ForeignKey,
    DateTime, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass


class Drug(Base):
    __tablename__ = "drugs"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)       
    rxcui = Column(String(50), nullable=True)
    generic_name = Column(String(255), nullable=True)
    brand_name = Column(String(255), nullable=True)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    label = relationship("DrugLabel", back_populates="drug", uselist=False, cascade="all, delete-orphan")

    interactions_as_a = relationship(
        "DrugInteraction",
        foreign_keys="DrugInteraction.drug_a_id",
        back_populates="drug_a",
        cascade="all, delete-orphan"
    )
    interactions_as_b = relationship(
        "DrugInteraction",
        foreign_keys="DrugInteraction.drug_b_id",
        back_populates="drug_b",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("name", name="uq_drug_name"),
    )


class DrugLabel(Base):
    __tablename__ = "drug_labels"

    id = Column(Integer, primary_key=True)
    drug_id = Column(Integer, ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False, unique=True)
    drug_interactions_text = Column(Text, nullable=True)
    warnings_text = Column(Text, nullable=True)
    contraindications_text = Column(Text, nullable=True)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    drug = relationship("Drug", back_populates="label")


class DrugInteraction(Base):
    __tablename__ = "drug_interactions"

    id = Column(Integer, primary_key=True)
    drug_a_id = Column(Integer, ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False)
    drug_b_id = Column(Integer, ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20), nullable=True)     
    source = Column(String(100), nullable=True, default="OpenFDA Drug Label")
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    drug_a = relationship("Drug", foreign_keys=[drug_a_id], back_populates="interactions_as_a")
    drug_b = relationship("Drug", foreign_keys=[drug_b_id], back_populates="interactions_as_b")

    __table_args__ = (
        UniqueConstraint("drug_a_id", "drug_b_id", name="uq_interaction_pair"),
    )
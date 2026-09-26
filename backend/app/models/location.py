from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, Boolean, JSON, Index
from sqlalchemy.orm import relationship

from app.database.base import Base


class AdministrativeDivision(Base):
    """
    Coimbatore Revenue Divisions (Coimbatore North, Coimbatore South, Pollachi).
    Authoritative Source: Government of Tamil Nadu Revenue Administration.
    """
    __tablename__ = "administrative_divisions"

    id = Column(Integer, primary_key=True, index=True)
    name_en = Column(String(100), nullable=False, unique=True, index=True)
    name_ta = Column(String(150), nullable=True)
    headquarters = Column(String(100), nullable=True)
    source = Column(String(100), default="Government of Tamil Nadu - Revenue Administration")
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    taluks = relationship("Taluk", back_populates="division", cascade="all, delete-orphan")


class Taluk(Base):
    """
    Coimbatore 11 Revenue Taluks.
    """
    __tablename__ = "taluks"

    id = Column(Integer, primary_key=True, index=True)
    division_id = Column(Integer, ForeignKey("administrative_divisions.id"), nullable=True, index=True)
    name_en = Column(String(100), nullable=False, unique=True, index=True)
    name_ta = Column(String(150), nullable=True)
    aliases = Column(JSON, default=list)  # Tanglish and phonetic aliases
    headquarters = Column(String(100), nullable=True)
    source = Column(String(100), default="TN Revenue Gazette - Coimbatore District")
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    division = relationship("AdministrativeDivision", back_populates="taluks")
    firkas = relationship("Firka", back_populates="taluk", cascade="all, delete-orphan")
    revenue_villages = relationship("RevenueVillage", back_populates="taluk", cascade="all, delete-orphan")
    areas = relationship("Area", back_populates="taluk")


class Firka(Base):
    """
    Coimbatore 38 Revenue Firkas.
    """
    __tablename__ = "firkas"

    id = Column(Integer, primary_key=True, index=True)
    taluk_id = Column(Integer, ForeignKey("taluks.id"), nullable=False, index=True)
    name_en = Column(String(100), nullable=False, index=True)
    name_ta = Column(String(150), nullable=True)
    aliases = Column(JSON, default=list)
    source = Column(String(100), default="TN Revenue Gazette - Coimbatore District")
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    taluk = relationship("Taluk", back_populates="firkas")
    revenue_villages = relationship("RevenueVillage", back_populates="firka")


class RevenueVillage(Base):
    """
    Coimbatore 295 Official Revenue Villages.
    """
    __tablename__ = "revenue_villages"

    id = Column(Integer, primary_key=True, index=True)
    taluk_id = Column(Integer, ForeignKey("taluks.id"), nullable=False, index=True)
    firka_id = Column(Integer, ForeignKey("firkas.id"), nullable=True, index=True)
    name_en = Column(String(150), nullable=False, index=True)
    name_ta = Column(String(200), nullable=True)
    village_code = Column(String(50), nullable=True)
    aliases = Column(JSON, default=list)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    source = Column(String(100), default="TN Revenue Administration - Coimbatore")
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    taluk = relationship("Taluk", back_populates="revenue_villages")
    firka = relationship("Firka", back_populates="revenue_villages")
    areas = relationship("Area", back_populates="village")


class CorporationZone(Base):
    """
    Coimbatore City Municipal Corporation (CCMC) 5 Zones: North, East, West, Central, South.
    """
    __tablename__ = "corporation_zones"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True, index=True)  # North, East, West, Central, South
    name_ta = Column(String(100), nullable=True)
    office_address = Column(String(255), nullable=True)
    source = Column(String(100), default="Coimbatore City Municipal Corporation (CCMC)")
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    wards = relationship("CorporationWard", back_populates="zone", cascade="all, delete-orphan")
    areas = relationship("Area", back_populates="zone")


class CorporationWard(Base):
    """
    Coimbatore City Municipal Corporation (CCMC) 100 Wards (Ward 1 to 100).
    """
    __tablename__ = "corporation_wards"

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(Integer, ForeignKey("corporation_zones.id"), nullable=False, index=True)
    ward_no = Column(Integer, nullable=False, unique=True, index=True)
    name = Column(String(150), nullable=True, index=True)
    name_ta = Column(String(200), nullable=True)
    major_localities = Column(Text, nullable=True)
    boundary_description = Column(Text, nullable=True)
    source = Column(String(100), default="CCMC Ward Delimitation Gazette")
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    zone = relationship("CorporationZone", back_populates="wards")
    areas = relationship("Area", back_populates="ward")
    streets = relationship("Street", back_populates="ward")
    landmarks = relationship("Landmark", back_populates="ward")


class Area(Base):
    """
    Recognized Localities / Sub-areas (e.g. Gandhipuram, RS Puram, Peelamedu, Saibaba Colony).
    """
    __tablename__ = "areas"

    id = Column(Integer, primary_key=True, index=True)
    name_en = Column(String(150), nullable=False, index=True)
    name_ta = Column(String(200), nullable=True)
    aliases = Column(JSON, default=list)
    ward_id = Column(Integer, ForeignKey("corporation_wards.id"), nullable=True, index=True)
    zone_id = Column(Integer, ForeignKey("corporation_zones.id"), nullable=True, index=True)
    taluk_id = Column(Integer, ForeignKey("taluks.id"), nullable=True, index=True)
    village_id = Column(Integer, ForeignKey("revenue_villages.id"), nullable=True, index=True)
    is_corporation_area = Column(Boolean, default=True)
    pincode = Column(String(10), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    source = Column(String(100), default="CCMC & Survey of Tamil Nadu")
    confidence = Column(Float, default=0.95)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    ward = relationship("CorporationWard", back_populates="areas")
    zone = relationship("CorporationZone", back_populates="areas")
    taluk = relationship("Taluk", back_populates="areas")
    village = relationship("RevenueVillage", back_populates="areas")
    streets = relationship("Street", back_populates="area")
    landmarks = relationship("Landmark", back_populates="area")


class Street(Base):
    """
    Street / Road level dataset with aliases, hierarchical links, and verified GPS.
    """
    __tablename__ = "streets"

    id = Column(Integer, primary_key=True, index=True)
    name_en = Column(String(200), nullable=False, index=True)
    name_ta = Column(String(250), nullable=True)
    aliases = Column(JSON, default=list)
    street_type = Column(String(50), default="Street")  # Main Road, Cross Street, Salai, Road, Highway, Lane
    area_id = Column(Integer, ForeignKey("areas.id"), nullable=True, index=True)
    ward_id = Column(Integer, ForeignKey("corporation_wards.id"), nullable=True, index=True)
    zone_id = Column(Integer, ForeignKey("corporation_zones.id"), nullable=True, index=True)
    taluk_id = Column(Integer, ForeignKey("taluks.id"), nullable=True, index=True)
    village_id = Column(Integer, ForeignKey("revenue_villages.id"), nullable=True, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    source = Column(String(100), default="CCMC Open GIS & OpenStreetMap")
    confidence = Column(Float, default=0.90)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    area = relationship("Area", back_populates="streets")
    ward = relationship("CorporationWard", back_populates="streets")
    landmarks = relationship("Landmark", back_populates="street")


class Landmark(Base):
    """
    High-value landmark points (Bus stands, Hospitals, Railway stations, Temples, Malls, Colleges, Lakes).
    """
    __tablename__ = "landmarks"

    id = Column(Integer, primary_key=True, index=True)
    name_en = Column(String(200), nullable=False, index=True)
    name_ta = Column(String(250), nullable=True)
    name_tanglish = Column(String(200), nullable=True)
    aliases = Column(JSON, default=list)
    landmark_type = Column(String(100), default="Other")  # Bus Stand, Hospital, College, Temple, Market, Police Station, Lake, Mall
    address = Column(String(255), nullable=True)
    area_id = Column(Integer, ForeignKey("areas.id"), nullable=True, index=True)
    street_id = Column(Integer, ForeignKey("streets.id"), nullable=True, index=True)
    ward_id = Column(Integer, ForeignKey("corporation_wards.id"), nullable=True, index=True)
    zone_id = Column(Integer, ForeignKey("corporation_zones.id"), nullable=True, index=True)
    taluk_id = Column(Integer, ForeignKey("taluks.id"), nullable=True, index=True)
    village_id = Column(Integer, ForeignKey("revenue_villages.id"), nullable=True, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    source = Column(String(100), default="Government of Tamil Nadu & OpenStreetMap")
    confidence = Column(Float, default=0.95)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    area = relationship("Area", back_populates="landmarks")
    street = relationship("Street", back_populates="landmarks")
    ward = relationship("CorporationWard", back_populates="landmarks")


class LocationAlias(Base):
    """
    Cross-lingual and phonetic aliases (Tamil, Tanglish, Whisper error variants).
    """
    __tablename__ = "location_aliases"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(50), nullable=False, index=True)  # taluk, firka, village, zone, ward, area, street, landmark
    entity_id = Column(Integer, nullable=False, index=True)
    alias = Column(String(200), nullable=False, index=True)
    normalized_value = Column(String(200), nullable=False, index=True)
    language = Column(String(20), default="Tanglish")  # Tamil, English, Tanglish
    alias_type = Column(String(50), default="phonetic")  # canonical, transliteration, phonetic, whisper_error, informal
    confidence = Column(Float, default=0.90)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_location_alias_normalized", "normalized_value", "entity_type"),
    )


class LocationSource(Base):
    """
    Audit registry for every authoritative data source used.
    """
    __tablename__ = "location_sources"

    id = Column(Integer, primary_key=True, index=True)
    source_name = Column(String(150), nullable=False, unique=True, index=True)
    source_type = Column(String(50), nullable=False)  # government_gazette, ccmc_official, openstreetmap, gis_portal
    source_url = Column(String(255), nullable=True)
    records_count = Column(Integer, default=0)
    retrieved_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_verified_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notes = Column(Text, nullable=True)


class LocationRelationship(Base):
    """
    Direct relationship mapping between administrative and corporation entities.
    """
    __tablename__ = "location_relationships"

    id = Column(Integer, primary_key=True, index=True)
    parent_type = Column(String(50), nullable=False, index=True)
    parent_id = Column(Integer, nullable=False, index=True)
    child_type = Column(String(50), nullable=False, index=True)
    child_id = Column(Integer, nullable=False, index=True)
    relationship_type = Column(String(50), default="contains")  # contains, overlaps, adjacent
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

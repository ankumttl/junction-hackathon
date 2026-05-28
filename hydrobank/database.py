from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./hydrobank.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- TABLES ---

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    business_type = Column(String)  # brick kiln, factory, EV station, residential
    load_kw = Column(Float)         # their typical load in kW
    credits = Column(Float, default=0.0)
    joined_at = Column(DateTime, default=datetime.utcnow)

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String)     # "surplus" or "shortage"
    message = Column(Text)
    discount_percent = Column(Float)
    start_time = Column(String)
    end_time = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class CustomerResponse(Base):
    __tablename__ = "customer_responses"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer)
    alert_id = Column(Integer)
    accepted = Column(Boolean)
    load_shifted_kw = Column(Float, default=0.0)
    credits_earned = Column(Float, default=0.0)
    responded_at = Column(DateTime, default=datetime.utcnow)

class NEAData(Base):
    __tablename__ = "nea_data"
    id = Column(Integer, primary_key=True, index=True)
    month = Column(Integer)   # 1-12
    year = Column(Integer)
    generation_mw = Column(Float)
    demand_mw = Column(Float)
    surplus_mw = Column(Float)  # can be negative (deficit)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
    seed_nea_data()

def seed_nea_data():
    """Seed real NEA seasonal data"""
    db = SessionLocal()
    existing = db.query(NEAData).first()
    if existing:
        db.close()
        return

    # Real NEA approximate data (MW) - monsoon high, dry season low
    nea_historical = [
        # month, year, generation, demand, surplus
        (1, 2024, 1100, 1400, -300),   # Jan - deficit
        (2, 2024, 1050, 1380, -330),   # Feb - deficit
        (3, 2024, 1200, 1350, -150),   # Mar - deficit
        (4, 2024, 1500, 1320, 180),    # Apr - slight surplus
        (5, 2024, 1900, 1350, 550),    # May - surplus
        (6, 2024, 2600, 1380, 1220),   # Jun - big surplus (monsoon starts)
        (7, 2024, 3200, 1400, 1800),   # Jul - peak surplus
        (8, 2024, 3400, 1420, 1980),   # Aug - peak surplus
        (9, 2024, 3100, 1400, 1700),   # Sep - high surplus
        (10, 2024, 2400, 1380, 1020),  # Oct - surplus
        (11, 2024, 1400, 1400, 0),     # Nov - breaking even
        (12, 2024, 1150, 1420, -270),  # Dec - deficit
    ]

    for month, year, gen, demand, surplus in nea_historical:
        record = NEAData(month=month, year=year, generation_mw=gen, demand_mw=demand, surplus_mw=surplus)
        db.add(record)

    db.commit()
    db.close()
from sqlalchemy import Column, Integer, String, Float, DateTime, func
from backend.database import Base

class Price(Base):
    __tablename__ = "prices"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)    # 'bitcoin', 'ethereum', 'cusd'
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

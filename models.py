from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Date,
    Time,
    ForeignKey,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()

class Task(Base):
    __tablename__ = "task"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=True)          # link hướng dẫn
    due_date = Column(Date, nullable=True)       # hạn chót (ngày)
    due_time = Column(Time, nullable=True)       # hạn chót (giờ)

    statuses = relationship("DailyStatus", back_populates="task", cascade="all, delete-orphan")

class DailyStatus(Base):
    __tablename__ = "daily_status"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("task.id"), nullable=False)
    date = Column(Date, nullable=False)
    done = Column(Boolean, default=False, nullable=False)

    task = relationship("Task", back_populates="statuses")

# SQLite URL — sẽ tạo file tasks.db ngay thư mục gốc
SQLALCHEMY_DATABASE_URL = "sqlite:///./tasks.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.drop_all(bind=engine)   # Xoá cũ nếu có
    Base.metadata.create_all(bind=engine) # Tạo lại

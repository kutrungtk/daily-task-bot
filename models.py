from sqlalchemy import (
    Column, Integer, String,
    Date, Boolean, ForeignKey,
    DateTime, create_engine, event
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()

class Task(Base):
    __tablename__ = 'tasks'
    id       = Column(Integer, primary_key=True)
    name     = Column(String, unique=True, nullable=False)
    link     = Column(String, nullable=True)       # URL hướng dẫn
    deadline = Column(DateTime, nullable=True)     # Ngày giờ deadline
    # Khi Task bị xóa, SQLAlchemy sẽ xóa luôn các DailyStatus liên quan:
    statuses = relationship(
        "DailyStatus",
        back_populates="task",
        cascade="all, delete-orphan"
    )

class DailyStatus(Base):
    __tablename__ = 'daily_status'
    id      = Column(Integer, primary_key=True)
    task_id = Column(
        Integer,
        ForeignKey('tasks.id', ondelete="CASCADE"),
        nullable=False
    )
    date    = Column(Date,   nullable=False)
    done    = Column(Boolean, default=False)
    task    = relationship("Task", back_populates="statuses")

# Tạo engine kết nối SQLite
engine = create_engine(
    "sqlite:///tasks.db",
    echo=False,
    connect_args={"check_same_thread": False}
)

# Bật PRAGMA foreign_keys mỗi khi có kết nối mới
@event.listens_for(engine, "connect")
def _enable_foreign_keys(dbapi_conn, connection_record):
    dbapi_conn.execute("PRAGMA foreign_keys=ON")

# Tạo session
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

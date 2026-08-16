import os
import secrets
import uuid
from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


def new_token() -> str:
    return secrets.token_urlsafe(24)


def new_id() -> str:
    return str(uuid.uuid4())


class Topic(Base):
    __tablename__ = "topics"

    id = Column(String, primary_key=True, default=new_id)
    date = Column(Date, default=date.today)
    headline = Column(String, nullable=False)
    summary = Column(Text, nullable=False)
    source_link = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, selected, discarded
    choose_token = Column(String, unique=True, index=True, default=new_token)
    created_at = Column(DateTime, default=datetime.utcnow)

    posts = relationship("Post", back_populates="topic")


class Post(Base):
    __tablename__ = "posts"

    id = Column(String, primary_key=True, default=new_id)
    topic_id = Column(String, ForeignKey("topics.id"), nullable=False)
    version = Column(Integer, default=1)
    content = Column(Text, nullable=False)
    feedback = Column(Text, nullable=True)
    status = Column(String, default="pending_approval")  # pending_approval, approved, posted, superseded
    approve_token = Column(String, unique=True, index=True, default=new_token)
    regenerate_token = Column(String, unique=True, index=True, default=new_token)
    linkedin_urn = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    posted_at = Column(DateTime, nullable=True)

    topic = relationship("Topic", back_populates="posts")


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        database_url = os.environ["DATABASE_URL"]
        _engine = create_engine(database_url, pool_pre_ping=True)
    return _engine


def get_session():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()


def init_db():
    Base.metadata.create_all(get_engine())

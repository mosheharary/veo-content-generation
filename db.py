import streamlit as st
from sqlalchemy import create_engine, Column, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import uuid
from datetime import datetime
import bcrypt
import os

Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True, default=generate_uuid)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    sessions = relationship("Session", back_populates="user")

class Session(Base):
    __tablename__ = 'sessions'
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    session_name = Column(String, nullable=False)
    api_key_used = Column(String)
    total_cost = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="sessions")
    generations = relationship("Generation", back_populates="session", cascade="all, delete-orphan")

class Generation(Base):
    __tablename__ = 'generations'
    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey('sessions.id'), nullable=False)
    gen_type = Column(String, nullable=False) # 'video', 'image', 'comics'
    prompt = Column(Text, nullable=False)
    metadata_json = Column(JSON)
    media_url = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("Session", back_populates="generations")

@st.cache_resource
def get_engine():
    db_url = ""
    try:
        db_url = st.secrets.get("DATABASE_URL")
    except Exception:
        pass
    
    if not db_url:
        db_url = os.environ.get("DATABASE_URL")
        
    if not db_url:
        # Fallback to sqlite for local dev if Neon URL isn't provided
        db_url = "sqlite:///local_history.db"
    
    engine = create_engine(db_url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return engine

def get_session():
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    if not hashed: return False
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def get_user_by_username(db_session, username):
    return db_session.query(User).filter(User.username == username).first()

def create_user(db_session, username, password):
    hashed = hash_password(password)
    user = User(username=username, password_hash=hashed)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

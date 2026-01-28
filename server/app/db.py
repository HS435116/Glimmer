import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.environ.get('GLIMMER_DB_PATH') or os.path.join(BASE_DIR, 'glimmer.db')
DATABASE_URL = os.environ.get('GLIMMER_DATABASE_URL') or f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith('sqlite') else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

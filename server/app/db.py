import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# 说明：仅更换文件名并不能提供真正的安全性，核心仍应依赖鉴权/权限控制。
# 这里提供一个更“隐蔽”的默认库文件名（同时保留可用环境变量覆盖）。
_DEFAULT_DB_FILENAME = os.environ.get('GLIMMER_DB_FILENAME') or 'data_7b1c0a9f3e2d4c6b.sqlite'
DB_PATH = os.environ.get('GLIMMER_DB_PATH') or os.path.join(BASE_DIR, _DEFAULT_DB_FILENAME)

# 兼容旧库：若未显式指定 GLIMMER_DB_PATH，且新路径不存在但旧 glimmer.db 存在，则自动迁移/改名
if not os.environ.get('GLIMMER_DB_PATH'):
    legacy = os.path.join(BASE_DIR, 'glimmer.db')
    if (not os.path.exists(DB_PATH)) and os.path.exists(legacy):
        try:
            os.replace(legacy, DB_PATH)
        except Exception:
            pass

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

from __future__ import annotations

import os
import random
from datetime import datetime, timedelta

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request

from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select, and_, or_, func, delete

from sqlalchemy.orm import Session

from .db import Base, engine, get_db
from .models import (
    AdConfig,
    Announcement,
    AnnouncementScope,
    Attendance,
    ChatMessage,
    CorrectionRequest,
    CorrectionStatus,
    Group,
    JoinRequest,
    JoinStatus,
    Membership,
    Role,
    User,
    VersionConfig,
)
from .schemas import (
    AdIn,
    AdOut,
    AnnouncementCreateIn,
    AnnouncementOut,
    ApplyJoinIn,
    AdminCorrectionIn,
    ChatMarkReadIn,
    ChatMessageOut,
    ChatSendIn,
    ChatUnreadOut,
    CorrectionIn,
    CorrectionOut,
    GroupCreateIn,
    GroupMemberOut,

    GroupOut,
    JoinRequestOut,
    ChangePasswordIn,
    LoginIn,
    PunchIn,
    PunchOut,
    RegisterIn,
    ResetPasswordIn,
    SecurityQuestionOut,
    TokenOut,
    UserOut,
    UserProfileOut,
    EngineerUserDetailOut,
    VersionIn,
    VersionOut,
)


from .security import create_access_token, decode_token, hash_password, verify_password


app = FastAPI(title='Glimmer Attendance Server', version='0.1.0')

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/auth/login')


_SERVER_DIR = Path(__file__).resolve().parents[1]  # .../server
_PUBLIC_DIR = _SERVER_DIR / 'public'
_DEFAULT_APK_NAMES = (
    'app.apk',
    'latest.apk',
    '晨曦智能打卡.apk',
)


def _resolve_apk_path() -> Path | None:
    env = (os.environ.get('GLIMMER_APK_PATH') or '').strip()
    if env:
        p = Path(env).expanduser()
        return p if p.is_file() else None

    for name in _DEFAULT_APK_NAMES:
        p = _PUBLIC_DIR / name
        if p.is_file():
            return p

    if _PUBLIC_DIR.is_dir():
        apks = sorted(
            _PUBLIC_DIR.glob('*.apk'),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )
        if apks:
            return apks[0]

    return None


def _now_date_str() -> str:
    return datetime.now().strftime('%Y-%m-%d')


def _ensure_group_code_unique(db: Session) -> str:
    # 6 位数字的邀请码（群ID）
    for _ in range(50):
        code = f"{random.randint(0, 999999):06d}"
        exists = db.execute(select(Group.id).where(Group.group_code == code)).first()
        if not exists:
            return code
    raise HTTPException(status_code=500, detail='failed to allocate group_code')


def _alloc_admin_username(db: Session, base: str = 'admin') -> str:
    base = str(base or 'admin').strip() or 'admin'
    # admin, admin1, admin2... 递增
    if not _get_user_by_username(db, base):
        return base
    for i in range(1, 10000):
        name = f"{base}{i}"
        if not _get_user_by_username(db, name):
            return name
    raise HTTPException(status_code=500, detail='failed to allocate admin username')





def _get_user_by_username(db: Session, username: str) -> User | None:
    return db.execute(select(User).where(User.username == username)).scalar_one_or_none()


def _require_engineer(user: User):
    if user.role != Role.engineer:
        raise HTTPException(status_code=403, detail='engineer only')


def _is_group_admin(db: Session, user_id: int, group_id: int) -> bool:
    row = db.execute(
        select(Membership.id)
        .where(and_(Membership.user_id == user_id, Membership.group_id == group_id, Membership.is_group_admin == True))
    ).first()
    return bool(row)


def _require_group_admin(db: Session, user: User, group_id: int):
    # 管理员权限约束：
    # - engineer：可管理所有团队
    # - admin：仅可管理自己创建的团队（默认只看到/管理自己的团队）
    if user.role == Role.engineer:
        return
    if user.role != Role.admin:
        raise HTTPException(status_code=403, detail='admin only')

    g = db.execute(select(Group).where(Group.id == int(group_id))).scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail='group not found')
    if int(getattr(g, 'created_by_user_id', 0) or 0) != int(user.id):
        raise HTTPException(status_code=403, detail='not group owner')




def _share_any_group(db: Session, user_a_id: int, user_b_id: int) -> bool:
    try:
        a_groups = db.execute(select(Membership.group_id).where(Membership.user_id == int(user_a_id))).scalars().all()
        if not a_groups:
            return False
        row = db.execute(
            select(Membership.id).where(and_(Membership.user_id == int(user_b_id), Membership.group_id.in_(a_groups)))
        ).first()
        return bool(row)
    except Exception:
        return False





def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    try:
        payload = decode_token(token)
        username = payload.get('sub')
        if not username:
            raise HTTPException(status_code=401, detail='invalid token')
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail='invalid token')

    user = _get_user_by_username(db, str(username))
    if not user:
        raise HTTPException(status_code=401, detail='user not found')
    return user


@app.on_event('startup')
def _startup():
    Base.metadata.create_all(bind=engine)

    # 轻量迁移：SQLite 旧库可能没有新增字段
    if getattr(engine, 'dialect', None) is not None and engine.dialect.name == 'sqlite':
        try:
            with engine.begin() as conn:
                # ad_config.scroll_mode
                cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info('ad_config')").fetchall()]
                if 'scroll_mode' not in cols:
                    conn.exec_driver_sql("ALTER TABLE ad_config ADD COLUMN scroll_mode VARCHAR(20) DEFAULT '垂直滚动'")
                conn.exec_driver_sql("UPDATE ad_config SET scroll_mode='垂直滚动' WHERE scroll_mode IS NULL OR scroll_mode='' ")

                # users 个人资料/密保字段
                ucols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info('users')").fetchall()]
                if 'real_name' not in ucols:
                    conn.exec_driver_sql("ALTER TABLE users ADD COLUMN real_name VARCHAR(120) DEFAULT ''")
                if 'phone' not in ucols:
                    conn.exec_driver_sql("ALTER TABLE users ADD COLUMN phone VARCHAR(40) DEFAULT ''")
                if 'department' not in ucols:
                    conn.exec_driver_sql("ALTER TABLE users ADD COLUMN department VARCHAR(120) DEFAULT ''")
                if 'security_question' not in ucols:
                    conn.exec_driver_sql("ALTER TABLE users ADD COLUMN security_question VARCHAR(200) DEFAULT ''")
                if 'security_answer_hash' not in ucols:
                    conn.exec_driver_sql("ALTER TABLE users ADD COLUMN security_answer_hash VARCHAR(255) DEFAULT ''")
                if 'last_login' not in ucols:
                    conn.exec_driver_sql("ALTER TABLE users ADD COLUMN last_login DATETIME")
                if 'last_login_ip' not in ucols:
                    conn.exec_driver_sql("ALTER TABLE users ADD COLUMN last_login_ip VARCHAR(64) DEFAULT ''")

        except Exception:
            pass


    from .db import SessionLocal

    db = SessionLocal()

    try:
        # 初始化配置单例
        if not db.execute(select(VersionConfig.id)).first():
            db.add(VersionConfig(latest_version='1.0.0', note=''))
        if not db.execute(select(AdConfig.id)).first():
            db.add(AdConfig(enabled=True, text='', image_url='', link_url=''))
        db.commit()

        # 引导工程师账号（超级管理员）
        eng_user = os.environ.get('GLIMMER_ENGINEER_USER') or 'engineer'
        eng_pass = os.environ.get('GLIMMER_ENGINEER_PASS') or 'engineer123'
        u = _get_user_by_username(db, eng_user)
        if not u:
            db.add(User(username=eng_user, password_hash=hash_password(eng_pass), role=Role.engineer))
            db.commit()

        # 引导管理员账号（仅管理权限，不含工程师权限）
        admin_user = os.environ.get('GLIMMER_ADMIN_USER') or 'admin'
        admin_pass = os.environ.get('GLIMMER_ADMIN_PASS') or 'admin123'
        a = _get_user_by_username(db, admin_user)
        if not a:
            db.add(
                User(
                    username=admin_user,
                    password_hash=hash_password(admin_pass),
                    role=Role.admin,
                    real_name='管理员',
                    security_question='默认密保问题',
                    security_answer_hash=hash_password('admin'),
                )
            )
            db.commit()
        else:
            # 若已有同名账号：确保其为管理员且可用（不覆盖 engineer）
            if a.role != Role.engineer:
                a.role = Role.admin
                a.password_hash = hash_password(admin_pass)
                if not str(getattr(a, 'security_question', '') or '').strip():
                    a.security_question = '默认密保问题'
                if not str(getattr(a, 'security_answer_hash', '') or '').strip():
                    a.security_answer_hash = hash_password('admin')
                db.commit()

    finally:
        db.close()


@app.get('/health')
def health():
    return {'ok': True}


@app.get('/download/apk')
def download_apk():
    p = _resolve_apk_path()
    if not p:
        raise HTTPException(status_code=404, detail='apk not found')

    # filename 参数会自动设置 Content-Disposition: attachment
    return FileResponse(
        path=str(p),
        media_type='application/vnd.android.package-archive',
        filename=p.name,
    )


@app.post('/auth/register', response_model=UserOut)
def register(data: RegisterIn, db: Annotated[Session, Depends(get_db)]):
    if _get_user_by_username(db, data.username):
        raise HTTPException(status_code=400, detail='username exists')

    q = str(getattr(data, 'security_question', '') or '').strip()
    a = str(getattr(data, 'security_answer', '') or '').strip()
    if not q or not a:
        raise HTTPException(status_code=400, detail='security_question/security_answer required')

    user = User(
        username=str(data.username),
        password_hash=hash_password(str(data.password)),
        role=Role.user,
        real_name=str(getattr(data, 'real_name', '') or '').strip(),
        phone=str(getattr(data, 'phone', '') or '').strip(),
        department=str(getattr(data, 'department', '') or '').strip(),
        security_question=q,
        security_answer_hash=hash_password(a),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut(id=user.id, username=user.username, role=str(user.role.value))



@app.post('/auth/login', response_model=TokenOut)
def login(data: LoginIn, db: Annotated[Session, Depends(get_db)], request: Request):

    user = _get_user_by_username(db, data.username)
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail='bad credentials')

    try:
        user.last_login = datetime.utcnow()
        try:
            user.last_login_ip = str(getattr(getattr(request, 'client', None), 'host', '') or '')
        except Exception:
            user.last_login_ip = ''
        db.commit()
    except Exception:
        db.rollback()


    token = create_access_token(user.username, extra={'role': user.role.value})
    return TokenOut(access_token=token)






@app.post('/auth/change_password')
def change_password(
    data: ChangePasswordIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    if not verify_password(str(data.old_password), str(user.password_hash)):
        raise HTTPException(status_code=401, detail='bad credentials')

    user.password_hash = hash_password(str(data.new_password))
    db.commit()
    return {'ok': True}


@app.get('/auth/security_question', response_model=SecurityQuestionOut)
def get_security_question(
    username: str = Query(..., min_length=3, max_length=64),
    db: Annotated[Session, Depends(get_db)] = None,
):
    u = _get_user_by_username(db, str(username))
    if not u:
        raise HTTPException(status_code=404, detail='user not found')
    q = str(getattr(u, 'security_question', '') or '')
    if not q:
        raise HTTPException(status_code=404, detail='security_question not set')
    return SecurityQuestionOut(username=u.username, security_question=q)


@app.post('/auth/reset_password')
def reset_password(data: ResetPasswordIn, db: Annotated[Session, Depends(get_db)]):
    u = _get_user_by_username(db, str(data.username))
    if not u:
        raise HTTPException(status_code=404, detail='user not found')

    stored = str(getattr(u, 'security_answer_hash', '') or '')
    if not stored:
        raise HTTPException(status_code=400, detail='security_answer not set')

    if not verify_password(str(data.security_answer), stored):
        raise HTTPException(status_code=401, detail='security_answer mismatch')

    u.password_hash = hash_password(str(data.new_password))
    db.commit()
    return {'ok': True}


@app.get('/me', response_model=UserProfileOut)

def me(user: Annotated[User, Depends(get_current_user)]):
    return UserProfileOut(
        id=user.id,
        username=user.username,
        role=str(user.role.value),
        real_name=str(getattr(user, 'real_name', '') or ''),
        phone=str(getattr(user, 'phone', '') or ''),
        department=str(getattr(user, 'department', '') or ''),
        created_at=user.created_at,
        last_login=getattr(user, 'last_login', None),
        security_question=str(getattr(user, 'security_question', '') or ''),
    )



@app.post('/groups', response_model=GroupOut)
def create_group(
    data: GroupCreateIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    # engineer/admin 都允许创建团队；admin 只能管理自己创建的团队
    if user.role not in (Role.engineer, Role.admin):
        raise HTTPException(status_code=403, detail='admin only')

    code = _ensure_group_code_unique(db)
    g = Group(name=data.name, group_code=code, created_by_user_id=user.id)
    db.add(g)
    db.commit()
    db.refresh(g)

    # 创建者默认加入该群；工程师在该群默认拥有群管理员权限
    if not db.execute(select(Membership.id).where(and_(Membership.user_id == user.id, Membership.group_id == g.id))).first():
        db.add(Membership(user_id=user.id, group_id=g.id, is_group_admin=True))
        db.commit()

    return GroupOut(id=g.id, name=g.name, group_code=g.group_code)


@app.get('/groups/my', response_model=list[GroupOut])
def my_groups(db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    rows = db.execute(
        select(Group)
        .join(Membership, Membership.group_id == Group.id)
        .where(Membership.user_id == user.id)
        .order_by(Group.id.desc())
    ).scalars().all()
    return [GroupOut(id=g.id, name=g.name, group_code=g.group_code) for g in rows]


@app.get('/groups/{group_id}/members', response_model=list[GroupMemberOut])
def group_members(
    group_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    # 只有团队成员可见
    if not db.execute(select(Membership.id).where(and_(Membership.user_id == user.id, Membership.group_id == group_id))).first():
        raise HTTPException(status_code=403, detail='not in group')

    rows = db.execute(
        select(User.id, User.username, Membership.joined_at, Membership.is_group_admin)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.group_id == group_id)
        .order_by(Membership.joined_at.asc())
        .limit(800)
    ).all()
    return [
        GroupMemberOut(user_id=int(uid), username=str(uname), joined_at=joined_at, is_group_admin=bool(is_admin))
        for uid, uname, joined_at, is_admin in rows
    ]


@app.post('/groups/apply')
def apply_join(

    data: ApplyJoinIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    g = db.execute(select(Group).where(Group.group_code == data.group_code)).scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail='group not found')

    # 已在群内
    if db.execute(select(Membership.id).where(and_(Membership.user_id == user.id, Membership.group_id == g.id))).first():
        return {'ok': True, 'detail': 'already in group'}

    existing = db.execute(
        select(JoinRequest).where(and_(JoinRequest.user_id == user.id, JoinRequest.group_id == g.id, JoinRequest.status == JoinStatus.pending))
    ).scalar_one_or_none()
    if existing:
        return {'ok': True, 'detail': 'already requested'}

    req = JoinRequest(user_id=user.id, group_id=g.id, status=JoinStatus.pending)
    db.add(req)
    db.commit()
    return {'ok': True, 'detail': 'requested'}


@app.get('/groups/requests/pending', response_model=list[JoinRequestOut])
def pending_join_requests(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    q = select(JoinRequest, User.username, Group.name, Group.group_code).join(User, User.id == JoinRequest.user_id).join(Group, Group.id == JoinRequest.group_id).where(JoinRequest.status == JoinStatus.pending)

    if user.role == Role.engineer:
        pass
    elif user.role == Role.admin:
        # 管理员默认只看到自己创建的团队的 pending
        q = q.where(Group.created_by_user_id == user.id)
    else:
        raise HTTPException(status_code=403, detail='admin only')

    rows = db.execute(q.order_by(JoinRequest.requested_at.asc())).all()

    out: list[JoinRequestOut] = []
    for req, username, group_name, group_code in rows:
        out.append(JoinRequestOut(
            id=req.id,
            user_id=req.user_id,
            username=username,
            group_id=req.group_id,
            group_name=group_name,
            group_code=str(group_code or ''),
            status=req.status.value,
            requested_at=req.requested_at,
        ))

    return out


@app.post('/groups/requests/{request_id}/approve')
def approve_join(
    request_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    req = db.execute(select(JoinRequest).where(JoinRequest.id == request_id)).scalar_one_or_none()
    if not req or req.status != JoinStatus.pending:
        raise HTTPException(status_code=404, detail='request not found')

    _require_group_admin(db, user, req.group_id)

    req.status = JoinStatus.approved
    req.reviewed_at = datetime.utcnow()
    req.reviewed_by_user_id = user.id

    mem = Membership(user_id=req.user_id, group_id=req.group_id, is_group_admin=False)
    db.add(mem)
    db.commit()
    return {'ok': True}


@app.post('/groups/requests/{request_id}/reject')
def reject_join(
    request_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    req = db.execute(select(JoinRequest).where(JoinRequest.id == request_id)).scalar_one_or_none()
    if not req or req.status != JoinStatus.pending:
        raise HTTPException(status_code=404, detail='request not found')

    _require_group_admin(db, user, req.group_id)

    req.status = JoinStatus.rejected
    req.reviewed_at = datetime.utcnow()
    req.reviewed_by_user_id = user.id
    db.commit()
    return {'ok': True}


@app.post('/groups/{group_id}/members/{member_user_id}/set-group-admin')
def set_group_admin(
    group_id: int,
    member_user_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    is_admin: bool = True,
):


    # 只有工程师可以授予/回收群管理员
    # engineer/admin 都允许创建团队；admin 只能管理自己创建的团队
    if user.role not in (Role.engineer, Role.admin):
        raise HTTPException(status_code=403, detail='admin only')

    mem = db.execute(select(Membership).where(and_(Membership.group_id == group_id, Membership.user_id == member_user_id))).scalar_one_or_none()
    if not mem:
        raise HTTPException(status_code=404, detail='membership not found')

    mem.is_group_admin = bool(is_admin)

    target = db.execute(select(User).where(User.id == member_user_id)).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail='user not found')

    # 群管理员属于"管理员"等级（工程师除外）
    if mem.is_group_admin:
        if target.role == Role.user:
            target.role = Role.admin
    else:
        if target.role == Role.admin:
            # 若该用户不再是任何群的群管理员，则降回普通用户
            still_admin = db.execute(
                select(Membership.id).where(and_(Membership.user_id == target.id, Membership.is_group_admin == True))
            ).first()
            if not still_admin:
                target.role = Role.user

    db.commit()
    return {'ok': True}


@app.post('/announcements/global', response_model=AnnouncementOut)
def post_global_announcement(
    data: AnnouncementCreateIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    # engineer/admin 都允许创建团队；admin 只能管理自己创建的团队
    if user.role not in (Role.engineer, Role.admin):
        raise HTTPException(status_code=403, detail='admin only')

    a = Announcement(scope=AnnouncementScope.global_, group_id=None, title=data.title, content=data.content, created_by_user_id=user.id)
    db.add(a)
    db.commit()
    db.refresh(a)
    return AnnouncementOut(id=a.id, scope=a.scope.value, group_id=a.group_id, title=a.title, content=a.content, created_at=a.created_at)


@app.post('/announcements/group/{group_id}', response_model=AnnouncementOut)
def post_group_announcement(
    group_id: int,
    data: AnnouncementCreateIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_group_admin(db, user, group_id)
    a = Announcement(scope=AnnouncementScope.group, group_id=group_id, title=data.title, content=data.content, created_by_user_id=user.id)
    db.add(a)
    db.commit()
    db.refresh(a)
    return AnnouncementOut(id=a.id, scope=a.scope.value, group_id=a.group_id, title=a.title, content=a.content, created_at=a.created_at)


@app.get('/announcements/feed', response_model=list[AnnouncementOut])
def announcements_feed(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    since: str | None = Query(default=None, description='ISO datetime, e.g. 2026-01-28T10:00:00'),
):

    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except Exception:
            raise HTTPException(status_code=400, detail='bad since')

    group_ids = db.execute(select(Membership.group_id).where(Membership.user_id == user.id)).scalars().all()

    q = select(Announcement).where(
        or_(
            Announcement.scope == AnnouncementScope.global_,
            and_(Announcement.scope == AnnouncementScope.group, Announcement.group_id.in_(group_ids or [-1])),
        )
    )
    if since_dt:
        q = q.where(Announcement.created_at > since_dt)

    rows = db.execute(q.order_by(Announcement.created_at.asc()).limit(200)).scalars().all()
    return [AnnouncementOut(id=a.id, scope=a.scope.value, group_id=a.group_id, title=a.title, content=a.content, created_at=a.created_at) for a in rows]


@app.get('/config/version', response_model=VersionOut)
def get_version(db: Annotated[Session, Depends(get_db)]):
    v = db.execute(select(VersionConfig).order_by(VersionConfig.id.asc())).scalar_one()
    return VersionOut(latest_version=v.latest_version, note=v.note, updated_at=v.updated_at)


@app.post('/config/version', response_model=VersionOut)
def set_version(
    data: VersionIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    # engineer/admin 都允许创建团队；admin 只能管理自己创建的团队
    if user.role not in (Role.engineer, Role.admin):
        raise HTTPException(status_code=403, detail='admin only')

    v = db.execute(select(VersionConfig).order_by(VersionConfig.id.asc())).scalar_one()
    v.latest_version = data.latest_version
    v.note = data.note
    v.updated_at = datetime.utcnow()
    v.updated_by_user_id = user.id
    db.commit()
    return VersionOut(latest_version=v.latest_version, note=v.note, updated_at=v.updated_at)


def _normalize_scroll_mode(v: str) -> str:
    x = str(v or '').strip()
    if x in ('水平滚动', '垂直滚动', '静止'):
        return x
    # 兼容可能的中文别名
    if x in ('左右滚动',):
        return '水平滚动'
    if x in ('上下滚动',):
        return '垂直滚动'
    return '垂直滚动'


@app.get('/config/ads', response_model=AdOut)
def get_ads(db: Annotated[Session, Depends(get_db)]):
    a = db.execute(select(AdConfig).order_by(AdConfig.id.asc())).scalar_one()
    return AdOut(
        enabled=a.enabled,
        text=a.text,
        image_url=a.image_url,
        link_url=a.link_url,
        scroll_mode=_normalize_scroll_mode(getattr(a, 'scroll_mode', '') or '垂直滚动'),
        updated_at=a.updated_at,
    )


@app.post('/config/ads', response_model=AdOut)
def set_ads(
    data: AdIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    # engineer/admin 都允许创建团队；admin 只能管理自己创建的团队
    if user.role not in (Role.engineer, Role.admin):
        raise HTTPException(status_code=403, detail='admin only')

    a = db.execute(select(AdConfig).order_by(AdConfig.id.asc())).scalar_one()
    a.enabled = bool(data.enabled)
    a.text = data.text
    a.image_url = data.image_url
    a.link_url = data.link_url
    a.scroll_mode = _normalize_scroll_mode(getattr(data, 'scroll_mode', '') or '垂直滚动')
    a.updated_at = datetime.utcnow()
    a.updated_by_user_id = user.id
    db.commit()
    return AdOut(
        enabled=a.enabled,
        text=a.text,
        image_url=a.image_url,
        link_url=a.link_url,
        scroll_mode=_normalize_scroll_mode(getattr(a, 'scroll_mode', '') or '垂直滚动'),
        updated_at=a.updated_at,
    )



@app.post('/attendance/punch', response_model=PunchOut)
def punch(
    data: PunchIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    # 若指定群，则要求是群成员
    if data.group_id is not None:
        if not db.execute(select(Membership.id).where(and_(Membership.user_id == user.id, Membership.group_id == data.group_id))).first():
            raise HTTPException(status_code=403, detail='not in group')

    r = Attendance(
        user_id=user.id,
        group_id=data.group_id,
        punched_at=datetime.utcnow(),
        date=_now_date_str(),
        status=data.status,
        lat=data.lat,
        lon=data.lon,
        notes=data.notes or '',
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return PunchOut(
        id=r.id,
        date=r.date,
        punched_at=r.punched_at,
        status=r.status,
        group_id=r.group_id,
        lat=r.lat,
        lon=r.lon,
        notes=r.notes,
    )


@app.get('/attendance/month', response_model=list[PunchOut])
def attendance_month(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    month: str = Query(..., description='YYYY-MM'),
):

    if len(month) != 7:
        raise HTTPException(status_code=400, detail='bad month')
    rows = db.execute(
        select(Attendance)
        .where(and_(Attendance.user_id == user.id, Attendance.date.like(f"{month}-%")))
        .order_by(Attendance.punched_at.desc())
        .limit(400)
    ).scalars().all()
    return [PunchOut(id=r.id, date=r.date, punched_at=r.punched_at, status=r.status, group_id=r.group_id, lat=r.lat, lon=r.lon, notes=r.notes) for r in rows]


@app.get('/admin/users/{target_user_id}/attendance/month', response_model=list[PunchOut])
def admin_attendance_month(
    target_user_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    month: str = Query(..., description='YYYY-MM'),
):
    if len(month) != 7:
        raise HTTPException(status_code=400, detail='bad month')

    # 管理端：
    # - 工程师：可查看任意用户
    # - 管理员：仅可查看自己创建的团队内的成员
    if user.role == Role.engineer:
        pass
    elif user.role == Role.admin:
        admin_group_ids = db.execute(select(Group.id).where(Group.created_by_user_id == user.id)).scalars().all()
        if not admin_group_ids:
            raise HTTPException(status_code=403, detail='no managed groups')
        in_group = db.execute(
            select(Membership.id).where(and_(Membership.user_id == int(target_user_id), Membership.group_id.in_(admin_group_ids)))
        ).first()
        if not in_group:
            raise HTTPException(status_code=403, detail='not your member')
    else:
        raise HTTPException(status_code=403, detail='admin only')




    rows = db.execute(
        select(Attendance)
        .where(and_(Attendance.user_id == int(target_user_id), Attendance.date.like(f"{month}-%")))
        .order_by(Attendance.punched_at.desc())
        .limit(400)
    ).scalars().all()
    return [PunchOut(id=r.id, date=r.date, punched_at=r.punched_at, status=r.status, group_id=r.group_id, lat=r.lat, lon=r.lon, notes=r.notes) for r in rows]



@app.post('/corrections/request', response_model=CorrectionOut)
def request_correction(
    data: CorrectionIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    # 只有入群用户可以申请补录
    if not db.execute(select(Membership.id).where(and_(Membership.user_id == user.id, Membership.group_id == data.group_id))).first():
        raise HTTPException(status_code=403, detail='not in group')

    req = CorrectionRequest(
        user_id=user.id,
        group_id=data.group_id,
        date=data.date,
        reason=data.reason or '',
        status=CorrectionStatus.pending,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return CorrectionOut(
        id=req.id,
        user_id=req.user_id,
        username=user.username,
        group_id=req.group_id,
        date=req.date,
        reason=req.reason,
        status=req.status.value,
        requested_at=req.requested_at,
    )


@app.post('/admin/corrections/request', response_model=CorrectionOut)
def admin_request_correction(
    data: AdminCorrectionIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    # 管理端：工程师允许；管理员仅允许对自己创建的团队操作
    _require_group_admin(db, user, int(data.group_id))

    # 目标用户必须是该团队成员

    if not db.execute(select(Membership.id).where(and_(Membership.user_id == int(data.user_id), Membership.group_id == int(data.group_id)))).first():
        raise HTTPException(status_code=404, detail='target not in group')

    target = db.execute(select(User).where(User.id == int(data.user_id))).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail='user not found')

    req = CorrectionRequest(
        user_id=int(data.user_id),
        group_id=int(data.group_id),
        date=str(data.date),
        reason=str(data.reason or ''),
        status=CorrectionStatus.pending,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return CorrectionOut(
        id=req.id,
        user_id=req.user_id,
        username=target.username,
        group_id=req.group_id,
        date=req.date,
        reason=req.reason,
        status=req.status.value,
        requested_at=req.requested_at,
    )


@app.get('/corrections/pending', response_model=list[CorrectionOut])
def pending_corrections(

    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    q = (
        select(CorrectionRequest, User.username)
        .join(User, User.id == CorrectionRequest.user_id)
        .join(Group, Group.id == CorrectionRequest.group_id)
        .where(CorrectionRequest.status == CorrectionStatus.pending)
    )

    if user.role == Role.engineer:
        pass
    elif user.role == Role.admin:
        q = q.where(Group.created_by_user_id == user.id)
    else:
        raise HTTPException(status_code=403, detail='admin only')

    rows = db.execute(q.order_by(CorrectionRequest.requested_at.asc()).limit(200)).all()

    out: list[CorrectionOut] = []
    for req, username in rows:
        out.append(CorrectionOut(
            id=req.id,
            user_id=req.user_id,
            username=username,
            group_id=req.group_id,
            date=req.date,
            reason=req.reason,
            status=req.status.value,
            requested_at=req.requested_at,
        ))
    return out


@app.post('/corrections/{request_id}/approve')
def approve_correction(
    request_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    req = db.execute(select(CorrectionRequest).where(CorrectionRequest.id == request_id)).scalar_one_or_none()
    if not req or req.status != CorrectionStatus.pending:
        raise HTTPException(status_code=404, detail='request not found')

    _require_group_admin(db, user, req.group_id)

    req.status = CorrectionStatus.approved
    req.reviewed_at = datetime.utcnow()
    req.reviewed_by_user_id = user.id

    # 审核通过：自动写一条"补录"打卡记录
    r = Attendance(
        user_id=req.user_id,
        group_id=req.group_id,
        punched_at=datetime.utcnow(),
        date=req.date,
        status='补录',
        lat=None,
        lon=None,
        notes=req.reason or '',
    )
    db.add(r)

    db.commit()
    return {'ok': True}


@app.post('/corrections/{request_id}/reject')
def reject_correction(
    request_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    req = db.execute(select(CorrectionRequest).where(CorrectionRequest.id == request_id)).scalar_one_or_none()
    if not req or req.status != CorrectionStatus.pending:
        raise HTTPException(status_code=404, detail='request not found')

    _require_group_admin(db, user, req.group_id)

    req.status = CorrectionStatus.rejected
    req.reviewed_at = datetime.utcnow()
    req.reviewed_by_user_id = user.id
    db.commit()
    return {'ok': True}


@app.get('/admin/groups/managed', response_model=list[GroupOut])
def managed_groups(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    # 工程师：可管理全部群；管理员：默认只看到/管理自己创建的群
    if user.role == Role.engineer:
        rows = db.execute(select(Group).order_by(Group.id.desc()).limit(500)).scalars().all()
        return [GroupOut(id=g.id, name=g.name, group_code=g.group_code) for g in rows]

    if user.role != Role.admin:
        raise HTTPException(status_code=403, detail='admin only')

    rows = db.execute(
        select(Group)
        .where(Group.created_by_user_id == user.id)
        .order_by(Group.id.desc())
        .limit(500)
    ).scalars().all()
    return [GroupOut(id=g.id, name=g.name, group_code=g.group_code) for g in rows]




@app.get('/admin/groups/{group_id}/members', response_model=list[GroupMemberOut])
def list_group_members(
    group_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_group_admin(db, user, group_id)
    rows = db.execute(
        select(User.id, User.username, Membership.joined_at, Membership.is_group_admin)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.group_id == group_id)
        .order_by(Membership.joined_at.asc())
        .limit(800)
    ).all()
    return [
        GroupMemberOut(user_id=int(uid), username=str(uname), joined_at=joined_at, is_group_admin=bool(is_admin))
        for uid, uname, joined_at, is_admin in rows
    ]



@app.delete('/admin/groups/{group_id}/members/{member_user_id}')
def remove_group_member(
    group_id: int,
    member_user_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_group_admin(db, user, group_id)

    # 管理员不能移除工程师账号（避免误操作）；工程师可操作所有
    target = db.execute(select(User).where(User.id == int(member_user_id))).scalar_one_or_none()
    if target and target.role == Role.engineer and user.role != Role.engineer:
        raise HTTPException(status_code=403, detail='cannot remove engineer')

    mem = db.execute(select(Membership).where(and_(Membership.group_id == group_id, Membership.user_id == member_user_id))).scalar_one_or_none()
    if not mem:
        raise HTTPException(status_code=404, detail='membership not found')
    db.delete(mem)
    db.commit()
    return {'ok': True}


@app.post('/engineer/admins/create')
def engineer_create_admin(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    password: str | None = Query(default=None, description='管理员初始密码（默认 admin123）'),
):
    # 支持多个 admin 用户名：admin, admin1, admin2 ... 自动累加
    _require_engineer(user)

    uname = _alloc_admin_username(db, 'admin')
    pwd = str(password or '').strip() or (os.environ.get('GLIMMER_ADMIN_PASS') or 'admin123')

    db.add(
        User(
            username=uname,
            password_hash=hash_password(pwd),
            role=Role.admin,
            real_name='管理员',
            security_question='默认密保问题',
            security_answer_hash=hash_password('admin'),
        )
    )
    db.commit()
    created = _get_user_by_username(db, uname)
    return {'id': (created.id if created else None), 'username': uname, 'password': pwd}



@app.get('/admin/users')

def admin_users(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    q: str | None = Query(default=None),
):

    # 仅工程师可查询服务器所有用户个人资料
    _require_engineer(user)

    stmt = select(
        User.id,
        User.username,
        User.role,
        User.real_name,
        User.phone,
        User.department,
        User.created_at,
        User.last_login,
    ).order_by(User.id.desc()).limit(1000)
    if q:
        stmt = stmt.where(User.username.like(f"%{q}%"))
    rows = db.execute(stmt).all()
    return [
        {
            'id': int(uid),
            'username': str(uname),
            'role': str(role.value),
            'real_name': str(real_name or ''),
            'phone': str(phone or ''),
            'department': str(dept or ''),
            'created_at': created_at,
            'last_login': last_login,
        }
        for uid, uname, role, real_name, phone, dept, created_at, last_login in rows
    ]


@app.get('/admin/stats/user_count')
def admin_user_count(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_engineer(user)
    cnt = db.execute(select(func.count(User.id))).scalar_one()
    return {'count': int(cnt or 0)}


@app.get('/engineer/users/{target_user_id}/detail', response_model=EngineerUserDetailOut)
def engineer_user_detail(
    target_user_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_engineer(user)
    u = db.execute(select(User).where(User.id == int(target_user_id))).scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail='user not found')

    return EngineerUserDetailOut(
        id=int(u.id),
        username=str(u.username),
        role=str(u.role.value),
        real_name=str(getattr(u, 'real_name', '') or ''),
        phone=str(getattr(u, 'phone', '') or ''),
        department=str(getattr(u, 'department', '') or ''),
        created_at=u.created_at,
        last_login=getattr(u, 'last_login', None),
        last_login_ip=str(getattr(u, 'last_login_ip', '') or ''),
        password_hash=str(getattr(u, 'password_hash', '') or ''),
    )


@app.get('/groups/requests/my')


def my_join_requests(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    rows = db.execute(
        select(JoinRequest, Group.name)
        .join(Group, Group.id == JoinRequest.group_id)
        .where(JoinRequest.user_id == user.id)
        .order_by(JoinRequest.requested_at.desc())
        .limit(50)
    ).all()
    return [
        {
            'id': req.id,
            'group_id': req.group_id,
            'group_name': group_name,
            'status': req.status.value,
            'requested_at': req.requested_at,
            'reviewed_at': req.reviewed_at,
        }
        for req, group_name in rows
    ]


@app.post('/groups/{group_id}/leave')
def leave_group(
    group_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    mem = db.execute(select(Membership).where(and_(Membership.group_id == group_id, Membership.user_id == user.id))).scalar_one_or_none()
    if not mem:
        raise HTTPException(status_code=404, detail='not in group')
    db.delete(mem)
    db.commit()
    return {'ok': True}


@app.get('/public/announcements/global/latest')
def public_latest_global_announcement(db: Annotated[Session, Depends(get_db)]):
    a = db.execute(
        select(Announcement)
        .where(Announcement.scope == AnnouncementScope.global_)
        .order_by(Announcement.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not a:
        return None
    return {
        'id': a.id,
        'title': a.title,
        'content': a.content,
        'created_at': a.created_at,
    }


@app.get('/public/config/version', response_model=VersionOut)
def public_get_version(db: Annotated[Session, Depends(get_db)]):
    return get_version(db)


# --- 团队成员离线聊天 ---


def _chat_cleanup_old(db: Session):
    # 聊天数据只保留约 1 个月
    try:
        cutoff = datetime.utcnow() - timedelta(days=31)
        db.execute(delete(ChatMessage).where(ChatMessage.created_at < cutoff))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


@app.post('/chat/send', response_model=ChatMessageOut)

def chat_send(
    data: ChatSendIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _chat_cleanup_old(db)

    target = _get_user_by_username(db, str(data.to_username))

    if not target:
        raise HTTPException(status_code=404, detail='user not found')
    if int(target.id) == int(user.id):
        raise HTTPException(status_code=400, detail='cannot send to self')

    # 必须同团队成员才能聊天
    if not _share_any_group(db, int(user.id), int(target.id)):
        raise HTTPException(status_code=403, detail='not in same group')

    msg = ChatMessage(sender_id=int(user.id), receiver_id=int(target.id), text=str(data.text or '').strip())
    db.add(msg)
    db.commit()
    db.refresh(msg)

    return ChatMessageOut(
        id=msg.id,
        from_username=user.username,
        to_username=target.username,
        text=msg.text,
        created_at=msg.created_at,
        read_at=msg.read_at,
    )


@app.get('/chat/history', response_model=list[ChatMessageOut])
def chat_history(
    peer: str = Query(..., description='对方用户名'),
    limit: int = Query(default=200, ge=1, le=400),
    db: Annotated[Session, Depends(get_db)] = None,
    user: Annotated[User, Depends(get_current_user)] = None,
):
    _chat_cleanup_old(db)

    peer_user = _get_user_by_username(db, str(peer))

    if not peer_user:
        raise HTTPException(status_code=404, detail='user not found')

    if not _share_any_group(db, int(user.id), int(peer_user.id)):
        raise HTTPException(status_code=403, detail='not in same group')

    # 双向会话：各自删除不互相影响
    q = select(ChatMessage).where(
        or_(
            and_(
                ChatMessage.sender_id == int(user.id),
                ChatMessage.receiver_id == int(peer_user.id),
                ChatMessage.deleted_by_sender == False,
            ),
            and_(
                ChatMessage.sender_id == int(peer_user.id),
                ChatMessage.receiver_id == int(user.id),
                ChatMessage.deleted_by_receiver == False,
            ),
        )
    )

    rows = db.execute(q.order_by(ChatMessage.created_at.asc()).limit(int(limit))).scalars().all()

    out: list[ChatMessageOut] = []
    for m in rows:
        out.append(
            ChatMessageOut(
                id=m.id,
                from_username=(peer_user.username if int(m.sender_id) == int(peer_user.id) else user.username),
                to_username=(peer_user.username if int(m.receiver_id) == int(peer_user.id) else user.username),
                text=m.text,
                created_at=m.created_at,
                read_at=m.read_at,
            )
        )
    return out


@app.get('/chat/unread_count', response_model=ChatUnreadOut)
def chat_unread_count(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _chat_cleanup_old(db)

    cnt = db.execute(

        select(func.count(ChatMessage.id)).where(
            and_(
                ChatMessage.receiver_id == int(user.id),
                ChatMessage.read_at.is_(None),
                ChatMessage.deleted_by_receiver == False,
            )
        )
    ).scalar_one()
    return ChatUnreadOut(count=int(cnt or 0))


@app.post('/chat/mark_read')
def chat_mark_read(
    data: ChatMarkReadIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _chat_cleanup_old(db)

    peer_user = _get_user_by_username(db, str(data.peer_username))

    if not peer_user:
        raise HTTPException(status_code=404, detail='user not found')

    if not _share_any_group(db, int(user.id), int(peer_user.id)):
        raise HTTPException(status_code=403, detail='not in same group')

    now = datetime.utcnow()
    rows = db.execute(
        select(ChatMessage).where(
            and_(
                ChatMessage.sender_id == int(peer_user.id),
                ChatMessage.receiver_id == int(user.id),
                ChatMessage.read_at.is_(None),
                ChatMessage.deleted_by_receiver == False,
            )
        )
    ).scalars().all()

    updated = 0
    for m in rows:
        m.read_at = now
        updated += 1

    if updated:
        db.commit()

    return {'updated': updated}


@app.delete('/chat/messages/{message_id}')
def chat_delete_message(
    message_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _chat_cleanup_old(db)

    msg = db.execute(select(ChatMessage).where(ChatMessage.id == int(message_id))).scalar_one_or_none()

    if not msg:
        raise HTTPException(status_code=404, detail='message not found')

    if int(msg.sender_id) == int(user.id):
        msg.deleted_by_sender = True
    elif int(msg.receiver_id) == int(user.id):
        msg.deleted_by_receiver = True
        # 删除时顺手标记已读，避免未读统计卡住
        if msg.read_at is None:
            msg.read_at = datetime.utcnow()
    else:
        raise HTTPException(status_code=403, detail='not allowed')

    # 两边都删除：物理删除
    if bool(msg.deleted_by_sender) and bool(msg.deleted_by_receiver):
        db.delete(msg)

    db.commit()
    return {'ok': True}


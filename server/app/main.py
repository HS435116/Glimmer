from __future__ import annotations

import os
import random
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import Session

from .db import Base, engine, get_db
from .models import (
    AdConfig,
    Announcement,
    AnnouncementScope,
    Attendance,
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
    CorrectionIn,
    CorrectionOut,
    GroupCreateIn,
    GroupOut,
    JoinRequestOut,
    LoginIn,
    PunchIn,
    PunchOut,
    RegisterIn,
    TokenOut,
    UserOut,
    VersionIn,
    VersionOut,
)
from .security import create_access_token, decode_token, hash_password, verify_password


app = FastAPI(title='Glimmer Attendance Server', version='0.1.0')

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/auth/login')


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
    if user.role == Role.engineer:
        return
    if user.role != Role.admin:
        raise HTTPException(status_code=403, detail='admin only')
    if not _is_group_admin(db, user.id, group_id):
        raise HTTPException(status_code=403, detail='not group admin')


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
    finally:
        db.close()


@app.get('/health')
def health():
    return {'ok': True}


@app.post('/auth/register', response_model=UserOut)
def register(data: RegisterIn, db: Annotated[Session, Depends(get_db)]):
    if _get_user_by_username(db, data.username):
        raise HTTPException(status_code=400, detail='username exists')
    user = User(username=data.username, password_hash=hash_password(data.password), role=Role.user)
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut(id=user.id, username=user.username, role=str(user.role.value))


@app.post('/auth/login', response_model=TokenOut)
def login(data: LoginIn, db: Annotated[Session, Depends(get_db)]):
    user = _get_user_by_username(db, data.username)
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail='bad credentials')
    token = create_access_token(user.username, extra={'role': user.role.value})
    return TokenOut(access_token=token)


@app.get('/me', response_model=UserOut)
def me(user: Annotated[User, Depends(get_current_user)]):
    return UserOut(id=user.id, username=user.username, role=str(user.role.value))


@app.post('/groups', response_model=GroupOut)
def create_group(
    data: GroupCreateIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_engineer(user)
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
    # 工程师：看全部 pending；管理员：只看自己管理的群
    q = select(JoinRequest, User.username, Group.name).join(User, User.id == JoinRequest.user_id).join(Group, Group.id == JoinRequest.group_id).where(JoinRequest.status == JoinStatus.pending)
    if user.role != Role.engineer:
        if user.role != Role.admin:
            raise HTTPException(status_code=403, detail='admin only')
        admin_group_ids = db.execute(
            select(Membership.group_id).where(and_(Membership.user_id == user.id, Membership.is_group_admin == True))
        ).scalars().all()
        if not admin_group_ids:
            return []
        q = q.where(JoinRequest.group_id.in_(admin_group_ids))

    rows = db.execute(q.order_by(JoinRequest.requested_at.asc())).all()
    out: list[JoinRequestOut] = []
    for req, username, group_name in rows:
        out.append(JoinRequestOut(
            id=req.id,
            user_id=req.user_id,
            username=username,
            group_id=req.group_id,
            group_name=group_name,
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
    _require_engineer(user)
    mem = db.execute(select(Membership).where(and_(Membership.group_id == group_id, Membership.user_id == member_user_id))).scalar_one_or_none()
    if not mem:
        raise HTTPException(status_code=404, detail='membership not found')

    mem.is_group_admin = bool(is_admin)

    target = db.execute(select(User).where(User.id == member_user_id)).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail='user not found')

    # 群管理员属于“管理员”等级（工程师除外）
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
    _require_engineer(user)
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
    _require_engineer(user)
    v = db.execute(select(VersionConfig).order_by(VersionConfig.id.asc())).scalar_one()
    v.latest_version = data.latest_version
    v.note = data.note
    v.updated_at = datetime.utcnow()
    v.updated_by_user_id = user.id
    db.commit()
    return VersionOut(latest_version=v.latest_version, note=v.note, updated_at=v.updated_at)


@app.get('/config/ads', response_model=AdOut)
def get_ads(db: Annotated[Session, Depends(get_db)]):
    a = db.execute(select(AdConfig).order_by(AdConfig.id.asc())).scalar_one()
    return AdOut(enabled=a.enabled, text=a.text, image_url=a.image_url, link_url=a.link_url, updated_at=a.updated_at)


@app.post('/config/ads', response_model=AdOut)
def set_ads(
    data: AdIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_engineer(user)
    a = db.execute(select(AdConfig).order_by(AdConfig.id.asc())).scalar_one()
    a.enabled = bool(data.enabled)
    a.text = data.text
    a.image_url = data.image_url
    a.link_url = data.link_url
    a.updated_at = datetime.utcnow()
    a.updated_by_user_id = user.id
    db.commit()
    return AdOut(enabled=a.enabled, text=a.text, image_url=a.image_url, link_url=a.link_url, updated_at=a.updated_at)


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


@app.get('/corrections/pending', response_model=list[CorrectionOut])
def pending_corrections(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    # 工程师：看全部 pending；管理员：只看自己管理的群
    q = select(CorrectionRequest, User.username).join(User, User.id == CorrectionRequest.user_id).where(CorrectionRequest.status == CorrectionStatus.pending)
    if user.role != Role.engineer:
        if user.role != Role.admin:
            raise HTTPException(status_code=403, detail='admin only')
        admin_group_ids = db.execute(
            select(Membership.group_id).where(and_(Membership.user_id == user.id, Membership.is_group_admin == True))
        ).scalars().all()
        if not admin_group_ids:
            return []
        q = q.where(CorrectionRequest.group_id.in_(admin_group_ids))

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

    # 审核通过：自动写一条“补录”打卡记录
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
    # 工程师：管理全部群；管理员：仅管理自己是群管理员的群
    if user.role == Role.engineer:
        rows = db.execute(select(Group).order_by(Group.id.desc()).limit(500)).scalars().all()
        return [GroupOut(id=g.id, name=g.name, group_code=g.group_code) for g in rows]

    if user.role != Role.admin:
        raise HTTPException(status_code=403, detail='admin only')

    rows = db.execute(
        select(Group)
        .join(Membership, Membership.group_id == Group.id)
        .where(and_(Membership.user_id == user.id, Membership.is_group_admin == True))
        .order_by(Group.id.desc())
        .limit(500)
    ).scalars().all()
    return [GroupOut(id=g.id, name=g.name, group_code=g.group_code) for g in rows]


@app.get('/admin/groups/{group_id}/members')
def list_group_members(
    group_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_group_admin(db, user, group_id)
    rows = db.execute(
        select(User.id, User.username, Membership.is_group_admin)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.group_id == group_id)
        .order_by(User.username.asc())
        .limit(500)
    ).all()
    return [{'user_id': uid, 'username': uname, 'is_group_admin': bool(is_admin)} for uid, uname, is_admin in rows]


@app.delete('/admin/groups/{group_id}/members/{member_user_id}')
def remove_group_member(
    group_id: int,
    member_user_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_group_admin(db, user, group_id)
    mem = db.execute(select(Membership).where(and_(Membership.group_id == group_id, Membership.user_id == member_user_id))).scalar_one_or_none()
    if not mem:
        raise HTTPException(status_code=404, detail='membership not found')
    db.delete(mem)
    db.commit()
    return {'ok': True}


@app.get('/admin/users')
def admin_users(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    q: str | None = Query(default=None),
):

    _require_engineer(user)
    stmt = select(User.id, User.username, User.role, User.created_at).order_by(User.id.desc()).limit(500)
    if q:
        stmt = stmt.where(User.username.like(f"%{q}%"))
    rows = db.execute(stmt).all()
    return [{'id': uid, 'username': uname, 'role': role.value, 'created_at': created_at} for uid, uname, role, created_at in rows]


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

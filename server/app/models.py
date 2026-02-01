from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Role(str, enum.Enum):
    user = 'user'
    admin = 'admin'
    engineer = 'engineer'


class JoinStatus(str, enum.Enum):
    pending = 'pending'
    approved = 'approved'
    rejected = 'rejected'


class CorrectionStatus(str, enum.Enum):
    pending = 'pending'
    approved = 'approved'
    rejected = 'rejected'


class AnnouncementScope(str, enum.Enum):
    global_ = 'global'
    group = 'group'


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.user, index=True)

    # 个人资料（服务器为准）
    real_name: Mapped[str | None] = mapped_column(String(120), default='')
    phone: Mapped[str | None] = mapped_column(String(40), default='')
    department: Mapped[str | None] = mapped_column(String(120), default='')

    # 密保（用于忘记密码找回）
    security_question: Mapped[str | None] = mapped_column(String(200), default='')
    security_answer_hash: Mapped[str | None] = mapped_column(String(255), default='')

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_ip: Mapped[str | None] = mapped_column(String(64), default='')

    memberships: Mapped[list[Membership]] = relationship('Membership', back_populates='user', cascade='all, delete-orphan')


class Group(Base):
    __tablename__ = 'groups'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    group_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'))

    memberships: Mapped[list[Membership]] = relationship('Membership', back_populates='group', cascade='all, delete-orphan')


class Membership(Base):
    __tablename__ = 'memberships'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), index=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey('groups.id'), index=True)
    is_group_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship('User', back_populates='memberships')
    group: Mapped[Group] = relationship('Group', back_populates='memberships')

    __table_args__ = (
        UniqueConstraint('user_id', 'group_id', name='uq_membership_user_group'),
    )


class JoinRequest(Base):
    __tablename__ = 'join_requests'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), index=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey('groups.id'), index=True)
    status: Mapped[JoinStatus] = mapped_column(Enum(JoinStatus), default=JoinStatus.pending, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)

    __table_args__ = (
        Index('ix_join_requests_group_status', 'group_id', 'status'),
        UniqueConstraint('user_id', 'group_id', 'status', name='uq_join_request_user_group_status'),
    )


class Announcement(Base):
    __tablename__ = 'announcements'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope: Mapped[AnnouncementScope] = mapped_column(Enum(AnnouncementScope), index=True)
    group_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('groups.id'), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(120))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    created_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'))


class VersionConfig(Base):
    __tablename__ = 'version_config'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    latest_version: Mapped[str] = mapped_column(String(32), default='1.0.0')
    note: Mapped[str] = mapped_column(Text, default='')
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)


class AdConfig(Base):
    __tablename__ = 'ad_config'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    text: Mapped[str] = mapped_column(String(200), default='')
    image_url: Mapped[str] = mapped_column(String(400), default='')
    link_url: Mapped[str] = mapped_column(String(400), default='')

    # 广告展示模式（与客户端一致）
    # - 垂直滚动：上下滚动
    # - 水平滚动：左右滚动
    # - 静止：不滚动
    scroll_mode: Mapped[str] = mapped_column(String(20), default='垂直滚动')

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)


class ChatMessage(Base):
    __tablename__ = 'chat_messages'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sender_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), index=True)
    receiver_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), index=True)

    text: Mapped[str] = mapped_column(String(1000), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # 仅接收方使用：是否已读
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    # 每个用户可以独立删除（软删除）
    deleted_by_sender: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_by_receiver: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index('ix_chat_receiver_read', 'receiver_id', 'read_at'),
    )


class Attendance(Base):
    __tablename__ = 'attendance'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), index=True)
    group_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('groups.id'), nullable=True, index=True)

    punched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    date: Mapped[str] = mapped_column(String(10), index=True)

    # 打卡类型：checkin / checkout（同日最多两次有效打卡：上班一次、下班一次）
    punch_type: Mapped[str] = mapped_column(String(16), default='', index=True)

    status: Mapped[str] = mapped_column(String(40), default='打卡成功')

    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(String(200), default='')


class CorrectionRequest(Base):
    __tablename__ = 'correction_requests'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), index=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey('groups.id'), index=True)

    date: Mapped[str] = mapped_column(String(10), index=True)
    reason: Mapped[str] = mapped_column(String(400), default='')
    status: Mapped[CorrectionStatus] = mapped_column(Enum(CorrectionStatus), default=CorrectionStatus.pending, index=True)

    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)

    __table_args__ = (
        Index('ix_corrections_group_status', 'group_id', 'status'),
    )

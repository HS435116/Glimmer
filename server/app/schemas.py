from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class TokenOut(BaseModel):
    access_token: str
    token_type: str = 'bearer'


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)

    # 个人资料
    real_name: str = Field(default='', max_length=120)
    phone: str = Field(default='', max_length=40)
    department: str = Field(default='', max_length=120)

    # 密保
    security_question: str = Field(default='', max_length=200)
    security_answer: str = Field(default='', max_length=200)


class LoginIn(BaseModel):
    username: str
    password: str


class ChangePasswordIn(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


class ResetPasswordIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    security_answer: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=6, max_length=128)


class SecurityQuestionOut(BaseModel):
    username: str
    security_question: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str


class UserProfileOut(BaseModel):
    id: int
    username: str
    role: str
    real_name: str = ''
    phone: str = ''
    department: str = ''
    created_at: datetime
    last_login: datetime | None = None
    security_question: str = ''


class EngineerUserDetailOut(BaseModel):
    id: int
    username: str
    role: str
    real_name: str = ''
    phone: str = ''
    department: str = ''
    created_at: datetime
    last_login: datetime | None = None
    last_login_ip: str = ''
    password_hash: str = ''


class EngineerWipeIn(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class GroupOut(BaseModel):
    id: int
    name: str
    group_code: str


class GroupCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ApplyJoinIn(BaseModel):
    group_code: str = Field(min_length=3, max_length=16)


class JoinRequestOut(BaseModel):
    id: int
    user_id: int
    username: str
    group_id: int
    group_name: str
    group_code: str = ''
    status: str
    requested_at: datetime


class GroupMemberOut(BaseModel):
    user_id: int
    username: str
    joined_at: datetime
    is_group_admin: bool = False


class AdminCorrectionIn(BaseModel):
    user_id: int
    group_id: int
    date: str = Field(min_length=10, max_length=10, description='YYYY-MM-DD')
    reason: str = Field(default='', max_length=400)


class AnnouncementCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=5000)


class AnnouncementOut(BaseModel):
    id: int
    scope: str
    group_id: int | None
    title: str
    content: str
    created_at: datetime


class VersionOut(BaseModel):
    latest_version: str
    note: str
    updated_at: datetime


class VersionIn(BaseModel):
    latest_version: str = Field(min_length=1, max_length=32)
    note: str = Field(default='', max_length=5000)


class AdOut(BaseModel):
    enabled: bool
    text: str
    image_url: str
    link_url: str
    scroll_mode: str
    updated_at: datetime


class AdIn(BaseModel):
    enabled: bool = True
    text: str = ''
    image_url: str = ''
    link_url: str = ''
    scroll_mode: str = '垂直滚动'


class ChatSendIn(BaseModel):
    to_username: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=1000)


class ChatMarkReadIn(BaseModel):
    peer_username: str = Field(min_length=1, max_length=64)


class ChatMessageOut(BaseModel):
    id: int
    from_username: str
    to_username: str
    text: str
    created_at: datetime
    read_at: datetime | None = None


class ChatUnreadOut(BaseModel):
    count: int


class PunchIn(BaseModel):
    group_id: int | None = None
    status: str = '打卡成功'
    lat: float | None = None
    lon: float | None = None
    notes: str = ''

    # 客户端时间（用于“打卡时间以手机实际时间为准”）
    # 允许传入 ISO 格式：2026-01-30T09:12:00 或 2026-01-30 09:12:00
    client_time: str | None = None


class PunchOut(BaseModel):
    id: int
    date: str
    punched_at: datetime
    status: str
    group_id: int | None
    lat: float | None
    lon: float | None
    notes: str


class CorrectionIn(BaseModel):
    group_id: int
    date: str = Field(min_length=10, max_length=10, description='YYYY-MM-DD')
    reason: str = Field(default='', max_length=400)


class CorrectionOut(BaseModel):
    id: int
    user_id: int
    username: str
    group_id: int
    date: str
    reason: str
    status: str
    requested_at: datetime

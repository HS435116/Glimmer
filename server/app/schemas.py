from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class TokenOut(BaseModel):
    access_token: str
    token_type: str = 'bearer'


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str


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
    status: str
    requested_at: datetime


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
    updated_at: datetime


class AdIn(BaseModel):
    enabled: bool = True
    text: str = ''
    image_url: str = ''
    link_url: str = ''


class PunchIn(BaseModel):
    group_id: int | None = None
    status: str = '打卡成功'
    lat: float | None = None
    lon: float | None = None
    notes: str = ''


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

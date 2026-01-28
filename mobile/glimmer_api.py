from __future__ import annotations

import json
from typing import Any

import requests


class GlimmerAPIError(Exception):
    pass


class GlimmerAPI:
    def __init__(self, base_url: str, timeout: float = 6.0):
        self.base_url = (base_url or '').strip().rstrip('/')
        self.timeout = float(timeout)

    def _url(self, path: str) -> str:
        path = (path or '').strip()
        if not path.startswith('/'):
            path = '/' + path
        return f"{self.base_url}{path}"

    def _headers(self, token: str | None = None) -> dict[str, str]:
        h: dict[str, str] = {'Accept': 'application/json'}
        if token:
            h['Authorization'] = f"Bearer {token}"
        return h

    def _raise(self, resp: requests.Response):
        try:
            data = resp.json()
            detail = data.get('detail') if isinstance(data, dict) else None
        except Exception:
            detail = None
        msg = detail or f"HTTP {resp.status_code}"
        raise GlimmerAPIError(msg)

    def health(self) -> bool:
        if not self.base_url:
            return False
        try:
            r = requests.get(self._url('/health'), timeout=self.timeout)
            return r.status_code == 200
        except Exception:
            return False

    def register(self, username: str, password: str) -> dict[str, Any]:
        r = requests.post(
            self._url('/auth/register'),
            json={'username': username, 'password': password},
            timeout=self.timeout,
            headers=self._headers(),
        )
        if r.status_code != 200:
            self._raise(r)
        return r.json()

    def login(self, username: str, password: str) -> str:
        r = requests.post(
            self._url('/auth/login'),
            json={'username': username, 'password': password},
            timeout=self.timeout,
            headers=self._headers(),
        )
        if r.status_code != 200:
            self._raise(r)
        data = r.json() or {}
        token = data.get('access_token')
        if not token:
            raise GlimmerAPIError('missing token')
        return str(token)

    def me(self, token: str) -> dict[str, Any]:
        r = requests.get(self._url('/me'), timeout=self.timeout, headers=self._headers(token))
        if r.status_code != 200:
            self._raise(r)
        return r.json()

    def my_groups(self, token: str) -> list[dict[str, Any]]:
        r = requests.get(self._url('/groups/my'), timeout=self.timeout, headers=self._headers(token))
        if r.status_code != 200:
            self._raise(r)
        return r.json() or []

    def apply_join(self, token: str, group_code: str) -> dict[str, Any]:
        r = requests.post(
            self._url('/groups/apply'),
            json={'group_code': group_code},
            timeout=self.timeout,
            headers=self._headers(token),
        )
        if r.status_code != 200:
            self._raise(r)
        return r.json() or {}

    def my_join_requests(self, token: str) -> list[dict[str, Any]]:
        r = requests.get(self._url('/groups/requests/my'), timeout=self.timeout, headers=self._headers(token))
        if r.status_code != 200:
            self._raise(r)
        return r.json() or []

    def leave_group(self, token: str, group_id: int) -> dict[str, Any]:
        r = requests.post(self._url(f'/groups/{int(group_id)}/leave'), timeout=self.timeout, headers=self._headers(token))
        if r.status_code != 200:
            self._raise(r)
        return r.json() or {}

    def public_latest_global_announcement(self) -> dict[str, Any] | None:
        r = requests.get(self._url('/public/announcements/global/latest'), timeout=self.timeout, headers=self._headers())
        if r.status_code != 200:
            self._raise(r)
        data = r.json()
        if data is None:
            return None
        return data

    def public_version(self) -> dict[str, Any]:
        r = requests.get(self._url('/public/config/version'), timeout=self.timeout, headers=self._headers())
        if r.status_code != 200:
            self._raise(r)
        return r.json() or {}

    def announcements_feed(self, token: str, since_iso: str | None = None) -> list[dict[str, Any]]:
        params = {}
        if since_iso:
            params['since'] = since_iso
        r = requests.get(self._url('/announcements/feed'), params=params, timeout=self.timeout, headers=self._headers(token))
        if r.status_code != 200:
            self._raise(r)
        return r.json() or []

    # 管理端能力（群管理员/工程师）
    def pending_join_requests(self, token: str) -> list[dict[str, Any]]:
        r = requests.get(self._url('/groups/requests/pending'), timeout=self.timeout, headers=self._headers(token))
        if r.status_code != 200:
            self._raise(r)
        return r.json() or []

    def approve_join(self, token: str, request_id: int) -> dict[str, Any]:
        r = requests.post(self._url(f'/groups/requests/{int(request_id)}/approve'), timeout=self.timeout, headers=self._headers(token))
        if r.status_code != 200:
            self._raise(r)
        return r.json() or {}

    def reject_join(self, token: str, request_id: int) -> dict[str, Any]:
        r = requests.post(self._url(f'/groups/requests/{int(request_id)}/reject'), timeout=self.timeout, headers=self._headers(token))
        if r.status_code != 200:
            self._raise(r)
        return r.json() or {}

    def pending_corrections(self, token: str) -> list[dict[str, Any]]:
        r = requests.get(self._url('/corrections/pending'), timeout=self.timeout, headers=self._headers(token))
        if r.status_code != 200:
            self._raise(r)
        return r.json() or []

    def approve_correction(self, token: str, request_id: int) -> dict[str, Any]:
        r = requests.post(self._url(f'/corrections/{int(request_id)}/approve'), timeout=self.timeout, headers=self._headers(token))
        if r.status_code != 200:
            self._raise(r)
        return r.json() or {}

    def reject_correction(self, token: str, request_id: int) -> dict[str, Any]:
        r = requests.post(self._url(f'/corrections/{int(request_id)}/reject'), timeout=self.timeout, headers=self._headers(token))
        if r.status_code != 200:
            self._raise(r)
        return r.json() or {}

    def post_global_announcement(self, token: str, title: str, content: str) -> dict[str, Any]:
        r = requests.post(
            self._url('/announcements/global'),
            json={'title': title, 'content': content},
            timeout=self.timeout,
            headers=self._headers(token),
        )
        if r.status_code != 200:
            self._raise(r)
        return r.json() or {}

    def post_group_announcement(self, token: str, group_id: int, title: str, content: str) -> dict[str, Any]:
        r = requests.post(
            self._url(f'/announcements/group/{int(group_id)}'),
            json={'title': title, 'content': content},
            timeout=self.timeout,
            headers=self._headers(token),
        )
        if r.status_code != 200:
            self._raise(r)
        return r.json() or {}

    def get_version(self) -> dict[str, Any]:
        r = requests.get(self._url('/config/version'), timeout=self.timeout, headers=self._headers())
        if r.status_code != 200:
            self._raise(r)
        return r.json() or {}

    def set_version(self, token: str, latest_version: str, note: str) -> dict[str, Any]:
        r = requests.post(
            self._url('/config/version'),
            json={'latest_version': latest_version, 'note': note},
            timeout=self.timeout,
            headers=self._headers(token),
        )
        if r.status_code != 200:
            self._raise(r)
        return r.json() or {}

    def get_ads(self) -> dict[str, Any]:
        r = requests.get(self._url('/config/ads'), timeout=self.timeout, headers=self._headers())
        if r.status_code != 200:
            self._raise(r)
        return r.json() or {}

    def set_ads(self, token: str, enabled: bool, text: str, image_url: str, link_url: str) -> dict[str, Any]:
        r = requests.post(
            self._url('/config/ads'),
            json={'enabled': bool(enabled), 'text': text, 'image_url': image_url, 'link_url': link_url},
            timeout=self.timeout,
            headers=self._headers(token),
        )
        if r.status_code != 200:
            self._raise(r)
        return r.json() or {}

    def create_group(self, token: str, name: str) -> dict[str, Any]:
        r = requests.post(
            self._url('/groups'),
            json={'name': name},
            timeout=self.timeout,
            headers=self._headers(token),
        )
        if r.status_code != 200:
            self._raise(r)
        return r.json() or {}

    def request_correction(self, token: str, group_id: int, date: str, reason: str = '') -> dict[str, Any]:
        r = requests.post(
            self._url('/corrections/request'),
            json={'group_id': int(group_id), 'date': str(date), 'reason': str(reason or '')},
            timeout=self.timeout,
            headers=self._headers(token),
        )
        if r.status_code != 200:
            self._raise(r)
        return r.json() or {}

    def managed_groups(self, token: str) -> list[dict[str, Any]]:
        r = requests.get(self._url('/admin/groups/managed'), timeout=self.timeout, headers=self._headers(token))
        if r.status_code != 200:
            self._raise(r)
        return r.json() or []

    def list_group_members(self, token: str, group_id: int) -> list[dict[str, Any]]:
        r = requests.get(self._url(f'/admin/groups/{int(group_id)}/members'), timeout=self.timeout, headers=self._headers(token))
        if r.status_code != 200:
            self._raise(r)
        return r.json() or []

    def remove_group_member(self, token: str, group_id: int, member_user_id: int) -> dict[str, Any]:
        r = requests.delete(
            self._url(f'/admin/groups/{int(group_id)}/members/{int(member_user_id)}'),
            timeout=self.timeout,
            headers=self._headers(token),
        )
        if r.status_code != 200:
            self._raise(r)
        return r.json() or {}

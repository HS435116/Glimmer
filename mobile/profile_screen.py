from __future__ import annotations

import os
from threading import Thread
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.storage.jsonstore import JsonStore
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.textinput import TextInput
from kivy.graphics import Color, Rectangle

from glimmer_api import GlimmerAPI
from main import db, get_server_url


class ProfileScreen(Screen):
    """个人资料页（本地档案）"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(0.0667, 0.149, 0.3098, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        root = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(12))

        top = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        title = Label(text='个人资料', color=(1, 1, 1, 1), halign='left', valign='middle', shorten=True, shorten_from='right')
        title.bind(size=lambda i, v: setattr(i, 'text_size', v))

        clear_btn = Button(text='清理缓存', size_hint=(None, 1), width=dp(90), background_color=(0.85, 0.45, 0.1, 1))
        clear_btn.bind(on_press=lambda *_: self.clear_cache())

        back_btn = Button(text='返回', size_hint=(None, 1), width=dp(72), background_color=(0.6, 0.6, 0.6, 1))
        back_btn.bind(on_press=lambda *_: self.go_back())

        right_box = BoxLayout(size_hint=(None, 1), width=dp(170), spacing=dp(6))
        right_box.add_widget(clear_btn)
        right_box.add_widget(back_btn)

        top.add_widget(title)
        top.add_widget(right_box)
        root.add_widget(top)

        self.info = BoxLayout(orientation='vertical', spacing=dp(8), size_hint=(1, 1))
        root.add_widget(self.info)

        self.add_widget(root)

    def _update_bg(self, *_):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def on_enter(self, *args):
        app = App.get_running_app()
        try:
            prev = str(getattr(self.manager, 'previous', '') or '')
        except Exception:
            prev = ''
        if prev and prev != 'profile':
            app.profile_back_to = prev
        if not getattr(app, 'profile_back_to', None):
            app.profile_back_to = 'main'

        # 先用本地缓存渲染，再异步从服务器同步
        self.render()
        self._sync_profile_from_server()

    def go_back(self):
        # 返回打卡页面（离开即清理页面状态，效果与其它页面一致）
        try:
            self.info.clear_widgets()
        except Exception:
            pass

        try:
            self.manager.current = 'main'
        except Exception:
            pass

    def _popup(self, title: str, msg: str):
        text = str(msg or '')
        align = 'left' if ('\n' in text or len(text) > 18) else 'center'
        valign = 'top' if align == 'left' else 'middle'

        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(18))
        label = Label(text=text, color=(1, 1, 1, 1), halign=align, valign=valign)
        label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
        content.add_widget(label)

        p = Popup(
            title=str(title or ''),
            content=content,
            size_hint=(0.88, 0.45),
            background_color=(0.0667, 0.149, 0.3098, 1),
            background='',
        )
        p.open()

    def _server_ctx(self):
        app = App.get_running_app()
        token = str(getattr(app, 'api_token', '') or '')
        base_url = str(getattr(app, 'server_url', '') or get_server_url() or '').strip()
        if not token or not base_url:
            return None, None
        return GlimmerAPI(base_url), token

    def _sync_profile_from_server(self):
        app = App.get_running_app()
        username = str(getattr(app, 'current_user', '') or '')
        api, token = self._server_ctx()
        if not username or not api or not token:
            return

        def work():
            try:
                if not api.health():
                    return
                me = api.me(token) or {}
                cache = {
                    'username': str(me.get('username') or username),
                    'user_id': str(me.get('id') or ''),
                    'real_name': str(me.get('real_name') or ''),
                    'phone': str(me.get('phone') or ''),
                    'department': str(me.get('department') or ''),
                    'created_at': str(me.get('created_at') or ''),
                    'last_login': str(me.get('last_login') or ''),
                    'security_question': str(me.get('security_question') or ''),
                    'synced_at': datetime.now().isoformat(),
                }
                s = db.get_user_settings(username) or {}
                s['profile_cache'] = cache
                db.save_user_settings(username, s)
                Clock.schedule_once(lambda *_: self.render(), 0)
            except Exception:
                return

        Thread(target=work, daemon=True).start()

    def _open_change_password_popup(self):
        api, token = self._server_ctx()
        if not api or not token:
            self._popup('提示', '需要登录服务器后才能修改密码')
            return

        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(16))
        old_in = TextInput(hint_text='旧密码', password=True, multiline=False, size_hint=(1, None), height=dp(44))
        new_in = TextInput(hint_text='新密码（至少6位）', password=True, multiline=False, size_hint=(1, None), height=dp(44))
        new2_in = TextInput(hint_text='确认新密码', password=True, multiline=False, size_hint=(1, None), height=dp(44))
        content.add_widget(old_in)
        content.add_widget(new_in)
        content.add_widget(new2_in)

        btn_row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        ok_btn = Button(text='确认', background_color=(0.2, 0.6, 0.8, 1))
        cancel_btn = Button(text='取消', background_color=(0.6, 0.6, 0.6, 1))
        btn_row.add_widget(ok_btn)
        btn_row.add_widget(cancel_btn)
        content.add_widget(btn_row)

        popup = Popup(title='修改密码', content=content, size_hint=(0.9, 0.55), background_color=(0.0667, 0.149, 0.3098, 1), background='')
        cancel_btn.bind(on_press=lambda *_: popup.dismiss())

        def submit(*_):
            old_pwd = (old_in.text or '').strip()
            new_pwd = (new_in.text or '').strip()
            new2_pwd = (new2_in.text or '').strip()
            if not old_pwd or not new_pwd:
                self._popup('提示', '请输入旧密码和新密码')
                return
            if len(new_pwd) < 6:
                self._popup('提示', '新密码长度至少6位')
                return
            if new_pwd != new2_pwd:
                self._popup('提示', '两次输入的新密码不一致')
                return

            def work():
                try:
                    if not api.health():
                        raise RuntimeError('服务器不可用')
                    api.change_password(token, old_pwd, new_pwd)
                    Clock.schedule_once(lambda *_: (popup.dismiss(), self._popup('成功', '密码已修改')), 0)
                except Exception as e:
                    Clock.schedule_once(lambda *_, msg=str(e): self._popup('修改失败', msg), 0)

            Thread(target=work, daemon=True).start()

        ok_btn.bind(on_press=submit)
        popup.open()

    def _open_reset_password_popup(self):
        app = App.get_running_app()
        username = str(getattr(app, 'current_user', '') or '')
        base_url = str(getattr(app, 'server_url', '') or get_server_url() or '').strip()
        if not username:
            self._popup('提示', '未登录')
            return

        # 未配置服务器时允许手工输入
        api = GlimmerAPI(base_url) if base_url else None

        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(16))

        server_in = TextInput(hint_text='服务器地址（例如 http://1.2.3.4:8000）', multiline=False, size_hint=(1, None), height=dp(44), text=base_url)
        q_label = Label(text='密保问题：加载中...', color=(0.95, 0.97, 1, 1), halign='left', valign='middle', size_hint=(1, None), height=dp(32))
        q_label.bind(size=lambda i, v: setattr(i, 'text_size', v))
        ans_in = TextInput(hint_text='密保答案', password=False, multiline=False, size_hint=(1, None), height=dp(44))
        new_in = TextInput(hint_text='新密码（至少6位）', password=True, multiline=False, size_hint=(1, None), height=dp(44))
        new2_in = TextInput(hint_text='确认新密码', password=True, multiline=False, size_hint=(1, None), height=dp(44))

        content.add_widget(server_in)
        content.add_widget(q_label)
        content.add_widget(ans_in)
        content.add_widget(new_in)
        content.add_widget(new2_in)

        btn_row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        ok_btn = Button(text='确认找回', background_color=(0.2, 0.6, 0.8, 1))
        cancel_btn = Button(text='取消', background_color=(0.6, 0.6, 0.6, 1))
        btn_row.add_widget(ok_btn)
        btn_row.add_widget(cancel_btn)
        content.add_widget(btn_row)

        popup = Popup(title='忘记密码', content=content, size_hint=(0.9, 0.62), background_color=(0.0667, 0.149, 0.3098, 1), background='')
        cancel_btn.bind(on_press=lambda *_: popup.dismiss())

        def load_question():
            def work():
                try:
                    url = (server_in.text or '').strip().rstrip('/')
                    if not url:
                        raise RuntimeError('请输入服务器地址')
                    api2 = GlimmerAPI(url)
                    if not api2.health():
                        raise RuntimeError('服务器不在线')
                    data = api2.security_question(username)
                    q = str(data.get('security_question') or '')
                    Clock.schedule_once(lambda *_: setattr(q_label, 'text', f"密保问题：{q}" if q else '密保问题：未设置'), 0)
                except Exception as e:
                    Clock.schedule_once(lambda *_, msg=str(e): setattr(q_label, 'text', f"密保问题：加载失败（{msg}）"), 0)

            Thread(target=work, daemon=True).start()

        def submit(*_):
            ans = (ans_in.text or '').strip()
            new_pwd = (new_in.text or '').strip()
            new2_pwd = (new2_in.text or '').strip()
            if not ans or not new_pwd:
                self._popup('提示', '请输入答案和新密码')
                return
            if len(new_pwd) < 6:
                self._popup('提示', '新密码长度至少6位')
                return
            if new_pwd != new2_pwd:
                self._popup('提示', '两次输入的新密码不一致')
                return

            def work():
                try:
                    url = (server_in.text or '').strip().rstrip('/')
                    if not url:
                        raise RuntimeError('请输入服务器地址')
                    api2 = GlimmerAPI(url)
                    if not api2.health():
                        raise RuntimeError('服务器不在线')
                    api2.reset_password(username, ans, new_pwd)
                    Clock.schedule_once(lambda *_: (popup.dismiss(), self._popup('成功', '密码已重置，请用新密码重新登录')), 0)
                except Exception as e:
                    Clock.schedule_once(lambda *_, msg=str(e): self._popup('找回失败', msg), 0)

            Thread(target=work, daemon=True).start()

        ok_btn.bind(on_press=submit)
        popup.open()
        load_question()

    def render(self):
        self.info.clear_widgets()
        app = App.get_running_app()
        username = str(getattr(app, 'current_user', '') or '')
        if not username:
            self.info.add_widget(Label(text='（未登录）', color=(0.9, 0.95, 1, 1)))
            return

        s = db.get_user_settings(username) or {}
        prof = (s.get('profile_cache') or {}) if isinstance(s, dict) else {}

        # 兼容离线本地模式
        if not prof:
            prof = db.get_user_profile(username) or {}

        lines = [
            f"用户名：{prof.get('username') or username}",
            f"用户ID：{prof.get('user_id') or '未知'}",
            f"姓名：{prof.get('real_name') or '未填写'}",
            f"手机号：{prof.get('phone') or '未填写'}",
            f"部门/岗位：{prof.get('department') or '未填写'}",
            f"创建时间：{str(prof.get('created_at') or '')[:19]}",
            f"上次登录：{str(prof.get('last_login') or '')[:19]}",
        ]

        for t in lines:
            lb = Label(text=t, color=(0.95, 0.97, 1, 1), halign='left', valign='middle', shorten=True, shorten_from='right', size_hint=(1, None), height=dp(28))
            lb.bind(size=lambda i, v: setattr(i, 'text_size', v))
            self.info.add_widget(lb)

        # 密码修改/找回
        pwd_row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        change_btn = Button(text='修改密码', background_color=(0.2, 0.6, 0.8, 1))
        forget_btn = Button(text='忘记密码', background_color=(0.18, 0.62, 0.38, 1))
        change_btn.bind(on_press=lambda *_: self._open_change_password_popup())
        forget_btn.bind(on_press=lambda *_: self._open_reset_password_popup())
        pwd_row.add_widget(change_btn)
        pwd_row.add_widget(forget_btn)
        self.info.add_widget(pwd_row)

        synced_at = str(prof.get('synced_at') or '')
        hint_text = f"资料缓存同步：{synced_at[:19]}" if synced_at else '说明：个人资料以服务器为准，本机仅做缓存。'
        hint = Label(text=hint_text, color=(0.85, 0.9, 1, 1), halign='left', valign='middle', size_hint=(1, None), height=dp(26))
        hint.bind(size=lambda i, v: setattr(i, 'text_size', v))
        self.info.add_widget(hint)

    def clear_cache(self):
        app = App.get_running_app()
        username = str(getattr(app, 'current_user', '') or '')

        # 清理本机个人资料缓存（聊天不再保存本地）
        try:
            if username:
                s = db.get_user_settings(username) or {}
                if 'profile_cache' in s:
                    s.pop('profile_cache', None)
                    db.save_user_settings(username, s)
        except Exception:
            pass

        self.render()

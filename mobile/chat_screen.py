from __future__ import annotations

from threading import Thread
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.graphics import Color, Rectangle

from glimmer_api import GlimmerAPI
from main import db, get_server_url


class ChatScreen(Screen):
    """团队成员单聊（仅通过服务器中转）。"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(0.0667, 0.149, 0.3098, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        root = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(10))

        top = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        self.title_label = Label(text='聊天', color=(1, 1, 1, 1), halign='left', valign='middle', shorten=True, shorten_from='right')
        self.title_label.bind(size=lambda i, v: setattr(i, 'text_size', v))

        back_btn = Button(text='返回', size_hint=(None, 1), width=dp(72), background_color=(0.6, 0.6, 0.6, 1))
        back_btn.bind(on_press=lambda *_: self.go_back())

        top.add_widget(self.title_label)
        top.add_widget(back_btn)
        root.add_widget(top)

        self.scroll = ScrollView(size_hint=(1, 1), bar_width=dp(2))
        self.msg_list = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        self.msg_list.bind(minimum_height=self.msg_list.setter('height'))
        self.scroll.add_widget(self.msg_list)
        root.add_widget(self.scroll)

        bottom = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        self.input = TextInput(hint_text='输入消息...', multiline=False)
        self.send_btn = Button(text='发送', size_hint=(None, 1), width=dp(72), background_color=(0.2, 0.6, 0.8, 1))
        self.send_btn.bind(on_press=lambda *_: self.send())
        bottom.add_widget(self.input)
        bottom.add_widget(self.send_btn)
        root.add_widget(bottom)

        self.add_widget(root)

        self._me = ''
        self._peer = ''
        self._messages: list[dict] = []
        self._server_ok = False
        self._inflight = False

    def _update_bg(self, *_):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

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
            size_hint=(0.85, 0.45),
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

    def _set_chat_enabled(self, enabled: bool, reason: str = ''):
        self._server_ok = bool(enabled)
        try:
            self.input.disabled = (not enabled)
            self.send_btn.disabled = (not enabled)
            if not enabled:
                self.input.hint_text = reason or '服务器不在线，聊天不可用'
            else:
                self.input.hint_text = '输入消息...'
        except Exception:
            pass

    def on_enter(self, *args):
        app = App.get_running_app()
        self._me = str(getattr(app, 'current_user', '') or '')
        peer = getattr(app, 'chat_peer', {}) or {}
        self._peer = str(peer.get('username') or '')
        self.title_label.text = f"与 {self._peer} 聊天" if self._peer else '聊天'

        self._messages = []
        self._reload()

        # 默认禁用输入，检测服务器后再启用
        self._set_chat_enabled(False, '正在连接服务器...')
        self._check_server_and_load()

        # 进入聊天页视为已查看：清除公告提醒的聊天提示
        try:
            if self._me:
                settings = db.get_user_settings(self._me) or {}
                settings['chat_notice_count'] = 0
                settings['chat_notice_text'] = ''
                settings['chat_notice_time'] = ''
                db.save_user_settings(self._me, settings)
        except Exception:
            pass

    def on_leave(self, *args):
        # 离开即清理（近似销毁）
        try:
            self.msg_list.clear_widgets()
        except Exception:
            pass
        try:
            self.input.text = ''
        except Exception:
            pass
        self._messages = []
        self._peer = ''
        self._set_chat_enabled(False, '')

    def go_back(self):
        # 返回打卡页面（离开即清理）
        try:
            self.on_leave()
        except Exception:
            pass
        try:
            app = App.get_running_app()
            if hasattr(app, 'chat_peer'):
                app.chat_peer = {}
        except Exception:
            pass
        try:
            self.manager.current = 'main'
        except Exception:
            pass

    def _check_server_and_load(self):
        if getattr(self, '_inflight', False):
            return
        self._inflight = True

        api, token = self._server_ctx()
        if not api or not token:
            self._set_chat_enabled(False, '未登录服务器，聊天不可用')
            self._inflight = False
            self._reload()
            return

        def work():
            try:
                if not api.health():
                    raise RuntimeError('服务器不在线')

                if not self._peer:
                    Clock.schedule_once(lambda *_: (self._set_chat_enabled(True, ''), self._reload()), 0)
                    return

                items = api.chat_history(token, self._peer, limit=200)
                msgs = []
                for it in (items or []):
                    ts = str(it.get('created_at') or '')
                    if ts and 'T' in ts:
                        ts = ts[:19].replace('T', ' ')
                    msgs.append(
                        {
                            'id': int(it.get('id')),
                            'from': str(it.get('from_username') or ''),
                            'to': str(it.get('to_username') or ''),
                            'text': str(it.get('text') or ''),
                            'ts': ts,
                        }
                    )

                # 标记已读
                try:
                    api.chat_mark_read(token, self._peer)
                except Exception:
                    pass

                def ui():
                    self._messages = msgs
                    self._set_chat_enabled(True, '')
                    self._reload()

                Clock.schedule_once(lambda *_: ui(), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_, msg=str(e): (self._set_chat_enabled(False, f'服务器不在线，聊天不可用（{msg}）'), self._reload(), self._popup('提示', '服务器不在线，禁止使用聊天')), 0)
            finally:
                self._inflight = False

        Thread(target=work, daemon=True).start()

    def _reload(self):
        self.msg_list.clear_widgets()

        if not self._peer:
            self.msg_list.add_widget(Label(text='（未选择聊天对象）', size_hint_y=None, height=dp(26), color=(0.9, 0.95, 1, 1)))
            return

        if not self._server_ok:
            self.msg_list.add_widget(Label(text='服务器不在线，聊天不可用', size_hint_y=None, height=dp(26), color=(0.9, 0.95, 1, 1)))
            return

        if not self._messages:
            self.msg_list.add_widget(Label(text='（暂无消息）', size_hint_y=None, height=dp(26), color=(0.9, 0.95, 1, 1)))
            return

        for idx, m in enumerate(list(self._messages)):
            who = str(m.get('from') or '')
            txt = str(m.get('text') or '')
            ts = str(m.get('ts') or '')

            bubble = BoxLayout(size_hint_y=None, height=dp(34), padding=[dp(6), 0], spacing=dp(6))
            align = 'right' if who == self._me else 'left'

            label = Label(
                text=f"{who}: {txt}" if who else txt,
                color=(1, 1, 1, 1),
                halign=align,
                valign='middle',
                shorten=True,
                shorten_from='right',
            )
            label.bind(size=lambda i, v: setattr(i, 'text_size', v))

            time_label = Label(
                text=ts[11:16] if len(ts) >= 16 else ts,
                size_hint=(None, 1),
                width=dp(46),
                color=(0.8, 0.86, 0.95, 1),
                halign='right',
                valign='middle',
            )
            time_label.bind(size=lambda i, v: setattr(i, 'text_size', v))

            del_btn = Button(text='删', size_hint=(None, 1), width=dp(40), background_color=(0.8, 0.2, 0.2, 1))
            del_btn.bind(on_press=lambda *_btn, _i=idx: self._confirm_delete(int(_i)))

            if align == 'right':
                bubble.add_widget(time_label)
                bubble.add_widget(label)
            else:
                bubble.add_widget(label)
                bubble.add_widget(time_label)

            bubble.add_widget(del_btn)
            self.msg_list.add_widget(bubble)

        Clock.schedule_once(lambda *_: setattr(self.scroll, 'scroll_y', 0), 0)

    def _confirm_delete(self, index: int):
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(18))
        content.add_widget(Label(text='确认删除这条消息？', color=(1, 1, 1, 1)))
        btn_row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        ok_btn = Button(text='确认', background_color=(0.8, 0.2, 0.2, 1))
        cancel_btn = Button(text='取消', background_color=(0.6, 0.6, 0.6, 1))
        btn_row.add_widget(ok_btn)
        btn_row.add_widget(cancel_btn)
        content.add_widget(btn_row)

        popup = Popup(title='删除确认', content=content, size_hint=(0.85, 0.35), background_color=(0.0667, 0.149, 0.3098, 1), background='')
        cancel_btn.bind(on_press=lambda *_: popup.dismiss())
        ok_btn.bind(on_press=lambda *_: (popup.dismiss(), self._delete_message(index)))
        popup.open()

    def _delete_message(self, index: int):
        if index < 0 or index >= len(self._messages):
            return
        msg = self._messages[index] or {}
        mid = msg.get('id')
        if not mid:
            return

        api, token = self._server_ctx()
        if not api or not token:
            self._popup('提示', '未登录服务器')
            return

        def work():
            try:
                if not api.health():
                    raise RuntimeError('服务器不在线')
                api.chat_delete_message(token, int(mid))
                Clock.schedule_once(lambda *_: self._check_server_and_load(), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_, msg=str(e): self._popup('删除失败', msg), 0)

        Thread(target=work, daemon=True).start()

    def send(self):
        if not self._server_ok:
            self._popup('提示', '服务器不在线，禁止聊天')
            return

        text = (self.input.text or '').strip()
        if not text or not self._peer:
            return

        api, token = self._server_ctx()
        if not api or not token:
            self._popup('提示', '未登录服务器，聊天不可用')
            self._set_chat_enabled(False, '未登录服务器，聊天不可用')
            return

        self.send_btn.disabled = True
        self.input.text = ''

        def work():
            try:
                if not api.health():
                    raise RuntimeError('服务器不在线')
                api.chat_send(token, self._peer, text)
                Clock.schedule_once(lambda *_: self._check_server_and_load(), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_, msg=str(e): self._popup('发送失败', msg), 0)
            finally:
                Clock.schedule_once(lambda *_: setattr(self.send_btn, 'disabled', False), 0)

        Thread(target=work, daemon=True).start()

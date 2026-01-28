from __future__ import annotations

from threading import Thread

from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.metrics import dp

from glimmer_api import GlimmerAPI, GlimmerAPIError


class GroupScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(12))

        title = Label(text='群管理', font_size=dp(18), bold=True, size_hint=(1, None), height=dp(34), color=(1, 1, 1, 1))
        root.add_widget(title)

        row = BoxLayout(size_hint=(1, None), height=dp(42), spacing=dp(8))
        self.code_input = TextInput(hint_text='输入群ID（6位）', multiline=False)
        apply_btn = Button(text='申请进群', size_hint=(None, 1), width=dp(90))
        apply_btn.bind(on_press=self.apply_join)
        row.add_widget(self.code_input)
        row.add_widget(apply_btn)
        root.add_widget(row)

        btn_row = BoxLayout(size_hint=(1, None), height=dp(42), spacing=dp(8))
        refresh_btn = Button(text='刷新', size_hint=(0.35, 1))
        refresh_btn.bind(on_press=lambda *_: self.refresh())
        back_btn = Button(text='返回', size_hint=(0.35, 1))
        back_btn.bind(on_press=lambda *_: self.go_back())
        btn_row.add_widget(refresh_btn)
        btn_row.add_widget(back_btn)
        root.add_widget(btn_row)

        self.info_label = Label(text='', font_size=dp(12), color=(0.9, 0.95, 1, 1), size_hint=(1, None), height=dp(20))
        root.add_widget(self.info_label)

        # 列表
        scroll = ScrollView(size_hint=(1, 1))
        self.list_layout = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter('height'))
        scroll.add_widget(self.list_layout)
        root.add_widget(scroll)

        self.add_widget(root)

    def _get_api(self) -> GlimmerAPI:
        app = App.get_running_app()
        base_url = getattr(app, 'server_url', '') or ''
        return GlimmerAPI(base_url)

    def _get_token(self) -> str:
        app = App.get_running_app()
        token = getattr(app, 'api_token', '') or ''
        if not token:
            raise GlimmerAPIError('未登录/无Token')
        return token

    def on_enter(self, *args):
        Clock.schedule_once(lambda *_: self.refresh(), 0)

    def show_popup(self, title: str, message: str):
        popup = Popup(title=title, content=Label(text=message), size_hint=(0.85, 0.45), background='')
        popup.open()

    def go_back(self):
        try:
            self.manager.current = 'main'
        except Exception:
            pass

    def apply_join(self, *_):
        code = (self.code_input.text or '').strip()
        if not code:
            self.show_popup('提示', '请输入群ID')
            return

        def work():
            try:
                token = self._get_token()
                api = self._get_api()
                resp = api.apply_join(token, code)
                msg = resp.get('detail') or '已提交申请'
                Clock.schedule_once(lambda *_: (self.show_popup('申请进群', msg), self.refresh()), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_: self.show_popup('错误', str(e)), 0)

        Thread(target=work, daemon=True).start()

    def refresh(self, *_):
        self.info_label.text = '正在刷新...'
        self.list_layout.clear_widgets()

        def work():
            try:
                token = self._get_token()
                api = self._get_api()
                groups = api.my_groups(token)
                reqs = api.my_join_requests(token)

                def ui():
                    self.list_layout.clear_widgets()

                    self.list_layout.add_widget(Label(text='我加入的群：', size_hint_y=None, height=dp(26), color=(1, 1, 1, 1)))
                    if not groups:
                        self.list_layout.add_widget(Label(text='（暂无）', size_hint_y=None, height=dp(22), color=(0.85, 0.9, 1, 1)))
                    for g in groups:
                        gid = g.get('id')
                        name = g.get('name')
                        code = g.get('group_code')
                        row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
                        row.add_widget(Label(text=f"{name}（ID:{code}）", color=(0.9, 0.95, 1, 1)))
                        leave_btn = Button(text='退群', size_hint=(None, 1), width=dp(70))
                        leave_btn.bind(on_press=lambda _btn, _gid=gid: self.leave_group(_gid))
                        row.add_widget(leave_btn)
                        self.list_layout.add_widget(row)

                    self.list_layout.add_widget(Label(text='入群申请记录：', size_hint_y=None, height=dp(26), color=(1, 1, 1, 1)))
                    if not reqs:
                        self.list_layout.add_widget(Label(text='（暂无）', size_hint_y=None, height=dp(22), color=(0.85, 0.9, 1, 1)))
                    for r in reqs:
                        self.list_layout.add_widget(Label(
                            text=f"{r.get('group_name')} - {r.get('status')} - {str(r.get('requested_at') or '')[:19]}",
                            size_hint_y=None,
                            height=dp(22),
                            color=(0.85, 0.9, 1, 1),
                        ))

                    self.info_label.text = '刷新完成'

                Clock.schedule_once(lambda *_: ui(), 0)
            except Exception as e:
                err = str(e)
                Clock.schedule_once(lambda *_: (setattr(self.info_label, 'text', '刷新失败'), self.show_popup('错误', err)), 0)

        Thread(target=work, daemon=True).start()

    def leave_group(self, group_id: int):
        def work():
            try:
                token = self._get_token()
                api = self._get_api()
                api.leave_group(token, int(group_id))
                Clock.schedule_once(lambda *_: (self.show_popup('提示', '已退群'), self.refresh()), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_: self.show_popup('错误', str(e)), 0)

        Thread(target=work, daemon=True).start()

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

        title = Label(text='团队管理', font_size=dp(18), bold=True, size_hint=(1, None), height=dp(34), color=(1, 1, 1, 1))

        root.add_widget(title)

        row = BoxLayout(size_hint=(1, None), height=dp(42), spacing=dp(8))
        self.code_input = TextInput(hint_text='输入团队ID（6位）', multiline=False)

        apply_btn = Button(text='申请加入', size_hint=(None, 1), width=dp(90))

        apply_btn.bind(on_press=self.apply_join)
        row.add_widget(self.code_input)
        row.add_widget(apply_btn)
        root.add_widget(row)

        btn_row = BoxLayout(size_hint=(1, None), height=dp(42), spacing=dp(8))
        refresh_btn = Button(text='刷新', size_hint=(0.33, 1))
        refresh_btn.bind(on_press=lambda *_: self.refresh())
        back_btn = Button(text='返回', size_hint=(0.33, 1))
        back_btn.bind(on_press=lambda *_: self.go_back())
        logout_btn = Button(text='退出', size_hint=(0.33, 1))
        logout_btn.bind(on_press=lambda *_: self.logout())
        btn_row.add_widget(refresh_btn)
        btn_row.add_widget(back_btn)
        btn_row.add_widget(logout_btn)
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
        msg = str(message or '')
        align = 'left' if ('\n' in msg or len(msg) > 18) else 'center'
        valign = 'top' if align == 'left' else 'middle'

        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(18))
        label = Label(text=msg, color=(1, 1, 1, 1), halign=align, valign=valign)
        label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
        content.add_widget(label)

        popup = Popup(
            title=str(title or ''),
            content=content,
            size_hint=(0.85, 0.45),
            background_color=(0.0667, 0.149, 0.3098, 1),
            background='',
        )
        popup.open()



    def go_back(self):
        try:
            self.manager.current = 'main'
        except Exception:
            pass

    def logout(self):
        """退出登录"""
        try:
            app = App.get_running_app()
            if hasattr(app, 'current_user'):
                delattr(app, 'current_user')
            if hasattr(app, 'user_data'):
                delattr(app, 'user_data')
            if hasattr(app, 'api_token'):
                delattr(app, 'api_token')
            if hasattr(app, 'server_role'):
                delattr(app, 'server_role')
            if hasattr(app, 'server_url'):
                delattr(app, 'server_url')
        except Exception:
            pass
        try:
            self.manager.current = 'login'
        except Exception:
            pass


    def apply_join(self, *_):
        code = (self.code_input.text or '').strip()
        if not code:
            self.show_popup('提示', '请输入团队ID')

            return

        def work():
            try:
                token = self._get_token()
                api = self._get_api()
                resp = api.apply_join(token, code)
                msg = resp.get('detail') or '已提交申请'
                Clock.schedule_once(lambda *_: (self.show_popup('申请加入团队', msg), self.refresh()), 0)

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

                    self.list_layout.add_widget(Label(text='我加入的团队：', size_hint_y=None, height=dp(26), color=(1, 1, 1, 1)))

                    if not groups:
                        self.list_layout.add_widget(Label(text='（暂无）', size_hint_y=None, height=dp(22), color=(0.85, 0.9, 1, 1)))
                    for g in groups:
                        gid = g.get('id')
                        name = str(g.get('name') or '')
                        code = str(g.get('group_code') or '')

                        row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))

                        text_row = BoxLayout(orientation='horizontal', spacing=dp(6))
                        name_label = Label(
                            text=name,
                            size_hint=(0.7, 1),
                            color=(0.9, 0.95, 1, 1),
                            halign='center',
                            valign='middle',
                            shorten=True,
                            shorten_from='right',
                        )
                        name_label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))

                        id_label = Label(
                            text=(f"ID:{code}" if code else ''),
                            size_hint=(0.3, 1),
                            color=(0.82, 0.88, 0.95, 1),
                            halign='right',
                            valign='middle',
                            shorten=True,
                            shorten_from='right',
                        )
                        id_label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))

                        text_row.add_widget(name_label)
                        text_row.add_widget(id_label)
                        row.add_widget(text_row)

                        leave_btn = Button(text='退出团队', size_hint=(None, 1), width=dp(80))
                        leave_btn.bind(on_press=lambda _btn, _gid=gid: self.leave_group(_gid))
                        row.add_widget(leave_btn)
                        self.list_layout.add_widget(row)


                    self.list_layout.add_widget(Label(text='入队申请记录：', size_hint_y=None, height=dp(26), color=(1, 1, 1, 1)))

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
                Clock.schedule_once(lambda *_: (self.show_popup('提示', '已退出团队'), self.refresh()), 0)

            except Exception as e:
                Clock.schedule_once(lambda *_: self.show_popup('错误', str(e)), 0)

        Thread(target=work, daemon=True).start()

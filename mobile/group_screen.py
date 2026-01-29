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
from kivy.graphics import Color, Rectangle, RoundedRectangle

from glimmer_api import GlimmerAPI, GlimmerAPIError
from main import db



class GroupScreen(Screen):
    def _short_team_name(self, name: str, max_len: int = 10) -> str:
        s = str(name or '')
        max_len = int(max_len or 10)
        if len(s) <= max_len:
            return s
        if max_len <= 1:
            return '.'
        return s[: max_len - 1] + '.'

    def _make_tag(self, text: str):
        label = Label(
            text=str(text or ''),
            color=(1, 1, 1, 1),
            size_hint=(1, None),
            height=dp(28),
            halign='center',
            valign='middle',
            shorten=True,
            shorten_from='right',
        )
        label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
        with label.canvas.before:
            Color(0.12, 0.2, 0.35, 0.95)
            rect = RoundedRectangle(pos=label.pos, size=label.size, radius=[8])
        label.bind(pos=lambda instance, value: setattr(rect, 'pos', value))
        label.bind(size=lambda instance, value: setattr(rect, 'size', value))
        return label

    def update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def __init__(self, **kwargs):


        super().__init__(**kwargs)

        with self.canvas.before:
            Color(0.0667, 0.149, 0.3098, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self.update_bg, size=self.update_bg)

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
        # 返回即清空动态列表，避免重复进入后内容堆积
        try:
            self.list_layout.clear_widgets()
        except Exception:
            pass
        try:
            self.info_label.text = ''
        except Exception:
            pass

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
                err_msg = str(e)
                Clock.schedule_once(lambda *_: self.show_popup('错误', err_msg), 0)

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

                        row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))

                        display_name = self._short_team_name(name, 10)
                        label_text = f"{display_name}  团队ID:{code}" if code else display_name
                        detail_btn = Button(
                            text=label_text,
                            size_hint=(1, 1),
                            background_color=(0.12, 0.2, 0.35, 0.95),
                            color=(0.95, 0.97, 1, 1),
                            halign='center',
                            valign='middle',
                            shorten=True,
                            shorten_from='right',
                        )
                        detail_btn.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
                        detail_btn.bind(on_press=lambda _btn, _gid=gid, _code=code, _name=name: self.open_team_detail(_gid, _code, _name))
                        row.add_widget(detail_btn)

                        leave_btn = Button(text='退出团队', size_hint=(None, 1), width=dp(84))
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

    def open_team_detail(self, group_id: int, group_code: str, group_name: str):
        """团队详情弹窗：成员数/成员列表（点成员进入本机聊天页）"""
        group_id = int(group_id or 0)
        code = str(group_code or '')
        name = str(group_name or '')

        app = App.get_running_app()
        my_user = str(getattr(app, 'current_user', '') or '')
        my_profile = db.get_user_profile(my_user) if my_user else {}

        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(14))

        title = Label(
            text=f"{name}\n团队ID:{code}" if code else name,
            size_hint=(1, None),
            height=dp(44),
            color=(1, 1, 1, 1),
            halign='center',
            valign='middle',
        )
        title.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
        content.add_widget(title)

        # 当前用户资料（本地档案）
        me_uid = str(my_profile.get('user_id') or '')
        me_real = str(my_profile.get('real_name') or '')
        me_phone = str(my_profile.get('phone') or '')

        avatar_row = BoxLayout(size_hint=(1, None), height=dp(64), spacing=dp(10))
        avatar_text = (me_real or my_user or '我')[:1]
        avatar_btn = Button(
            text=avatar_text,
            size_hint=(None, None),
            size=(dp(54), dp(54)),
            background_color=(0.15, 0.28, 0.5, 1),
            color=(1, 1, 1, 1),
        )
        name_label = Label(
            text=f"{me_real or my_user or '未填写'}",
            color=(0.95, 0.97, 1, 1),
            halign='left',
            valign='middle',
            shorten=True,
            shorten_from='right',
        )
        name_label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
        avatar_row.add_widget(avatar_btn)
        avatar_row.add_widget(name_label)
        content.add_widget(avatar_row)

        tag_grid = GridLayout(cols=2, spacing=dp(6), size_hint_y=None)
        tag_grid.bind(minimum_height=tag_grid.setter('height'))
        tag_grid.add_widget(self._make_tag(f"用户ID:{me_uid or '未知'}"))
        tag_grid.add_widget(self._make_tag(f"姓名:{me_real or my_user or '未填写'}"))
        tag_grid.add_widget(self._make_tag(f"手机号:{me_phone or '未填写'}"))
        members_count_label = self._make_tag('成员数:加载中...')
        tag_grid.add_widget(members_count_label)
        content.add_widget(tag_grid)

        scroll = ScrollView(size_hint=(1, 1), bar_width=dp(2))

        lst = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        lst.bind(minimum_height=lst.setter('height'))
        scroll.add_widget(lst)
        content.add_widget(scroll)

        btn_row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        close_btn = Button(text='返回', background_color=(0.6, 0.6, 0.6, 1))
        btn_row.add_widget(close_btn)
        content.add_widget(btn_row)

        popup = Popup(
            title='团队详情',
            content=content,
            size_hint=(0.92, 0.85),
            background_color=(0.0667, 0.149, 0.3098, 1),
            background='',
        )
        close_btn.bind(on_press=lambda *_: popup.dismiss())
        popup.open()

        def open_chat(peer_user_id: int, peer_username: str):
            try:
                app = App.get_running_app()
                app.chat_peer = {'user_id': int(peer_user_id), 'username': str(peer_username or '')}
                app.chat_group = {'group_id': group_id, 'group_code': code, 'group_name': name}
            except Exception:
                pass
            try:
                popup.dismiss()
            except Exception:
                pass
            try:
                self.manager.current = 'chat'
            except Exception:
                self.show_popup('提示', '聊天页面未就绪')

        def work():
            try:
                token = self._get_token()
                api = self._get_api()

                members = []
                if hasattr(api, 'group_members'):
                    members = api.group_members(token, group_id)
                else:
                    # 兼容：若服务器不支持普通成员列表，则尝试管理员接口（可能会 403）
                    try:
                        members = api.list_group_members(token, group_id)
                    except Exception:
                        members = []

                try:
                    members = sorted((members or []), key=lambda x: str(x.get('joined_at') or ''))
                except Exception:
                    members = members or []

                def ui():
                    lst.clear_widgets()
                    members_count_label.text = f"成员数:{len(members or [])}"
                    if not members:
                        lst.add_widget(Label(text='（暂无成员信息或无权限）', size_hint_y=None, height=dp(26), color=(0.9, 0.95, 1, 1)))
                        return

                    for m in (members or []):

                        uid = int(m.get('user_id') or 0)
                        uname = str(m.get('username') or '')
                        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))

                        avatar = Button(
                            text=(uname[:1] if uname else 'U'),
                            size_hint=(None, 1),
                            width=dp(44),
                            background_color=(0.15, 0.28, 0.5, 1),
                            color=(1, 1, 1, 1),
                        )
                        avatar.bind(on_press=lambda _b, _uid=uid, _uname=uname: open_chat(_uid, _uname))

                        name_btn = Button(
                            text=f"{uname}  ID:{uid}" if uid else uname,
                            size_hint=(1, 1),
                            background_color=(0.12, 0.2, 0.35, 0.95),
                            color=(0.95, 0.97, 1, 1),
                            halign='left',
                            valign='middle',
                            shorten=True,
                            shorten_from='right',
                        )
                        name_btn.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
                        name_btn.bind(on_press=lambda _b, _uid=uid, _uname=uname: open_chat(_uid, _uname))

                        row.add_widget(avatar)
                        row.add_widget(name_btn)
                        lst.add_widget(row)

                Clock.schedule_once(lambda *_: ui(), 0)

            except Exception as e:
                err_msg = str(e)
                Clock.schedule_once(lambda *_: (setattr(members_count_label, 'text', '团队成员：加载失败'), self.show_popup('错误', err_msg)), 0)


        Thread(target=work, daemon=True).start()


    def leave_group(self, group_id: int):
        def work():
            try:
                token = self._get_token()
                api = self._get_api()
                api.leave_group(token, int(group_id))
                Clock.schedule_once(lambda *_: (self.show_popup('提示', '已退出团队'), self.refresh()), 0)

            except Exception as e:
                err_msg = str(e)
                Clock.schedule_once(lambda *_: self.show_popup('错误', err_msg), 0)

        Thread(target=work, daemon=True).start()



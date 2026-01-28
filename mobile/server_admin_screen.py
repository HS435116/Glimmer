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
from kivy.uix.spinner import Spinner
from kivy.clock import Clock
from kivy.metrics import dp

from glimmer_api import GlimmerAPI


class ServerAdminScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(10))

        self.title_label = Label(text='在线管理', font_size=dp(18), bold=True, size_hint=(1, None), height=dp(34), color=(1, 1, 1, 1))
        root.add_widget(self.title_label)

        tab_row = BoxLayout(size_hint=(1, None), height=dp(40), spacing=dp(6))
        self.tab_join = Button(text='入群审核')
        self.tab_corr = Button(text='补录审核')
        self.tab_members = Button(text='成员管理')
        self.tab_announce = Button(text='发公告')
        self.tab_engineer = Button(text='工程师')

        self.tab_join.bind(on_press=lambda *_: self.show_tab('join'))
        self.tab_corr.bind(on_press=lambda *_: self.show_tab('corr'))
        self.tab_members.bind(on_press=lambda *_: self.show_tab('members'))
        self.tab_announce.bind(on_press=lambda *_: self.show_tab('announce'))
        self.tab_engineer.bind(on_press=lambda *_: self.show_tab('engineer'))

        tab_row.add_widget(self.tab_join)
        tab_row.add_widget(self.tab_corr)
        tab_row.add_widget(self.tab_members)
        tab_row.add_widget(self.tab_announce)
        tab_row.add_widget(self.tab_engineer)
        root.add_widget(tab_row)

        self.info = Label(text='', size_hint=(1, None), height=dp(22), font_size=dp(12), color=(0.9, 0.95, 1, 1))
        root.add_widget(self.info)

        self.content = BoxLayout(orientation='vertical', size_hint=(1, 1))
        root.add_widget(self.content)

        back_btn = Button(text='返回', size_hint=(1, None), height=dp(42))
        back_btn.bind(on_press=lambda *_: self._go_back())
        root.add_widget(back_btn)

        self.add_widget(root)

        self._tab = None

        # caches
        self._managed_groups: list[dict] = []
        self._announce_group_id: int | None = None
        self._members_group_id: int | None = None

    def _go_back(self):
        try:
            self.manager.current = 'main'
        except Exception:
            pass

    def _popup(self, title: str, msg: str):
        p = Popup(title=title, content=Label(text=msg), size_hint=(0.9, 0.5), background='')
        p.open()

    def _api(self) -> GlimmerAPI:
        app = App.get_running_app()
        return GlimmerAPI(str(getattr(app, 'server_url', '') or ''))

    def _token(self) -> str:
        app = App.get_running_app()
        t = str(getattr(app, 'api_token', '') or '')
        if not t:
            raise RuntimeError('无Token，请先登录服务器账号')
        return t

    def _role(self) -> str:
        app = App.get_running_app()
        return str(getattr(app, 'server_role', '') or (getattr(app, 'user_data', {}) or {}).get('role') or 'user')

    def _load_managed_groups(self, on_ok, on_err=None):
        def work():
            try:
                groups = self._api().managed_groups(self._token())
                self._managed_groups = groups or []
                Clock.schedule_once(lambda *_: on_ok(self._managed_groups), 0)
            except Exception as e:
                if on_err:
                    Clock.schedule_once(lambda *_: on_err(e), 0)

        Thread(target=work, daemon=True).start()

    def on_enter(self, *args):
        role = self._role()
        self.tab_engineer.disabled = (role != 'engineer')
        self.title_label.text = f"在线管理（{role}）"
        self.show_tab('join')

    def show_tab(self, tab: str):
        if tab == self._tab:
            return
        self._tab = tab
        self.content.clear_widgets()
        if tab == 'join':
            self._build_join_tab()
        elif tab == 'corr':
            self._build_corr_tab()
        elif tab == 'members':
            self._build_members_tab()
        elif tab == 'announce':
            self._build_announce_tab()
        elif tab == 'engineer':
            self._build_engineer_tab()

    def _build_join_tab(self):
        self.info.text = '加载入群申请...'
        scroll = ScrollView(size_hint=(1, 1))
        lst = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        lst.bind(minimum_height=lst.setter('height'))
        scroll.add_widget(lst)
        self.content.add_widget(scroll)

        def work():
            try:
                items = self._api().pending_join_requests(self._token())

                def ui():
                    lst.clear_widgets()
                    if not items:
                        lst.add_widget(Label(text='暂无待审核入群申请', size_hint_y=None, height=dp(28), color=(0.9, 0.95, 1, 1)))
                    for it in items:
                        rid = it.get('id')
                        text = f"{it.get('username')} 申请加入 {it.get('group_name')}"
                        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
                        row.add_widget(Label(text=text, color=(0.9, 0.95, 1, 1)))
                        ok_btn = Button(text='通过', size_hint=(None, 1), width=dp(70))
                        no_btn = Button(text='拒绝', size_hint=(None, 1), width=dp(70))
                        ok_btn.bind(on_press=lambda *_: self._approve_join(rid))
                        no_btn.bind(on_press=lambda *_: self._reject_join(rid))
                        row.add_widget(ok_btn)
                        row.add_widget(no_btn)
                        lst.add_widget(row)
                    self.info.text = '入群申请加载完成'

                Clock.schedule_once(lambda *_: ui(), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_: (setattr(self, 'info', self.info), setattr(self.info, 'text', '加载失败'), self._popup('错误', str(e))), 0)

        Thread(target=work, daemon=True).start()

    def _approve_join(self, request_id: int):
        def work():
            try:
                self._api().approve_join(self._token(), int(request_id))
                Clock.schedule_once(lambda *_: (self._popup('提示', '已通过'), self.show_tab('join')), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_: self._popup('错误', str(e)), 0)

        Thread(target=work, daemon=True).start()

    def _reject_join(self, request_id: int):
        def work():
            try:
                self._api().reject_join(self._token(), int(request_id))
                Clock.schedule_once(lambda *_: (self._popup('提示', '已拒绝'), self.show_tab('join')), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_: self._popup('错误', str(e)), 0)

        Thread(target=work, daemon=True).start()

    def _build_corr_tab(self):
        self.info.text = '加载补录申请...'
        scroll = ScrollView(size_hint=(1, 1))
        lst = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        lst.bind(minimum_height=lst.setter('height'))
        scroll.add_widget(lst)
        self.content.add_widget(scroll)

        def work():
            try:
                items = self._api().pending_corrections(self._token())

                def ui():
                    lst.clear_widgets()
                    if not items:
                        lst.add_widget(Label(text='暂无待审核补录申请', size_hint_y=None, height=dp(28), color=(0.9, 0.95, 1, 1)))
                    for it in items:
                        rid = it.get('id')
                        text = f"{it.get('username')} - {it.get('date')} - {it.get('reason')}"
                        row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(6))
                        row.add_widget(Label(text=text, color=(0.9, 0.95, 1, 1)))
                        ok_btn = Button(text='通过', size_hint=(None, 1), width=dp(70))
                        no_btn = Button(text='拒绝', size_hint=(None, 1), width=dp(70))
                        ok_btn.bind(on_press=lambda *_: self._approve_corr(rid))
                        no_btn.bind(on_press=lambda *_: self._reject_corr(rid))
                        row.add_widget(ok_btn)
                        row.add_widget(no_btn)
                        lst.add_widget(row)
                    self.info.text = '补录申请加载完成'

                Clock.schedule_once(lambda *_: ui(), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_: (setattr(self.info, 'text', '加载失败'), self._popup('错误', str(e))), 0)

        Thread(target=work, daemon=True).start()

    def _approve_corr(self, request_id: int):
        def work():
            try:
                self._api().approve_correction(self._token(), int(request_id))
                Clock.schedule_once(lambda *_: (self._popup('提示', '已通过'), self.show_tab('corr')), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_: self._popup('错误', str(e)), 0)

        Thread(target=work, daemon=True).start()

    def _reject_corr(self, request_id: int):
        def work():
            try:
                self._api().reject_correction(self._token(), int(request_id))
                Clock.schedule_once(lambda *_: (self._popup('提示', '已拒绝'), self.show_tab('corr')), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_: self._popup('错误', str(e)), 0)

        Thread(target=work, daemon=True).start()

    def _build_members_tab(self):
        self.info.text = '加载可管理的群...'
        box = BoxLayout(orientation='vertical', spacing=dp(8))

        top = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        self.members_group_spinner = Spinner(text='选择群', values=[], size_hint=(1, 1))
        refresh_btn = Button(text='刷新成员', size_hint=(None, 1), width=dp(90))
        top.add_widget(self.members_group_spinner)
        top.add_widget(refresh_btn)
        box.add_widget(top)

        scroll = ScrollView(size_hint=(1, 1))
        lst = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        lst.bind(minimum_height=lst.setter('height'))
        scroll.add_widget(lst)
        box.add_widget(scroll)

        self.content.add_widget(box)

        def set_groups(groups: list[dict]):
            values = []
            mapping = {}
            for g in groups:
                label = f"{g.get('name')}（群ID:{g.get('group_code')} / gid:{g.get('id')}）"
                values.append(label)
                mapping[label] = int(g.get('id'))
            self._members_group_map = mapping
            self.members_group_spinner.values = values
            if values:
                self.members_group_spinner.text = values[0]
                self._members_group_id = mapping.get(values[0])
                self._refresh_members_list(lst, int(self._members_group_id))
                self.info.text = '成员列表加载完成'
            else:
                self.info.text = '你没有可管理的群'
                lst.clear_widgets()
                lst.add_widget(Label(text='（暂无）', size_hint_y=None, height=dp(28), color=(0.9, 0.95, 1, 1)))

        def on_select(_spinner, text):
            try:
                gid = int(self._members_group_map.get(text))
                self._members_group_id = gid
                self._refresh_members_list(lst, gid)
            except Exception:
                return

        def on_refresh(*_):
            if not self._members_group_id:
                return
            self._refresh_members_list(lst, int(self._members_group_id))

        self.members_group_spinner.bind(text=on_select)
        refresh_btn.bind(on_press=on_refresh)

        self._load_managed_groups(set_groups, on_err=lambda e: self._popup('错误', str(e)))

    def _refresh_members_list(self, lst: GridLayout, group_id: int):
        self.info.text = '正在刷新成员...'
        lst.clear_widgets()

        def work():
            try:
                members = self._api().list_group_members(self._token(), int(group_id))

                def ui():
                    lst.clear_widgets()
                    if not members:
                        lst.add_widget(Label(text='（暂无成员）', size_hint_y=None, height=dp(28), color=(0.9, 0.95, 1, 1)))
                        self.info.text = '成员列表为空'
                        return

                    app = App.get_running_app()
                    my_name = str(getattr(app, 'current_user', '') or '')

                    for m in members:
                        uid = int(m.get('user_id'))
                        uname = str(m.get('username') or '')
                        is_admin = bool(m.get('is_group_admin'))
                        flag = '（管理员）' if is_admin else ''

                        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
                        row.add_widget(Label(text=f"{uname} {flag}", color=(0.9, 0.95, 1, 1)))

                        rm_btn = Button(text='移除', size_hint=(None, 1), width=dp(70))
                        if uname == my_name:
                            rm_btn.disabled = True
                            rm_btn.opacity = 0
                        rm_btn.bind(on_press=lambda *_btn, _uid=uid: self._remove_member(group_id, _uid))
                        row.add_widget(rm_btn)

                        lst.add_widget(row)

                    self.info.text = '成员列表已更新'

                Clock.schedule_once(lambda *_: ui(), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_: (setattr(self.info, 'text', '刷新失败'), self._popup('错误', str(e))), 0)

        Thread(target=work, daemon=True).start()

    def _remove_member(self, group_id: int, user_id: int):
        def work():
            try:
                self._api().remove_group_member(self._token(), int(group_id), int(user_id))
                Clock.schedule_once(lambda *_: (self._popup('提示', '已移除'), self.show_tab('members')), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_: self._popup('错误', str(e)), 0)

        Thread(target=work, daemon=True).start()

    def _build_announce_tab(self):
        role = self._role()
        self.info.text = '发布公告：工程师=全局；管理员=群内（先选群）'

        box = BoxLayout(orientation='vertical', spacing=dp(8))
        self.announce_title = TextInput(hint_text='标题', multiline=False, size_hint=(1, None), height=dp(44))
        self.announce_content = TextInput(hint_text='内容', multiline=True)

        box.add_widget(self.announce_title)
        box.add_widget(self.announce_content)

        self._announce_group_id = None
        self.announce_group_spinner = None

        if role != 'engineer':
            self.announce_group_spinner = Spinner(text='选择群（我管理的群）', values=[], size_hint=(1, None), height=dp(44))
            box.add_widget(self.announce_group_spinner)

            def set_groups(groups: list[dict]):
                values = []
                mapping = {}
                for g in groups:
                    label = f"{g.get('name')}（群ID:{g.get('group_code')} / gid:{g.get('id')}）"
                    values.append(label)
                    mapping[label] = int(g.get('id'))
                self._announce_group_map = mapping
                self.announce_group_spinner.values = values
                if values:
                    self.announce_group_spinner.text = values[0]
                    self._announce_group_id = mapping.get(values[0])
                else:
                    self.announce_group_spinner.text = '（无可管理群）'
                    self._announce_group_id = None

            def on_select(_spinner, text):
                try:
                    self._announce_group_id = int(self._announce_group_map.get(text))
                except Exception:
                    self._announce_group_id = None

            self.announce_group_spinner.bind(text=on_select)
            self._load_managed_groups(set_groups, on_err=lambda e: self._popup('错误', str(e)))

        send_btn = Button(text='发布', size_hint=(1, None), height=dp(44))
        send_btn.bind(on_press=lambda *_: self._send_announcement())
        box.add_widget(send_btn)

        self.content.add_widget(box)

    def _send_announcement(self):
        title = (self.announce_title.text or '').strip()
        content = (self.announce_content.text or '').strip()
        if not title or not content:
            self._popup('提示', '请输入标题和内容')
            return

        role = self._role()

        def work():
            try:
                api = self._api()
                token = self._token()
                if role == 'engineer':
                    api.post_global_announcement(token, title, content)
                else:
                    gid = int(self._announce_group_id or 0)
                    if gid <= 0:
                        raise RuntimeError('请选择要发布公告的群')
                    api.post_group_announcement(token, gid, title, content)
                Clock.schedule_once(lambda *_: self._popup('成功', '已发布'), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_: self._popup('错误', str(e)), 0)

        Thread(target=work, daemon=True).start()

    def _build_engineer_tab(self):
        if self._role() != 'engineer':
            self.content.add_widget(Label(text='仅工程师可用', color=(0.9, 0.95, 1, 1)))
            return

        box = BoxLayout(orientation='vertical', spacing=dp(10))

        # 创建群
        grp_row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        self.group_name_input = TextInput(hint_text='新群名称', multiline=False)
        grp_btn = Button(text='创建群', size_hint=(None, 1), width=dp(90))
        grp_btn.bind(on_press=lambda *_: self._create_group())
        grp_row.add_widget(self.group_name_input)
        grp_row.add_widget(grp_btn)
        box.add_widget(grp_row)

        # 版本发布
        self.ver_input = TextInput(hint_text='最新版本号，例如 1.2.0', multiline=False, size_hint=(1, None), height=dp(44))
        self.ver_note = TextInput(hint_text='版本说明', multiline=True, size_hint=(1, None), height=dp(120))
        ver_btn = Button(text='发布版本提醒', size_hint=(1, None), height=dp(44))
        ver_btn.bind(on_press=lambda *_: self._set_version())
        box.add_widget(self.ver_input)
        box.add_widget(self.ver_note)
        box.add_widget(ver_btn)

        # 广告配置
        self.ad_text = TextInput(hint_text='广告文字', multiline=False, size_hint=(1, None), height=dp(44))
        self.ad_img = TextInput(hint_text='图片URL', multiline=False, size_hint=(1, None), height=dp(44))
        self.ad_link = TextInput(hint_text='跳转URL', multiline=False, size_hint=(1, None), height=dp(44))
        ad_btn = Button(text='发布广告', size_hint=(1, None), height=dp(44))
        ad_btn.bind(on_press=lambda *_: self._set_ads())
        box.add_widget(self.ad_text)
        box.add_widget(self.ad_img)
        box.add_widget(self.ad_link)
        box.add_widget(ad_btn)

        self.content.add_widget(box)

    def _create_group(self):
        name = (self.group_name_input.text or '').strip()
        if not name:
            self._popup('提示', '请输入群名称')
            return

        def work():
            try:
                resp = self._api().create_group(self._token(), name)
                gid = resp.get('id')
                code = resp.get('group_code')
                Clock.schedule_once(lambda *_: self._popup('创建成功', f'group_id={gid}\n群ID={code}'), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_: self._popup('错误', str(e)), 0)

        Thread(target=work, daemon=True).start()

    def _set_version(self):
        ver = (self.ver_input.text or '').strip()
        note = (self.ver_note.text or '').strip()
        if not ver:
            self._popup('提示', '请输入版本号')
            return

        def work():
            try:
                self._api().set_version(self._token(), ver, note)
                Clock.schedule_once(lambda *_: self._popup('成功', '版本已发布'), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_: self._popup('错误', str(e)), 0)

        Thread(target=work, daemon=True).start()

    def _set_ads(self):
        text = (self.ad_text.text or '').strip()
        img = (self.ad_img.text or '').strip()
        link = (self.ad_link.text or '').strip()

        def work():
            try:
                self._api().set_ads(self._token(), True, text, img, link)
                Clock.schedule_once(lambda *_: self._popup('成功', '广告已发布'), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_: self._popup('错误', str(e)), 0)

        Thread(target=work, daemon=True).start()

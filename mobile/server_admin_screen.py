from __future__ import annotations

from threading import Thread
from datetime import datetime

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
from kivy.graphics import Color, Rectangle

from glimmer_api import GlimmerAPI


class ServerAdminScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(0.0667, 0.149, 0.3098, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self.update_bg, size=self.update_bg)

        root = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(10))

        self.title_label = Label(text='在线管理', font_size=dp(18), bold=True, size_hint=(1, None), height=dp(34), color=(1, 1, 1, 1))
        root.add_widget(self.title_label)

        tab_row = BoxLayout(size_hint=(1, None), height=dp(40), spacing=dp(6))
        self._tab_row = tab_row
        self.tab_join = Button(text='入队审核')
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

        self.back_btn = Button(text='返回', size_hint=(1, None), height=dp(42))
        self.back_btn.bind(on_press=lambda *_: self._go_back())
        root.add_widget(self.back_btn)

        self.add_widget(root)

        self._tab = None

        # caches
        self._managed_groups: list[dict] = []
        self._announce_group_id: int | None = None
        self._members_group_id: int | None = None

    def update_bg(self, *_):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def _go_back(self):
        # 返回即清理内容区，避免重复进入后内容堆积
        try:
            self.content.clear_widgets()
        except Exception:
            pass
        self._tab = None

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
            size_hint=(0.9, 0.5),
            background_color=(0.0667, 0.149, 0.3098, 1),
            background='',
        )
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
                    Clock.schedule_once(lambda *_, ex=e: on_err(ex), 0)

        Thread(target=work, daemon=True).start()

    def on_enter(self, *args):
        role = self._role()

        # 权限控制：
        # - admin：可管理团队（入队/补录/成员/发公告）
        # - engineer：工程师页
        # - user：仅允许查看自己的打卡记录
        is_user = (role == 'user')
        is_eng = (role == 'engineer')

        # 工程师页仅工程师可见；管理员也不显示该标签（避免误用工程师权限）
        try:
            if is_eng:
                if getattr(self.tab_engineer, 'parent', None) is None and getattr(self, '_tab_row', None) is not None:
                    self._tab_row.add_widget(self.tab_engineer)
            else:
                if getattr(self.tab_engineer, 'parent', None) is not None:
                    self.tab_engineer.parent.remove_widget(self.tab_engineer)
        except Exception:
            pass

        self.tab_engineer.disabled = (not is_eng)

        try:
            self.tab_join.disabled = is_user
            self.tab_corr.disabled = is_user
            self.tab_announce.disabled = is_user
        except Exception:
            pass

        try:
            self.tab_members.text = '打卡记录' if is_user else '成员管理'
        except Exception:
            pass

        self.title_label.text = f"在线管理（{role}）"

        if is_eng:
            self.show_tab('engineer')
        elif is_user:
            self.show_tab('members')
        else:
            self.show_tab('join')

    def show_tab(self, tab: str):
        if tab == self._tab:
            return
        self._tab = tab
        try:
            if hasattr(self, 'back_btn'):
                is_eng = (tab == 'engineer')
                self.back_btn.disabled = is_eng
                self.back_btn.opacity = 0 if is_eng else 1
                # engineer 页有内部返回按钮，这里把底部返回条高度置 0，避免挤压内容区域
                self.back_btn.height = 0 if is_eng else dp(42)
        except Exception:
            pass
        self.content.clear_widgets()
        if tab == 'join':
            self._build_join_tab()
        elif tab == 'corr':
            self._build_corr_tab()
        elif tab == 'members':
            if self._role() == 'user':
                self._build_my_attendance_tab()
            else:
                self._build_members_tab()
        elif tab == 'announce':
            self._build_announce_tab()
        elif tab == 'engineer':
            self._build_engineer_tab()

    def _build_join_tab(self):
        self.info.text = '加载入队申请...'
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
                        lst.add_widget(Label(text='暂无待审核入队申请', size_hint_y=None, height=dp(28), color=(0.9, 0.95, 1, 1)))
                    for it in items:
                        rid = it.get('id')
                        uname = str(it.get('username') or '')
                        gname = str(it.get('group_name') or '')
                        gcode = str(it.get('group_code') or '')
                        code_part = f" 团队ID:{gcode}" if gcode else ''
                        text = f"{uname}{code_part} 申请加入 {gname}"
                        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
                        text_label = Label(text=text, color=(0.9, 0.95, 1, 1), halign='left', valign='middle', shorten=True, shorten_from='right')
                        text_label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
                        row.add_widget(text_label)
                        ok_btn = Button(text='通过', size_hint=(None, 1), width=dp(70))
                        no_btn = Button(text='拒绝', size_hint=(None, 1), width=dp(70))
                        ok_btn.bind(on_press=lambda *_: self._approve_join(rid))
                        no_btn.bind(on_press=lambda *_: self._reject_join(rid))
                        row.add_widget(ok_btn)
                        row.add_widget(no_btn)
                        lst.add_widget(row)
                    self.info.text = '入队申请加载完成'

                Clock.schedule_once(lambda *_: ui(), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_, msg=str(e): (setattr(self, 'info', self.info), setattr(self.info, 'text', '加载失败'), self._popup('错误', msg)), 0)

        Thread(target=work, daemon=True).start()

    def _approve_join(self, request_id: int):
        def work():
            try:
                self._api().approve_join(self._token(), int(request_id))
                Clock.schedule_once(lambda *_: (self._popup('提示', '已通过'), self.show_tab('join')), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_, msg=str(e): self._popup('错误', msg), 0)

        Thread(target=work, daemon=True).start()

    def _reject_join(self, request_id: int):
        def work():
            try:
                self._api().reject_join(self._token(), int(request_id))
                Clock.schedule_once(lambda *_: (self._popup('提示', '已拒绝'), self.show_tab('join')), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_, msg=str(e): self._popup('错误', msg), 0)

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
                Clock.schedule_once(lambda *_, msg=str(e): (setattr(self.info, 'text', '加载失败'), self._popup('错误', msg)), 0)

        Thread(target=work, daemon=True).start()

    def _approve_corr(self, request_id: int):
        def work():
            try:
                self._api().approve_correction(self._token(), int(request_id))
                Clock.schedule_once(lambda *_: (self._popup('提示', '已通过'), self.show_tab('corr')), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_, msg=str(e): self._popup('错误', msg), 0)

        Thread(target=work, daemon=True).start()

    def _reject_corr(self, request_id: int):
        def work():
            try:
                self._api().reject_correction(self._token(), int(request_id))
                Clock.schedule_once(lambda *_: (self._popup('提示', '已拒绝'), self.show_tab('corr')), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_, msg=str(e): self._popup('错误', msg), 0)

        Thread(target=work, daemon=True).start()

    def _month_options_last2(self) -> list[str]:
        now = datetime.now()
        cur = now.strftime('%Y-%m')
        y = int(now.year)
        m = int(now.month) - 1
        if m <= 0:
            y -= 1
            m = 12
        prev = f"{y:04d}-{m:02d}"
        return [cur, prev]

    def _short_status(self, status: str) -> str:
        st = str(status or '')
        if '补录' in st:
            return '补录'
        if '失败' in st:
            return '失败'
        if '成功' in st:
            return '成功'
        return (st or '').strip()

    def _short_time_key(self, punched_at: str, date: str) -> tuple[str, str]:
        at = str(punched_at or '')
        when = at[:19].replace('T', ' ') if at else ''
        key = when or (f"{str(date or '')} 00:00:00" if date else '')
        t = when[11:16] if len(when) >= 16 else (when[11:] if len(when) > 11 else '')
        return key, t

    def _short_attendance_line(self, date: str, punched_at: str, status: str) -> str:
        d = str(date or '')
        if len(d) >= 10 and d[4] == '-' and d[7] == '-':
            d = d[5:]
        _k, t = self._short_time_key(punched_at, date)
        st = self._short_status(status)
        return f"{d} {t} {st}".strip()

    def _summarize_attendance_month(self, items: list[dict]) -> list[str]:
        by_day: dict[str, list[tuple[str, str, str]]] = {}
        for it in (items or []):
            d = str((it or {}).get('date') or '')
            if not d:
                continue
            punched_at = str((it or {}).get('punched_at') or '')
            status = str((it or {}).get('status') or '')
            key, t = self._short_time_key(punched_at, d)
            st = self._short_status(status)
            by_day.setdefault(d, []).append((key, t, st))

        lines: list[str] = []
        for d, rows in sorted(by_day.items(), key=lambda x: x[0]):
            rows = sorted(rows, key=lambda x: x[0])
            first = rows[0]
            last = rows[-1]

            dd = d
            if len(dd) >= 10 and dd[4] == '-' and dd[7] == '-':
                dd = dd[5:]

            if first[1] == last[1] and first[2] == last[2]:
                line = f"{dd} {first[1]} {first[2]}".strip()
            else:
                line = f"{dd} 首{first[1]} {first[2]} 末{last[1]} {last[2]}".strip()

            lines.append(line)

        return lines

    def _attendance_cache_get(self, month: str) -> list[dict] | None:
        try:
            app = App.get_running_app()
            username = str(getattr(app, 'current_user', '') or '')
            if not username:
                return None
            from main import db
            s = db.get_user_settings(username) or {}
            cache = s.get('attendance_cache', {}) or {}
            items = cache.get(str(month))
            return items if isinstance(items, list) else None
        except Exception:
            return None

    def _attendance_cache_put(self, month: str, items: list[dict]):
        try:
            app = App.get_running_app()
            username = str(getattr(app, 'current_user', '') or '')
            if not username:
                return
            from main import db
            s = db.get_user_settings(username) or {}
            cache = dict(s.get('attendance_cache', {}) or {})
            cache[str(month)] = list(items or [])

            # 仅保留最近 2 个月，其他自动清除
            keep = set(self._month_options_last2())
            cache = {k: v for k, v in cache.items() if k in keep}

            s['attendance_cache'] = cache
            db.save_user_settings(username, s)
        except Exception:
            return

    def _build_my_attendance_tab(self):
        self.info.text = '打卡记录查询'

        box = BoxLayout(orientation='vertical', spacing=dp(8))

        row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        months = self._month_options_last2()
        month_spinner = Spinner(text=months[0] if months else datetime.now().strftime('%Y-%m'), values=months, size_hint=(0.6, 1))
        query_btn = Button(text='查询', size_hint=(0.4, 1))
        row.add_widget(month_spinner)
        row.add_widget(query_btn)
        box.add_widget(row)

        info = Label(text='请选择月份后点击查询（本地缓存保留最近2个月）', size_hint=(1, None), height=dp(22), color=(0.9, 0.95, 1, 1), halign='left', valign='middle')
        info.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
        box.add_widget(info)

        scroll = ScrollView(size_hint=(1, 1), bar_width=dp(2))
        lst = GridLayout(cols=1, spacing=dp(2), size_hint_y=None)
        lst.bind(minimum_height=lst.setter('height'))
        scroll.add_widget(lst)
        box.add_widget(scroll)

        self.content.add_widget(box)

        def render_lines(lines: list[str]):
            lst.clear_widgets()
            if not lines:
                lst.add_widget(Label(text='（暂无记录）', size_hint_y=None, height=dp(22), color=(0.9, 0.95, 1, 1)))
                return
            for line in lines:
                lb = Label(text=str(line or ''), size_hint_y=None, height=dp(24), color=(0.9, 0.95, 1, 1), halign='left', valign='middle', shorten=True, shorten_from='right')
                lb.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
                lst.add_widget(lb)

        def load():
            m = str(getattr(month_spinner, 'text', '') or '').strip()
            if len(m) != 7:
                self._popup('提示', '月份格式应为 YYYY-MM')
                return

            # 先读本地缓存（仅保留最近2个月）
            cached = self._attendance_cache_get(m)
            if cached is not None:
                lines = self._summarize_attendance_month(cached)
                render_lines(lines)
                info.text = f'加载完成（缓存）: {m}'
                return

            info.text = '正在查询...'
            lst.clear_widgets()

            def work():
                try:
                    items = self._api().attendance_month(self._token(), m)
                    self._attendance_cache_put(m, items or [])
                    lines = self._summarize_attendance_month(items or [])

                    def ui():
                        render_lines(lines)
                        info.text = f'查询完成: {m}'

                    Clock.schedule_once(lambda *_: ui(), 0)
                except Exception as e:
                    Clock.schedule_once(lambda *_, msg=str(e): (setattr(info, 'text', '查询失败'), self._popup('错误', msg)), 0)

            Thread(target=work, daemon=True).start()

        query_btn.bind(on_press=lambda *_: load())
        load()

    def _build_members_tab(self):
        self.info.text = '加载可管理的团队...'
        box = BoxLayout(orientation='vertical', spacing=dp(8))

        role = self._role()

        # 管理员团队管理：创建团队 + 管理成员（工程师也可查看全部团队）
        create_btn = None
        if role in ('admin', 'engineer'):
            box.add_widget(Label(text='创建团队', size_hint=(1, None), height=dp(22), color=(0.9, 0.95, 1, 1)))
            create_row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
            self._members_create_group_input = TextInput(hint_text='新团队名称（最多10字）', multiline=False)
            create_btn = Button(text='创建', size_hint=(None, 1), width=dp(80))
            create_row.add_widget(self._members_create_group_input)
            create_row.add_widget(create_btn)
            box.add_widget(create_row)

        top = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        self.members_group_spinner = Spinner(
            text='选择团队',
            values=[],
            size_hint=(0.55, 1),
            shorten=True,
            shorten_from='right',
            halign='center',
            valign='middle',
        )
        self.members_group_spinner.bind(size=lambda instance, value: setattr(instance, 'text_size', value))

        self.members_group_code_label = Label(
            text='团队ID:',
            size_hint=(0.25, 1),
            color=(0.9, 0.95, 1, 1),
            halign='right',
            valign='middle',
            shorten=True,
            shorten_from='right',
        )
        self.members_group_code_label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))

        refresh_btn = Button(text='刷新成员', size_hint=(0.2, 1))
        top.add_widget(self.members_group_spinner)
        top.add_widget(self.members_group_code_label)
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
            mapping: dict[str, int] = {}
            code_map: dict[str, str] = {}
            for g in groups:
                name = str(g.get('name') or '')
                code = str(g.get('group_code') or '')
                try:
                    gid = int(g.get('id'))
                except Exception:
                    continue
                if not name:
                    name = f"团队{gid}"

                # 显示更多团队信息，便于工程师/管理员下拉滚动查看
                display = f"{name}  (编号:{gid}  ID:{code})" if code else f"{name}  (编号:{gid})"

                values.append(display)
                mapping[display] = gid
                code_map[display] = code

            self._members_group_map = mapping
            self._members_group_code_map = code_map
            self.members_group_spinner.values = values

            if values:
                self.members_group_spinner.text = values[0]
                self._members_group_id = mapping.get(values[0])
                c0 = str(code_map.get(values[0]) or '')
                self.members_group_code_label.text = f"团队ID:{c0}" if c0 else '团队ID:'
                self._refresh_members_list(lst, int(self._members_group_id))
                self.info.text = '成员列表加载完成'
            else:
                self.info.text = '你没有可管理的团队'
                self.members_group_code_label.text = '团队ID:'
                lst.clear_widgets()
                lst.add_widget(Label(text='（暂无）', size_hint_y=None, height=dp(28), color=(0.9, 0.95, 1, 1)))

        def on_select(_spinner, text):
            try:
                gid = int(self._members_group_map.get(text))
                self._members_group_id = gid
                code = str((getattr(self, '_members_group_code_map', {}) or {}).get(text) or '')
                self.members_group_code_label.text = f"团队ID:{code}" if code else '团队ID:'
                self._refresh_members_list(lst, gid)
            except Exception:
                return

        def on_refresh(*_):
            if not self._members_group_id:
                return
            self._refresh_members_list(lst, int(self._members_group_id))

        self.members_group_spinner.bind(text=on_select)
        refresh_btn.bind(on_press=on_refresh)

        def on_create(*_):
            if not create_btn:
                return
            name = ''
            try:
                name = str(getattr(self, '_members_create_group_input', None).text or '').strip()
            except Exception:
                name = ''

            if not name:
                self._popup('提示', '请输入团队名称')
                return

            if len(name) > 10:
                name = name[:9] + '.'
                try:
                    getattr(self, '_members_create_group_input', None).text = name
                except Exception:
                    pass

            def work():
                try:
                    resp = self._api().create_group(self._token(), name)
                    gid = resp.get('id')
                    code = resp.get('group_code')

                    def ui():
                        self._popup('创建成功', f'团队编号:{gid}\n团队ID:{code}')
                        self._load_managed_groups(set_groups, on_err=lambda e: self._popup('错误', str(e)))

                    Clock.schedule_once(lambda *_: ui(), 0)
                except Exception as e:
                    Clock.schedule_once(lambda *_, msg=str(e): self._popup('错误', msg), 0)

            Thread(target=work, daemon=True).start()

        if create_btn:
            create_btn.bind(on_press=on_create)

        self._load_managed_groups(set_groups, on_err=lambda e: self._popup('错误', str(e)))

    def _refresh_members_list(self, lst: GridLayout, group_id: int):
        self.info.text = '正在刷新成员...'
        lst.clear_widgets()

        def work():
            try:
                members = self._api().list_group_members(self._token(), int(group_id))
                try:
                    members = sorted((members or []), key=lambda x: str(x.get('joined_at') or ''))
                except Exception:
                    pass

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

                        name_btn = Button(
                            text=f"{uname} {flag}",
                            size_hint=(1, 1),
                            background_color=(0.12, 0.2, 0.35, 0.95),
                            color=(0.9, 0.95, 1, 1),
                            halign='left',
                            valign='middle',
                            shorten=True,
                            shorten_from='right',
                        )
                        name_btn.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
                        name_btn.bind(on_press=lambda *_btn, _uid=uid, _uname=uname: self._show_member_attendance(_uid, _uname))
                        row.add_widget(name_btn)

                        att_btn = Button(text='打卡', size_hint=(None, 1), width=dp(62))
                        att_btn.bind(on_press=lambda *_btn, _uid=uid, _uname=uname: self._show_member_attendance(_uid, _uname))
                        row.add_widget(att_btn)

                        corr_btn = Button(text='补录', size_hint=(None, 1), width=dp(62))
                        corr_btn.bind(on_press=lambda *_btn, _uid=uid, _uname=uname: self._admin_apply_correction(group_id, _uid, _uname))
                        row.add_widget(corr_btn)

                        rm_btn = Button(text='移除', size_hint=(None, 1), width=dp(62))
                        if uname == my_name:
                            rm_btn.disabled = True
                            rm_btn.opacity = 0
                        rm_btn.bind(on_press=lambda *_btn, _uid=uid: self._remove_member(group_id, _uid))
                        row.add_widget(rm_btn)

                        lst.add_widget(row)

                    self.info.text = '成员列表已更新'

                Clock.schedule_once(lambda *_: ui(), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_, msg=str(e): (setattr(self.info, 'text', '刷新失败'), self._popup('错误', msg)), 0)

        Thread(target=work, daemon=True).start()

    def _remove_member(self, group_id: int, user_id: int):
        def work():
            try:
                self._api().remove_group_member(self._token(), int(group_id), int(user_id))
                Clock.schedule_once(lambda *_: (self._popup('提示', '已移除'), self.show_tab('members')), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_, msg=str(e): self._popup('错误', msg), 0)

        Thread(target=work, daemon=True).start()

    def _show_member_attendance(self, user_id: int, username: str):
        user_id = int(user_id or 0)
        uname = str(username or '')
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(14))

        row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        months = self._month_options_last2()
        month_spinner = Spinner(text=months[0] if months else datetime.now().strftime('%Y-%m'), values=months, size_hint=(0.55, 1))
        query_btn = Button(text='查询', size_hint=(0.2, 1))
        close_btn = Button(text='返回', size_hint=(0.25, 1))
        row.add_widget(month_spinner)
        row.add_widget(query_btn)
        row.add_widget(close_btn)
        content.add_widget(row)

        info = Label(text='正在查询...', size_hint=(1, None), height=dp(22), color=(0.9, 0.95, 1, 1), halign='left', valign='middle')
        info.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
        content.add_widget(info)

        scroll = ScrollView(size_hint=(1, 1), bar_width=dp(2))
        # 缩小间距/行高，尽量多显示当天的离开打卡记录
        lst = GridLayout(cols=1, spacing=dp(2), size_hint_y=None)
        lst.bind(minimum_height=lst.setter('height'))
        scroll.add_widget(lst)
        content.add_widget(scroll)

        popup = Popup(
            title=f"打卡记录查询：{uname}",
            content=content,
            size_hint=(0.92, 0.85),
            background_color=(0.0667, 0.149, 0.3098, 1),
            background='',
        )
        close_btn.bind(on_press=lambda *_: popup.dismiss())

        def render_lines(lines: list[str]):
            lst.clear_widgets()
            if not lines:
                lst.add_widget(Label(text='（暂无记录）', size_hint_y=None, height=dp(26), color=(0.9, 0.95, 1, 1)))
                return
            for line in lines:
                lb = Label(text=str(line or ''), size_hint_y=None, height=dp(24), color=(0.9, 0.95, 1, 1), halign='left', valign='middle', shorten=True, shorten_from='right')
                lb.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
                lst.add_widget(lb)

        def load():
            m = str(getattr(month_spinner, 'text', '') or '').strip()
            if len(m) != 7:
                Clock.schedule_once(lambda *_: self._popup('提示', '月份格式应为 YYYY-MM'), 0)
                return

            info.text = '正在查询...'
            lst.clear_widgets()

            def work():
                try:
                    items = self._api().admin_attendance_month(self._token(), user_id, m)
                    lines = self._summarize_attendance_month(items or [])

                    def ui():
                        render_lines(lines)
                        info.text = f'查询完成: {m}'

                    Clock.schedule_once(lambda *_: ui(), 0)
                except Exception as e:
                    Clock.schedule_once(lambda *_, msg=str(e): (setattr(info, 'text', '查询失败'), self._popup('错误', msg)), 0)

            Thread(target=work, daemon=True).start()

        query_btn.bind(on_press=lambda *_: load())
        popup.open()
        load()

    def _admin_apply_correction(self, group_id: int, user_id: int, username: str):
        gid = int(group_id or 0)
        uid = int(user_id or 0)
        uname = str(username or '')

        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(14))
        content.add_widget(Label(text=f"为成员申请补录：{uname}", size_hint=(1, None), height=dp(26), color=(1, 1, 1, 1)))

        date_input = TextInput(text=datetime.now().strftime('%Y-%m-%d'), multiline=False, size_hint=(1, None), height=dp(44), hint_text='YYYY-MM-DD')
        reason_input = TextInput(hint_text='原因（选填）', multiline=True, size_hint=(1, None), height=dp(110))
        content.add_widget(date_input)
        content.add_widget(reason_input)

        btn_row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        ok_btn = Button(text='提交', background_color=(0.2, 0.6, 0.8, 1))
        cancel_btn = Button(text='返回', background_color=(0.6, 0.6, 0.6, 1))
        btn_row.add_widget(ok_btn)
        btn_row.add_widget(cancel_btn)
        content.add_widget(btn_row)

        popup = Popup(
            title='申请补录',
            content=content,
            size_hint=(0.9, 0.65),
            background_color=(0.0667, 0.149, 0.3098, 1),
            background='',
        )
        cancel_btn.bind(on_press=lambda *_: popup.dismiss())

        def submit(*_):
            d = (date_input.text or '').strip()
            r = (reason_input.text or '').strip()
            if len(d) != 10 or d[4] != '-' or d[7] != '-':
                self._popup('提示', '日期格式应为 YYYY-MM-DD')
                return

            def work():
                try:
                    self._api().admin_request_correction(self._token(), uid, gid, d, r)
                    Clock.schedule_once(lambda *_: (popup.dismiss(), self._popup('成功', '已提交补录申请（待审核）')), 0)
                except Exception as e:
                    Clock.schedule_once(lambda *_, msg=str(e): self._popup('错误', msg), 0)

            Thread(target=work, daemon=True).start()

        ok_btn.bind(on_press=submit)
        popup.open()

    def _build_announce_tab(self):
        role = self._role()
        self.info.text = '发布公告：工程师=全局；管理员=团队内（先选团队）'

        box = BoxLayout(orientation='vertical', spacing=dp(8), padding=[dp(6), dp(6), dp(6), dp(12)])
        self.announce_title = TextInput(hint_text='标题', multiline=False, size_hint=(1, None), height=dp(44))
        # 固定高度，避免小屏/软键盘场景下遮挡后续控件
        self.announce_content = TextInput(hint_text='内容', multiline=True, size_hint=(1, None), height=dp(160))

        box.add_widget(self.announce_title)
        box.add_widget(self.announce_content)

        self._announce_group_id = None
        self.announce_group_spinner = None
        self.announce_group_code_label = None

        if role != 'engineer':
            row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
            self.announce_group_spinner = Spinner(
                text='选择团队（我管理的团队）',
                values=[],
                size_hint=(0.7, 1),
                shorten=True,
                shorten_from='right',
                halign='center',
                valign='middle',
            )
            self.announce_group_spinner.bind(size=lambda instance, value: setattr(instance, 'text_size', value))

            self.announce_group_code_label = Label(
                text='团队ID:',
                size_hint=(0.3, 1),
                color=(0.9, 0.95, 1, 1),
                halign='right',
                valign='middle',
                shorten=True,
                shorten_from='right',
            )
            self.announce_group_code_label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))

            row.add_widget(self.announce_group_spinner)
            row.add_widget(self.announce_group_code_label)
            box.add_widget(row)

            def set_groups(groups: list[dict]):
                values = []
                mapping: dict[str, int] = {}
                code_map: dict[str, str] = {}
                for g in groups:
                    name = str(g.get('name') or '')
                    code = str(g.get('group_code') or '')
                    if not name:
                        continue
                    values.append(name)
                    try:
                        mapping[name] = int(g.get('id'))
                        code_map[name] = code
                    except Exception:
                        continue
                self._announce_group_map = mapping
                self._announce_group_code_map = code_map
                self.announce_group_spinner.values = values
                if values:
                    self.announce_group_spinner.text = values[0]
                    self._announce_group_id = mapping.get(values[0])
                    c0 = str(code_map.get(values[0]) or '')
                    self.announce_group_code_label.text = f"团队ID:{c0}" if c0 else '团队ID:'
                else:
                    self.announce_group_spinner.text = '（无可管理团队）'
                    self.announce_group_code_label.text = '团队ID:'
                    self._announce_group_id = None

            def on_select(_spinner, text):
                try:
                    self._announce_group_id = int(self._announce_group_map.get(text))
                    code = str((getattr(self, '_announce_group_code_map', {}) or {}).get(text) or '')
                    self.announce_group_code_label.text = f"团队ID:{code}" if code else '团队ID:'
                except Exception:
                    self._announce_group_id = None
                    self.announce_group_code_label.text = '团队ID:'

            self.announce_group_spinner.bind(text=on_select)
            self._load_managed_groups(set_groups, on_err=lambda e: self._popup('错误', str(e)))

        send_btn = Button(text='发布', size_hint=(1, None), height=dp(44))
        send_btn.bind(on_press=lambda *_: self._send_announcement())
        box.add_widget(send_btn)

        box.size_hint_y = None
        box.bind(minimum_height=box.setter('height'))
        scroll = ScrollView(size_hint=(1, 1), bar_width=dp(2))
        scroll.add_widget(box)
        self.content.add_widget(scroll)

    def _send_announcement(self):
        title = (self.announce_title.text or '').strip()
        content = (self.announce_content.text or '').strip()
        if not title or not content:
            self._popup('提示', '请输入标题和内容')
            return

        c = len(content or '')
        if c > 3500:
            self._popup('提示', f'公告内容过长（{c}字），最大3500字，请精简后再发布')
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
                        raise RuntimeError('请选择要发布公告的团队')
                    api.post_group_announcement(token, gid, title, content)
                Clock.schedule_once(lambda *_: self._popup('成功', '已发布'), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_, msg=str(e): self._popup('错误', msg), 0)

        Thread(target=work, daemon=True).start()

    def _build_engineer_tab(self):
        if self._role() != 'engineer':
            self.content.add_widget(Label(text='仅工程师可用', color=(0.9, 0.95, 1, 1)))
            return

        # 工程师页内容较多：使用滚动区域 + 底部固定“发布广告”按钮，确保小屏也能看到。
        container = BoxLayout(orientation='vertical', spacing=dp(8))

        scroll = ScrollView(size_hint=(1, 1), bar_width=dp(2))
        box = BoxLayout(orientation='vertical', spacing=dp(10), size_hint=(1, None), padding=[dp(8), dp(8)])
        box.bind(minimum_height=box.setter('height'))
        scroll.add_widget(box)
        container.add_widget(scroll)

        top = BoxLayout(size_hint=(1, None), height=dp(36), spacing=dp(8))
        title = Label(text='工程师管理', color=(1, 1, 1, 1), halign='left', valign='middle')
        title.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
        back_btn = Button(text='返回', size_hint=(None, 1), width=dp(72), background_color=(0.6, 0.6, 0.6, 1))
        back_btn.bind(on_press=lambda *_: self._go_back())
        clear_btn = Button(text='清理', size_hint=(None, 1), width=dp(72), background_color=(0.9, 0.2, 0.2, 1))
        top.add_widget(title)
        top.add_widget(back_btn)
        top.add_widget(clear_btn)
        box.add_widget(top)

        # 服务器用户总人数（仅工程师可见）：红色标记
        user_count_label = Label(text='服务器用户总人数：加载中...', size_hint=(1, None), height=dp(22), color=(1, 0.2, 0.2, 1), halign='left', valign='middle')
        user_count_label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
        box.add_widget(user_count_label)

        def _load_user_count():
            def work():
                try:
                    cnt = int(self._api().admin_user_count(self._token()) or 0)
                    Clock.schedule_once(lambda *_, c=cnt: setattr(user_count_label, 'text', f'服务器用户总人数：{c}'), 0)
                except Exception as e:
                    Clock.schedule_once(lambda *_, msg=str(e): setattr(user_count_label, 'text', f'服务器用户总人数：加载失败（{msg}）'), 0)

            Thread(target=work, daemon=True).start()

        _load_user_count()

        def _confirm_popup(title: str, msg: str, on_yes):
            content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(14))
            label = Label(text=str(msg or ''), color=(1, 1, 1, 1), halign='left', valign='top')
            label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
            content.add_widget(label)

            btn_row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
            no_btn = Button(text='取消')
            ok_btn = Button(text='确认', background_color=(0.2, 0.6, 0.8, 1))
            btn_row.add_widget(no_btn)
            btn_row.add_widget(ok_btn)
            content.add_widget(btn_row)

            p = Popup(
                title=str(title or ''),
                content=content,
                size_hint=(0.92, 0.5),
                background_color=(0.0667, 0.149, 0.3098, 1),
                background='',
            )
            no_btn.bind(on_press=lambda *_: p.dismiss())
            ok_btn.bind(on_press=lambda *_: (p.dismiss(), on_yes()))
            p.open()

        def _ask_password_popup(title: str, on_submit):
            content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(14))
            label = Label(text='请输入密码确认操作：', color=(1, 1, 1, 1), halign='left', valign='middle', size_hint=(1, None), height=dp(26))
            label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
            pwd_in = TextInput(hint_text='密码', password=True, multiline=False, size_hint=(1, None), height=dp(44))
            content.add_widget(label)
            content.add_widget(pwd_in)

            btn_row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
            no_btn = Button(text='取消')
            ok_btn = Button(text='确认', background_color=(0.9, 0.2, 0.2, 1))
            btn_row.add_widget(no_btn)
            btn_row.add_widget(ok_btn)
            content.add_widget(btn_row)

            p = Popup(
                title=str(title or ''),
                content=content,
                size_hint=(0.92, 0.45),
                background_color=(0.0667, 0.149, 0.3098, 1),
                background='',
            )
            no_btn.bind(on_press=lambda *_: p.dismiss())

            def _do_submit(*_):
                pwd = str(pwd_in.text or '').strip()
                if not pwd:
                    self._popup('提示', '请输入密码')
                    return
                p.dismiss()
                on_submit(pwd)

            ok_btn.bind(on_press=_do_submit)
            p.open()

        def _do_clear_all():
            def submit(pwd: str):
                def work():
                    try:
                        resp = self._api().engineer_wipe_all(self._token(), pwd)
                        ok = bool(resp.get('ok')) if isinstance(resp, dict) else True
                        msg = '清理成功' if ok else '清理完成'
                        Clock.schedule_once(lambda *_: self._popup('结果', msg), 0)
                        Clock.schedule_once(lambda *_: _load_user_count(), 0)
                    except Exception as e:
                        Clock.schedule_once(lambda *_, msg=str(e): self._popup('清理失败', msg), 0)

                Thread(target=work, daemon=True).start()

            _ask_password_popup('清理数据', submit)

        clear_btn.bind(
            on_press=lambda *_: _confirm_popup(
                '危险操作',
                '将清理服务器内所有用户数据（不可恢复）。\n\n是否继续？',
                _do_clear_all,
            )
        )

        # 创建管理员（工程师）：输入基础用户名，系统自动分配可用用户名，默认密码 admin123
        box.add_widget(Label(text='创建管理员', size_hint=(1, None), height=dp(22), color=(0.9, 0.95, 1, 1)))
        ca_row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        ca_in = TextInput(hint_text='输入基础用户名（例如 admin）', multiline=False, text='admin')
        ca_btn = Button(text='创建', size_hint=(None, 1), width=dp(80))
        ca_row.add_widget(ca_in)
        ca_row.add_widget(ca_btn)
        box.add_widget(ca_row)

        def _do_create_admin(base: str):
            def work():
                try:
                    data = self._api().engineer_create_admin(self._token(), base_username=base)
                    uname = str((data or {}).get('username') or '')
                    pwd = str((data or {}).get('password') or 'admin123')
                    Clock.schedule_once(lambda *_: self._popup('管理员已创建', f'用户名：{uname}\n默认密码：{pwd}'), 0)
                except Exception as e:
                    Clock.schedule_once(lambda *_, msg=str(e): self._popup('创建失败', msg), 0)

            Thread(target=work, daemon=True).start()

        def _on_create_admin(*_):
            base = str(ca_in.text or '').strip() or 'admin'
            _confirm_popup('确认', f'是否确认创建管理员？\n\n基础用户名：{base}\n默认密码：admin123', lambda: _do_create_admin(base))

        ca_btn.bind(on_press=_on_create_admin)

        # 用户ID查询（仅工程师）：显示用户个人资料、密码哈希、最后登录IP
        box.add_widget(Label(text='用户ID查询', size_hint=(1, None), height=dp(22), color=(0.9, 0.95, 1, 1)))
        q_row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        q_in = TextInput(hint_text='输入用户ID（数字）', multiline=False)
        q_btn = Button(text='查询', size_hint=(None, 1), width=dp(80))
        q_row.add_widget(q_in)
        q_row.add_widget(q_btn)
        box.add_widget(q_row)

        def _query_user_detail(*_):
            raw = str(q_in.text or '').strip()
            if not raw.isdigit():
                self._popup('提示', '请输入正确的用户ID（数字）')
                return
            uid = int(raw)

            def work():
                try:
                    data = self._api().engineer_user_detail(self._token(), uid)
                    # 注意：服务器不保存明文密码，只保存密码哈希
                    msg = (
                        f"用户ID：{data.get('id','')}\n"
                        f"用户名：{data.get('username','')}\n"
                        f"角色：{data.get('role','')}\n"
                        f"姓名：{data.get('real_name','')}\n"
                        f"电话：{data.get('phone','')}\n"
                        f"部门：{data.get('department','')}\n"
                        f"创建时间：{data.get('created_at','')}\n"
                        f"最后登录：{data.get('last_login','')}\n"
                        f"最后登录IP：{data.get('last_login_ip','')}\n"
                        f"登录密码哈希：{data.get('password_hash','')}"
                    )
                    Clock.schedule_once(lambda *_: self._popup('用户资料', msg), 0)
                except Exception as e:
                    Clock.schedule_once(lambda *_, msg=str(e): self._popup('查询失败', msg), 0)

            Thread(target=work, daemon=True).start()

        q_btn.bind(on_press=_query_user_detail)

        box.add_widget(Label(text='创建团队', size_hint=(1, None), height=dp(22), color=(0.9, 0.95, 1, 1)))
        grp_row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        self.group_name_input = TextInput(hint_text='新团队名称（最多10字）', multiline=False)
        grp_btn = Button(text='创建团队', size_hint=(None, 1), width=dp(96))
        grp_btn.bind(on_press=lambda *_: self._create_group())
        grp_row.add_widget(self.group_name_input)
        grp_row.add_widget(grp_btn)
        box.add_widget(grp_row)

        box.add_widget(Label(text='版本发布', size_hint=(1, None), height=dp(22), color=(0.9, 0.95, 1, 1)))
        self.ver_input = TextInput(hint_text='最新版本号，例如 1.2.0', multiline=False, size_hint=(1, None), height=dp(44))
        self.ver_note = TextInput(hint_text='版本说明', multiline=True, size_hint=(1, None), height=dp(96))
        ver_btn = Button(text='发布版本提醒', size_hint=(1, None), height=dp(44))
        ver_btn.bind(on_press=lambda *_: self._set_version())
        box.add_widget(self.ver_input)
        box.add_widget(self.ver_note)
        box.add_widget(ver_btn)

        box.add_widget(Label(text='广告发布', size_hint=(1, None), height=dp(22), color=(0.9, 0.95, 1, 1)))
        self.ad_text = TextInput(hint_text='广告文字', multiline=False, size_hint=(1, None), height=dp(44))
        self.ad_img = TextInput(hint_text='图片URL', multiline=False, size_hint=(1, None), height=dp(44))
        self.ad_link = TextInput(hint_text='跳转URL', multiline=False, size_hint=(1, None), height=dp(44))

        # 广告发布：下拉选择展示模式（与首页广告展示效果对应）
        mode_row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        mode_row.add_widget(Label(text='展示模式:', size_hint=(0.3, 1), color=(0.9, 0.95, 1, 1)))
        # 说明："上下滚动" 对应首页的 "垂直滚动"；"左右滚动" 对应 "水平滚动"
        self.ad_scroll_spinner = Spinner(text='上下滚动', values=['上下滚动', '左右滚动', '静止'], size_hint=(0.7, 1))
        mode_row.add_widget(self.ad_scroll_spinner)

        box.add_widget(self.ad_text)
        box.add_widget(self.ad_img)
        box.add_widget(self.ad_link)
        box.add_widget(mode_row)
        box.add_widget(Label(text='提示：广告发布后会展示在首页底部', size_hint=(1, None), height=dp(18), color=(0.82, 0.88, 0.95, 1)))

        footer = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        ad_btn = Button(text='发布广告', background_color=(0.2, 0.6, 0.8, 1))
        ad_btn.bind(on_press=lambda *_: self._set_ads())
        footer.add_widget(ad_btn)
        container.add_widget(footer)

        self.content.add_widget(container)

    def _create_group(self):
        name = (self.group_name_input.text or '').strip()
        if not name:
            self._popup('提示', '请输入团队名称')
            return

        # 团队名称最长 10 字，超出使用 . 表示
        if len(name) > 10:
            name = name[:9] + '.'
            try:
                self.group_name_input.text = name
            except Exception:
                pass

        def work():
            try:
                resp = self._api().create_group(self._token(), name)
                gid = resp.get('id')
                code = resp.get('group_code')
                Clock.schedule_once(lambda *_: self._popup('创建成功', f'团队编号:{gid}\n团队ID:{code}'), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_, msg=str(e): self._popup('错误', msg), 0)

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
                Clock.schedule_once(lambda *_, msg=str(e): self._popup('错误', msg), 0)

        Thread(target=work, daemon=True).start()

    def _set_ads(self):
        text = (self.ad_text.text or '').strip()
        img = (self.ad_img.text or '').strip()
        link = (self.ad_link.text or '').strip()

        if text and img:
            self._popup('提示', '文字广告和图片广告只能选择一种')
            return
        if not text and not img:
            self._popup('提示', '请输入广告文字或图片URL')
            return

        def work():
            try:
                sel = ''
                try:
                    sel = str(getattr(self, 'ad_scroll_spinner', None).text or '')
                except Exception:
                    sel = ''

                if sel == '左右滚动':
                    mode = '水平滚动'
                elif sel == '静止':
                    mode = '静止'
                else:
                    mode = '垂直滚动'

                self._api().set_ads(self._token(), True, text, img, link, mode)

                # 本机立即生效：工程师页默认“垂直滚动”，避免看不到滚动效果
                try:
                    from main import db
                    s = db.get_user_settings('__global__') or {}
                    s['ad_bottom_enabled'] = True
                    s['ad_bottom_text'] = text
                    s['ad_bottom_image_url'] = img
                    s['ad_bottom_text_url'] = link

                    # 互斥：只保留一种
                    if img:
                        s['ad_bottom_text'] = ''
                    if text:
                        s['ad_bottom_image_url'] = ''
                    sel = ''
                    try:
                        sel = str(getattr(self, 'ad_scroll_spinner', None).text or '')
                    except Exception:
                        sel = ''

                    if sel == '左右滚动':
                        s['ad_bottom_scroll_mode'] = '水平滚动'
                    elif sel == '静止':
                        s['ad_bottom_scroll_mode'] = '静止'
                    else:
                        s['ad_bottom_scroll_mode'] = '垂直滚动'
                    db.save_user_settings('__global__', s)
                except Exception:
                    pass

                Clock.schedule_once(lambda *_: self._popup('成功', '广告已发布'), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_, msg=str(e): self._popup('错误', msg), 0)

        Thread(target=work, daemon=True).start()

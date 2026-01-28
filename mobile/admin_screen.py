# Copyright (C) [2026] [晨曦微光]
# 此软件受著作权法保护。未经明确书面许可，任何单位或个人不得复制、分发、修改或用于商业用途。
# APP名称：[晨曦智能打卡]
# 版本号：1.0.0

"""
管理员界面模块
"""


import hashlib
import hmac
import calendar
from kivy.app import App


from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.uix.anchorlayout import AnchorLayout
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.graphics import Color, RoundedRectangle
from datetime import datetime, timedelta

from main import db, StyledButton




class AdminScreen(Screen):
    """管理员界面"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(0.0667, 0.149, 0.3098, 1)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
        self.bind(pos=self.update_bg, size=self.update_bg)
        self.inactive_user_map = {}
        self.current_version = ''
        self.current_version_note = ''
        self.current_version_time = ''
        self.current_announcement = ''
        self.current_announcement_time = ''

        # 主布局


        main_layout = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))


        
        # 顶部栏（移动端适配）
        top_container = BoxLayout(orientation='vertical', size_hint=(1, None), height=dp(48), padding=[dp(8), dp(6)], spacing=dp(4))

        action_row = AnchorLayout(size_hint=(1, None), height=dp(36), anchor_x='right', anchor_y='center')
        btn_box = BoxLayout(size_hint=(None, 1), width=dp(300), spacing=dp(6))
        super_btn = Button(text='超级密码管理', size_hint=(None, 1), width=dp(90), font_size=dp(11))
        super_btn.bind(on_press=self.open_super_password_manager)
        clear_btn = Button(text='清除用户', size_hint=(None, 1), width=dp(70), font_size=dp(11))
        clear_btn.bind(on_press=self.open_clear_users)
        back_btn = Button(text='返回', size_hint=(None, 1), width=dp(50), font_size=dp(11))
        back_btn.bind(on_press=self.go_back)
        logout_btn = Button(text='退出', size_hint=(None, 1), width=dp(50), font_size=dp(11))
        logout_btn.bind(on_press=self.logout_admin)
        btn_box.add_widget(super_btn)
        btn_box.add_widget(clear_btn)
        btn_box.add_widget(back_btn)
        btn_box.add_widget(logout_btn)
        action_row.add_widget(btn_box)


        top_container.add_widget(action_row)



        main_layout.add_widget(top_container)

        # 用户统计与清理
        stats_layout = BoxLayout(orientation='vertical', size_hint=(1, None), height=dp(140), spacing=dp(6), padding=dp(10))
        stats_layout.add_widget(Label(text='用户管理', size_hint=(1, None), height=dp(20), font_size=dp(13), color=(1, 1, 1, 1), bold=True))

        self.user_count_label = Label(text='注册用户：0', size_hint=(1, None), height=dp(20), font_size=dp(12), color=(0.9, 0.95, 1, 1))
        stats_layout.add_widget(self.user_count_label)

        inactive_row = BoxLayout(size_hint=(1, None), height=dp(36), spacing=dp(8))
        inactive_row.add_widget(Label(text='未登录天数', size_hint=(0.28, 1), font_size=dp(12), color=(1, 1, 1, 1)))
        self.inactive_days_spinner = Spinner(text='90', values=['30', '60', '90', '180'], size_hint=(0.2, 1), font_size=dp(12))
        self.inactive_days_spinner.bind(text=self.refresh_inactive_users)
        inactive_row.add_widget(self.inactive_days_spinner)

        self.inactive_user_spinner = Spinner(text='选择待删除用户', values=['暂无数据'], size_hint=(0.52, 1), font_size=dp(12))
        inactive_row.add_widget(self.inactive_user_spinner)
        stats_layout.add_widget(inactive_row)

        delete_btn = StyledButton(text='删除选中用户', font_size=dp(12))
        delete_btn.bind(on_press=self.delete_inactive_user)
        stats_layout.add_widget(delete_btn)

        main_layout.add_widget(stats_layout)

        # 管理员账号设置

        password_card = BoxLayout(orientation='vertical', size_hint=(1, None), height=dp(160), padding=dp(10), spacing=dp(6))

        password_card.add_widget(Label(text='管理员密码修改', size_hint=(1, None), height=dp(22), font_size=dp(14), bold=True, color=(1, 1, 1, 1)))

        user_layout = BoxLayout(size_hint=(1, None), height=dp(36), spacing=dp(8))
        user_layout.add_widget(Label(text='用户名:', size_hint=(0.28, 1), font_size=dp(12), color=(1, 1, 1, 1)))

        self.admin_user_input = TextInput(text='admin', multiline=False, background_color=(0.95, 0.97, 1, 1), foreground_color=(0.1, 0.15, 0.25, 1), font_size=dp(12), padding=[dp(8), dp(8)])


        user_layout.add_widget(self.admin_user_input)

        pwd_layout = BoxLayout(size_hint=(1, None), height=dp(36), spacing=dp(8))
        pwd_layout.add_widget(Label(text='新密码:', size_hint=(0.28, 1), font_size=dp(12), color=(1, 1, 1, 1)))

        self.admin_pwd_input = TextInput(password=True, multiline=False, background_color=(0.95, 0.97, 1, 1), foreground_color=(0.1, 0.15, 0.25, 1), font_size=dp(12), padding=[dp(8), dp(8)])


        pwd_layout.add_widget(self.admin_pwd_input)

        update_btn = StyledButton(text='更新密码', font_size=dp(12))
        update_btn.bind(on_press=self.update_admin_password)


        password_card.add_widget(user_layout)
        password_card.add_widget(pwd_layout)
        password_card.add_widget(update_btn)

        main_layout.add_widget(password_card)

        # 管理标签
        tag_layout = BoxLayout(size_hint=(1, None), height=dp(40), spacing=dp(8), padding=[dp(10), 0])
        announcement_tab = Button(text='公告发布', font_size=dp(12), background_color=(0.2, 0.6, 0.8, 1))
        version_tab = Button(text='版本升级', font_size=dp(12), background_color=(0.2, 0.6, 0.8, 1))
        ad_tab = Button(text='广告管理', font_size=dp(12), background_color=(0.2, 0.6, 0.8, 1))
        announcement_tab.bind(on_press=self.open_announcement_popup)
        version_tab.bind(on_press=self.open_version_popup)
        ad_tab.bind(on_press=self.open_ad_manager)
        tag_layout.add_widget(announcement_tab)
        tag_layout.add_widget(version_tab)
        tag_layout.add_widget(ad_tab)
        main_layout.add_widget(tag_layout)

        info_layout = BoxLayout(orientation='vertical', size_hint=(1, None), height=dp(44), spacing=dp(4), padding=[dp(10), 0])
        self.announcement_info_label = Label(text='当前公告：未发布', size_hint=(1, None), height=dp(20), font_size=dp(11), color=(0.85, 0.9, 1, 1))
        self.version_info_label = Label(text='当前发布版本：未设置', size_hint=(1, None), height=dp(20), font_size=dp(11), color=(0.85, 0.9, 1, 1))
        info_layout.add_widget(self.announcement_info_label)
        info_layout.add_widget(self.version_info_label)
        main_layout.add_widget(info_layout)

        # 筛选区域



        filter_layout = BoxLayout(size_hint=(1, None), height=dp(50), spacing=dp(8), padding=[dp(8), dp(6)])

        # 用户筛选
        self.user_spinner = Spinner(
            text='所有用户',
            values=['所有用户', '用户搜索'],
            size_hint=(0.38, 1),
            font_size=dp(11)
        )
        self.user_spinner.bind(text=self.handle_user_spinner)
        filter_layout.add_widget(self.user_spinner)

        
        # 状态筛选
        self.status_spinner = Spinner(
            text='所有状态',
            values=['所有状态', '打卡成功', '打卡失败', '补录'],
            size_hint=(0.38, 1),
            font_size=dp(11)
        )
        filter_layout.add_widget(self.status_spinner)

        
        # 筛选按钮
        filter_btn = Button(text='开始筛选', size_hint=(0.24, 1), font_size=dp(11))
        filter_btn.bind(on_press=self.filter_records)
        filter_layout.add_widget(filter_btn)



        
        main_layout.add_widget(filter_layout)
        
        # 记录标题
        titles = BoxLayout(size_hint=(1, None), height=dp(28), padding=dp(8))

        titles.add_widget(Label(text='时间', size_hint=(0.22, 1), bold=True, font_size=dp(12), color=(0.9, 0.93, 1, 1)))
        titles.add_widget(Label(text='用户', size_hint=(0.28, 1), bold=True, font_size=dp(12), color=(0.9, 0.93, 1, 1)))
        titles.add_widget(Label(text='状态', size_hint=(0.18, 1), bold=True, font_size=dp(12), color=(0.9, 0.93, 1, 1)))
        titles.add_widget(Label(text='操作', size_hint=(0.32, 1), bold=True, font_size=dp(12), color=(0.9, 0.93, 1, 1)))

        main_layout.add_widget(titles)

        
        # 滚动视图容器
        scroll_view = ScrollView(size_hint=(1, 1))

        
        # 记录列表容器
        self.records_layout = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.records_layout.bind(minimum_height=self.records_layout.setter('height'))
        
        scroll_view.add_widget(self.records_layout)
        main_layout.add_widget(scroll_view)
        
        self.add_widget(main_layout)
        
        # 加载用户列表和记录
        Clock.schedule_once(self.load_data, 0.1)
    
    def on_enter(self):
        """进入界面时刷新数据"""
        app = App.get_running_app()
        user_data = getattr(app, 'user_data', {}) if hasattr(app, 'user_data') else {}
        if not user_data or not user_data.get('is_admin'):
            self.show_popup("提示", "无管理员权限，请重新登录")
            self.manager.current = 'login'
            return
        self.load_data(0)


    def update_bg(self, *args):
        """更新背景尺寸"""
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
    
    def load_data(self, dt):
        """加载用户列表和记录"""
        self.purge_old_attendance_records()

        # 加载用户列表
        users = db.get_all_users()
        abnormal_users = self.get_abnormal_users(users)
        self.user_spinner.values = ['所有用户', '用户搜索'] + abnormal_users

        if self.user_spinner.text not in self.user_spinner.values:
            self.user_spinner.text = '所有用户'
        self.user_count_label.text = f"注册用户：{len(users)}"



        self.load_version_settings()
        self.load_announcement_settings()
        self.refresh_inactive_users()

        # 加载所有记录
        self.load_all_records()






    def handle_user_spinner(self, spinner, text):
        if text == '用户搜索':
            spinner.text = '所有用户'
            self.open_user_search()

    def open_user_search(self):
        self.manager.current = 'user_search'

    def get_abnormal_users(self, users):
        now = datetime.now()
        start_dt = self.get_month_start(now, 0)
        end_dt = self.get_month_start(start_dt, -1)
        year = start_dt.year
        month = start_dt.month
        days_in_month = calendar.monthrange(year, month)[1]
        if year == now.year and month == now.month:
            days_in_month = min(days_in_month, now.day)
        total_days = {f"{year}-{month:02d}-{day:02d}" for day in range(1, days_in_month + 1)}

        abnormal_users = []
        for username in users:
            record = db.get_user_record(username) if hasattr(db, 'get_user_record') else {}
            if record.get('is_admin'):
                continue
            records = db.get_user_attendance(username)
            abnormal_flag = False
            day_status_map = {}
            for item in records:
                try:
                    record_time = datetime.fromisoformat(item.get('timestamp', ''))
                except ValueError:
                    continue
                if not (start_dt <= record_time < end_dt):
                    continue
                day_key = record_time.strftime("%Y-%m-%d")
                day_status_map.setdefault(day_key, []).append(item.get('status'))
                if item.get('status') not in ("打卡成功", "补录"):
                    abnormal_flag = True

            if not abnormal_flag:
                valid_days = {
                    day for day, statuses in day_status_map.items()
                    if any(status in ("打卡成功", "补录") for status in statuses)
                }
                if total_days - valid_days:
                    abnormal_flag = True

            if abnormal_flag:
                abnormal_users.append(username)

        return abnormal_users



    def get_month_start(self, base_date, offset_months):

        year = base_date.year
        month = base_date.month - offset_months
        while month <= 0:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1
        return datetime(year, month, 1)


    def purge_old_attendance_records(self):
        if not hasattr(db, 'attendance_store'):
            return
        now = datetime.now()
        cutoff = self.get_month_start(now, 2)
        for record_id in list(db.attendance_store.keys()):
            record = db.attendance_store.get(record_id)
            timestamp_text = record.get('timestamp', '')
            try:
                record_time = datetime.fromisoformat(timestamp_text)
            except ValueError:
                record_time = None
            if record_time and record_time < cutoff:
                db.attendance_store.delete(record_id)

    def load_all_records(self):
        """加载所有打卡记录"""
        self.records_layout.clear_widgets()
        
        records = db.get_all_attendance()
        
        for record in records:
            self.add_record_row(record)

    
    def add_record_row(self, record):
        """添加记录行"""
        row = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(40),
            padding=dp(5),
            spacing=dp(5)
        )
        
        # 设置行背景
        with row.canvas.before:
            Color(0.95, 0.95, 0.95, 1)
            RoundedRectangle(pos=row.pos, size=row.size, radius=[5])
        
        # 时间
        timestamp = datetime.fromisoformat(record['timestamp'])
        time_str = timestamp.strftime("%m-%d %H:%M")
        time_label = Label(text=time_str, size_hint=(0.22, 1), font_size=dp(11), color=(1, 1, 1, 1))

        # 用户名（可横向滚动查看）
        user_scroll = ScrollView(size_hint=(0.28, 1), do_scroll_x=True, do_scroll_y=False, bar_width=dp(2))
        user_label = Label(text=record['username'], size_hint=(None, 1), font_size=dp(11), color=(1, 1, 1, 1))
        user_label.bind(texture_size=lambda instance, value: setattr(instance, 'width', max(value[0], dp(80))))
        user_scroll.add_widget(user_label)

        # 状态
        status_color = (0.2, 0.8, 0.2, 1) if record['status'] == "打卡成功" else (0.8, 0.2, 0.2, 1)
        status_label = Label(text=record['status'], size_hint=(0.18, 1), font_size=dp(11), color=status_color)

        # 操作按钮容器
        action_layout = BoxLayout(size_hint=(0.32, 1), spacing=dp(4))

        
        # 查看详情按钮
        detail_btn = Button(text='详情', font_size=dp(11), size_hint=(None, 1), width=dp(52))
        detail_btn.record = record
        detail_btn.bind(on_press=self.show_record_detail)
        
        # 补录按钮（仅对失败记录显示）
        if record['status'] == '打卡失败':
            reapply_btn = Button(text='补录', font_size=dp(11), size_hint=(None, 1), width=dp(52), background_color=(0.2, 0.6, 0.8, 1))
            reapply_btn.record_id = record.get('record_id', '')
            reapply_btn.bind(on_press=self.approve_reapply)
            action_layout.add_widget(reapply_btn)

        else:
            # 占位空间
            action_layout.add_widget(Label(size_hint=(None, 1), width=dp(52)))
        
        action_layout.add_widget(detail_btn)

        
        row.add_widget(time_label)
        row.add_widget(user_scroll)
        row.add_widget(status_label)
        row.add_widget(action_layout)

        
        self.records_layout.add_widget(row)

    def add_empty_record_row(self, username, created_at):
        row = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(40),
            padding=dp(5),
            spacing=dp(5)
        )

        with row.canvas.before:
            Color(0.3, 0.35, 0.5, 1)
            RoundedRectangle(pos=row.pos, size=row.size, radius=[5])

        display_time = created_at if created_at else '未知'
        time_label = Label(text=f"注册: {display_time}", size_hint=(0.22, 1), font_size=dp(10), color=(1, 1, 1, 1))

        user_scroll = ScrollView(size_hint=(0.28, 1), do_scroll_x=True, do_scroll_y=False, bar_width=dp(2))
        user_label = Label(text=username, size_hint=(None, 1), font_size=dp(11), color=(1, 1, 1, 1))
        user_label.bind(texture_size=lambda instance, value: setattr(instance, 'width', max(value[0], dp(80))))
        user_scroll.add_widget(user_label)

        status_label = Label(text='未打卡', size_hint=(0.18, 1), font_size=dp(11), color=(0.9, 0.75, 0.2, 1))
        action_layout = BoxLayout(size_hint=(0.32, 1), spacing=dp(4))
        empty_label = Label(text='—', size_hint=(None, 1), width=dp(52), color=(1, 1, 1, 1))
        detail_btn = Button(text='详情', font_size=dp(11), size_hint=(None, 1), width=dp(52))
        detail_btn.bind(on_press=lambda x: self.show_user_detail(username))
        action_layout.add_widget(empty_label)
        action_layout.add_widget(detail_btn)

        row.add_widget(time_label)
        row.add_widget(user_scroll)
        row.add_widget(status_label)
        row.add_widget(action_layout)


        self.records_layout.add_widget(row)
    
    def filter_records(self, instance):

        """筛选记录"""
        selected_user = self.user_spinner.text
        selected_status = self.status_spinner.text

        self.records_layout.clear_widgets()

        records = db.get_all_attendance()

        matched = False


        for record in records:
            # 用户筛选
            if selected_user != '所有用户' and record['username'] != selected_user:
                continue

            # 状态筛选
            if selected_status != '所有状态' and record['status'] != selected_status:
                continue

            matched = True
            self.add_record_row(record)

        if not matched and selected_user != '所有用户' and selected_status == '所有状态':
            record = db.get_user_record(selected_user) if hasattr(db, 'get_user_record') else {}
            created_at = record.get('created_at', '')
            self.add_empty_record_row(selected_user, created_at)

    
    def show_record_detail(self, instance):
        """显示记录详情"""
        record = instance.record
        self.show_user_detail(record['username'], record)

    def show_user_detail(self, username, record=None):
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(20))

        profile = db.get_user_profile(username) if hasattr(db, 'get_user_profile') else {}
        real_name = profile.get('real_name') or '未填写'
        phone = profile.get('phone') or '未填写'
        department = profile.get('department') or '未填写'
        created_at = profile.get('created_at') or '—'
        last_login = profile.get('last_login') or '—'

        base_details = (
            f"用户: {username}\n"
            f"姓名: {real_name}\n"
            f"手机号: {phone}\n"
            f"部门/岗位: {department}\n"
            f"注册时间: {created_at}\n"
            f"最近登录: {last_login}"
        )

        if record:
            extra_details = (
                f"\n时间: {datetime.fromisoformat(record['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}"
                f"\n状态: {record['status']}"
                f"\n位置: {record['location']}"
                f"\n备注: {record.get('notes', '无')}"
            )
        else:
            extra_details = "\n暂无打卡记录"

        detail_label = Label(text=base_details + extra_details, halign='left', valign='top')
        detail_label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
        content.add_widget(detail_label)

        btn_layout = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        delete_btn = Button(text='删除', background_color=(0.8, 0.2, 0.2, 1))
        close_btn = Button(text='关闭', background_color=(0.6, 0.6, 0.6, 1))
        btn_layout.add_widget(delete_btn)
        btn_layout.add_widget(close_btn)

        content.add_widget(btn_layout)

        popup = Popup(title='用户详情',
                     content=content,
                     size_hint=(0.9, 0.7),
                     background_color=(0.0667, 0.149, 0.3098, 1),
                     background='')

        delete_btn.bind(on_press=lambda x: self.open_delete_user_popup(username, popup))
        close_btn.bind(on_press=lambda x: popup.dismiss())
        popup.open()


    
    def open_delete_user_popup(self, username, parent_popup):
        record = db.get_user_record(username) if hasattr(db, 'get_user_record') else {}
        if record.get('is_admin'):
            self.show_popup("提示", "管理员账号不可删除")
            return

        def open_confirm():
            content = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(20))
            content.add_widget(Label(text=f"确认删除用户 {username}？\n该用户全部资料将被清除。", color=(1, 1, 1, 1)))
            btn_layout = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
            yes_btn = Button(text='确认删除', background_color=(0.8, 0.2, 0.2, 1))
            no_btn = Button(text='退出', background_color=(0.6, 0.6, 0.6, 1))
            btn_layout.add_widget(yes_btn)
            btn_layout.add_widget(no_btn)
            content.add_widget(btn_layout)

            popup = Popup(title='删除确认', content=content, size_hint=(0.85, 0.4), background_color=(0.0667, 0.149, 0.3098, 1), background='')

            yes_btn.bind(on_press=lambda x: self.confirm_delete_user_from_detail(username, parent_popup, popup))
            no_btn.bind(on_press=lambda x: popup.dismiss())
            popup.open()

        self.require_super_password(open_confirm)


    def confirm_delete_user_from_detail(self, username, parent_popup, popup):
        if hasattr(db, 'delete_user') and db.delete_user(username):
            popup.dismiss()
            parent_popup.dismiss()
            self.load_data(0)
            self.show_popup("成功", f"已删除用户 {username}")
        else:
            popup.dismiss()
            self.show_popup("失败", "删除失败或用户不存在")

    def approve_reapply(self, instance):
        """批准补录申请"""
        record_id = instance.record_id

        
        if db.update_attendance_status(record_id, '补录'):
            self.show_popup("成功", "补录成功")
            # 刷新记录
            self.load_all_records()
        else:
            self.show_popup("失败", "补录失败，记录不存在")

    def update_admin_password(self, instance):
        """管理员修改密码"""
        username = self.admin_user_input.text.strip()
        new_password = self.admin_pwd_input.text.strip()

        if not username or not new_password:
            self.show_popup("错误", "请输入用户名和新密码")
            return

        if len(new_password) < 6:
            self.show_popup("错误", "密码长度至少6位")
            return

        success, message = db.update_user_password(username, new_password)
        if success:
            self.admin_pwd_input.text = ''
            self.show_popup("成功", message)
        else:
            self.show_popup("失败", message)

    def load_version_settings(self):
        settings = db.get_user_settings('__global__') or {}
        self.current_version = settings.get('latest_version', '')
        self.current_version_note = settings.get('latest_version_note', '')
        self.current_version_time = settings.get('latest_version_time', '')

        if self.current_version:
            display_time = f" {self.current_version_time}" if self.current_version_time else ''
            self.version_info_label.text = f"当前发布版本：{self.current_version}{display_time}"
        else:
            self.version_info_label.text = "当前发布版本：未设置"

    def open_version_popup(self, instance):
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(20))
        display_time = f" {self.current_version_time}" if self.current_version_time else ''
        if self.current_version:
            info_text = f"当前发布版本：{self.current_version}{display_time}\n{self.current_version_note or '暂无升级说明'}"
        else:
            info_text = "当前发布版本：未设置"
        info_label = Label(text=info_text, halign='left', valign='top', color=(0.9, 0.95, 1, 1))
        info_label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
        content.add_widget(info_label)

        version_row = BoxLayout(size_hint=(1, None), height=dp(36), spacing=dp(8))
        version_row.add_widget(Label(text='最新版本', size_hint=(0.3, 1), font_size=dp(12), color=(1, 1, 1, 1)))
        version_input = TextInput(multiline=False, text=self.current_version, hint_text='例如 1.0.1', font_size=dp(12), background_color=(0.95, 0.97, 1, 1), foreground_color=(0.1, 0.15, 0.25, 1))
        version_row.add_widget(version_input)

        note_row = BoxLayout(size_hint=(1, None), height=dp(64), spacing=dp(8))
        note_row.add_widget(Label(text='升级说明', size_hint=(0.3, 1), font_size=dp(12), color=(1, 1, 1, 1)))
        note_input = TextInput(multiline=True, text=self.current_version_note, hint_text='填写升级内容说明', font_size=dp(12), background_color=(0.95, 0.97, 1, 1), foreground_color=(0.1, 0.15, 0.25, 1))
        note_row.add_widget(note_input)

        btn_layout = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        publish_btn = Button(text='发布升级', background_color=(0.2, 0.6, 0.8, 1))
        cancel_btn = Button(text='取消', background_color=(0.6, 0.6, 0.6, 1))
        btn_layout.add_widget(publish_btn)
        btn_layout.add_widget(cancel_btn)

        content.add_widget(version_row)
        content.add_widget(note_row)
        content.add_widget(btn_layout)


        popup = Popup(title='版本升级', content=content, size_hint=(0.9, 0.6), background_color=(0.0667, 0.149, 0.3098, 1), background='')
        publish_btn.bind(on_press=lambda x: self.publish_version_from_popup(version_input.text, note_input.text, popup))
        cancel_btn.bind(on_press=lambda x: popup.dismiss())
        popup.open()

    def publish_version_from_popup(self, version_text, note_text, popup):
        version_text = version_text.strip()
        note_text = note_text.strip()
        if not version_text:
            self.show_popup("错误", "请输入最新版本号")
            return

        def apply_publish():
            settings = db.get_user_settings('__global__') or {}
            settings['latest_version'] = version_text
            settings['latest_version_note'] = note_text
            settings['latest_version_time'] = datetime.now().strftime("%Y-%m-%d %H:%M")
            db.save_user_settings('__global__', settings)
            self.load_version_settings()
            popup.dismiss()
            self.show_popup("成功", "版本升级信息已发布")

        self.require_super_password(apply_publish)


    def load_announcement_settings(self):
        settings = db.get_user_settings('__global__') or {}
        self.current_announcement = settings.get('announcement_text', '')
        self.current_announcement_time = settings.get('announcement_time', '')
        if self.current_announcement:
            time_display = f" {self.current_announcement_time}" if self.current_announcement_time else ''
            text = self.current_announcement
            self.announcement_info_label.text = f"当前公告：{text[:12]}...{time_display}" if len(text) > 12 else f"当前公告：{text}{time_display}"
        else:
            self.announcement_info_label.text = '当前公告：未发布'

    def open_announcement_popup(self, instance):
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(20))
        display_time = f" {self.current_announcement_time}" if self.current_announcement_time else ''
        if self.current_announcement:
            info_text = f"当前公告：{self.current_announcement}{display_time}"
        else:
            info_text = "当前公告：未发布"
        info_label = Label(text=info_text, halign='left', valign='top', color=(0.9, 0.95, 1, 1))
        info_label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
        content.add_widget(info_label)

        row = BoxLayout(size_hint=(1, None), height=dp(70), spacing=dp(8))
        row.add_widget(Label(text='公告内容', size_hint=(0.28, 1), font_size=dp(12), color=(1, 1, 1, 1)))
        announcement_input = TextInput(multiline=True, text=self.current_announcement, hint_text='请输入公告内容', font_size=dp(12), background_color=(0.95, 0.97, 1, 1), foreground_color=(0.1, 0.15, 0.25, 1))
        row.add_widget(announcement_input)

        btn_layout = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        publish_btn = Button(text='发布公告', background_color=(0.2, 0.6, 0.8, 1))
        cancel_btn = Button(text='取消', background_color=(0.6, 0.6, 0.6, 1))
        btn_layout.add_widget(publish_btn)
        btn_layout.add_widget(cancel_btn)

        content.add_widget(row)
        content.add_widget(btn_layout)


        popup = Popup(title='公告发布', content=content, size_hint=(0.9, 0.5), background_color=(0.0667, 0.149, 0.3098, 1), background='')
        publish_btn.bind(on_press=lambda x: self.publish_announcement_from_popup(announcement_input.text, popup))
        cancel_btn.bind(on_press=lambda x: popup.dismiss())
        popup.open()

    def publish_announcement_from_popup(self, text, popup):
        text = text.strip()
        if not text:
            self.show_popup("错误", "请输入公告内容")
            return

        def apply_publish():
            settings = db.get_user_settings('__global__') or {}
            settings['announcement_text'] = text
            settings['announcement_time'] = datetime.now().strftime("%Y-%m-%d %H:%M")
            db.save_user_settings('__global__', settings)
            self.load_announcement_settings()
            popup.dismiss()
            self.show_popup("成功", "公告已发布")

        self.require_super_password(apply_publish)

    def verify_super_password_value(self, password, stored_value):
        if not stored_value:
            return False
        if hasattr(db, '_verify_password') and stored_value.startswith('pbkdf2$'):
            is_valid, _ = db._verify_password(password, stored_value)
            return is_valid
        return hmac.compare_digest(password, stored_value)

    def require_super_password(self, on_success):
        settings = db.get_user_settings('__global__') or {}
        stored_value = settings.get('super_password', '')
        if not stored_value:
            self.show_popup("提示", "请先在超级密码管理中设置超级密码")
            return

        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(20))
        content.add_widget(Label(text='请输入超级密码确认操作', color=(0.9, 0.95, 1, 1)))
        password_input = TextInput(password=True, multiline=False, size_hint=(1, None), height=dp(48), background_color=(0.95, 0.97, 1, 1), foreground_color=(0.1, 0.15, 0.25, 1))
        content.add_widget(password_input)

        btn_layout = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        confirm_btn = Button(text='确认', background_color=(0.2, 0.6, 0.8, 1))
        cancel_btn = Button(text='取消', background_color=(0.6, 0.6, 0.6, 1))
        btn_layout.add_widget(confirm_btn)
        btn_layout.add_widget(cancel_btn)
        content.add_widget(btn_layout)

        popup = Popup(title='超级密码确认', content=content, size_hint=(0.85, 0.45), background_color=(0.0667, 0.149, 0.3098, 1), background='')

        def handle_confirm(instance):
            password = password_input.text.strip()
            if not password:
                self.show_popup("错误", "请输入超级密码")
                return
            if not self.verify_super_password_value(password, stored_value):
                self.show_popup("错误", "超级密码错误")
                return
            popup.dismiss()
            on_success()

        confirm_btn.bind(on_press=handle_confirm)
        cancel_btn.bind(on_press=lambda x: popup.dismiss())
        popup.open()

    def open_super_password_manager(self, instance):
        settings = db.get_user_settings('__global__') or {}
        stored_value = settings.get('super_password', '')
        has_password = bool(stored_value)

        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(20))
        status_text = '已设置超级密码' if has_password else '未设置超级密码'
        content.add_widget(Label(text=status_text, color=(0.9, 0.95, 1, 1)))

        current_input = TextInput(
            hint_text='当前超级密码' if has_password else '当前超级密码（未设置可空）',
            password=True,
            multiline=False,
            size_hint=(1, None),
            height=dp(48),
            background_color=(0.95, 0.97, 1, 1),
            foreground_color=(0.1, 0.15, 0.25, 1)
        )
        new_input = TextInput(
            hint_text='新超级密码',
            password=True,
            multiline=False,
            size_hint=(1, None),
            height=dp(48),
            background_color=(0.95, 0.97, 1, 1),
            foreground_color=(0.1, 0.15, 0.25, 1)
        )
        confirm_input = TextInput(
            hint_text='确认新超级密码',
            password=True,
            multiline=False,
            size_hint=(1, None),
            height=dp(48),
            background_color=(0.95, 0.97, 1, 1),
            foreground_color=(0.1, 0.15, 0.25, 1)
        )

        content.add_widget(current_input)
        content.add_widget(new_input)
        content.add_widget(confirm_input)

        btn_layout = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        save_btn = Button(text='确认', background_color=(0.2, 0.6, 0.8, 1))
        cancel_btn = Button(text='退出', background_color=(0.6, 0.6, 0.6, 1))
        btn_layout.add_widget(save_btn)
        btn_layout.add_widget(cancel_btn)
        content.add_widget(btn_layout)

        popup = Popup(title='超级密码管理', content=content, size_hint=(0.9, 0.6), background_color=(0.0667, 0.149, 0.3098, 1), background='')

        def handle_save(instance):
            current_value = current_input.text.strip()
            new_value = new_input.text.strip()
            confirm_value = confirm_input.text.strip()

            if has_password:
                if not current_value:
                    self.show_popup("错误", "请输入当前超级密码")
                    return
                if not self.verify_super_password_value(current_value, stored_value):
                    self.show_popup("错误", "当前超级密码错误")
                    return

            if not new_value or not confirm_value:
                self.show_popup("错误", "请输入新超级密码并确认")
                return
            if len(new_value) < 6:
                self.show_popup("错误", "超级密码长度至少6位")
                return
            if new_value != confirm_value:
                self.show_popup("错误", "两次输入的新密码不一致")
                return

            hashed = db._hash_password(new_value) if hasattr(db, '_hash_password') else new_value
            settings['super_password'] = hashed
            db.save_user_settings('__global__', settings)
            popup.dismiss()
            self.show_popup("成功", "超级密码已更新")

        save_btn.bind(on_press=handle_save)
        cancel_btn.bind(on_press=lambda x: popup.dismiss())
        popup.open()

    def open_clear_users(self, instance):
        def open_confirm():
            content = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(20))
            content.add_widget(Label(text='确认清除所有普通用户及其打卡数据？', color=(1, 1, 1, 1)))
            btn_layout = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
            yes_btn = Button(text='确认清除', background_color=(0.8, 0.2, 0.2, 1))
            no_btn = Button(text='退出', background_color=(0.6, 0.6, 0.6, 1))
            btn_layout.add_widget(yes_btn)
            btn_layout.add_widget(no_btn)
            content.add_widget(btn_layout)

            popup = Popup(title='清除用户确认', content=content, size_hint=(0.88, 0.4), background_color=(0.0667, 0.149, 0.3098, 1), background='')
            yes_btn.bind(on_press=lambda x: self.confirm_clear_users(popup))
            no_btn.bind(on_press=lambda x: popup.dismiss())
            popup.open()

        self.require_super_password(open_confirm)

    def confirm_clear_users(self, popup):
        deleted = 0
        for username in db.get_all_users():
            record = db.get_user_record(username) if hasattr(db, 'get_user_record') else {}
            if record.get('is_admin'):
                continue
            if db.delete_user(username):
                deleted += 1
        if popup:
            popup.dismiss()
        self.load_data(0)
        self.show_popup('完成', f'已清除 {deleted} 个普通用户数据')

    def refresh_inactive_users(self, *args):


        try:
            days = int(self.inactive_days_spinner.text)
        except ValueError:
            days = 90

        cutoff = datetime.now() - timedelta(days=days)
        users = db.get_all_users()
        self.inactive_user_map = {}
        display_values = []

        for username in users:
            record = db.get_user_record(username) if hasattr(db, 'get_user_record') else {}
            if record.get('is_admin'):
                continue
            last_login = record.get('last_login') or record.get('created_at') or ''
            if last_login:
                try:
                    last_login_dt = datetime.fromisoformat(last_login)
                except ValueError:
                    last_login_dt = None
            else:
                last_login_dt = None

            if last_login_dt is None or last_login_dt <= cutoff:
                last_text = last_login_dt.strftime('%Y-%m-%d') if last_login_dt else '未登录'
                label = f"{username} - {last_text}"
                display_values.append(label)
                self.inactive_user_map[label] = username

        if display_values:
            self.inactive_user_spinner.values = display_values
            self.inactive_user_spinner.text = display_values[0]
        else:
            self.inactive_user_spinner.values = ['暂无数据']
            self.inactive_user_spinner.text = '暂无数据'

    def delete_inactive_user(self, instance):
        label = self.inactive_user_spinner.text
        username = self.inactive_user_map.get(label)
        if not username:
            self.show_popup("提示", "暂无可删除用户")
            return

        content = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(20))
        content.add_widget(Label(text=f"确认删除用户 {username}？\n该用户记录将被清理。", color=(1, 1, 1, 1)))
        btn_layout = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        yes_btn = Button(text='删除', background_color=(0.8, 0.2, 0.2, 1))
        no_btn = Button(text='取消', background_color=(0.6, 0.6, 0.6, 1))
        btn_layout.add_widget(yes_btn)
        btn_layout.add_widget(no_btn)
        content.add_widget(btn_layout)

        popup = Popup(title='删除确认', content=content, size_hint=(0.85, 0.4), background_color=(0.0667, 0.149, 0.3098, 1), background='')
        yes_btn.bind(on_press=lambda x: self.confirm_delete_user(username, popup))
        no_btn.bind(on_press=lambda x: popup.dismiss())
        popup.open()

    def confirm_delete_user(self, username, popup):
        if hasattr(db, 'delete_user') and db.delete_user(username):
            popup.dismiss()
            self.refresh_inactive_users()
            self.load_data(0)
            self.show_popup("成功", f"已删除用户 {username}")
        else:
            popup.dismiss()
            self.show_popup("失败", "删除失败或用户不存在")

    def open_ad_manager(self, instance):
        """进入广告管理页面"""
        self.manager.current = 'ad_manager'


    def logout_admin(self, instance):
        """退出登录"""
        app = App.get_running_app()
        if hasattr(app, 'current_user'):
            delattr(app, 'current_user')
        if hasattr(app, 'user_data'):
            delattr(app, 'user_data')
        self.manager.current = 'login'

    def go_back(self, instance):
        """返回主界面"""
        self.manager.current = 'main'


    
    def show_popup(self, title, message):
        """显示提示弹窗"""
        popup = Popup(title=title,
                     content=Label(text=message),
                     size_hint=(0.8, 0.4),
                     background_color=(0.0667, 0.149, 0.3098, 1),
                     background='')

        popup.open()


class UserSearchScreen(Screen):
    """用户搜索页面"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(0.0667, 0.149, 0.3098, 1)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
        self.bind(pos=self.update_bg, size=self.update_bg)

        main_layout = BoxLayout(orientation='vertical', spacing=dp(4), padding=dp(10))

        top_container = BoxLayout(orientation='vertical', size_hint=(1, None), height=dp(68), padding=[dp(8), dp(3)], spacing=dp(2))


        title_label = Label(text='用户搜索', font_size=dp(18), bold=True, color=(1, 1, 1, 1))
        title_box = AnchorLayout(size_hint=(1, None), height=dp(34), anchor_x='center', anchor_y='center')
        title_box.add_widget(title_label)

        action_row = AnchorLayout(size_hint=(1, None), height=dp(38), anchor_x='right', anchor_y='center')
        btn_box = BoxLayout(size_hint=(None, 1), width=dp(140), spacing=dp(8))
        back_btn = Button(text='返回', size_hint=(None, 1), width=dp(60), font_size=dp(12))
        back_btn.bind(on_press=self.go_back)
        logout_btn = Button(text='退出', size_hint=(None, 1), width=dp(60), font_size=dp(12))
        logout_btn.bind(on_press=self.logout_admin)
        btn_box.add_widget(back_btn)
        btn_box.add_widget(logout_btn)
        action_row.add_widget(btn_box)

        top_container.add_widget(title_box)
        top_container.add_widget(action_row)
        main_layout.add_widget(top_container)

        search_layout = BoxLayout(orientation='vertical', spacing=dp(4), padding=[dp(10), dp(2)])


        user_row = BoxLayout(size_hint=(1, None), height=dp(36), spacing=dp(8))
        user_row.add_widget(Label(text='用户名', size_hint=(0.25, 1), font_size=dp(12), color=(1, 1, 1, 1)))
        self.search_input = TextInput(multiline=False, hint_text='输入要查询的用户名', font_size=dp(12), background_color=(0.95, 0.97, 1, 1), foreground_color=(0.1, 0.15, 0.25, 1))
        user_row.add_widget(self.search_input)

        month_row = BoxLayout(size_hint=(1, None), height=dp(36), spacing=dp(8))
        month_row.add_widget(Label(text='月份', size_hint=(0.25, 1), font_size=dp(12), color=(1, 1, 1, 1)))
        self.month_spinner = Spinner(text='', values=[], size_hint=(0.45, 1), font_size=dp(12))
        month_row.add_widget(self.month_spinner)
        search_btn = Button(text='查询', size_hint=(0.3, 1), font_size=dp(12), background_color=(0.2, 0.6, 0.8, 1))
        search_btn.bind(on_press=self.search_user)
        month_row.add_widget(search_btn)

        search_layout.add_widget(user_row)
        search_layout.add_widget(month_row)
        main_layout.add_widget(search_layout)

        header = BoxLayout(size_hint=(1, None), height=dp(28), padding=dp(6))
        header.add_widget(Label(text='时间', size_hint=(0.35, 1), bold=True, font_size=dp(12), color=(0.9, 0.93, 1, 1)))
        header.add_widget(Label(text='状态', size_hint=(0.25, 1), bold=True, font_size=dp(12), color=(0.9, 0.93, 1, 1)))
        header.add_widget(Label(text='备注', size_hint=(0.4, 1), bold=True, font_size=dp(12), color=(0.9, 0.93, 1, 1)))
        main_layout.add_widget(header)


        scroll_view = ScrollView(size_hint=(1, 1))
        self.results_layout = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.results_layout.bind(minimum_height=self.results_layout.setter('height'))
        scroll_view.add_widget(self.results_layout)
        main_layout.add_widget(scroll_view)

        self.add_widget(main_layout)

    def update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def get_month_start(self, base_date, offset_months):
        year = base_date.year
        month = base_date.month - offset_months
        while month <= 0:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1
        return datetime(year, month, 1)


    def update_month_options(self):
        now = datetime.now()
        months = [self.get_month_start(now, offset).strftime('%Y-%m') for offset in range(0, 3)]
        self.month_spinner.values = months
        if self.month_spinner.text not in months:
            self.month_spinner.text = months[0] if months else ''

    def purge_old_attendance_records(self):
        if not hasattr(db, 'attendance_store'):
            return
        now = datetime.now()
        cutoff = self.get_month_start(now, 2)
        for record_id in list(db.attendance_store.keys()):
            record = db.attendance_store.get(record_id)
            timestamp_text = record.get('timestamp', '')
            try:
                record_time = datetime.fromisoformat(timestamp_text)
            except ValueError:
                record_time = None
            if record_time and record_time < cutoff:
                db.attendance_store.delete(record_id)

    def on_enter(self):
        self.update_month_options()
        self.results_layout.clear_widgets()
        self.purge_old_attendance_records()

    def search_user(self, instance):
        username = self.search_input.text.strip()
        if not username:
            self.show_popup("提示", "请输入要查询的用户名")
            return
        record = db.get_user_record(username) if hasattr(db, 'get_user_record') else {}
        if not record:
            self.show_popup("提示", "用户不存在")
            return
        month_text = self.month_spinner.text
        if not month_text:
            self.show_popup("提示", "请选择月份")
            return
        self.load_user_records(username, month_text)

    def load_user_records(self, username, month_text):
        self.results_layout.clear_widgets()
        records = db.get_user_attendance(username)
        try:
            start_dt = datetime.strptime(f"{month_text}-01", "%Y-%m-%d")
        except ValueError:
            self.show_popup("提示", "月份格式不正确")
            return
        end_dt = self.get_month_start(start_dt, -1)

        record_map = {}
        for record in records:
            try:
                record_time = datetime.fromisoformat(record.get('timestamp', ''))
            except ValueError:
                continue
            if start_dt <= record_time < end_dt:
                day_key = record_time.strftime("%Y-%m-%d")
                record_map.setdefault(day_key, []).append(record)

        year = start_dt.year
        month = start_dt.month
        days_in_month = calendar.monthrange(year, month)[1]
        now = datetime.now()
        if year == now.year and month == now.month:
            days_in_month = min(days_in_month, now.day)

        for day in range(days_in_month, 0, -1):
            day_key = f"{year}-{month:02d}-{day:02d}"
            day_records = record_map.get(day_key, [])
            if day_records:
                day_records.sort(key=lambda item: item.get('timestamp', ''), reverse=True)
                for record in day_records:
                    self.add_record_row(record, fallback_date=day_key)
            else:
                self.add_missing_row(day_key)


    def add_record_row(self, record, fallback_date=''):
        row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46), padding=dp(6), spacing=dp(6))
        with row.canvas.before:
            Color(0.12, 0.2, 0.35, 0.95)
            RoundedRectangle(pos=row.pos, size=row.size, radius=[8])

        try:
            timestamp = datetime.fromisoformat(record.get('timestamp', ''))
            time_text = timestamp.strftime("%m-%d %H:%M")
        except ValueError:
            time_text = fallback_date or record.get('timestamp', '')

        status = record.get('status', '未知')
        if status == "打卡成功":
            status_color = (0.2, 0.8, 0.2, 1)
            note_text = "正常打卡"
            note_color = (0.2, 0.8, 0.2, 1)
        elif status == "补录":
            status_color = (0.9, 0.3, 0.2, 1)
            note_text = "管理员补录"
            note_color = (0.9, 0.3, 0.2, 1)
        else:
            status_color = (0.9, 0.3, 0.2, 1)
            note_text = "打卡异常"
            note_color = (0.9, 0.3, 0.2, 1)

        row.add_widget(Label(text=time_text, size_hint=(0.35, 1), font_size=dp(11), color=(0.9, 0.95, 1, 1)))
        row.add_widget(Label(text=status, size_hint=(0.25, 1), font_size=dp(11), color=status_color))
        row.add_widget(Label(text=note_text, size_hint=(0.4, 1), font_size=dp(11), color=note_color))

        self.results_layout.add_widget(row)

    def add_missing_row(self, date_text):
        row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46), padding=dp(6), spacing=dp(6))
        with row.canvas.before:
            Color(0.12, 0.2, 0.35, 0.95)
            RoundedRectangle(pos=row.pos, size=row.size, radius=[8])

        row.add_widget(Label(text=date_text, size_hint=(0.35, 1), font_size=dp(11), color=(0.9, 0.95, 1, 1)))
        row.add_widget(Label(text='未打卡', size_hint=(0.25, 1), font_size=dp(11), color=(0.9, 0.3, 0.2, 1)))
        row.add_widget(Label(text='未打卡', size_hint=(0.4, 1), font_size=dp(11), color=(0.9, 0.3, 0.2, 1)))

        self.results_layout.add_widget(row)


    def logout_admin(self, instance):
        app = App.get_running_app()
        if hasattr(app, 'current_user'):
            delattr(app, 'current_user')
        if hasattr(app, 'user_data'):
            delattr(app, 'user_data')
        self.manager.current = 'login'

    def go_back(self, instance):
        self.manager.current = 'admin'

    def show_popup(self, title, message):
        popup = Popup(title=title,
                     content=Label(text=message),
                     size_hint=(0.8, 0.4),
                     background_color=(0.0667, 0.149, 0.3098, 1),
                     background='')
        popup.open()


class AdManagerScreen(Screen):

    """广告管理页面"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(0.0667, 0.149, 0.3098, 1)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
        self.bind(pos=self.update_bg, size=self.update_bg)

        main_layout = BoxLayout(orientation='vertical', spacing=dp(4), padding=dp(10))

        top_container = BoxLayout(orientation='vertical', size_hint=(1, None), height=dp(68), padding=[dp(8), dp(3)], spacing=dp(2))



        title_label = Label(text='广告管理', font_size=dp(18), bold=True, color=(1, 1, 1, 1))
        title_box = AnchorLayout(size_hint=(1, None), height=dp(34), anchor_x='center', anchor_y='center')
        title_box.add_widget(title_label)

        action_row = AnchorLayout(size_hint=(1, None), height=dp(38), anchor_x='right', anchor_y='center')
        back_btn = Button(text='返回', size_hint=(None, 1), width=dp(60), font_size=dp(12))
        back_btn.bind(on_press=self.go_back)
        action_row.add_widget(back_btn)

        top_container.add_widget(title_box)
        top_container.add_widget(action_row)
        main_layout.add_widget(top_container)


        form_layout = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))

        form_layout.add_widget(Label(text='顶部广告内容', size_hint=(1, None), height=dp(22), font_size=dp(13), bold=True, color=(1, 1, 1, 1)))

        top_text_layout = BoxLayout(size_hint=(1, None), height=dp(36), spacing=dp(8))
        top_text_layout.add_widget(Label(text='顶部文字', size_hint=(0.3, 1), font_size=dp(12), color=(1, 1, 1, 1)))
        self.top_text_input = TextInput(multiline=False, hint_text='请输入顶部广告文字', font_size=dp(12), background_color=(0.95, 0.97, 1, 1), foreground_color=(0.1, 0.15, 0.25, 1))
        top_text_layout.add_widget(self.top_text_input)

        top_image_layout = BoxLayout(size_hint=(1, None), height=dp(36), spacing=dp(8))
        top_image_layout.add_widget(Label(text='顶部图片', size_hint=(0.3, 1), font_size=dp(12), color=(1, 1, 1, 1)))
        self.top_image_input = TextInput(multiline=False, hint_text='请输入顶部图片URL', font_size=dp(12), background_color=(0.95, 0.97, 1, 1), foreground_color=(0.1, 0.15, 0.25, 1))
        top_image_layout.add_widget(self.top_image_input)

        top_link_layout = BoxLayout(size_hint=(1, None), height=dp(36), spacing=dp(8))
        top_link_layout.add_widget(Label(text='顶部跳转', size_hint=(0.3, 1), font_size=dp(12), color=(1, 1, 1, 1)))
        self.top_link_input = TextInput(multiline=False, hint_text='图片/文字跳转链接（可空）', font_size=dp(12), background_color=(0.95, 0.97, 1, 1), foreground_color=(0.1, 0.15, 0.25, 1))
        top_link_layout.add_widget(self.top_link_input)

        top_scroll_layout = BoxLayout(size_hint=(1, None), height=dp(36), spacing=dp(8))
        top_scroll_layout.add_widget(Label(text='顶部模式', size_hint=(0.3, 1), font_size=dp(12), color=(1, 1, 1, 1)))
        self.top_scroll_spinner = Spinner(text='静止', values=['静止', '水平滚动', '垂直滚动', '等待'], font_size=dp(12), size_hint=(0.7, 1))
        top_scroll_layout.add_widget(self.top_scroll_spinner)

        top_toggle_layout = BoxLayout(size_hint=(1, None), height=dp(36), spacing=dp(8))
        top_toggle_layout.add_widget(Label(text='顶部广告', size_hint=(0.3, 1), font_size=dp(12), color=(1, 1, 1, 1)))
        self.ad_top_toggle = Button(text='关闭', font_size=dp(12), background_color=(0.8, 0.2, 0.2, 1))
        self.ad_top_toggle.bind(on_press=lambda x: self.toggle_switch(self.ad_top_toggle))
        top_toggle_layout.add_widget(self.ad_top_toggle)

        form_layout.add_widget(top_text_layout)
        form_layout.add_widget(top_image_layout)
        form_layout.add_widget(top_link_layout)
        form_layout.add_widget(top_scroll_layout)
        form_layout.add_widget(top_toggle_layout)

        form_layout.add_widget(Label(text='底部广告内容', size_hint=(1, None), height=dp(22), font_size=dp(13), bold=True, color=(1, 1, 1, 1)))

        bottom_text_layout = BoxLayout(size_hint=(1, None), height=dp(36), spacing=dp(8))
        bottom_text_layout.add_widget(Label(text='底部文字', size_hint=(0.3, 1), font_size=dp(12), color=(1, 1, 1, 1)))
        self.bottom_text_input = TextInput(multiline=False, hint_text='请输入底部广告文字', font_size=dp(12), background_color=(0.95, 0.97, 1, 1), foreground_color=(0.1, 0.15, 0.25, 1))
        bottom_text_layout.add_widget(self.bottom_text_input)

        bottom_image_layout = BoxLayout(size_hint=(1, None), height=dp(36), spacing=dp(8))
        bottom_image_layout.add_widget(Label(text='底部图片', size_hint=(0.3, 1), font_size=dp(12), color=(1, 1, 1, 1)))
        self.bottom_image_input = TextInput(multiline=False, hint_text='请输入底部图片URL', font_size=dp(12), background_color=(0.95, 0.97, 1, 1), foreground_color=(0.1, 0.15, 0.25, 1))
        bottom_image_layout.add_widget(self.bottom_image_input)

        bottom_link_layout = BoxLayout(size_hint=(1, None), height=dp(36), spacing=dp(8))
        bottom_link_layout.add_widget(Label(text='底部跳转', size_hint=(0.3, 1), font_size=dp(12), color=(1, 1, 1, 1)))
        self.bottom_link_input = TextInput(multiline=False, hint_text='图片/文字跳转链接（可空）', font_size=dp(12), background_color=(0.95, 0.97, 1, 1), foreground_color=(0.1, 0.15, 0.25, 1))
        bottom_link_layout.add_widget(self.bottom_link_input)

        bottom_scroll_layout = BoxLayout(size_hint=(1, None), height=dp(36), spacing=dp(8))
        bottom_scroll_layout.add_widget(Label(text='底部模式', size_hint=(0.3, 1), font_size=dp(12), color=(1, 1, 1, 1)))
        self.bottom_scroll_spinner = Spinner(text='静止', values=['静止', '水平滚动', '垂直滚动', '等待'], font_size=dp(12), size_hint=(0.7, 1))
        bottom_scroll_layout.add_widget(self.bottom_scroll_spinner)

        bottom_toggle_layout = BoxLayout(size_hint=(1, None), height=dp(36), spacing=dp(8))
        bottom_toggle_layout.add_widget(Label(text='底部广告', size_hint=(0.3, 1), font_size=dp(12), color=(1, 1, 1, 1)))
        self.ad_bottom_toggle = Button(text='关闭', font_size=dp(12), background_color=(0.8, 0.2, 0.2, 1))
        self.ad_bottom_toggle.bind(on_press=lambda x: self.toggle_switch(self.ad_bottom_toggle))
        bottom_toggle_layout.add_widget(self.ad_bottom_toggle)

        form_layout.add_widget(bottom_text_layout)
        form_layout.add_widget(bottom_image_layout)
        form_layout.add_widget(bottom_link_layout)
        form_layout.add_widget(bottom_scroll_layout)
        form_layout.add_widget(bottom_toggle_layout)


        button_layout = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        save_btn = StyledButton(text='保存设置', font_size=dp(12))
        save_btn.bind(on_press=self.save_settings)
        button_layout.add_widget(save_btn)

        main_layout.add_widget(form_layout)
        main_layout.add_widget(button_layout)
        self.add_widget(main_layout)

        Clock.schedule_once(self.load_settings, 0.1)

    def update_bg(self, *args):
        """更新背景尺寸"""
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def on_enter(self):
        self.load_settings(0)

    def set_toggle_state(self, button, enabled):
        button.text = '开启' if enabled else '关闭'
        button.background_color = (0.2, 0.8, 0.2, 1) if enabled else (0.8, 0.2, 0.2, 1)

    def toggle_switch(self, button):
        enabled = button.text != '开启'
        self.set_toggle_state(button, enabled)

    def load_settings(self, dt):
        settings = db.get_user_settings('__global__') or {}
        self.top_text_input.text = settings.get('ad_top_text', settings.get('ad_text', ''))
        self.top_image_input.text = settings.get('ad_top_image_url', settings.get('ad_image_url', ''))
        self.top_link_input.text = settings.get('ad_top_text_url', settings.get('ad_text_url', ''))
        self.top_scroll_spinner.text = settings.get('ad_top_scroll_mode', settings.get('ad_scroll_mode', '静止'))

        self.bottom_text_input.text = settings.get('ad_bottom_text', settings.get('ad_text', ''))
        self.bottom_image_input.text = settings.get('ad_bottom_image_url', settings.get('ad_image_url', ''))
        self.bottom_link_input.text = settings.get('ad_bottom_text_url', settings.get('ad_text_url', ''))
        self.bottom_scroll_spinner.text = settings.get('ad_bottom_scroll_mode', settings.get('ad_scroll_mode', '静止'))

        self.set_toggle_state(self.ad_top_toggle, settings.get('ad_top_enabled', False))
        self.set_toggle_state(self.ad_bottom_toggle, settings.get('ad_bottom_enabled', False))

    def save_settings(self, instance):
        settings = db.get_user_settings('__global__') or {}
        settings.update({
            'ad_top_text': self.top_text_input.text.strip(),
            'ad_top_image_url': self.top_image_input.text.strip(),
            'ad_top_text_url': self.top_link_input.text.strip(),
            'ad_top_scroll_mode': self.top_scroll_spinner.text,
            'ad_bottom_text': self.bottom_text_input.text.strip(),
            'ad_bottom_image_url': self.bottom_image_input.text.strip(),
            'ad_bottom_text_url': self.bottom_link_input.text.strip(),
            'ad_bottom_scroll_mode': self.bottom_scroll_spinner.text,
            'ad_top_enabled': self.ad_top_toggle.text == '开启',
            'ad_bottom_enabled': self.ad_bottom_toggle.text == '开启'
        })
        db.save_user_settings('__global__', settings)
        popup = Popup(title='成功', content=Label(text='广告设置已保存'), size_hint=(0.8, 0.4), background_color=(0.0667, 0.149, 0.3098, 1), background='')

        popup.open()


    def go_back(self, instance):
        self.manager.current = 'admin'


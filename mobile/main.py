# Copyright (C) [2026] [晨曦微光]
# 此软件受著作权法保护。未经明确书面许可，任何单位或个人不得复制、分发、修改或用于商业用途。
# APP名称：[晨曦智能打卡]
# 版本号：1.0.0

"""
打卡系统主应用文件
作者：晨曦微光
功能：移动端打卡应用，支持位置验证、自动打卡、管理员补录
"""


import os
import json
from threading import Thread
from datetime import datetime, time, timedelta

from glimmer_api import GlimmerAPIError

from kivy.config import Config
from kivy.resources import resource_add_path

# 设置默认中文字体（必须在导入其他Kivy模块前设置）
_font_path = os.path.join(os.path.dirname(__file__), 'assets', 'fonts', 'simhei.ttf')
if os.path.exists(_font_path):
    Config.set('kivy', 'default_font', str(['Chinese', _font_path, _font_path, _font_path, _font_path]))
    resource_add_path(os.path.dirname(_font_path))



from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.modalview import ModalView
from kivy.uix.spinner import Spinner
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.image import Image
from kivy.uix.stencilview import StencilView


from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, RoundedRectangle, StencilPush, StencilUse, StencilUnUse, StencilPop, Ellipse

from kivy.core.window import Window
from kivy.metrics import dp
from kivy.storage.jsonstore import JsonStore
from kivy.utils import platform as kivy_platform

# plyer 在不同平台/权限环境下可能不可用。为避免移动端启动即异常导致“看起来进后台/闪退”，这里做容错。
try:
    from plyer import gps, notification
except Exception:  # pragma: no cover
    gps = None

    class _NotificationFallback:
        @staticmethod
        def notify(**kwargs):
            return

    notification = _NotificationFallback()

import hashlib
import hmac
import base64
import uuid
import math



# 设置窗口大小（仅桌面测试，移动端保持全屏）
if kivy_platform in ('win', 'linux', 'macosx'):
    Window.size = (360, 640)


class Database:
    """简单的JSON数据库类，用于存储用户和打卡数据"""
    
    def __init__(self):
        self.users_store = JsonStore('users.json')
        self.attendance_store = JsonStore('attendance.json')
        self.settings_store = JsonStore('settings.json')

    def _hash_password(self, password, salt=None, iterations=120000):
        salt_bytes = salt or os.urandom(16)
        derived = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt_bytes, iterations)
        return f"pbkdf2${iterations}${base64.b64encode(salt_bytes).decode()}${base64.b64encode(derived).decode()}"

    def _verify_password(self, password, stored_value):
        if stored_value.startswith('pbkdf2$'):
            try:
                _, iter_text, salt_b64, hash_b64 = stored_value.split('$', 3)
                iterations = int(iter_text)
                salt = base64.b64decode(salt_b64.encode())
                expected = base64.b64decode(hash_b64.encode())
                derived = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
                return hmac.compare_digest(derived, expected), False
            except Exception:
                return False, False

        legacy_hash = hashlib.sha256(password.encode()).hexdigest()
        is_match = hmac.compare_digest(legacy_hash, stored_value)
        return is_match, True
        
    def add_user(self, username, password, is_admin=False, profile=None):

        """添加用户"""
        if self.users_store.exists(username):
            return False, "用户名已存在"

        # 使用PBKDF2哈希密码
        hashed_password = self._hash_password(password)
        user_id = str(uuid.uuid4())
        profile_data = profile or {}

        self.users_store.put(username,
                            user_id=user_id,
                            password=hashed_password,

                            is_admin=is_admin,
                            profile=profile_data,
                            created_at=datetime.now().isoformat(),
                            last_login='')
        return True, "注册成功"


    
    def validate_user(self, username, password):
        """验证用户登录"""
        if not self.users_store.exists(username):
            return False, "用户不存在"
        
        user_data = self.users_store.get(username)
        stored_password = user_data.get('password', '')
        is_valid, legacy = self._verify_password(password, stored_password)

        if is_valid:
            if legacy:
                user_data['password'] = self._hash_password(password)
            user_data['last_login'] = datetime.now().isoformat()
            self.users_store.put(username, **user_data)
            return True, user_data
        else:
            return False, "密码错误"


    
    def get_all_users(self):
        """获取所有用户"""
        return list(self.users_store.keys())

    def get_user_record(self, username):
        if not self.users_store.exists(username):
            return {}
        return self.users_store.get(username)

    def update_last_login(self, username):
        if not self.users_store.exists(username):
            return
        record = self.users_store.get(username)
        record['last_login'] = datetime.now().isoformat()
        self.users_store.put(username, **record)

    def delete_user(self, username):
        if not self.users_store.exists(username):
            return False
        self.users_store.delete(username)

        # 删除用户打卡记录
        for key in list(self.attendance_store.keys()):
            record = self.attendance_store.get(key)
            if record.get('username') == username:
                self.attendance_store.delete(key)

        # 删除用户设置
        if self.settings_store.exists(username):
            self.settings_store.delete(username)
        return True

    def get_user_profile(self, username):

        """获取用户详细资料"""
        if not self.users_store.exists(username):
            return {}
        user_data = self.users_store.get(username)
        profile = user_data.get('profile', {}) or {}
        return {
            'username': username,
            'user_id': user_data.get('user_id', ''),
            'created_at': user_data.get('created_at', ''),
            'last_login': user_data.get('last_login', ''),
            'real_name': profile.get('real_name', ''),
            'phone': profile.get('phone', ''),
            'department': profile.get('department', ''),
            'security_question': profile.get('security_question', ''),
            'security_answer': profile.get('security_answer', '')
        }


    
    def add_attendance(self, user_id, username, status, location, notes=""):

        """添加打卡记录。

        说明：记录默认 `server_synced=False`，用于在服务器恢复连接后自动补传历史数据。
        """
        record_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        self.attendance_store.put(
            record_id,
            user_id=user_id,
            username=username,
            status=status,
            location=location,
            notes=notes,
            timestamp=timestamp,
            date=datetime.now().strftime("%Y-%m-%d"),
            server_synced=False,
            server_synced_at='',
            server_sync_error='',
        )
        return record_id

    def mark_attendance_synced(self, record_id: str, synced: bool = True, error: str = ''):
        """标记某条打卡记录是否已同步到服务器（离线补传用）。"""
        try:
            if not record_id or not self.attendance_store.exists(record_id):
                return
            record = self.attendance_store.get(record_id)
            record['server_synced'] = bool(synced)
            record['server_synced_at'] = datetime.now().isoformat(timespec='seconds') if synced else ''
            record['server_sync_error'] = str(error or '')[:300]
            self.attendance_store.put(record_id, **record)
        except Exception:
            return

    def get_unsynced_attendance(self, username: str, limit: int = 50) -> list[dict]:
        """获取未同步到服务器的打卡记录（按时间从旧到新）。"""
        try:
            items = []
            for key in self.attendance_store.keys():
                record = self.attendance_store.get(key)
                if record.get('username') != username:
                    continue
                if bool(record.get('server_synced')):
                    continue
                record = dict(record)
                record['record_id'] = key
                items.append(record)
            items.sort(key=lambda x: x.get('timestamp') or '')
            return items[: int(limit or 50)]
        except Exception:
            return []

    
    def get_user_attendance(self, username):
        """获取用户的打卡记录"""
        records = []
        for key in self.attendance_store.keys():
            record = self.attendance_store.get(key)
            if record['username'] == username:
                record['record_id'] = key
                records.append(record)
        # 按时间倒序排序
        records.sort(key=lambda x: x['timestamp'], reverse=True)
        return records
    
    def get_all_attendance(self):
        """获取所有打卡记录"""
        records = []
        for key in self.attendance_store.keys():
            record = self.attendance_store.get(key)
            record['record_id'] = key
            records.append(record)
        # 按时间倒序排序
        records.sort(key=lambda x: x['timestamp'], reverse=True)
        return records

    
    def update_attendance_status(self, record_id, new_status):
        """更新打卡状态（管理员补录用）"""
        if self.attendance_store.exists(record_id):
            record = self.attendance_store.get(record_id)
            record['status'] = new_status
            record['notes'] = "管理员补录"
            self.attendance_store.put(record_id, **record)
            return True
        return False
    
    def save_user_settings(self, username, settings):
        """保存用户设置"""
        self.settings_store.put(username, **settings)
    
    def get_user_settings(self, username):
        """获取用户设置"""
        if self.settings_store.exists(username):
            return self.settings_store.get(username)
        return None

    def update_user_password(self, username, new_password):
        """更新用户密码"""
        if not self.users_store.exists(username):
            return False, "用户不存在"

        hashed_password = self._hash_password(new_password)
        record = self.users_store.get(username)
        record['password'] = hashed_password

        self.users_store.put(username, **record)
        return True, "密码已更新"

# 初始化数据库
db = Database()

# 服务器配置与鉴权缓存
client_store = JsonStore('glimmer_client.json')
DEFAULT_SERVER_URL = os.environ.get('GLIMMER_SERVER_URL') or ''


def get_server_url() -> str:
    try:
        if client_store.exists('config'):
            url = (client_store.get('config') or {}).get('server_url')
            if url:
                return str(url)
    except Exception:
        pass
    return DEFAULT_SERVER_URL


def set_server_url(url: str):
    url = (url or '').strip().rstrip('/')
    client_store.put('config', server_url=url)


def get_api() -> 'GlimmerAPI':
    from glimmer_api import GlimmerAPI
    return GlimmerAPI(get_server_url())


class StyledButton(Button):

    """自定义样式按钮"""
    def __init__(self, **kwargs):
        self._bg_color = kwargs.pop('bg_color', kwargs.get('background_color', (0.2, 0.6, 0.8, 1)))
        super().__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)
        self.color = (1, 1, 1, 1)
        self.font_size = dp(16)
        self.bold = True
        
        with self.canvas.before:
            self._bg = Color(*self._bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[15])
        
        self.bind(pos=self.update_rect, size=self.update_rect)
    
    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def set_bg_color(self, color):
        """更新背景色"""
        self._bg_color = color
        self._bg.rgba = color


class CircularImage(StencilView):
    def __init__(self, source='', **kwargs):
        super().__init__(**kwargs)
        self.image = Image(source=source, allow_stretch=True, keep_ratio=False)
        self.add_widget(self.image)

        with self.canvas.before:
            StencilPush()
            self._stencil_color = Color(1, 1, 1, 1)
            self._stencil_ellipse = Ellipse(pos=self.pos, size=self.size)
            StencilUse()

        with self.canvas.after:
            StencilUnUse()
            self._stencil_ellipse_after = Ellipse(pos=self.pos, size=self.size)
            StencilPop()

        self.bind(pos=self._update_stencil, size=self._update_stencil)

    def _update_stencil(self, *args):
        self._stencil_ellipse.pos = self.pos
        self._stencil_ellipse.size = self.size
        self._stencil_ellipse_after.pos = self.pos
        self._stencil_ellipse_after.size = self.size
        self.image.pos = self.pos
        self.image.size = self.size


class LoginScreen(Screen):

    """登录界面"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with self.canvas.before:


            Color(0.0667, 0.149, 0.3098, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self.update_bg, size=self.update_bg)
        
        layout = BoxLayout(orientation='vertical', padding=dp(24), spacing=dp(14))


        
        # 标题
        title = Label(text='晨曦智能打卡', font_size=dp(32), bold=True, color=(1, 1, 1, 1))

        top_row = AnchorLayout(size_hint=(1, None), height=dp(36), anchor_x='right', anchor_y='center')
        self._announcement_flash_event = None
        self._announcement_flash_on = False
        self._announcement_seen_token = ''
        self._announcement_alert_token = ''
        self.announcement_btn = Button(


            text='公告',
            size_hint=(None, 1),
            width=dp(52),
            font_size=dp(12),
            background_color=(0.18, 0.32, 0.55, 1),
            color=(1, 1, 1, 1)
        )
        self.announcement_btn.bind(on_press=self.show_announcement_popup)

        about_btn = Button(
            text='关于',
            size_hint=(None, 1),
            width=dp(52),
            font_size=dp(12),
            background_color=(0.15, 0.28, 0.5, 1),
            color=(1, 1, 1, 1)
        )
        about_btn.bind(on_press=self.show_about_popup)

        share_btn = Button(
            text='分享',
            size_hint=(None, 1),
            width=dp(52),
            font_size=dp(12),
            background_color=(0.15, 0.28, 0.5, 1),
            color=(1, 1, 1, 1)
        )
        share_btn.bind(on_press=self.share_to_wechat)

        btn_row = BoxLayout(size_hint=(None, 1), width=dp(170), spacing=dp(6))
        btn_row.add_widget(self.announcement_btn)
        btn_row.add_widget(about_btn)
        btn_row.add_widget(share_btn)
        top_row.add_widget(btn_row)




        title_row = AnchorLayout(size_hint=(1, None), height=dp(40), anchor_x='center', anchor_y='center')
        title_row.add_widget(title)

        self.logo_container = AnchorLayout(size_hint=(1, None), height=dp(110), anchor_x='center', anchor_y='center')
        self.logo_image = None
        logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'icon.png')
        if os.path.exists(logo_path):
            self.logo_image = CircularImage(source=logo_path, size_hint=(None, None))
            self.logo_container.add_widget(self.logo_image)
            self.logo_container.bind(size=self.update_logo_size)
            Clock.schedule_once(self.update_logo_size, 0)
        else:
            self.logo_container.height = 0

        # 输入框容器
        input_layout = BoxLayout(orientation='vertical', spacing=dp(15))





        
        # 用户名输入
        self.username_input = TextInput(
            hint_text='用户名',
            multiline=False,
            size_hint=(1, None),
            height=dp(50),
            background_color=(0.95, 0.95, 0.95, 1),
            foreground_color=(0.2, 0.2, 0.2, 1),
            padding=dp(10)
        )

        # 姓名输入

        self.real_name_input = TextInput(
            hint_text='姓名',
            multiline=False,
            size_hint=(1, None),
            height=dp(50),
            background_color=(0.95, 0.95, 0.95, 1),
            foreground_color=(0.2, 0.2, 0.2, 1),
            padding=dp(10)
        )

        # 手机号输入
        self.phone_input = TextInput(
            hint_text='手机号',
            multiline=False,
            input_filter='int',
            size_hint=(1, None),
            height=dp(50),
            background_color=(0.95, 0.95, 0.95, 1),
            foreground_color=(0.2, 0.2, 0.2, 1),
            padding=dp(10)
        )

        # 部门/岗位
        self.department_input = TextInput(
            hint_text='部门/岗位',
            multiline=False,
            size_hint=(1, None),
            height=dp(50),
            background_color=(0.95, 0.95, 0.95, 1),
            foreground_color=(0.2, 0.2, 0.2, 1),
            padding=dp(10)
        )

        self.security_question_spinner = Spinner(
            text='请选择安全问题',
            values=['您小学班主任姓名', '您出生的城市', '您最喜欢的运动', '您母亲的名字'],
            size_hint=(1, None),
            height=dp(46),
            font_size=dp(12)
        )

        self.security_answer_input = TextInput(
            hint_text='安全问题答案',
            multiline=False,
            size_hint=(1, None),
            height=dp(50),
            background_color=(0.95, 0.95, 0.95, 1),
            foreground_color=(0.2, 0.2, 0.2, 1),
            padding=dp(10)
        )
        
        # 密码输入
        self.password_input = TextInput(


            hint_text='密码',
            password=True,
            multiline=False,
            size_hint=(1, None),
            height=dp(50),
            background_color=(0.95, 0.95, 0.95, 1),
            foreground_color=(0.2, 0.2, 0.2, 1),
            padding=dp(10)
        )
        
        input_layout.add_widget(self.username_input)
        input_layout.add_widget(self.password_input)
        
        # 按钮容器
        button_layout = BoxLayout(orientation='vertical', spacing=dp(10))
        
        # 登录按钮
        login_btn = StyledButton(text='登录')
        login_btn.bind(on_press=self.login)
        
        # 注册按钮
        register_btn = StyledButton(text='注册新账号', background_color=(0.73, 0.73, 0.73, 1))
        register_btn.bind(on_press=self.go_to_register)
        
        button_layout.add_widget(login_btn)
        button_layout.add_widget(register_btn)

        forgot_btn = StyledButton(text='忘记密码', background_color=(0.18, 0.62, 0.38, 1))
        forgot_btn.bind(on_press=self.open_forgot_password)
        button_layout.add_widget(forgot_btn)

        
        # 添加所有组件
        layout.add_widget(top_row)
        layout.add_widget(title_row)


        layout.add_widget(self.logo_container)
        layout.add_widget(input_layout)


        layout.add_widget(button_layout)






        
        self.add_widget(layout)

    def on_enter(self):
        # 移动端部分机型/权限环境下，通知等能力可能不可用。
        # 为避免启动即异常导致应用看起来“直接进后台/闪退”，这里做容错处理。
        try:
            self.refresh_server_public_announcement()
        except Exception:
            pass
        try:
            self.update_announcement()
        except Exception:
            pass

        # 登录页也周期性刷新“全局公告/版本信息”，确保工程师发布后尽快可见
        if not getattr(self, '_public_cfg_ev', None):
            self._public_cfg_ev = Clock.schedule_interval(lambda *_: self.refresh_server_public_announcement(), 15)




    def get_announcement_token(self, text, time_text):
        return time_text or text or ''

    def refresh_server_public_announcement(self):
        # 未登录时也能获取“全局公告/版本信息”（工程师发布，所有用户可见）
        url = get_server_url()
        if not url:
            return

        def work():
            try:
                api = get_api()
                if not api.health():
                    return

                latest = api.public_latest_global_announcement()
                version = api.public_version()

                settings = db.get_user_settings('__global__') or {}

                if latest:
                    settings['announcement_text'] = str(latest.get('content') or '')
                    created_at = str(latest.get('created_at') or '')
                    settings['announcement_time'] = created_at[:16].replace('T', ' ') if created_at else ''

                if version:
                    settings['latest_version'] = str(version.get('latest_version') or '')
                    settings['latest_version_note'] = str(version.get('note') or '')
                    updated_at = str(version.get('updated_at') or '')
                    settings['latest_version_time'] = updated_at[:16].replace('T', ' ') if updated_at else ''

                db.save_user_settings('__global__', settings)
                Clock.schedule_once(lambda *_: self.update_announcement(), 0)
            except Exception:
                return

        Thread(target=work, daemon=True).start()

    def update_announcement(self):
        settings = db.get_user_settings('__global__') or {}

        text = settings.get('announcement_text', '')
        time_text = settings.get('announcement_time', '')
        token = self.get_announcement_token(text, time_text)
        if token and token != self._announcement_seen_token:
            self.start_announcement_flash()
            if token != self._announcement_alert_token:
                self.send_announcement_alert(text)
                self._announcement_alert_token = token
        else:
            self.stop_announcement_flash()

    def send_announcement_alert(self, text):
        message = (text or '').strip()
        if not message:
            return
        try:
            notification.notify(
                title='公告提醒',
                message=message,
                timeout=3
            )
        except Exception:
            # 通知能力不可用时忽略，不影响登录页显示
            return


    def start_announcement_flash(self):

        if self._announcement_flash_event:
            return
        self._announcement_flash_event = Clock.schedule_interval(self.toggle_announcement_flash, 0.6)

    def stop_announcement_flash(self):
        if self._announcement_flash_event:
            self._announcement_flash_event.cancel()
            self._announcement_flash_event = None
        self._announcement_flash_on = False
        self.announcement_btn.background_color = (0.18, 0.32, 0.55, 1)

    def toggle_announcement_flash(self, dt):
        self._announcement_flash_on = not self._announcement_flash_on
        self.announcement_btn.background_color = (0.85, 0.45, 0.1, 1) if self._announcement_flash_on else (0.18, 0.32, 0.55, 1)




    def show_announcement_popup(self, instance):
        settings = db.get_user_settings('__global__') or {}
        text = settings.get('announcement_text', '')
        time_text = settings.get('announcement_time', '')
        if not text:
            self.show_popup("通知", "暂无公告")
            return

        token = self.get_announcement_token(text, time_text)
        self._announcement_seen_token = token
        self.stop_announcement_flash()

        content = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(20))
        title = f"公告时间：{time_text}" if time_text else "公告"

        content.add_widget(Label(text=title, color=(0.9, 0.95, 1, 1)))

        # 公告内容：滚动展示，避免字数过多导致布局/渲染异常
        msg_scroll = ScrollView(size_hint=(1, 1), bar_width=dp(2))
        message = Label(text=text, halign='left', valign='top', color=(1, 1, 1, 1), size_hint=(1, None))
        message.bind(size=lambda instance, value: setattr(instance, 'text_size', (value[0], None)))
        message.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1]))
        msg_scroll.add_widget(message)
        content.add_widget(msg_scroll)

        close_btn = Button(text='关闭', size_hint=(1, None), height=dp(44), background_color=(0.2, 0.6, 0.8, 1))

        content.add_widget(close_btn)

        popup = Popup(title='公告提醒', content=content, size_hint=(0.88, 0.5), background_color=(0.0667, 0.149, 0.3098, 1), background='')
        close_btn.bind(on_press=lambda x: popup.dismiss())
        popup.open()

    def show_about_popup(self, instance):
        content = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(22))
        logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'icon.png')
        if os.path.exists(logo_path):
            logo = Image(source=logo_path, size_hint=(1, None), height=dp(120), allow_stretch=True, keep_ratio=True)
            content.add_widget(logo)

        title = Label(text='晨曦智能打卡', font_size=dp(18), bold=True, color=(1, 1, 1, 1))
        content.add_widget(title)

        copyright_label = Label(text='Copyright (C) [2026] [晨曦微光]', font_size=dp(12), color=(0.9, 0.95, 1, 1))
        content.add_widget(copyright_label)

        legal_text = (
            "此软件受著作权法保护。未经明确书面许可，任何单位或个人不得复制、分发、修改或用于商业用途。"
        )
        legal_label = Label(text=legal_text, halign='left', valign='top', color=(0.9, 0.95, 1, 1))
        legal_label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
        content.add_widget(legal_label)

        meta_label = Label(text='APP名称：[晨曦智能打卡]\n版本号：1.0.0', halign='left', valign='top', color=(0.9, 0.95, 1, 1))
        meta_label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
        content.add_widget(meta_label)

        popup = Popup(title='关于', content=content, size_hint=(0.88, 0.72), background_color=(0.0667, 0.149, 0.3098, 1), background='')
        popup.open()

    def share_to_wechat(self, *_):
        # 微信分享：Android 使用 Intent 调起微信分享；其它平台给出提示
        try:
            if kivy_platform != 'android':
                self.show_popup('提示', '微信分享仅支持安卓设备')
                return

            try:
                from jnius import autoclass, cast
            except Exception:
                self.show_popup('提示', '分享组件不可用（缺少 jnius）')
                return

            Intent = autoclass('android.content.Intent')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            String = autoclass('java.lang.String')

            activity = PythonActivity.mActivity
            pm = activity.getPackageManager()

            # 检测微信是否安装
            try:
                pm.getPackageInfo('com.tencent.mm', 0)
            except Exception:
                self.show_popup('提示', '未检测到微信，请先安装微信')
                return

            share_text = '晨曦智能打卡：团队考勤打卡应用（请在服务器内下载/安装最新版本）'

            intent = Intent()
            intent.setAction(Intent.ACTION_SEND)
            intent.setType('text/plain')
            intent.putExtra(Intent.EXTRA_TEXT, String(share_text))
            intent.setPackage('com.tencent.mm')

            chooser = Intent.createChooser(intent, cast('java.lang.CharSequence', String('分享到微信')))
            activity.startActivity(chooser)
        except Exception as e:
            self.show_popup('分享失败', str(e))


    def update_logo_size(self, *args):

        if not self.logo_image:
            return
        container = self.logo_container
        max_size = min(container.width * 0.28, container.height - dp(8))
        max_size = min(max_size, dp(96))
        size = max(dp(56), max_size)
        self.logo_image.size = (size, size)

    def update_bg(self, *args):


        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size


    def show_login_failed_popup(self, message):
        content = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(20))
        content.add_widget(Label(text=message, color=(1, 1, 1, 1)))

        btn_layout = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        reset_btn = Button(text='找回密码', background_color=(0.2, 0.6, 0.8, 1))
        close_btn = Button(text='关闭', background_color=(0.6, 0.6, 0.6, 1))
        btn_layout.add_widget(reset_btn)
        btn_layout.add_widget(close_btn)
        content.add_widget(btn_layout)

        popup = Popup(title='登录失败', content=content, size_hint=(0.86, 0.42), background_color=(0.0667, 0.149, 0.3098, 1), background='')
        reset_btn.bind(on_press=lambda x: (popup.dismiss(), self.open_password_reset()))
        close_btn.bind(on_press=lambda x: popup.dismiss())
        popup.open()

    def verify_security_answer(self, answer, stored_value):
        if not stored_value:
            return False
        if stored_value.startswith('pbkdf2$') or len(stored_value) == 64:
            if hasattr(db, '_verify_password'):
                is_valid, _ = db._verify_password(answer, stored_value)
                return is_valid
        return hmac.compare_digest(str(answer), str(stored_value))

    def open_password_reset(self):
        username = self.username_input.text.strip()
        if not username:
            self.show_popup("提示", "请先输入用户名")
            return

        user_record = db.get_user_record(username)
        if not user_record:
            self.show_popup("提示", "用户不存在")
            return

        profile = user_record.get('profile', {}) or {}
        stored_question = profile.get('security_question', '')
        stored_answer = profile.get('security_answer', '')
        if not stored_question or not stored_answer:
            self.show_popup("提示", "该账号未设置安全问题，无法找回密码")
            return

        question_values = ['您小学班主任姓名', '您出生的城市', '您最喜欢的运动', '您母亲的名字']

        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(20))
        content.add_widget(Label(text=f"账号：{username}", color=(0.9, 0.95, 1, 1)))

        security_spinner = Spinner(
            text=stored_question if stored_question in question_values else '请选择安全问题',
            values=question_values,
            size_hint=(1, None),
            height=dp(46),
            font_size=dp(12)
        )
        answer_input = TextInput(
            hint_text='安全问题答案',
            multiline=False,
            size_hint=(1, None),
            height=dp(50),
            background_color=(0.95, 0.95, 0.95, 1),
            foreground_color=(0.2, 0.2, 0.2, 1),
            padding=dp(10)
        )
        new_password_input = TextInput(
            hint_text='新密码',
            password=True,
            multiline=False,
            size_hint=(1, None),
            height=dp(50),
            background_color=(0.95, 0.95, 0.95, 1),
            foreground_color=(0.2, 0.2, 0.2, 1),
            padding=dp(10)
        )
        confirm_password_input = TextInput(
            hint_text='确认新密码',
            password=True,
            multiline=False,
            size_hint=(1, None),
            height=dp(50),
            background_color=(0.95, 0.95, 0.95, 1),
            foreground_color=(0.2, 0.2, 0.2, 1),
            padding=dp(10)
        )

        content.add_widget(security_spinner)
        content.add_widget(answer_input)
        content.add_widget(new_password_input)
        content.add_widget(confirm_password_input)

        btn_layout = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        submit_btn = Button(text='重置密码', background_color=(0.2, 0.6, 0.8, 1))
        cancel_btn = Button(text='取消', background_color=(0.6, 0.6, 0.6, 1))
        btn_layout.add_widget(submit_btn)
        btn_layout.add_widget(cancel_btn)
        content.add_widget(btn_layout)

        popup = Popup(title='找回密码', content=content, size_hint=(0.9, 0.65), background_color=(0.0667, 0.149, 0.3098, 1), background='')

        def handle_submit(instance):
            if security_spinner.text == '请选择安全问题':
                self.show_popup("错误", "请选择安全问题")
                return
            if security_spinner.text != stored_question:
                self.show_popup("错误", "安全问题选择不正确")
                return

            answer = answer_input.text.strip()
            if not answer:
                self.show_popup("错误", "请输入安全问题答案")
                return
            if not self.verify_security_answer(answer, stored_answer):
                self.show_popup("错误", "安全问题答案不正确")
                return

            new_password = new_password_input.text.strip()
            confirm_password = confirm_password_input.text.strip()
            if not new_password or not confirm_password:
                self.show_popup("错误", "请输入新密码并确认")
                return
            if len(new_password) < 6:
                self.show_popup("错误", "密码长度至少6位")
                return
            if new_password != confirm_password:
                self.show_popup("错误", "两次输入的密码不一致")
                return

            success, message = db.update_user_password(username, new_password)
            if success:
                popup.dismiss()
                self.show_popup("成功", "密码已重置，请使用新密码登录")
            else:
                self.show_popup("错误", message)

        submit_btn.bind(on_press=handle_submit)
        cancel_btn.bind(on_press=lambda x: popup.dismiss())
        popup.open()

    
    def _fallback_local_login(self, username: str, password: str, err: str | None):
        if err:
            # 服务器不在线时统一提示“维护中”，但仍继续尝试本地登录
            try:
                self.show_popup('提示', '服务器维护中，请稍后再试。。。')
            except Exception:
                pass


        success, result = db.validate_user(username, password)
        if success:
            app = App.get_running_app()
            app.current_user = username
            app.user_data = result
            try:
                if hasattr(app, 'api_token'):
                    delattr(app, 'api_token')
                if hasattr(app, 'server_role'):
                    delattr(app, 'server_role')
                if hasattr(app, 'server_url'):
                    delattr(app, 'server_url')
            except Exception:
                pass
            self._show_welcome_then_enter()
        else:
            self.show_login_failed_popup(result)

    def _show_welcome_then_enter(self):
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(18))
        title = Label(text='欢迎使用晨曦智能打卡', font_size=dp(18), bold=True, color=(1, 1, 1, 1))
        content.add_widget(title)

        # 欢迎提示窗展示 LOGO
        try:
            logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'icon.png')
            if os.path.exists(logo_path):
                img = Image(source=logo_path, allow_stretch=True, keep_ratio=True, size_hint=(1, None), height=dp(160))
                content.add_widget(img)
        except Exception:
            pass


        popup = Popup(
            title='',
            content=content,
            size_hint=(0.85, 0.6),
            background_color=(0.0667, 0.149, 0.3098, 1),
            background=''
        )
        popup.open()

        def _goto(*_):
            try:
                popup.dismiss()
            except Exception:
                pass
            try:
                self.manager.current = 'main'
            except Exception:
                pass

        Clock.schedule_once(_goto, 5)



    def login(self, instance):



        """处理登录"""

        username = self.username_input.text.strip()
        password = self.password_input.text.strip()
        
        if not username or not password:
            self.show_popup("错误", "请输入用户名和密码")
            return
        
        # 优先走服务器登录（支持群/公告/版本/广告等在线能力）；失败再回退本地登录
        server_url = get_server_url()

        # 工程师账号：若未配置服务器地址，则默认走花生壳域名（方便首次登录）
        if not server_url and username == 'engineer':
            server_url = 'http://78oq264463tb.vicp.fun'
            try:
                set_server_url(server_url)
            except Exception:
                pass

        if server_url:
            # 登录页不展示具体网址，避免泄露/影响观感

            def work():

                api = None
                try:
                    api = get_api()

                    # 服务器不在线：统一提示“维护中”
                    if not api.health():
                        Clock.schedule_once(lambda *_: self.show_popup('登录失败', '服务器维护中，请稍后再试。。。'), 0)
                        return

                    token = api.login(username, password)
                    me = api.me(token)
                    role = str((me or {}).get('role') or 'user')

                    # 缓存到 App（供其它页面使用）
                    app = App.get_running_app()
                    app.server_url = server_url
                    app.api_token = token
                    app.server_role = role

                    # 兼容旧逻辑：is_admin 用于显示管理员入口
                    app.current_user = username
                    app.user_data = {
                        'role': role,
                        'is_admin': role in ('admin', 'engineer')
                    }

                    try:
                        client_store.put('auth', username=username, token=token, role=role, server_url=server_url)
                    except Exception:
                        pass

                    # 本机仅缓存个人资料（不保存密码/密保答案；用户数据以服务器为准）
                    try:
                        profile_cache = {
                            'username': username,
                            'user_id': str((me or {}).get('id') or ''),
                            'real_name': str((me or {}).get('real_name') or ''),
                            'phone': str((me or {}).get('phone') or ''),
                            'department': str((me or {}).get('department') or ''),
                            'created_at': str((me or {}).get('created_at') or ''),
                            'last_login': str((me or {}).get('last_login') or ''),
                            'security_question': str((me or {}).get('security_question') or ''),
                        }
                        s = db.get_user_settings(username) or {}
                        s['profile_cache'] = profile_cache
                        db.save_user_settings(username, s)
                    except Exception:
                        pass

                    # 补齐 user_id（用于主界面显示与个人资料页）
                    try:
                        app.user_data['user_id'] = str((me or {}).get('id') or '')
                    except Exception:
                        pass


                    Clock.schedule_once(lambda *_: self._show_welcome_then_enter(), 0)


                except Exception as e:
                    msg = '服务器维护中，请稍后再试。。。'
                    try:
                        if api and api.health():
                            msg = str(e)
                    except Exception:
                        pass
                    Clock.schedule_once(lambda *_, m=msg: self.show_popup('登录失败', m), 0)



            Thread(target=work, daemon=True).start()
            return


        self._fallback_local_login(username, password, None)


    
    def open_forgot_password(self, instance):
        """忘记密码：通过密保问题找回（允许未配置服务器地址时手工输入）"""
        default_url = str(get_server_url() or '').strip()
        if not default_url:
            try:
                if client_store.exists('auth'):
                    d = client_store.get('auth') or {}
                    default_url = str(d.get('server_url') or '').strip()
            except Exception:
                default_url = ''

        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(16))

        server_in = TextInput(hint_text='服务器地址（例如 http://1.2.3.4:8000）', multiline=False, size_hint=(1, None), height=dp(44), text=default_url)
        user_in = TextInput(hint_text='用户名', multiline=False, size_hint=(1, None), height=dp(44), text=self.username_input.text.strip())

        q_label = Label(text='密保问题：', color=(1, 1, 1, 1), halign='left', valign='middle', size_hint=(1, None), height=dp(30))
        q_label.bind(size=lambda i, v: setattr(i, 'text_size', v))
        ans_in = TextInput(hint_text='密保答案', multiline=False, size_hint=(1, None), height=dp(44))
        new_in = TextInput(hint_text='新密码（至少6位）', password=True, multiline=False, size_hint=(1, None), height=dp(44))
        new2_in = TextInput(hint_text='确认新密码', password=True, multiline=False, size_hint=(1, None), height=dp(44))

        content.add_widget(server_in)
        content.add_widget(user_in)
        content.add_widget(q_label)

        content.add_widget(ans_in)
        content.add_widget(new_in)
        content.add_widget(new2_in)

        btn_row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        load_btn = Button(text='加载问题', background_color=(0.85, 0.45, 0.1, 1))
        ok_btn = Button(text='确认找回', background_color=(0.2, 0.6, 0.8, 1))
        cancel_btn = Button(text='取消', background_color=(0.6, 0.6, 0.6, 1))
        btn_row.add_widget(load_btn)
        btn_row.add_widget(ok_btn)
        btn_row.add_widget(cancel_btn)
        content.add_widget(btn_row)

        popup = Popup(title='忘记密码', content=content, size_hint=(0.9, 0.7), background_color=(0.0667, 0.149, 0.3098, 1), background='')
        cancel_btn.bind(on_press=lambda *_: popup.dismiss())

        def load_question(*_):
            u = (user_in.text or '').strip()
            if not u:
                self.show_popup('提示', '请输入用户名')
                return

            def work():
                try:
                    url = (server_in.text or '').strip().rstrip('/')
                    if not url:
                        raise RuntimeError('请输入服务器地址')
                    from glimmer_api import GlimmerAPI
                    api = GlimmerAPI(url)
                    if not api.health():
                        raise RuntimeError('服务器不在线')
                    data = api.security_question(u)

                    q = str((data or {}).get('security_question') or '')
                    Clock.schedule_once(lambda *_: setattr(q_label, 'text', f"密保问题：{q}" if q else '密保问题：未设置'), 0)
                except Exception as e:
                    Clock.schedule_once(lambda *_, msg=str(e): setattr(q_label, 'text', f"密保问题：加载失败（{msg}）"), 0)


            Thread(target=work, daemon=True).start()

        def submit(*_):
            u = (user_in.text or '').strip()
            ans = (ans_in.text or '').strip()
            new_pwd = (new_in.text or '').strip()
            new2_pwd = (new2_in.text or '').strip()
            if not u or not ans or not new_pwd:
                self.show_popup('提示', '请输入用户名、答案和新密码')
                return
            if len(new_pwd) < 6:
                self.show_popup('提示', '新密码长度至少6位')
                return
            if new_pwd != new2_pwd:
                self.show_popup('提示', '两次输入的新密码不一致')
                return

            def work():
                try:
                    url = (server_in.text or '').strip().rstrip('/')
                    if not url:
                        raise RuntimeError('请输入服务器地址')
                    from glimmer_api import GlimmerAPI
                    api = GlimmerAPI(url)
                    if not api.health():
                        raise RuntimeError('服务器不在线')
                    api.reset_password(u, ans, new_pwd)

                    Clock.schedule_once(lambda *_: (popup.dismiss(), self.show_popup('成功', '密码已重置，请用新密码登录')), 0)
                except Exception as e:
                    Clock.schedule_once(lambda *_, msg=str(e): self.show_popup('找回失败', msg), 0)


            Thread(target=work, daemon=True).start()

        load_btn.bind(on_press=load_question)
        ok_btn.bind(on_press=submit)
        popup.open()
        load_question()

    def go_to_register(self, instance):
        """跳转到注册界面"""
        self.manager.current = 'register'

    
    def show_popup(self, title, message):
        """显示提示弹窗（自动换行/对齐，背景色与首页一致）"""
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
            background=''
        )
        popup.open()





class RegisterScreen(Screen):

    """注册界面"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with self.canvas.before:


            Color(0.0667, 0.149, 0.3098, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self.update_bg, size=self.update_bg)
        
        main_layout = BoxLayout(orientation='vertical', padding=dp(18), spacing=dp(10))

        # 标题
        title = Label(text='用户注册', font_size=dp(28), bold=True, color=(1, 1, 1, 1), size_hint=(1, None), height=dp(42))

        notice_text = (
            "注册须知：请如实填写必要信息，仅用于考勤管理。"
            "我们遵守《个人信息保护法》，不会要求与打卡无关的敏感资料。"
        )
        notice_label = Label(text=notice_text, font_size=dp(12), color=(0.9, 0.94, 1, 1), halign='left', valign='top', size_hint=(1, None))
        notice_label.bind(size=lambda instance, value: setattr(instance, 'text_size', (value[0], None)))
        notice_label.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1]))

        form_scroll = ScrollView(size_hint=(1, 1), bar_width=dp(2))
        form_layout = GridLayout(cols=1, spacing=dp(10), size_hint_y=None)
        form_layout.bind(minimum_height=form_layout.setter('height'))

        # 输入框容器
        input_layout = GridLayout(cols=1, spacing=dp(12), size_hint_y=None)
        input_layout.bind(minimum_height=input_layout.setter('height'))


        
        # 用户名输入
        self.username_input = TextInput(
            hint_text='用户名',
            multiline=False,
            size_hint=(1, None),
            height=dp(50),
            background_color=(0.95, 0.95, 0.95, 1),
            foreground_color=(0.2, 0.2, 0.2, 1),
            padding=dp(10)
        )

        # 姓名输入

        self.real_name_input = TextInput(
            hint_text='姓名',
            multiline=False,
            size_hint=(1, None),
            height=dp(50),
            background_color=(0.95, 0.95, 0.95, 1),
            foreground_color=(0.2, 0.2, 0.2, 1),
            padding=dp(10)
        )

        # 手机号输入
        self.phone_input = TextInput(
            hint_text='手机号',
            multiline=False,
            input_filter='int',
            size_hint=(1, None),
            height=dp(50),
            background_color=(0.95, 0.95, 0.95, 1),
            foreground_color=(0.2, 0.2, 0.2, 1),
            padding=dp(10)
        )

        # 部门/岗位
        self.department_input = TextInput(
            hint_text='部门/岗位',
            multiline=False,
            size_hint=(1, None),
            height=dp(50),
            background_color=(0.95, 0.95, 0.95, 1),
            foreground_color=(0.2, 0.2, 0.2, 1),
            padding=dp(10)
        )

        self.security_question_spinner = Spinner(
            text='请选择安全问题',
            values=['您小学班主任姓名', '您出生的城市', '您最喜欢的运动', '您母亲的名字'],
            size_hint=(1, None),
            height=dp(46),
            font_size=dp(12)
        )

        self.security_answer_input = TextInput(
            hint_text='安全问题答案',
            multiline=False,
            size_hint=(1, None),
            height=dp(50),
            background_color=(0.95, 0.95, 0.95, 1),
            foreground_color=(0.2, 0.2, 0.2, 1),
            padding=dp(10)
        )
        
        # 密码输入
        self.password_input = TextInput(


            hint_text='密码',
            password=True,
            multiline=False,
            size_hint=(1, None),
            height=dp(50),
            background_color=(0.95, 0.95, 0.95, 1),
            foreground_color=(0.2, 0.2, 0.2, 1),
            padding=dp(10)
        )
        
        # 确认密码输入
        self.confirm_password_input = TextInput(
            hint_text='确认密码',
            password=True,
            multiline=False,
            size_hint=(1, None),
            height=dp(50),
            background_color=(0.95, 0.95, 0.95, 1),
            foreground_color=(0.2, 0.2, 0.2, 1),
            padding=dp(10)
        )
        
        input_layout.add_widget(self.username_input)
        input_layout.add_widget(self.real_name_input)
        input_layout.add_widget(self.phone_input)
        input_layout.add_widget(self.department_input)
        input_layout.add_widget(self.security_question_spinner)
        input_layout.add_widget(self.security_answer_input)
        input_layout.add_widget(self.password_input)
        input_layout.add_widget(self.confirm_password_input)


        
        # 按钮容器
        button_layout = GridLayout(cols=1, spacing=dp(10), size_hint_y=None)
        button_layout.bind(minimum_height=button_layout.setter('height'))
        
        # 注册按钮
        register_btn = StyledButton(text='注册', size_hint=(1, None), height=dp(44))
        register_btn.bind(on_press=self.register)
        
        # 返回登录按钮
        back_btn = StyledButton(text='返回登录', background_color=(0.8, 0.8, 0.8, 1), size_hint=(1, None), height=dp(44))
        back_btn.bind(on_press=self.go_back)
        
        button_layout.add_widget(register_btn)
        button_layout.add_widget(back_btn)


        # 组装表单
        form_layout.add_widget(title)
        form_layout.add_widget(notice_label)
        form_layout.add_widget(input_layout)
        form_layout.add_widget(button_layout)
        form_scroll.add_widget(form_layout)

        # 添加所有组件
        main_layout.add_widget(form_scroll)

        
        self.add_widget(main_layout)


    def update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
    
    def register(self, instance):

        """处理注册"""
        username = self.username_input.text.strip()
        password = self.password_input.text.strip()
        confirm_password = self.confirm_password_input.text.strip()
        real_name = self.real_name_input.text.strip()
        phone = self.phone_input.text.strip()
        department = self.department_input.text.strip()

        if not username or not password:
            self.show_popup("错误", "请输入用户名和密码")
            return

        if not real_name or not phone or not department:
            self.show_popup("错误", "请填写姓名、手机号与部门/岗位")
            return

        if not phone.isdigit() or len(phone) < 7:
            self.show_popup("错误", "手机号格式不正确")
            return

        if password != confirm_password:
            self.show_popup("错误", "两次输入的密码不一致")
            return
        
        if len(password) < 6:
            self.show_popup("错误", "密码长度至少6位")
            return

        security_question = self.security_question_spinner.text
        security_answer = self.security_answer_input.text.strip()
        if security_question == '请选择安全问题' or not security_answer:
            self.show_popup("错误", "请填写安全问题与答案")
            return

        # 服务器为准：密保答案不落本地，仅保存必要的资料缓存
        profile_cache = {
            'username': username,
            'real_name': real_name,
            'phone': phone,
            'department': department,
            'security_question': security_question,
            'created_at': datetime.now().isoformat(),
        }

        # 先走服务器注册（用于群/公告等在线功能；用户数据保留服务器）
        server_url = get_server_url()
        if server_url:
            def work():
                try:
                    api = get_api()
                    if not api.health():
                        raise RuntimeError('服务器维护中，请稍后再试。。。')

                    api.register(username, password, real_name, phone, department, security_question, security_answer)

                    # 注册成功后：自动登录并进入主界面
                    token = api.login(username, password)
                    me = api.me(token) or {}
                    role = str(me.get('role') or 'user')

                    app = App.get_running_app()
                    app.server_url = server_url
                    app.api_token = token
                    app.server_role = role
                    app.current_user = username
                    app.user_data = {
                        'role': role,
                        'is_admin': role in ('admin', 'engineer'),
                        'user_id': str(me.get('id') or ''),
                    }

                    try:
                        client_store.put('auth', username=username, token=token, role=role, server_url=server_url)
                    except Exception:
                        pass

                    # 本机仅缓存个人资料（不保存密码/密保答案）
                    try:
                        s = db.get_user_settings(username) or {}
                        profile_cache2 = dict(profile_cache or {})
                        profile_cache2['user_id'] = str(me.get('id') or '')
                        s['profile_cache'] = profile_cache2
                        db.save_user_settings(username, s)
                    except Exception:
                        pass

                    def _go(*_):
                        try:
                            self.manager.current = 'main'
                        except Exception:
                            pass

                    Clock.schedule_once(lambda *_: self.show_popup('成功', '注册并登录成功'), 0)
                    Clock.schedule_once(_go, 0.2)
                except Exception as e:
                    Clock.schedule_once(lambda *_, msg=str(e): self.show_popup("注册失败", msg), 0)



            Thread(target=work, daemon=True).start()
            return

        # 未配置服务器：仅本地模式（兼容离线使用）
        security_answer_hash = db._hash_password(security_answer) if hasattr(db, '_hash_password') else security_answer
        profile = {
            'real_name': real_name,
            'phone': phone,
            'department': department,
            'security_question': security_question,
            'security_answer': security_answer_hash,
        }

        success, message = db.add_user(username, password, profile=profile)
        if success:
            try:
                s = db.get_user_settings(username) or {}
                s['profile_cache'] = profile_cache
                db.save_user_settings(username, s)
            except Exception:
                pass

            # 本地模式：注册后直接登录进入主界面
            ok, user_data = db.validate_user(username, password)
            if ok:
                app = App.get_running_app()
                app.current_user = username
                app.user_data = user_data
                try:
                    if hasattr(app, 'api_token'):
                        delattr(app, 'api_token')
                    if hasattr(app, 'server_role'):
                        delattr(app, 'server_role')
                    if hasattr(app, 'server_url'):
                        delattr(app, 'server_url')
                except Exception:
                    pass

                Clock.schedule_once(lambda *_: self.show_popup('成功', '注册并登录成功'), 0)
                Clock.schedule_once(lambda *_: setattr(self.manager, 'current', 'main'), 0.2)
            else:
                self.show_popup('成功', '注册成功，请返回登录')
        else:
            self.show_popup("注册失败", message)




    
    def go_back(self, instance):
        """返回登录界面"""
        self.manager.current = 'login'


    
    def show_popup(self, title, message):
        """显示提示弹窗（自动换行/对齐，背景色与首页一致）"""
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
            background=''
        )
        popup.open()





# buildozer 默认入口通常是 main.py。为了避免移动端安装后点击图标直接退回桌面，
# 这里提供一个兜底启动逻辑：当 main.py 作为入口脚本执行时，启动 app_main.AttendanceApp。
if __name__ == '__main__':
    import os
    import sys
    import traceback

    def _add_path(p: str, tag: str = ''):
        if not p:
            return
        try:
            if os.path.isdir(p) and p not in sys.path:
                sys.path.insert(0, p)
                try:
                    from kivy.logger import Logger
                    Logger.info(f"STARTUP sys.path + {p} ({tag})")
                except Exception:
                    pass
        except Exception:
            pass

    # 1) 先用环境变量（p4a 常见）
    private = os.environ.get('ANDROID_PRIVATE') or ''
    argument = os.environ.get('ANDROID_ARGUMENT') or ''
    _add_path(os.path.join(private, 'app'), 'ANDROID_PRIVATE/app')
    _add_path(os.path.join(argument, 'app'), 'ANDROID_ARGUMENT/app')

    # 2) 再用 Activity.getFilesDir() 推导（最稳）
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        act = PythonActivity.mActivity
        files_dir = str(act.getFilesDir().getAbsolutePath())
        _add_path(os.path.join(files_dir, 'app'), 'Activity.getFilesDir/app')
    except Exception:
        pass

    # 3) 兜底：如果 cwd 本身就是 app 目录
    try:
        _add_path(os.getcwd(), 'cwd')
    except Exception:
        pass


    try:
        from app_main import AttendanceApp
        AttendanceApp().run()
    except Exception:
        # 不要静默：把根因打印到 logcat，便于 adb 抓取
        try:
            from kivy.logger import Logger
            Logger.error(f"STARTUP main.py bootstrap failed: {traceback.format_exc()}")
        except Exception:
            pass

        # 兜底显示错误页（避免“点开就回桌面”）
        try:
            from kivy.app import App
            from kivy.uix.label import Label

            msg = traceback.format_exc()
            if len(msg) > 1500:
                msg = msg[-1500:]

            class _BootFail(App):
                def build(self):
                    return Label(text='启动失败\n\n' + msg)

            _BootFail().run()
        except Exception:
            raise

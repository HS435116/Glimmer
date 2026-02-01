# Copyright (C) [2026] [晨曦微光]
# 此软件受著作权法保护。未经明确书面许可，任何单位或个人不得复制、分发、修改或用于商业用途。
# APP名称：[晨曦智能打卡]
# 版本号：1.0.0

"""
主界面和打卡功能模块
"""


import os
import json
import calendar
import time

from threading import Thread
from datetime import datetime, time as dt_time, timedelta

from glimmer_api import GlimmerAPI




from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.modalview import ModalView
from kivy.uix.spinner import Spinner
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import AsyncImage
from kivy.uix.textinput import TextInput
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.utils import platform as kivy_platform

# plyer 在不同平台/权限环境下可能不可用；为避免启动即异常导致"看起来进后台/闪退"，这里做容错。
try:
    from plyer import gps, notification
except Exception:  # pragma: no cover
    gps = None

    class _NotificationFallback:
        @staticmethod
        def notify(**kwargs):
            return

    notification = _NotificationFallback()

from main import StyledButton, db, get_server_url, safe_notify


import math
import webbrowser
from urllib.parse import urlparse




class MainScreen(Screen):
    """主界面"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_location = None
        self.gps_enabled = False
        self.ad_marquee_jobs = {}
        self._update_prompt_version = None
        self._announcement_flash_event = None
        self._announcement_flash_on = False
        self._announcement_alert_token_system = ''
        self._announcement_alert_token_punch = ''




        with self.canvas.before:

            Color(0.0667, 0.149, 0.3098, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self.update_bg, size=self.update_bg)
        
        # 主布局
        main_layout = BoxLayout(orientation='vertical', spacing=dp(10))

        
        # 顶部栏（移动端适配）
        top_container = BoxLayout(orientation='vertical', size_hint=(1, None), height=dp(92), padding=[dp(8), dp(6)], spacing=dp(4))

        title_box = AnchorLayout(size_hint=(1, None), height=dp(34), anchor_x='center', anchor_y='center')
        title_box.add_widget(Label(text='晨曦智能打卡', font_size=dp(20), bold=True, color=(1, 1, 1, 1)))

        info_row = BoxLayout(orientation='horizontal', size_hint=(1, None), height=dp(40), spacing=dp(6))

        # 用户信息 + 用户ID标签（可点击查看个人资料）
        self.user_label = Label(text='', font_size=dp(13), color=(0.9, 0.9, 0.9, 1), shorten=True, shorten_from='right', halign='left', valign='middle')
        self.user_label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))

        self.user_id_btn = Button(
            text='ID:未知',
            size_hint=(None, 1),
            width=dp(110),
            font_size=dp(10),
            background_color=(0.12, 0.2, 0.35, 0.95),
            color=(0.95, 0.97, 1, 1),
            halign='center',
            valign='middle',
            shorten=True,
            shorten_from='right',
        )
        self.user_id_btn.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
        self.user_id_btn.bind(on_press=lambda *_: self.open_profile())

        left_box = BoxLayout(size_hint=(0.38, 1), spacing=dp(6))
        left_box.add_widget(self.user_label)
        left_box.add_widget(self.user_id_btn)


        # 右侧按钮
        actions_box = GridLayout(cols=5, size_hint=(0.62, 1), spacing=dp(6))
        settings_btn = Button(text='设置', size_hint=(1, 1), font_size=dp(11), background_color=(0.15, 0.28, 0.5, 1), color=(1, 1, 1, 1))
        settings_btn.bind(on_press=self.open_settings)

        groups_btn = Button(text='团队', size_hint=(1, 1), font_size=dp(11), background_color=(0.15, 0.28, 0.5, 1), color=(1, 1, 1, 1))

        groups_btn.bind(on_press=self.open_groups)

        # 管理员按钮（仅管理员可见）
        self.admin_btn = Button(text='管理员', size_hint=(1, 1), font_size=dp(11), background_color=(0.15, 0.28, 0.5, 1), color=(1, 1, 1, 1))
        self.admin_btn.bind(on_press=self.open_admin)

        self.announcement_btn = Button(text='公告', size_hint=(1, 1), font_size=dp(11), background_color=(0.18, 0.32, 0.55, 1), color=(1, 1, 1, 1))
        self.announcement_btn.bind(on_press=self.show_announcement_popup)


        # 退出按钮
        logout_btn = Button(text='退出', size_hint=(1, 1), font_size=dp(11), background_color=(0.28, 0.16, 0.2, 1), color=(1, 1, 1, 1))
        logout_btn.bind(on_press=self.logout)

        actions_box.add_widget(settings_btn)
        actions_box.add_widget(groups_btn)
        actions_box.add_widget(self.admin_btn)
        actions_box.add_widget(self.announcement_btn)
        actions_box.add_widget(logout_btn)



        info_row.add_widget(left_box)
        info_row.add_widget(actions_box)

        top_container.add_widget(title_box)
        top_container.add_widget(info_row)


        # 顶部广告位
        self.ad_top = BoxLayout(size_hint=(1, None), height=dp(60), padding=dp(10))




        
        main_layout.add_widget(top_container)
        main_layout.add_widget(self.ad_top)

        
        # 打卡区域

        punch_card_area = BoxLayout(
            orientation='vertical',
            size_hint=(1, None),
            padding=[dp(18), dp(14), dp(18), dp(14)],
            spacing=dp(10),
        )
        self.punch_card_area = punch_card_area
        punch_card_area.bind(minimum_height=punch_card_area.setter('height'))

        # 当前状态显示
        self.status_label = Label(
            text='准备打卡',
            font_size=dp(18),
            bold=True,
            color=(0.95, 0.97, 1, 1),
            size_hint=(1, None),
            height=dp(34),
        )

        # 位置信息显示
        self.location_label = Label(
            text='位置: 等待获取...',
            font_size=dp(14),
            color=(0.82, 0.88, 0.95, 1),
            size_hint=(1, None),
            height=dp(24),
        )

        # 范围状态提示
        self.range_status_label = Label(
            text='范围状态: 未获取',
            font_size=dp(14),
            color=(0.82, 0.88, 0.95, 1),
            size_hint=(1, None),
            height=dp(24),
        )

        
        # 打卡按钮（根据屏幕高度自适应）
        self.punch_btn = StyledButton(
            text='立即打卡',
            background_color=(0.2, 0.8, 0.2, 1)
        )
        self.punch_btn.size_hint = (1, None)

        self.punch_btn.bind(on_press=self.punch_card)

        try:
            Window.bind(size=self._update_punch_button_layout)
        except Exception:
            pass
        Clock.schedule_once(self._update_punch_button_layout, 0)
        
        # 自动打卡开关
        auto_punch_layout = BoxLayout(size_hint=(1, None), height=dp(42), spacing=dp(10))
        self.auto_punch_layout = auto_punch_layout
        auto_punch_layout.add_widget(Label(text='自动打卡:', font_size=dp(14), color=(0.92, 0.95, 1, 1)))

        
        self.auto_punch_switch = Button(
            text='开启',
            background_color=(0.2, 0.8, 0.2, 1),
            size_hint=(0.3, 1)
        )

        self.auto_punch_switch.bind(on_press=self.toggle_auto_punch)
        auto_punch_layout.add_widget(self.auto_punch_switch)
        
        punch_card_area.add_widget(self.status_label)
        punch_card_area.add_widget(self.location_label)
        punch_card_area.add_widget(self.range_status_label)
        punch_card_area.add_widget(self.punch_btn)
        punch_card_area.add_widget(auto_punch_layout)

        
        main_layout.add_widget(punch_card_area)
        
        # 打卡记录区域
        records_header = BoxLayout(size_hint=(1, None), height=dp(32), spacing=dp(6), padding=[dp(8), 0])
        records_label = Label(
            text='本月打卡概览',
            font_size=dp(14),
            bold=True,
            size_hint=(0.42, 1),
            color=(0.95, 0.97, 1, 1),
            halign='left',
            valign='middle'
        )
        records_label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))

        self.punch_days_label = Label(text='打卡天数：0', font_size=dp(11), size_hint=(0.29, 1), color=(0.95, 0.97, 1, 1), markup=True)
        self.missed_days_label = Label(text='未打卡天数：0', font_size=dp(11), size_hint=(0.29, 1), color=(0.95, 0.97, 1, 1), markup=True)


        records_header.add_widget(records_label)
        records_header.add_widget(self.punch_days_label)
        records_header.add_widget(self.missed_days_label)

        main_layout.add_widget(records_header)

        
        # 滚动视图容器（占据剩余空间，避免底部广告位变高后挤压错位）
        scroll_view = ScrollView(size_hint=(1, 1))

        
        # 记录列表容器
        self.records_layout = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.records_layout.bind(minimum_height=self.records_layout.setter('height'))
        
        scroll_view.add_widget(self.records_layout)
        main_layout.add_widget(scroll_view)

        # 底部广告位（图片广告时：无内边距，铺满容器）
        self.ad_bottom = BoxLayout(size_hint=(1, None), height=dp(60), padding=[0, 0, 0, 0])


        main_layout.add_widget(self.ad_bottom)
        
        self.add_widget(main_layout)

        
        # 启动GPS
        Clock.schedule_once(self.start_gps, 1)
        
        # 检查自动打卡设置
        Clock.schedule_once(self.check_auto_punch_settings, 2)
    
    def on_enter(self):
        """进入界面时更新显示"""
        app = App.get_running_app()
        if hasattr(app, 'current_user'):
            display_name = str(app.current_user or '')
            try:
                prof = db.get_user_profile(app.current_user) or {}
                real_name = str(prof.get('real_name') or '').strip()
                if real_name:
                    display_name = real_name
            except Exception:
                pass
            self.user_label.text = f"用户: {display_name}" if display_name else "用户: 未知"
            try:
                uname = str(app.current_user or '')
                self.user_id_btn.text = f"用户:{uname}" if uname else '用户:未知'
            except Exception:
                self.user_id_btn.text = '用户:未知'



            self.load_attendance_records()

            self.update_ad_visibility()
            self.check_for_updates()
            self.update_announcement_indicator()

            # 管理员按钮可见性


            is_admin = bool(app.user_data.get('is_admin')) if hasattr(app, 'user_data') else False
            self.admin_btn.disabled = not is_admin
            self.admin_btn.opacity = 1 if is_admin else 0

            # 在线公告轮询（群内公告/全局公告）：只要有网络就可收到通知
            self._start_server_feed_polling()

            # 刷新"全局公告/版本信息"，用于公告按钮展示与闪烁提醒
            self._start_public_config_polling()

            # 离线补传：连接主服务器后自动同步历史打卡记录
            self._start_attendance_sync_polling()

            # 网络状态监听：从离线->在线时立即触发一次同步/刷新
            self._start_network_monitoring()

            # 管理员提醒：补录申请/聊天消息等
            self._start_admin_notice_polling()

            # 聊天提醒：未读聊天消息上线后通过"公告"提醒
            self._start_chat_notice_polling()





    def _start_public_config_polling(self):
        if getattr(self, '_public_cfg_ev', None):
            return

        # 进入主界面立即拉一次
        Clock.schedule_once(lambda *_: self.refresh_server_public_announcement(), 0.4)
        # 后续周期刷新（避免发布公告后客户端不更新）
        self._public_cfg_ev = Clock.schedule_interval(lambda *_: self.refresh_server_public_announcement(), 10)



    def refresh_server_public_announcement(self):
        app = App.get_running_app()
        base_url = str(getattr(app, 'server_url', '') or get_server_url() or '').strip()

        if not base_url:
            return

        def work():
            try:
                api = GlimmerAPI(base_url)
                if not api.health():
                    return

                latest = api.public_latest_global_announcement()
                version = api.public_version()
                ads = None
                try:
                    ads = api.get_ads()
                except Exception:
                    ads = None

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

                # 广告位：工程师发布后固定显示在登录后页面底部
                if isinstance(ads, dict) and ads:
                    enabled = bool(ads.get('enabled', False))
                    settings['ad_top_enabled'] = False
                    settings['ad_bottom_enabled'] = enabled
                    settings['ad_bottom_text'] = str(ads.get('text') or '')
                    settings['ad_bottom_image_url'] = str(ads.get('image_url') or '')
                    settings['ad_bottom_text_url'] = str(ads.get('link_url') or '')
                    # 工程师发布广告：展示模式由服务端下发（垂直/水平/静止）
                    settings['ad_bottom_scroll_mode'] = str(ads.get('scroll_mode') or '垂直滚动')



                db.save_user_settings('__global__', settings)


                Clock.schedule_once(lambda *_: (self.update_announcement_indicator(), self.check_for_updates()), 0)
            except Exception:
                return

        Thread(target=work, daemon=True).start()


    def _start_server_feed_polling(self):

        if getattr(self, '_feed_poll_ev', None):
            return

        app = App.get_running_app()
        token = getattr(app, 'api_token', None)
        base_url = getattr(app, 'server_url', None)
        if not token or not base_url:
            return

        if not hasattr(self, '_feed_since_iso'):
            self._feed_since_iso = None

        self._feed_poll_ev = Clock.schedule_interval(self._poll_server_feed, 8)
        Clock.schedule_once(self._poll_server_feed, 0.8)


    def _poll_server_feed(self, _dt):
        app = App.get_running_app()
        token = getattr(app, 'api_token', None)
        base_url = getattr(app, 'server_url', None)
        if not token or not base_url:
            return

        since = getattr(self, '_feed_since_iso', None)

        def work():
            try:
                api = GlimmerAPI(str(base_url))
                items = api.announcements_feed(str(token), since_iso=since)
                if not items:
                    return

                last_created = None
                for it in items:
                    try:
                        title = str(it.get('title') or '公告')
                        content = str(it.get('content') or '')
                        created_at = str(it.get('created_at') or '')
                        if created_at:
                            last_created = created_at

                        # 系统通知（尽量不打断用户）
                        safe_notify(title=title, message=content[:120], timeout=3)
                    except Exception:
                        continue

                if last_created:
                    self._feed_since_iso = last_created
            except Exception:
                return

        Thread(target=work, daemon=True).start()


    def _start_attendance_sync_polling(self):
        if getattr(self, '_attendance_sync_ev', None):
            return
        self._attendance_sync_ev = Clock.schedule_interval(lambda *_: self._trigger_attendance_sync(), 20)
        Clock.schedule_once(lambda *_: self._trigger_attendance_sync(), 2)


    def _start_network_monitoring(self):
        # 轻量网络监听：从离线恢复为在线时，立即触发一次同步与当月回填
        if getattr(self, '_net_mon_ev', None):
            return
        self._net_online = None
        self._net_mon_inflight = False
        self._net_mon_ev = Clock.schedule_interval(lambda *_: self._network_monitor_tick(), 12)
        Clock.schedule_once(lambda *_: self._network_monitor_tick(), 1.2)


    def _network_monitor_tick(self):
        if getattr(self, '_net_mon_inflight', False):
            return

        app = App.get_running_app()
        base_url = str(getattr(app, 'server_url', '') or get_server_url() or '')
        if not base_url:
            return

        self._net_mon_inflight = True

        def work():
            online = False
            try:
                api = GlimmerAPI(base_url, timeout=3.0)
                online = bool(api.health())
            except Exception:
                online = False

            def ui(_dt):
                try:
                    prev = getattr(self, '_net_online', None)
                    self._net_online = online

                    # 离线 -> 在线：立刻补传一次，并拉当月记录回填
                    if prev is False and online is True:
                        self._trigger_attendance_sync()
                        try:
                            self._sync_attendance_month_from_server(datetime.now().strftime('%Y-%m'))
                        except Exception:
                            pass
                finally:
                    self._net_mon_inflight = False

            Clock.schedule_once(ui, 0)

        Thread(target=work, daemon=True).start()


    def _parse_location_text(self, location_text: str):
        try:
            if not location_text:
                return None, None
            parts = [p.strip() for p in str(location_text).split(',')]
            if len(parts) < 2:
                return None, None
            return float(parts[0]), float(parts[1])
        except Exception:
            return None, None


    def _trigger_attendance_sync(self):
        if getattr(self, '_attendance_sync_inflight', False):
            return

        app = App.get_running_app()
        if not hasattr(app, 'current_user'):
            return

        token = str(getattr(app, 'api_token', '') or '')
        base_url = str(getattr(app, 'server_url', '') or get_server_url() or '')
        if not token or not base_url:
            return

        self._attendance_sync_inflight = True

        def work():
            try:
                api = GlimmerAPI(base_url)
                if not api.health():
                    return

                username = str(getattr(app, 'current_user', '') or '')
                items = db.get_unsynced_attendance(username, limit=80) if hasattr(db, 'get_unsynced_attendance') else []
                for rec in (items or []):
                    rid = str(rec.get('record_id') or '')
                    status = str(rec.get('status') or '打卡成功')
                    notes = str(rec.get('notes') or '')
                    lat, lon = self._parse_location_text(str(rec.get('location') or ''))

                    tag = f"[cid:{rid}]" if rid else ''
                    if tag and tag not in notes:
                        notes = (notes + ' ' + tag).strip()

                    client_time = str(rec.get('timestamp') or '').strip() or None
                    punch_type = str(rec.get('punch_type') or '').strip() or None
                    api.punch_attendance(
                        token,
                        status=status,
                        lat=lat,
                        lon=lon,
                        notes=notes,
                        group_id=None,
                        client_time=client_time,
                        punch_type=punch_type,
                    )


                    if rid and hasattr(db, 'mark_attendance_synced'):
                        db.mark_attendance_synced(rid, True, '')

            except Exception as e:
                # 网络不通/服务器不可达：只记录错误，不允许导致应用崩溃
                try:
                    username = str(getattr(app, 'current_user', '') or '')
                    if username:
                        settings = db.get_user_settings(username) or {}
                        settings['last_sync_error'] = str(e)[:200]
                        settings['last_sync_error_time'] = datetime.now().strftime('%Y-%m-%d %H:%M')
                        db.save_user_settings(username, settings)
                except Exception:
                    pass
            finally:
                self._attendance_sync_inflight = False

        Thread(target=work, daemon=True).start()


    def _is_admin_account(self) -> bool:
        app = App.get_running_app()
        role = ''
        try:
            role = str(getattr(app, 'server_role', '') or (getattr(app, 'user_data', {}) or {}).get('role') or '')
        except Exception:
            role = ''
        return role == 'admin'


    def _start_admin_notice_polling(self):
        if getattr(self, '_admin_notice_ev', None):
            return
        if not self._is_admin_account():
            return

        self._admin_notice_ev = Clock.schedule_interval(lambda *_: self._poll_admin_notices(), 12)
        Clock.schedule_once(lambda *_: self._poll_admin_notices(), 1.5)


    def _poll_admin_notices(self):
        if getattr(self, '_admin_notice_inflight', False):
            return

        app = App.get_running_app()
        if not hasattr(app, 'current_user'):
            return

        token = str(getattr(app, 'api_token', '') or '')
        base_url = str(getattr(app, 'server_url', '') or get_server_url() or '')
        if not token or not base_url:
            return

        self._admin_notice_inflight = True

        def work():
            try:
                api = GlimmerAPI(base_url)
                if not api.health():
                    return

                username = str(getattr(app, 'current_user', '') or '')
                settings = db.get_user_settings(username) or {}

                # 1) 补录待审核
                corr_cnt = 0
                try:
                    corr_cnt = len(api.pending_corrections(token) or [])
                except Exception:
                    corr_cnt = 0

                # 2) 聊天消息（本机缓存）：文件更新则提示
                chat_unseen = False
                try:
                    chat_path = 'chat_cache.json'
                    if os.path.exists(chat_path):
                        mtime = float(os.path.getmtime(chat_path) or 0)
                        seen = float(settings.get('admin_chat_seen_mtime', 0) or 0)
                        if mtime > seen:
                            chat_unseen = True
                except Exception:
                    chat_unseen = False

                parts = []
                if corr_cnt > 0:
                    parts.append(f"有{corr_cnt}条补录待审核（在线管理->补录审核）")
                if chat_unseen:
                    parts.append('收到新的聊天消息（团队详情->成员->聊天）')

                text = "\n".join(parts).strip()
                now_text = datetime.now().strftime('%Y-%m-%d %H:%M')

                need_save = False
                new_cnt = int(corr_cnt or 0)
                old_cnt = int(settings.get('admin_notice_corr_count', 0) or 0)
                if old_cnt != new_cnt:
                    settings['admin_notice_corr_count'] = new_cnt
                    need_save = True

                if text:
                    if str(settings.get('admin_notice_text', '') or '') != text:
                        settings['admin_notice_text'] = text
                        settings['admin_notice_time'] = now_text
                        need_save = True
                else:
                    if settings.get('admin_notice_text') or old_cnt != 0:
                        settings['admin_notice_text'] = ''
                        settings['admin_notice_time'] = ''
                        settings['admin_notice_corr_count'] = 0
                        need_save = True

                if need_save:
                    db.save_user_settings(username, settings)


                Clock.schedule_once(lambda *_: self.update_announcement_indicator(), 0)
            except Exception:
                return
            finally:
                self._admin_notice_inflight = False

        Thread(target=work, daemon=True).start()


    def _start_chat_notice_polling(self):
        if getattr(self, '_chat_notice_ev', None):
            return
        if not self.is_logged_in():
            return

        self._chat_notice_ev = Clock.schedule_interval(lambda *_: self._poll_chat_notices(), 10)
        Clock.schedule_once(lambda *_: self._poll_chat_notices(), 1.2)


    def _poll_chat_notices(self):
        if getattr(self, '_chat_notice_inflight', False):
            return

        app = App.get_running_app()
        if not hasattr(app, 'current_user'):
            return

        token = str(getattr(app, 'api_token', '') or '')
        base_url = str(getattr(app, 'server_url', '') or get_server_url() or '')
        if not token or not base_url:
            return

        self._chat_notice_inflight = True

        def work():
            try:
                api = GlimmerAPI(base_url)
                if not api.health():
                    return

                cnt = 0
                try:
                    cnt = int(api.chat_unread_count(token) or 0)
                except Exception:
                    cnt = 0

                username = str(getattr(app, 'current_user', '') or '')
                settings = db.get_user_settings(username) or {}
                old_cnt = int(settings.get('chat_notice_count', 0) or 0)

                if cnt > 0:
                    # 只在数量变化时更新时间，避免一直闪
                    if old_cnt != cnt:
                        settings['chat_notice_count'] = cnt
                        settings['chat_notice_text'] = f"收到{cnt}条新聊天消息（团队详情->成员->聊天）"
                        settings['chat_notice_time'] = datetime.now().strftime('%Y-%m-%d %H:%M')
                        db.save_user_settings(username, settings)
                else:
                    if old_cnt != 0 or settings.get('chat_notice_text'):
                        settings['chat_notice_count'] = 0
                        settings['chat_notice_text'] = ''
                        settings['chat_notice_time'] = ''
                        db.save_user_settings(username, settings)

                Clock.schedule_once(lambda *_: self.update_announcement_indicator(), 0)
            except Exception:
                return
            finally:
                self._chat_notice_inflight = False

        Thread(target=work, daemon=True).start()


    def parse_version(self, version_text):



        parts = []
        for item in str(version_text).split('.'):
            if item.isdigit():
                parts.append(int(item))
                continue
            digits = ''.join(ch for ch in item if ch.isdigit())
            if digits:
                parts.append(int(digits))
        return tuple(parts) if parts else (0,)

    def get_installed_version(self):
        app = App.get_running_app()
        app_version = getattr(app, 'app_version', '1.0.0')
        settings = db.get_user_settings(app.current_user) or {}
        installed = settings.get('installed_version', app_version)
        if settings.get('installed_version') != installed:
            settings['installed_version'] = installed
            db.save_user_settings(app.current_user, settings)
        return installed, settings

    def check_for_updates(self):
        app = App.get_running_app()
        if not hasattr(app, 'current_user'):
            return

        global_settings = db.get_user_settings('__global__') or {}
        latest_version = global_settings.get('latest_version')
        if not latest_version:
            return

        installed_version, user_settings = self.get_installed_version()
        if self.parse_version(latest_version) <= self.parse_version(installed_version):
            return

        if self._update_prompt_version == latest_version:
            return

        if user_settings.get('last_notified_version') != latest_version:
            safe_notify(
                title='版本升级提醒',
                message=f"检测到新版本 {latest_version}，请及时升级",
                timeout=3
            )
            user_settings['last_notified_version'] = latest_version
            db.save_user_settings(app.current_user, user_settings)

        self._update_prompt_version = latest_version
        self.show_upgrade_prompt(latest_version, global_settings.get('latest_version_note', ''))

    def show_upgrade_prompt(self, latest_version, note_text):
        content = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(20))
        message = f"检测到新版本：{latest_version}\n{note_text or '建议尽快完成升级'}"
        info_label = Label(text=message, halign='left', valign='top', color=(1, 1, 1, 1))
        info_label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
        content.add_widget(info_label)

        btn_layout = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        upgrade_btn = Button(text='立即升级', background_color=(0.2, 0.6, 0.8, 1))
        later_btn = Button(text='稍后', background_color=(0.6, 0.6, 0.6, 1))
        btn_layout.add_widget(upgrade_btn)
        btn_layout.add_widget(later_btn)
        content.add_widget(btn_layout)

        self.upgrade_popup = Popup(title='版本升级', content=content, size_hint=(0.85, 0.45), background_color=(0.0667, 0.149, 0.3098, 1), background='')

        upgrade_btn.bind(on_press=lambda x: self.apply_upgrade(latest_version))
        later_btn.bind(on_press=lambda x: self.upgrade_popup.dismiss())
        self.upgrade_popup.open()

    def apply_upgrade(self, latest_version):
        app = App.get_running_app()
        settings = db.get_user_settings(app.current_user) or {}
        settings['installed_version'] = latest_version
        settings['last_notified_version'] = latest_version
        db.save_user_settings(app.current_user, settings)

        if hasattr(self, 'upgrade_popup'):
            self.upgrade_popup.dismiss()

        self.show_upgrade_done_popup(latest_version)

    def show_upgrade_done_popup(self, latest_version):
        content = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(20))
        info = f"升级完成，当前版本：{latest_version}\n请重新登录以完成更新。"
        info_label = Label(text=info, halign='left', valign='top', color=(1, 1, 1, 1))
        info_label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
        content.add_widget(info_label)


        btn = Button(text='重新登录', size_hint=(1, None), height=dp(44), background_color=(0.2, 0.6, 0.8, 1))
        content.add_widget(btn)

        popup = Popup(title='升级完成', content=content, size_hint=(0.82, 0.38), background_color=(0.0667, 0.149, 0.3098, 1), background='')

        btn.bind(on_press=lambda x: (popup.dismiss(), self.logout(None)))
        popup.open()


    def is_safe_url(self, url):
        if not url:
            return False
        parsed = urlparse(url.strip())
        return parsed.scheme in ('http', 'https') and bool(parsed.netloc)

    def confirm_open_link(self, url):
        if not self.is_safe_url(url):
            self.show_popup("提示", "链接格式不安全，已阻止打开")
            return

        content = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(20))
        info = Label(text=f"即将打开外部链接：\n{url}", halign='left', valign='top', color=(1, 1, 1, 1))
        info.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
        content.add_widget(info)

        btn_layout = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        open_btn = Button(text='打开', background_color=(0.2, 0.6, 0.8, 1))
        cancel_btn = Button(text='取消', background_color=(0.6, 0.6, 0.6, 1))
        btn_layout.add_widget(open_btn)
        btn_layout.add_widget(cancel_btn)
        content.add_widget(btn_layout)

        popup = Popup(title='外部链接提示', content=content, size_hint=(0.9, 0.45), background_color=(0.0667, 0.149, 0.3098, 1), background='')
        open_btn.bind(on_press=lambda x: (popup.dismiss(), webbrowser.open(url)))
        cancel_btn.bind(on_press=lambda x: popup.dismiss())
        popup.open()

    def get_system_announcement(self):
        settings = db.get_user_settings('__global__') or {}
        return settings.get('announcement_text', ''), settings.get('announcement_time', '')

    def get_punch_announcement(self):
        if not self.is_logged_in():
            return '', ''
        app = App.get_running_app()
        settings = db.get_user_settings(app.current_user) or {}

        # 管理员提醒（补录/聊天等）优先展示
        role = ''
        try:
            role = str(getattr(app, 'server_role', '') or (getattr(app, 'user_data', {}) or {}).get('role') or '')
        except Exception:
            role = ''

        if role == 'admin':
            admin_text = str(settings.get('admin_notice_text', '') or '')
            admin_time = str(settings.get('admin_notice_time', '') or '')
            if admin_text:
                return admin_text, admin_time

        # 聊天提醒（团队成员离线消息）：优先于普通打卡提示
        chat_text = str(settings.get('chat_notice_text', '') or '')
        chat_time = str(settings.get('chat_notice_time', '') or '')
        if chat_text:
            return chat_text, chat_time

        return settings.get('punch_notice_text', ''), settings.get('punch_notice_time', '')




    def is_logged_in(self):
        app = App.get_running_app()
        return hasattr(app, 'current_user')

    def get_announcement_token(self, text, time_text):
        return time_text or text or ''


    def get_announcement_seen_token(self, key):
        app = App.get_running_app()
        if not hasattr(app, 'current_user'):
            return ''
        settings = db.get_user_settings(app.current_user) or {}
        return settings.get(f'announcement_seen_token_{key}', '')

    def mark_announcement_seen(self, key, token):
        if not token:
            return
        app = App.get_running_app()
        if not hasattr(app, 'current_user'):
            return
        settings = db.get_user_settings(app.current_user) or {}
        settings[f'announcement_seen_token_{key}'] = token
        db.save_user_settings(app.current_user, settings)

    def update_announcement_indicator(self):
        if not hasattr(self, 'announcement_btn'):
            return
        system_text, system_time = self.get_system_announcement()
        punch_text, punch_time = self.get_punch_announcement()
        system_token = self.get_announcement_token(system_text, system_time)
        punch_token = self.get_announcement_token(punch_text, punch_time)
        seen_system = self.get_announcement_seen_token('system')
        seen_punch = self.get_announcement_seen_token('punch')
        system_unseen = system_token and system_token != seen_system
        punch_unseen = punch_token and punch_token != seen_punch

        if not self.is_logged_in():
            punch_unseen = False

        if system_unseen or punch_unseen:
            self.start_announcement_flash()
            if system_unseen and system_token != self._announcement_alert_token_system:
                self.send_announcement_alert(system_text)
                self._announcement_alert_token_system = system_token
            if punch_unseen and punch_token != self._announcement_alert_token_punch:
                self.send_announcement_alert(punch_text)
                self._announcement_alert_token_punch = punch_token
        else:
            self.stop_announcement_flash()



    def send_announcement_alert(self, text):
        message = (text or '').strip()
        if not message:
            return
        safe_notify(
            title='公告提醒',
            message=message,
            timeout=3
        )

    def start_announcement_flash(self):

        if self._announcement_flash_event:
            return
        self._announcement_flash_event = Clock.schedule_interval(self.toggle_announcement_flash, 0.6)

    def stop_announcement_flash(self):
        if self._announcement_flash_event:
            self._announcement_flash_event.cancel()
            self._announcement_flash_event = None
        self._announcement_flash_on = False
        self._announcement_alert_token_system = ''
        self._announcement_alert_token_punch = ''


        self.announcement_btn.background_color = (0.18, 0.32, 0.55, 1)

    def toggle_announcement_flash(self, dt):
        self._announcement_flash_on = not self._announcement_flash_on
        self.announcement_btn.background_color = (0.85, 0.45, 0.1, 1) if self._announcement_flash_on else (0.18, 0.32, 0.55, 1)


    def show_announcement_popup(self, instance):
        system_text, system_time = self.get_system_announcement()
        punch_text, punch_time = self.get_punch_announcement()

        if not system_text and not punch_text:
            self.show_popup("通知", "暂无公告")
            return

        if not self.is_logged_in():
            if not system_text:
                self.show_popup("通知", "暂无公告")
                return
            def close_only(*args):
                self.update_announcement_indicator()
            open_popup = None
            def open_popup(text, time_text, key, token, on_close=None):
                content = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(20))
                title = f"公告时间：{time_text}" if time_text else "公告"
                content.add_widget(Label(text=title, color=(0.9, 0.95, 1, 1)))

                msg_scroll = ScrollView(size_hint=(1, 1), bar_width=dp(2))
                message = Label(text=text, halign='left', valign='top', color=(1, 1, 1, 1), size_hint=(1, None))
                message.bind(size=lambda instance, value: setattr(instance, 'text_size', (value[0], None)))
                message.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1]))
                msg_scroll.add_widget(message)
                content.add_widget(msg_scroll)


                close_btn = Button(text='关闭', size_hint=(1, None), height=dp(44), background_color=(0.2, 0.6, 0.8, 1))
                content.add_widget(close_btn)

                popup = Popup(title='公告提醒', content=content, size_hint=(0.88, 0.5), background_color=(0.0667, 0.149, 0.3098, 1), background='')

                def handle_close(*args):
                    popup.dismiss()
                    if on_close:
                        on_close()

                close_btn.bind(on_press=handle_close)
                popup.open()
            open_popup(system_text, system_time, 'system', self.get_announcement_token(system_text, system_time), close_only)
            return


        system_token = self.get_announcement_token(system_text, system_time)
        punch_token = self.get_announcement_token(punch_text, punch_time)
        seen_system = self.get_announcement_seen_token('system')
        seen_punch = self.get_announcement_seen_token('punch')
        system_unseen = system_token and system_token != seen_system
        punch_unseen = punch_token and punch_token != seen_punch

        app = App.get_running_app()
        role = ''
        try:
            role = str(getattr(app, 'server_role', '') or (getattr(app, 'user_data', {}) or {}).get('role') or '')
        except Exception:
            role = ''

        admin_corr_cnt = 0
        try:
            if role == 'admin' and hasattr(app, 'current_user'):
                s = db.get_user_settings(app.current_user) or {}
                admin_corr_cnt = int(s.get('admin_notice_corr_count', 0) or 0)
        except Exception:
            admin_corr_cnt = 0

        def goto_corr_tab():
            try:
                self.manager.current = 'server_admin'
            except Exception:
                return

            def _jump(_dt):
                try:
                    scr = self.manager.get_screen('server_admin')
                    if hasattr(scr, 'show_tab'):
                        scr.show_tab('corr')
                except Exception:
                    pass

            Clock.schedule_once(_jump, 0.2)

        punch_action = goto_corr_tab if (role == 'admin' and admin_corr_cnt > 0) else None

        def open_popup(text, time_text, key, token, on_close=None, action=None, action_text='去处理'):
            content = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(20))
            title = f"公告时间：{time_text}" if time_text else "公告"
            content.add_widget(Label(text=title, color=(0.9, 0.95, 1, 1)))

            msg_scroll = ScrollView(size_hint=(1, 1), bar_width=dp(2))
            message = Label(text=text, halign='left', valign='top', color=(1, 1, 1, 1), size_hint=(1, None))
            message.bind(size=lambda instance, value: setattr(instance, 'text_size', (value[0], None)))
            message.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1]))
            msg_scroll.add_widget(message)
            content.add_widget(msg_scroll)


            btn_row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
            close_btn = Button(text='关闭', background_color=(0.2, 0.6, 0.8, 1))

            def handle_close(*args):
                self.mark_announcement_seen(key, token)
                try:
                    popup.dismiss()
                except Exception:
                    pass
                if on_close:
                    on_close()
                else:
                    self.update_announcement_indicator()

            def handle_action(*args):
                self.mark_announcement_seen(key, token)
                try:
                    popup.dismiss()
                except Exception:
                    pass
                try:
                    if action:
                        action()
                finally:
                    self.update_announcement_indicator()

            if action:
                go_btn = Button(text=str(action_text or '去处理'), background_color=(0.18, 0.62, 0.38, 1))
                go_btn.bind(on_press=handle_action)
                btn_row.add_widget(go_btn)
                close_btn.size_hint = (0.5, 1)
                go_btn.size_hint = (0.5, 1)
            else:
                close_btn.size_hint = (1, 1)

            close_btn.bind(on_press=handle_close)
            btn_row.add_widget(close_btn)
            content.add_widget(btn_row)

            popup = Popup(title='公告提醒', content=content, size_hint=(0.88, 0.5), background_color=(0.0667, 0.149, 0.3098, 1), background='')
            popup.open()


        if system_unseen:
            next_step = None
            if punch_unseen:
                next_step = lambda: open_popup(punch_text, punch_time, 'punch', punch_token, action=punch_action, action_text='去补录审核')

            open_popup(system_text, system_time, 'system', system_token, next_step)
            return

        if punch_unseen:
            open_popup(punch_text, punch_time, 'punch', punch_token, action=punch_action, action_text='去补录审核')

            return

        if system_text:
            open_popup(system_text, system_time, 'system', system_token)
        else:
            open_popup(punch_text, punch_time, 'punch', punch_token, action=punch_action, action_text='去补录审核')



    def _update_punch_button_layout(self, *_args):
        # 让“立即打卡”在不同机型上有足够的可点击高度
        try:
            h = float(getattr(Window, 'height', 0) or 0)
        except Exception:
            h = 0

        if h and h < 650:
            ratio = 0.095
            btn_min, btn_max = dp(52), dp(72)
            status_fs, info_fs = dp(16), dp(12)
            status_h, info_h = dp(30), dp(22)
            auto_h = dp(40)
        elif h and h < 900:
            ratio = 0.088
            btn_min, btn_max = dp(54), dp(78)
            status_fs, info_fs = dp(18), dp(13)
            status_h, info_h = dp(34), dp(24)
            auto_h = dp(42)
        else:
            ratio = 0.082
            btn_min, btn_max = dp(56), dp(82)
            status_fs, info_fs = dp(20), dp(14)
            status_h, info_h = dp(38), dp(26)
            auto_h = dp(44)

        target_h = h * ratio if h else dp(62)
        target_h = max(btn_min, min(btn_max, target_h))

        try:
            # 按钮高度与字体
            self.punch_btn.height = target_h
            self.punch_btn.font_size = max(dp(15), min(dp(22), target_h * 0.33))

            # 文字区域高度与字体，避免挤压导致重叠
            self.status_label.font_size = status_fs
            self.location_label.font_size = info_fs
            self.range_status_label.font_size = info_fs

            self.status_label.height = status_h
            self.location_label.height = info_h
            self.range_status_label.height = info_h

            apl = getattr(self, 'auto_punch_layout', None)
            if apl is not None:
                apl.height = auto_h
        except Exception:
            pass


    def update_ad_visibility(self):

        """根据管理员广告设置显示广告位"""
        settings = db.get_user_settings('__global__') or {}
        top_enabled = settings.get('ad_top_enabled', False)
        bottom_enabled = settings.get('ad_bottom_enabled', False)

        self.render_ad_content(self.ad_top, settings, 'top', top_enabled)
        self.render_ad_content(self.ad_bottom, settings, 'bottom', bottom_enabled)



    def render_ad_content(self, container, settings, position, enabled):
        container.clear_widgets()
        self.stop_marquee(position)
        container.size_hint = (1, None)

        # 清理旧的点击绑定，避免重复触发
        try:
            cb = getattr(container, '_ad_touch_cb', None)
            if cb:
                container.unbind(on_touch_down=cb)
                container._ad_touch_cb = None
        except Exception:
            pass

        if not enabled:
            container.height = 0
            container.opacity = 0
            container.disabled = True
            return

        container.height = dp(60)
        container.opacity = 1
        container.disabled = False
        # 默认留出内边距；图片广告（底部）会在后面改为 0 以铺满
        try:
            container.padding = dp(10)
        except Exception:
            pass



        text = str(settings.get(f'ad_{position}_text', '') or '').strip()
        image_url = str(settings.get(f'ad_{position}_image_url', '') or '').strip()
        link_url = str(settings.get(f'ad_{position}_text_url', '') or '').strip()
        scroll_mode = str(settings.get(f'ad_{position}_scroll_mode', '静止') or '静止')
        # 兼容旧值："等待" 作为静止展示处理
        if scroll_mode == '等待':
            scroll_mode = '静止'

        # 互斥：文字广告与图片广告只能显示一种（若两者都有，默认以图片为准）
        if image_url:
            text = ''

        if not text and not image_url:
            container.add_widget(Label(text='广告位已开启', color=(1, 1, 1, 1)))
            return


        safe_image_url = image_url if self.is_safe_url(image_url) else ''
        safe_link_url = link_url if self.is_safe_url(link_url) else ''

        if image_url and not safe_image_url:
            container.add_widget(Label(text='广告图片地址无效', color=(1, 1, 1, 1)))
            return

        if image_url:
            # 图片广告：底部固定铺满显示，不展示文字
            if position == 'bottom':
                # 底部图片广告：固定高度，宽度自适应
                container.padding = [0, 0, 0, 0]
                container.height = dp(60)

                img = AsyncImage(
                    source=safe_image_url,
                    allow_stretch=True,
                    keep_ratio=False,
                    size_hint=(1, None),
                    height=container.height,
                )

                if safe_link_url:
                    def handle_touch(_instance, touch):
                        if container.collide_point(*touch.pos):
                            self.confirm_open_link(safe_link_url)
                            return True
                        return False

                    container._ad_touch_cb = handle_touch
                    container.bind(on_touch_down=handle_touch)

                container.add_widget(img)
                return

            # 其它位置：图片也优先展示，不拼接文字
            content = BoxLayout(orientation='horizontal', spacing=dp(8), padding=[dp(4), 0])
            image = AsyncImage(source=safe_image_url, allow_stretch=True, keep_ratio=True, size_hint=(None, 1), width=dp(60))
            content.add_widget(image)
            content.add_widget(Label(text='广告图片', color=(1, 1, 1, 1)))

            if safe_link_url:
                def handle_touch(instance, touch):
                    if instance.collide_point(*touch.pos):
                        self.confirm_open_link(safe_link_url)
                        return True
                    return False

                content.bind(on_touch_down=handle_touch)

            container.add_widget(content)
            return



        if scroll_mode in ('水平滚动', '垂直滚动'):
            marquee = FloatLayout(size_hint=(1, 1))
            marquee.size = container.size
            container.bind(size=lambda instance, value: setattr(marquee, 'size', value))
            text_label = Label(text=text, color=(1, 1, 1, 1), size_hint=(None, None))
            marquee.add_widget(text_label)

            # 滚动模式也支持点击跳转
            if safe_link_url:
                def handle_touch(_instance, touch):
                    if marquee.collide_point(*touch.pos):
                        self.confirm_open_link(safe_link_url)
                        return True
                    return False

                marquee.bind(on_touch_down=handle_touch)

            container.add_widget(marquee)
            Clock.schedule_once(lambda dt: self.start_marquee(marquee, text_label, scroll_mode, position), 0)
            return


        if safe_link_url:
            link_btn = Button(text=text or '广告链接', background_color=(0, 0, 0, 0), color=(1, 1, 1, 1))
            link_btn.bind(on_press=lambda x: self.confirm_open_link(safe_link_url))
            container.add_widget(link_btn)
        else:
            container.add_widget(Label(text=text, color=(1, 1, 1, 1)))


    def start_marquee(self, container, label, mode, key):
        def init_marquee(dt):
            if container.width <= 0 or container.height <= 0:
                Clock.schedule_once(init_marquee, 0.1)
                return

            label.texture_update()
            label.size = label.texture_size
            if mode == '水平滚动':
                label.pos = (container.width, (container.height - label.height) / 2)
            else:
                label.pos = ((container.width - label.width) / 2, -label.height)

            speed = dp(1.2)

            def move_label(move_dt):
                if mode == '水平滚动':
                    label.x -= speed
                    if label.right < 0:
                        label.x = container.width
                else:
                    label.y += speed
                    if label.y > container.height:
                        label.y = -label.height

            job = Clock.schedule_interval(move_label, 1 / 30)
            self.ad_marquee_jobs[key] = job

        init_marquee(0)


    def stop_marquee(self, key):
        job = self.ad_marquee_jobs.pop(key, None)
        if job:
            job.cancel()




    def update_bg(self, *args):

        """更新背景尺寸"""
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    
    def start_gps(self, dt):

        """启动GPS获取位置（移动端）。

        兼容点：
        - Android 需要运行时授权定位权限，否则不会回调。
        - plyer 回调的 lat/lon 可能是字符串，需转 float。
        - 部分机型首次定位较慢，增加超时提示与一次重试。
        """
        if kivy_platform in ('win', 'macosx', 'linux'):
            self.location_label.text = "位置: 桌面端不支持GPS"
            return

        self.location_label.text = "位置: 正在定位..."

        if not self._ensure_location_permission():
            return

        self._start_gps_stream()


    def _ensure_location_permission(self) -> bool:
        if kivy_platform != 'android':
            return True
        try:
            from android.permissions import request_permissions, Permission, check_permission
        except Exception:
            # 在少数环境里该模块可能不可用；此时只能尝试直接启动
            return True

        perms = [Permission.ACCESS_FINE_LOCATION, Permission.ACCESS_COARSE_LOCATION]
        missing = [p for p in perms if not check_permission(p)]
        if not missing:
            return True

        def _cb(_perms, grants):
            granted = all(bool(x) for x in grants)
            if granted:
                # 授权后立即再启动一次 GPS
                self.location_label.text = "位置: 正在定位..."
                Clock.schedule_once(lambda _dt: self.start_gps(0), 0)
            else:
                self.location_label.text = "位置: 未授权定位权限"
                try:
                    self.show_popup('权限提示', '请在系统设置中允许定位权限后再使用自动定位。')
                except Exception:
                    pass

        try:
            request_permissions(missing, _cb)
        except Exception:
            return True
        return False


    def _start_gps_stream(self):
        try:
            if not hasattr(self, '_gps_retry_done'):
                self._gps_retry_done = False

            if not self.gps_enabled:
                try:
                    gps.configure(on_location=self.on_location, on_status=self.on_gps_status)
                except TypeError:
                    gps.configure(on_location=self.on_location)

                try:
                    gps.start(minTime=1000, minDistance=0)
                except TypeError:
                    gps.start()

                self.gps_enabled = True

            # 首次定位超时提示
            Clock.unschedule(self._gps_first_fix_timeout)
            Clock.schedule_once(self._gps_first_fix_timeout, 8)

            # 兜底：部分机型 plyer.gps 不回调，用 Android 原生 lastKnownLocation 周期性补偿
            self._start_android_location_fallback()

        except Exception as e:
            self.location_label.text = "位置: GPS启动失败"
            try:
                self.show_popup('定位失败', f'GPS启动失败: {e}')
            except Exception:
                pass


    def on_gps_status(self, stype, status):
        # stype/status 的具体值因系统实现不同；这里仅做友好提示
        try:
            st = str(status)
            if 'disabled' in st.lower() or 'off' in st.lower():
                self.location_label.text = '位置: 定位服务未开启'
        except Exception:
            pass


    def _gps_first_fix_timeout(self, _dt):
        if self.current_location:
            return

        # 首次定位未返回：提示用户检查系统定位
        self.location_label.text = "位置: 未获取到定位，请检查系统定位/GPS已开启"

        # 机型提示（只提示一次）
        if not getattr(self, '_location_help_shown', False):
            hint = self._get_device_location_hint()
            if hint:
                self._location_help_shown = True
                try:
                    self.show_popup('定位提示', hint)
                except Exception:
                    pass

        # 兜底：继续启用 Android 原生位置轮询
        self._start_android_location_fallback()

        # 只重试一次，避免死循环
        if getattr(self, '_gps_retry_done', False):
            return

        self._gps_retry_done = True
        try:
            gps.stop()
        except Exception:
            pass
        self.gps_enabled = False
        Clock.schedule_once(lambda dt: self._start_gps_stream(), 0.6)



    def on_location(self, **kwargs):
        """GPS位置回调"""
        try:
            lat = kwargs.get('lat', None)
            lon = kwargs.get('lon', None)
            if lat is None:
                lat = kwargs.get('latitude', None)
            if lon is None:
                lon = kwargs.get('longitude', None)
            if lat is None or lon is None:
                return

            lat_f = float(lat)
            lon_f = float(lon)
        except Exception:
            return

        self._gps_last_fix_ts = time.time()
        self._apply_location(lat_f, lon_f, source='plyer')


    def _apply_location(self, lat: float, lon: float, source: str = ''):
        try:
            self.current_location = {
                'latitude': float(lat),
                'longitude': float(lon)
            }
            self.location_label.text = f"位置: {float(lat):.6f}, {float(lon):.6f}"
        except Exception:
            return

        try:
            self.evaluate_auto_mode()
        except Exception:
            pass


    def _get_android_device_profile(self):
        if getattr(self, '_device_profile', None) is not None:
            return self._device_profile

        self._device_profile = {}
        if kivy_platform != 'android':
            return self._device_profile

        try:
            from jnius import autoclass
            Build = autoclass('android.os.Build')
            VERSION = autoclass('android.os.Build$VERSION')
            self._device_profile = {
                'manufacturer': str(getattr(Build, 'MANUFACTURER', '') or ''),
                'brand': str(getattr(Build, 'BRAND', '') or ''),
                'model': str(getattr(Build, 'MODEL', '') or ''),
                'sdk': int(getattr(VERSION, 'SDK_INT', 0) or 0),
            }
        except Exception:
            self._device_profile = {}

        return self._device_profile


    def _get_device_location_hint(self) -> str:
        p = self._get_android_device_profile() or {}
        m = (p.get('manufacturer') or '').lower()
        b = (p.get('brand') or '').lower()
        model = (p.get('model') or '').strip()
        sdk = int(p.get('sdk') or 0)

        tag = (m or '') + ' ' + (b or '')
        tag = tag.strip()

        base = f"当前机型：{model or (m or b or '安卓设备')}"

        # Android 12+ 常见的“精确位置”开关提示
        precise_tip = '（如系统有“精确位置/大概位置”选项，请选择“精确位置”）' if sdk and sdk >= 31 else ''

        if any(x in tag for x in ('huawei', 'honor')):
            return (
                base
                + "\n建议：定位模式选“高精度/使用WLAN和移动网络”，并在电池/后台管理里允许本应用后台运行与定位。"
                + ("\n另外：请在权限里允许“始终定位/后台定位”。" if sdk and sdk >= 29 else '')
            )

        if any(x in tag for x in ('xiaomi', 'redmi', 'poco', 'miui')):
            return (
                base
                + f"\n建议：开启“精确位置”{precise_tip}，允许后台定位，并在省电策略中将本应用设为“不限制/无限制”。"
                + "\n另外：在“应用权限/自启动/后台弹出界面”里允许本应用。"
            )

        if any(x in tag for x in ('oppo', 'realme', 'oneplus', 'coloros')):
            return (
                base
                + "\n建议：允许后台定位/自启动，关闭省电限制，并确认系统定位服务为开启状态。"
                + "\n另外：在“应用管理-权限-定位”里选择“始终允许”。"
            )

        if any(x in tag for x in ('vivo', 'iqoo', 'originos')):
            return (
                base
                + "\n建议：允许后台定位/自启动，关闭省电限制，并确认系统定位服务为开启状态。"
                + "\n另外：在“电池-后台高耗电”里允许本应用。"
            )

        if 'samsung' in tag:
            return (
                base
                + f"\n建议：开启“精确位置”{precise_tip}；将本应用电池使用设为“不受限制/不优化”；允许后台定位。"
                + "\n路径参考：设置-位置-应用权限 / 设置-应用-电池。"
            )

        if any(x in tag for x in ('google', 'pixel', 'nexus')):
            return (
                base
                + f"\n建议：开启“精确位置”{precise_tip}；定位权限选“始终允许”；关闭对本应用的电池优化。"
            )

        if any(x in tag for x in ('meizu', 'flyme')):
            return (
                base
                + "\n建议：允许后台定位/自启动；在省电策略中将本应用设为“不限制”。"
            )

        if any(x in tag for x in ('lenovo', 'motorola', 'moto')):
            return (
                base
                + f"\n建议：开启“精确位置”{precise_tip}；定位权限选“始终允许”；关闭电池优化/省电限制。"
            )

        if any(x in tag for x in ('sony', 'asus', 'zte', 'nubia')):
            return (
                base
                + f"\n建议：开启“精确位置”{precise_tip}；允许后台定位；关闭电池优化；确保系统定位服务已开启。"
            )

        # 默认通用提示（覆盖更多机型）
        return (
            base
            + f"\n建议：开启“精确位置”{precise_tip}；定位权限选“始终允许/后台允许”；关闭电池优化/省电限制；允许后台运行/自启动。"
        )



    def _start_android_location_fallback(self):
        if kivy_platform != 'android':
            return

        if getattr(self, '_android_loc_ev', None):
            return

        self._android_loc_ev = Clock.schedule_interval(self._android_location_fallback_tick, 2.0)
        Clock.schedule_once(self._android_location_fallback_tick, 0)


    def _stop_android_location_fallback(self):
        ev = getattr(self, '_android_loc_ev', None)
        if ev:
            try:
                ev.cancel()
            except Exception:
                pass
        self._android_loc_ev = None


    def _android_location_fallback_tick(self, _dt):
        if kivy_platform != 'android':
            return

        # 若 plyer 最近已拿到定位，则停止兜底轮询，减少耗电
        last_fix = getattr(self, '_gps_last_fix_ts', 0) or 0
        if last_fix and (time.time() - last_fix) < 6:
            self._stop_android_location_fallback()
            return

        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Context = autoclass('android.content.Context')
            LocationManager = autoclass('android.location.LocationManager')

            activity = PythonActivity.mActivity
            lm = activity.getSystemService(Context.LOCATION_SERVICE)

            providers = [
                LocationManager.GPS_PROVIDER,
                LocationManager.NETWORK_PROVIDER,
                LocationManager.PASSIVE_PROVIDER,
            ]

            best = None
            for p in providers:
                try:
                    if not lm.isProviderEnabled(p):
                        continue
                    loc = lm.getLastKnownLocation(p)
                    if loc is None:
                        continue
                    if best is None:
                        best = loc
                    else:
                        try:
                            if float(loc.getAccuracy()) <= float(best.getAccuracy()):
                                best = loc
                        except Exception:
                            best = loc
                except Exception:
                    continue

            if best is None:
                return

            lat = float(best.getLatitude())
            lon = float(best.getLongitude())
            if lat == 0.0 and lon == 0.0:
                return

            self._gps_last_fix_ts = time.time()
            self._apply_location(lat, lon, source='android')
        except Exception:
            return


    
    def calculate_distance(self, lat1, lon1, lat2, lon2):

        """计算两个坐标之间的距离（公里）"""
        # 地球半径（公里）
        R = 6371.0
        
        # 将角度转换为弧度
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # 差值
        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad
        
        # Haversine公式
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        distance = R * c
        return distance

    def get_current_settings(self):
        """获取当前用户设置"""
        app = App.get_running_app()
        if not hasattr(app, 'current_user'):
            return None
        return db.get_user_settings(app.current_user)

    def get_today_str(self):
        """获取今日日期字符串"""
        return datetime.now().strftime("%Y-%m-%d")

    def _norm_punch_type(self, v: str | None) -> str:
        x = str(v or '').strip().lower()
        if x in ('checkin', 'in', 'start', '上班', '上班打卡', '上班签到'):
            return 'checkin'
        if x in ('checkout', 'out', 'end', '下班', '下班打卡', '下班签退'):
            return 'checkout'
        return ''

    def _get_today_punch_state(self):
        """返回今日有效打卡状态：{checkin: datetime|None, checkout: datetime|None}。

        兼容旧数据：punch_type 为空且状态为成功/补录时，视为 checkin。
        """
        app = App.get_running_app()
        if not hasattr(app, 'current_user'):
            return {'checkin': None, 'checkout': None}

        # 多端互通：在线时先把服务器当月记录同步到本地缓存，再渲染（离线仍可看）
        try:
            month_key = datetime.now().strftime('%Y-%m')
            self._sync_attendance_month_from_server(month_key)
        except Exception:
            pass

        username = app.current_user
        today = self.get_today_str()
        records = db.get_user_attendance(username)

        checkin_dt = None
        checkout_dt = None

        for r in (records or []):
            if r.get('date') != today:
                continue
            if str(r.get('status') or '') not in ('打卡成功', '补录'):
                continue

            pt = self._norm_punch_type(r.get('punch_type'))
            ts = str(r.get('timestamp') or '').strip()
            dt = None
            try:
                if ts:
                    dt = datetime.fromisoformat(ts)
            except Exception:
                dt = None

            if not dt:
                continue

            # 旧数据/未标注 punch_type：按上班处理
            if pt in ('', 'checkin'):
                if (checkin_dt is None) or (dt < checkin_dt):
                    checkin_dt = dt
            elif pt == 'checkout':
                if (checkout_dt is None) or (dt > checkout_dt):
                    checkout_dt = dt

        return {'checkin': checkin_dt, 'checkout': checkout_dt}

    def has_record_today(self):
        """兼容旧接口：今日是否已有有效打卡（上班或下班任意一次）。"""
        st = self._get_today_punch_state()
        return bool(st.get('checkin') or st.get('checkout'))

    def has_checkin_today(self) -> bool:
        st = self._get_today_punch_state()
        return bool(st.get('checkin'))

    def has_checkout_today(self) -> bool:
        st = self._get_today_punch_state()
        return bool(st.get('checkout'))

    def mark_setting(self, key, value):
        """更新用户设置中的状态字段"""
        app = App.get_running_app()
        if not hasattr(app, 'current_user'):
            return
        settings = db.get_user_settings(app.current_user) or {}
        settings[key] = value
        db.save_user_settings(app.current_user, settings)

    def has_success_today(self):
        """今日是否已完成上班打卡（用于“未打卡/补录提醒”等逻辑）。"""
        return self.has_checkin_today()

    def publish_announcement(self, text):
        text = (text or '').strip()
        if not text:
            return
        if not self.is_logged_in():
            return
        app = App.get_running_app()
        settings = db.get_user_settings(app.current_user) or {}
        settings['punch_notice_text'] = text
        settings['punch_notice_time'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        db.save_user_settings(app.current_user, settings)
        self.update_announcement_indicator()



    def remind_reapply_notice(self, settings):
        if not settings:
            return
        today = self.get_today_str()
        if settings.get('last_reapply_notice_date') == today:
            return
        current_time = datetime.now().time()
        punch_end = datetime.strptime(settings.get('punch_end', '10:00'), '%H:%M').time()
        if current_time <= punch_end:
            return
        if self.has_success_today():
            return
        app = App.get_running_app()
        username = app.current_user if hasattr(app, 'current_user') else ''
        message = f"补录提醒：{username} 今日未打卡或打卡异常，请申请补录或放弃。"
        self.publish_announcement(message)
        self.mark_setting('last_reapply_notice_date', today)


    def is_within_range_and_time(self, settings):
        """判断是否在定位范围内。

        说明：时间规则已由“打卡规则引擎”统一处理，这里只做范围判断。
        """
        if not settings or not self.current_location:
            return False, None

        set_lat = settings.get('latitude')
        set_lon = settings.get('longitude')
        set_radius = settings.get('radius', 100)

        distance = self.calculate_distance(
            self.current_location['latitude'],
            self.current_location['longitude'],
            set_lat,
            set_lon
        )
        distance_meters = distance * 1000

        in_range = distance_meters <= set_radius
        return bool(in_range), int(distance_meters)

    def auto_record_outside(self, settings, distance_meters):
        """超出范围或时间时自动记录一次"""
        app = App.get_running_app()
        if not hasattr(app, 'current_user'):
            return

        today = self.get_today_str()
        now = datetime.now()
        last_auto_time = settings.get('last_auto_punch_time') or settings.get('last_auto_outside_time')
        if last_auto_time:
            try:
                last_auto_dt = datetime.fromisoformat(last_auto_time)
                if now - last_auto_dt < timedelta(minutes=30):
                    return
            except ValueError:
                pass

        if settings.get('last_auto_outside') == today:
            return

        status = "自动记录"
        notes = f"离开范围/超出时间，距离{distance_meters}米"

        user_id = ''
        try:
            user_id = str((getattr(app, 'user_data', {}) or {}).get('user_id') or '')
        except Exception:
            user_id = ''
        if not user_id:
            try:
                user_id = str((db.get_user_record(app.current_user) or {}).get('user_id') or '')
            except Exception:
                user_id = ''
        if not user_id:
            user_id = str(app.current_user)

        db.add_attendance(
            user_id,
            app.current_user,
            status,
            f"{self.current_location['latitude']:.6f}, {self.current_location['longitude']:.6f}",
            notes
        )


        try:
            self._trigger_attendance_sync()
        except Exception:
            pass

        self.mark_setting('last_auto_outside', today)

        self.mark_setting('last_auto_outside_time', now.isoformat())
        self.mark_setting('last_auto_punch_time', now.isoformat())
        self.load_attendance_records()


    def _auto_window_type(self, t: dt_time) -> str:
        # 自动打卡窗口：
        # - 07:30-08:00 尝试上班
        # - 20:00-20:30 尝试下班
        if dt_time(7, 30) <= t <= dt_time(8, 0):
            return 'checkin'
        if dt_time(20, 0) <= t <= dt_time(20, 30):
            return 'checkout'
        return ''

    def _is_time_allowed_for_type(self, punch_type: str, t: dt_time) -> bool:
        # 规则：
        # 上班窗口：00:00-20:00
        # 下班窗口：08:00-23:59:59
        if punch_type == 'checkin':
            return dt_time(0, 0) <= t <= dt_time(20, 0)
        if punch_type == 'checkout':
            return dt_time(8, 0) <= t <= dt_time(23, 59, 59)
        return False

    def _decide_punch_type(self, now_dt: datetime, forced: str | None = None) -> tuple[str, str]:
        forced_norm = self._norm_punch_type(forced)
        if forced_norm in ('checkin', 'checkout'):
            return forced_norm, ''

        st = self._get_today_punch_state()
        has_in = bool(st.get('checkin'))
        has_out = bool(st.get('checkout'))

        t = now_dt.time()

        # 8:00前 -> 上班
        if t < dt_time(8, 0):
            if has_in:
                return '', '今日上班打卡已完成'
            return 'checkin', ''

        # 20:00后 -> 下班
        if t >= dt_time(20, 0):
            if not has_in:
                return '', '未上班打卡，无法下班打卡'
            if has_out:
                return '', '今日下班打卡已完成'
            return 'checkout', ''

        # 08:00-20:00：特殊规则
        if not has_in:
            return 'checkin', ''
        if not has_out:
            return 'checkout', ''
        return '', '今日已完成上班与下班打卡'

    def _send_punch_reminders(self, settings):
        # 上班前提醒：>=07:30 且未上班
        # 下班后提醒：>=20:00 且已上班未下班
        today = self.get_today_str()
        now = datetime.now()
        t = now.time()

        try:
            st = self._get_today_punch_state()
            has_in = bool(st.get('checkin'))
            has_out = bool(st.get('checkout'))
        except Exception:
            has_in, has_out = False, False

        if t >= dt_time(7, 30) and not has_in:
            if str(settings.get('last_checkin_remind_date') or '') != today:
                try:
                    safe_notify(title='打卡提醒', message='请记得打卡上班', timeout=3)
                except Exception:
                    pass
                settings['last_checkin_remind_date'] = today

        if t >= dt_time(20, 0) and has_in and not has_out:
            if str(settings.get('last_checkout_remind_date') or '') != today:
                try:
                    safe_notify(title='打卡提醒', message='请记得打卡下班', timeout=3)
                except Exception:
                    pass
                settings['last_checkout_remind_date'] = today

        try:
            app = App.get_running_app()
            if hasattr(app, 'current_user'):
                db.save_user_settings(app.current_user, settings)
        except Exception:
            pass

    def _try_auto_punch(self, settings, in_range: bool, distance_meters: int | None):
        if not settings:
            return
        if not settings.get('auto_punch', False):
            return

        now = datetime.now()
        today = self.get_today_str()
        t = now.time()

        target = self._auto_window_type(t)
        if not target:
            return

        st = self._get_today_punch_state()
        has_in = bool(st.get('checkin'))
        has_out = bool(st.get('checkout'))

        if target == 'checkin' and has_in:
            return
        if target == 'checkout':
            if not has_in:
                return
            if has_out:
                return

        # 重试：每 5 分钟一次，最多 3 次
        k_cnt = f"auto_retry_{today}_{target}_count"
        k_ts = f"auto_retry_{today}_{target}_last_ts"
        cnt = int(settings.get(k_cnt, 0) or 0)
        last_ts = float(settings.get(k_ts, 0) or 0)
        now_ts = time.time()

        if cnt >= 3:
            return
        if last_ts and (now_ts - last_ts) < 300:
            return

        # 不满足条件：只记录重试，不写失败打卡（避免刷屏/刷记录）
        if (not in_range) or (distance_meters is None):
            settings[k_cnt] = cnt + 1
            settings[k_ts] = now_ts
            try:
                app = App.get_running_app()
                if hasattr(app, 'current_user'):
                    db.save_user_settings(app.current_user, settings)
            except Exception:
                pass
            return

        # 满足条件立即打卡
        settings[k_cnt] = cnt + 1
        settings[k_ts] = now_ts
        try:
            app = App.get_running_app()
            if hasattr(app, 'current_user'):
                db.save_user_settings(app.current_user, settings)
        except Exception:
            pass

        try:
            self._perform_punch(forced_punch_type=target, is_auto=True)
        except Exception:
            return

    def evaluate_auto_mode(self):
        """根据位置与规则引擎自动处理打卡/提醒逻辑"""
        settings = self.get_current_settings()
        if not settings:
            self.range_status_label.text = '范围状态: 未设置'
            return

        # 桌面端手动定位测试：未获取GPS时使用设置坐标
        if not self.current_location and kivy_platform in ('win', 'macosx', 'linux'):
            if not settings.get('auto_location', True):
                self.current_location = {
                    'latitude': settings.get('latitude'),
                    'longitude': settings.get('longitude')
                }

        in_range, distance_meters = self.is_within_range_and_time(settings)

        if distance_meters is None:
            self.range_status_label.text = '范围状态: 未获取'
        elif in_range:
            self.range_status_label.text = '范围状态: 已进入范围'
        else:
            self.range_status_label.text = f"范围状态: 未在范围内（{int(distance_meters)}米）"

        # 智能提醒
        self._send_punch_reminders(settings)

        # 自动打卡策略 + 重试
        self._try_auto_punch(settings, bool(in_range), distance_meters)

        # 补录提醒（保留原逻辑）
        self.remind_reapply_notice(settings)

    
    def punch_card(self, instance):
        """手动打卡按钮入口"""
        self._perform_punch(forced_punch_type=None, is_auto=False)

    def _perform_punch(self, forced_punch_type: str | None = None, is_auto: bool = False):
        app = App.get_running_app()
        if not hasattr(app, 'current_user'):
            return

        settings = db.get_user_settings(app.current_user)
        if not settings:
            if not is_auto:
                self.show_popup("错误", "请先设置打卡位置")
            return

        # 桌面端手动定位测试：未获取GPS时使用设置坐标
        if not self.current_location and kivy_platform in ('win', 'macosx', 'linux'):
            if not settings.get('auto_location', True):
                self.current_location = {
                    'latitude': settings.get('latitude'),
                    'longitude': settings.get('longitude')
                }

        # Android 端强制使用"新鲜"的定位（避免用到很久之前的缓存坐标）
        if kivy_platform == 'android':
            last_fix = getattr(self, '_gps_last_fix_ts', 0) or 0
            if (not self.current_location) or (not last_fix) or (time.time() - float(last_fix) > 120):
                try:
                    self.start_gps(0)
                except Exception:
                    pass
                if is_auto:
                    return
                hint = ''
                try:
                    hint = str(self._get_device_location_hint() or '').strip()
                except Exception:
                    hint = ''
                msg = "正在获取GPS定位，请稍后再试"
                if hint:
                    msg = msg + "\n\n" + hint
                self.show_popup("定位中", msg)
                return

        if not self.current_location:
            if is_auto:
                return
            self.show_popup("错误", "无法获取当前位置")
            return

        now_dt = datetime.now()

        punch_type, reason = self._decide_punch_type(now_dt, forced=forced_punch_type)
        if not punch_type:
            if is_auto:
                return
            self.show_popup("提示", str(reason or '当前无需打卡'))
            return

        # 时间窗口校验
        if not self._is_time_allowed_for_type(punch_type, now_dt.time()):
            if is_auto:
                return
            self.show_popup("提示", "当前时间不符合打卡规则")
            return

        # 禁止时间倒流（同日内不能早于上一次有效打卡）
        st = self._get_today_punch_state()
        last_dt = None
        for x in (st.get('checkin'), st.get('checkout')):
            if x is None:
                continue
            if (last_dt is None) or (x > last_dt):
                last_dt = x
        if last_dt and now_dt < last_dt:
            if is_auto:
                return
            self.show_popup("提示", "禁止时间倒流：本次打卡时间不能早于上次打卡")
            return

        # 必须在定位范围内
        in_range, distance_meters = self.is_within_range_and_time(settings)
        if (not in_range) or (distance_meters is None):
            if is_auto:
                return
            dm = (str(int(distance_meters)) if distance_meters is not None else '未知')
            self.show_popup("提示", f"不在打卡范围内（{dm}米），请进入范围后再试")
            return

        role_text = '上班' if punch_type == 'checkin' else '下班'
        status = "打卡成功"
        notes = f"{role_text}打卡：位置匹配，距离{int(distance_meters)}米"

        # 保存打卡记录（离线缓存，联网后自动补传）
        user_id = ''
        try:
            user_id = str((getattr(app, 'user_data', {}) or {}).get('user_id') or '')
        except Exception:
            user_id = ''
        if not user_id:
            try:
                user_id = str((db.get_user_record(app.current_user) or {}).get('user_id') or '')
            except Exception:
                user_id = ''
        if not user_id:
            user_id = str(app.current_user)

        db.add_attendance(
            user_id,
            app.current_user,
            status,
            f"{self.current_location['latitude']:.6f}, {self.current_location['longitude']:.6f}",
            notes,
            punch_type=punch_type,
        )

        try:
            self._trigger_attendance_sync()
        except Exception:
            pass

        # UI
        self.status_label.text = f"{role_text}打卡成功"
        self.status_label.color = (0.2, 0.8, 0.2, 1)
        self.punch_btn.background_color = (0.2, 0.8, 0.2, 1)

        # 通知 + 公告
        try:
            safe_notify(title=f"{role_text}打卡成功", message=f"{role_text}打卡已完成", timeout=2)
        except Exception:
            pass

        try:
            username = app.current_user if hasattr(app, 'current_user') else ''
            message = f"{role_text}打卡成功：{username} {now_dt.strftime('%Y-%m-%d %H:%M')}"
            self.publish_announcement(message)
        except Exception:
            pass

        self.load_attendance_records()
        Clock.schedule_once(self.reset_punch_button, 10)


    
    def reset_punch_button(self, dt):
        """重置打卡按钮状态"""
        self.status_label.text = '准备打卡'
        self.status_label.color = (0.2, 0.2, 0.2, 1)
        self.punch_btn.background_color = (0.2, 0.8, 0.2, 1)
    
    def show_reapply_popup(self, message):
        """显示补录申请弹窗"""
        content = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(20))
        
        msg = str(message or '')
        msg_label = Label(text=msg, halign='left' if ('\n' in msg or len(msg) > 18) else 'center', valign='top', color=(1, 1, 1, 1))
        msg_label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
        content.add_widget(msg_label)

        
        btn_layout = BoxLayout(spacing=dp(10), size_hint=(1, None), height=dp(44))
        
        yes_btn = Button(text='申请补录', background_color=(0.2, 0.6, 0.8, 1))
        yes_btn.bind(on_press=self.apply_reapply)
        
        no_btn = Button(text='取消', background_color=(0.6, 0.6, 0.6, 1))
        
        btn_layout.add_widget(yes_btn)
        btn_layout.add_widget(no_btn)
        
        content.add_widget(btn_layout)
        
        self.reapply_popup = Popup(title='补录申请',
                                   content=content,
                                   size_hint=(0.82, 0.38),
                                   background_color=(0.0667, 0.149, 0.3098, 1),
                                   background='')

        no_btn.bind(on_press=lambda x: self.reapply_popup.dismiss())
        self.reapply_popup.open()


    
    def apply_reapply(self, instance):
        """申请补录"""
        try:
            if hasattr(self, 'reapply_popup'):
                self.reapply_popup.dismiss()
        except Exception:
            pass

        self.open_correction_request_popup()

    def open_correction_request_popup(self):
        app = App.get_running_app()
        token = str(getattr(app, 'api_token', '') or '')
        server_url = str(getattr(app, 'server_url', '') or '')
        if not token or not server_url:
            self.show_popup('提示', '补录申请需要连接服务器并登录\n请先在【设置】-【服务器设置】填写地址，再重新登录')
            return

        api = GlimmerAPI(server_url)

        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(14))
        content.add_widget(Label(text='补录申请将提交给管理员审核', color=(1, 1, 1, 1), size_hint=(1, None), height=dp(24)))

        team_row = BoxLayout(orientation='horizontal', size_hint=(1, None), height=dp(44), spacing=dp(8))
        group_spinner = Spinner(
            text='加载我的团队...',
            values=[],
            size_hint=(0.7, 1),
            shorten=True,
            shorten_from='right',
            halign='center',
            valign='middle',
        )
        group_spinner.bind(size=lambda instance, value: setattr(instance, 'text_size', value))

        team_id_label = Label(
            text='团队ID:',
            size_hint=(0.3, 1),
            color=(0.9, 0.95, 1, 1),
            halign='right',
            valign='middle',
            shorten=True,
            shorten_from='right',
        )
        team_id_label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))

        team_row.add_widget(group_spinner)
        team_row.add_widget(team_id_label)
        content.add_widget(team_row)

        date_input = TextInput(
            hint_text='补录日期（YYYY-MM-DD）',
            multiline=False,
            size_hint=(1, None),
            height=dp(44)
        )
        date_input.text = self.get_today_str()
        content.add_widget(date_input)

        reason_input = TextInput(hint_text='原因（选填）', multiline=True, size_hint=(1, None), height=dp(110))
        content.add_widget(reason_input)

        btn_row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        ok_btn = Button(text='提交', background_color=(0.2, 0.6, 0.8, 1))
        cancel_btn = Button(text='取消', background_color=(0.6, 0.6, 0.6, 1))
        btn_row.add_widget(ok_btn)
        btn_row.add_widget(cancel_btn)
        content.add_widget(btn_row)

        popup = Popup(
            title='补录申请',
            content=content,
            size_hint=(0.9, 0.7),
            background_color=(0.0667, 0.149, 0.3098, 1),
            background=''
        )

        cancel_btn.bind(on_press=lambda *_: popup.dismiss())

        group_map: dict[str, int] = {}
        group_code_map: dict[str, str] = {}
        selected_group_id = {'value': None}

        def on_group_select(_spinner, text):
            gid = group_map.get(text)
            selected_group_id['value'] = gid
            code = str(group_code_map.get(text) or '')
            team_id_label.text = f"团队ID:{code}" if code else '团队ID:'

        group_spinner.bind(text=on_group_select)

        def load_groups():
            try:
                groups = api.my_groups(token)

                def ui():
                    group_map.clear()
                    group_code_map.clear()
                    values = []
                    for g in (groups or []):
                        name = str(g.get('name') or '')
                        code = str(g.get('group_code') or '')
                        values.append(name)
                        try:
                            group_map[name] = int(g.get('id'))
                            group_code_map[name] = code
                        except Exception:
                            continue

                    if not values:
                        group_spinner.text = '（你尚未加入任何团队）'
                        group_spinner.values = []
                        selected_group_id['value'] = None
                        team_id_label.text = '团队ID:'
                        ok_btn.disabled = True
                        ok_btn.opacity = 0.5
                        return

                    ok_btn.disabled = False
                    ok_btn.opacity = 1
                    group_spinner.values = values
                    group_spinner.text = values[0]
                    selected_group_id['value'] = group_map.get(values[0])
                    code0 = str(group_code_map.get(values[0]) or '')
                    team_id_label.text = f"团队ID:{code0}" if code0 else '团队ID:'

                Clock.schedule_once(lambda *_: ui(), 0)
            except Exception as e:
                Clock.schedule_once(lambda *_, msg=str(e): (popup.dismiss(), self.show_popup('错误', msg)), 0)


        Thread(target=load_groups, daemon=True).start()


        def submit(*_):
            gid = selected_group_id.get('value')
            date_text = (date_input.text or '').strip()
            reason = (reason_input.text or '').strip()
            if not gid:
                self.show_popup('提示', '请先加入团队后再申请补录')

                return
            if len(date_text) != 10 or date_text[4] != '-' or date_text[7] != '-':
                self.show_popup('提示', '日期格式应为 YYYY-MM-DD')
                return

            def work():
                try:
                    api.request_correction(token, int(gid), date_text, reason)

                    def ui_ok():
                        try:
                            safe_notify(title='补录申请已提交', message='管理员将审核您的补录申请', timeout=2)
                        except Exception:
                            pass
                        popup.dismiss()

                    Clock.schedule_once(lambda *_: ui_ok(), 0)
                except Exception as e:
                    Clock.schedule_once(lambda *_, msg=str(e): self.show_popup('错误', msg), 0)


            Thread(target=work, daemon=True).start()

        ok_btn.bind(on_press=submit)
        popup.open()


    
    def set_auto_punch_state(self, enabled, save=True):
        if enabled:
            self.auto_punch_switch.text = '开启'
            self.auto_punch_switch.background_color = (0.2, 0.8, 0.2, 1)
            self.enable_auto_punch()
        else:
            self.auto_punch_switch.text = '关闭'
            self.auto_punch_switch.background_color = (0.8, 0.2, 0.2, 1)
            self.disable_auto_punch()

        if save:
            app = App.get_running_app()
            if hasattr(app, 'current_user'):
                settings = self.get_current_settings() or {}
                settings['auto_punch'] = enabled
                db.save_user_settings(app.current_user, settings)

    def toggle_auto_punch(self, instance):
        """切换自动打卡开关"""
        enabled = instance.text == '关闭'
        self.set_auto_punch_state(enabled, save=True)


    
    def enable_auto_punch(self):
        """启用自动打卡"""
        app = App.get_running_app()
        if hasattr(app, 'current_user'):
            settings = db.get_user_settings(app.current_user)
            if settings:
                # 设置定时检查
                Clock.schedule_interval(self.check_auto_punch, 60)  # 每分钟检查一次
    
    def disable_auto_punch(self):
        """禁用自动打卡"""
        # 取消定时检查
        Clock.unschedule(self.check_auto_punch)
    
    def check_auto_punch(self, dt):
        """检查是否应该自动打卡"""
        self.evaluate_auto_mode()

    
    def check_auto_punch_settings(self, dt):
        """检查自动打卡设置"""
        app = App.get_running_app()
        if hasattr(app, 'current_user'):
            settings = db.get_user_settings(app.current_user)
            if settings and settings.get('auto_punch', False):
                self.set_auto_punch_state(True, save=False)
            else:
                self.set_auto_punch_state(False, save=False)


    def _sync_attendance_month_from_server(self, month: str):
        """将服务器当月打卡记录同步到本机缓存（用于多端数据互通/离线可看）。"""
        month = str(month or '').strip()
        if not month:
            return

        # 限流：避免每次刷新都请求
        now_ts = time.time()
        last = getattr(self, '_attendance_month_sync_last', None) or {}
        if last.get('month') == month and now_ts - float(last.get('ts') or 0) < 25:
            return

        if getattr(self, '_attendance_month_sync_inflight', False):
            return

        app = App.get_running_app()
        token = str(getattr(app, 'api_token', '') or '')
        base_url = str(getattr(app, 'server_url', '') or get_server_url() or '').strip()
        if not token or not base_url:
            return

        self._attendance_month_sync_inflight = True
        self._attendance_month_sync_last = {'month': month, 'ts': now_ts}

        def work():
            try:
                api = GlimmerAPI(base_url)
                if not api.health():
                    return

                items = api.attendance_month(token, month)
                username = str(getattr(app, 'current_user', '') or '')
                user_id = ''
                try:
                    user_id = str((getattr(app, 'user_data', {}) or {}).get('user_id') or '')
                except Exception:
                    user_id = ''

                # 写入本机缓存：key 使用 server_{id}，避免重复
                store = getattr(db, 'attendance_store', None)
                if not store or not hasattr(store, 'put'):
                    return

                for it in (items or []):
                    try:
                        sid = it.get('id')
                        key = f"server_{sid}"
                        punched_at = str(it.get('punched_at') or '')
                        date_str = str(it.get('date') or punched_at[:10] or '')
                        punch_type = str(it.get('punch_type') or '').strip()
                        status = str(it.get('status') or '')
                        lat = it.get('lat', None)
                        lon = it.get('lon', None)
                        notes = str(it.get('notes') or '')

                        loc = ''
                        try:
                            if lat is not None and lon is not None:
                                loc = f"{float(lat):.6f}, {float(lon):.6f}"
                        except Exception:
                            loc = ''

                        store.put(
                            key,
                            user_id=user_id or str(username),
                            username=username,
                            punch_type=punch_type,
                            status=status,
                            location=loc,
                            notes=notes,
                            timestamp=punched_at or datetime.now().isoformat(),
                            date=date_str,
                            server_synced=True,
                            server_synced_at=datetime.now().isoformat(timespec='seconds'),
                            server_sync_error='',
                        )
                    except Exception:
                        continue

                Clock.schedule_once(lambda *_: self.load_attendance_records(), 0)
            except Exception:
                return
            finally:
                self._attendance_month_sync_inflight = False

        Thread(target=work, daemon=True).start()


    def load_attendance_records(self):

        """加载整个月打卡记录"""
        # 清空现有记录
        self.records_layout.clear_widgets()
        
        app = App.get_running_app()
        if not hasattr(app, 'current_user'):
            return
        
        # 多端互通：在线时先把服务器当月记录同步到本地缓存，再渲染（离线仍可看）
        try:
            month_key = datetime.now().strftime('%Y-%m')
            self._sync_attendance_month_from_server(month_key)
        except Exception:
            pass

        records = db.get_user_attendance(app.current_user)

        record_map = {}
        for record in records:
            record_date = record.get('date')
            if record_date:
                record_map.setdefault(record_date, []).append(record)

        now = datetime.now()
        year, month = now.year, now.month
        days_in_month = calendar.monthrange(year, month)[1]
        today = now.day

        punch_days = 0
        missed_days = 0

        for day in range(days_in_month, 0, -1):
            date_str = f"{year}-{month:02d}-{day:02d}"
            if day > today:
                continue
            day_records = record_map.get(date_str, [])


            has_checkin_effective = False

            if day_records:
                checkin_dt = None
                checkout_dt = None

                # 只以“有效打卡”（打卡成功/补录）计算上下班
                for item in day_records:
                    if str(item.get('status') or '') not in ("打卡成功", "补录"):
                        continue
                    ts = str(item.get('timestamp') or '').strip()
                    try:
                        dtv = datetime.fromisoformat(ts)
                    except Exception:
                        continue

                    pt = self._norm_punch_type(item.get('punch_type'))
                    if pt in ('', 'checkin'):
                        has_checkin_effective = True
                        if checkin_dt is None or dtv < checkin_dt:
                            checkin_dt = dtv
                    elif pt == 'checkout':
                        if checkout_dt is None or dtv > checkout_dt:
                            checkout_dt = dtv

                if checkin_dt and checkout_dt:
                    time_range = f"上 {checkin_dt.strftime('%H:%M')} / 下 {checkout_dt.strftime('%H:%M')}"
                    status_text = "已打卡"
                    status_color = (1, 1, 1, 1)
                elif checkin_dt and not checkout_dt:
                    time_range = f"上 {checkin_dt.strftime('%H:%M')}"
                    status_text = "未下班"
                    status_color = (0.95, 0.6, 0.2, 1)
                elif (not checkin_dt) and checkout_dt:
                    time_range = f"下 {checkout_dt.strftime('%H:%M')}"
                    status_text = "缺上班"
                    status_color = (0.95, 0.6, 0.2, 1)
                else:
                    # 有记录但无有效打卡
                    times = []
                    for item in day_records:
                        ts = str(item.get('timestamp') or '')
                        try:
                            times.append(datetime.fromisoformat(ts).strftime("%H:%M"))
                        except Exception:
                            continue
                    times = sorted(times)
                    time_range = f"{times[0]} - {times[-1]}" if len(times) > 1 else (times[0] if times else "记录异常")
                    status_text = "异常"
                    status_color = (0.95, 0.6, 0.2, 1)
            else:
                time_range = "无记录"
                status_text = "未打卡"
                status_color = (1, 0.2, 0.2, 1)



            if has_checkin_effective:
                punch_days += 1
            else:
                missed_days += 1



            # 创建记录卡片
            card = BoxLayout(
                orientation='horizontal',
                size_hint_y=None,
                height=dp(55),
                padding=dp(10),
                spacing=dp(10)
            )

            with card.canvas.before:
                Color(0.12, 0.2, 0.35, 0.95)
                RoundedRectangle(pos=card.pos, size=card.size, radius=[10])

            date_label = Label(
                text=date_str,
                size_hint=(0.4, 1),
                font_size=dp(12),
                color=(0.92, 0.95, 1, 1)
            )


            status_label = Label(
                text=status_text,
                size_hint=(0.25, 1),
                font_size=dp(14),
                bold=True,
                color=status_color
            )

            range_label = Label(
                text=time_range,
                size_hint=(0.35, 1),
                font_size=dp(12),
                color=(0.8, 0.86, 0.95, 1)
            )


            card.add_widget(date_label)
            card.add_widget(status_label)
            card.add_widget(range_label)

            self.records_layout.add_widget(card)

        if hasattr(self, 'punch_days_label'):
            self.punch_days_label.text = f"打卡天数：[color=#ff4d4f]{punch_days}[/color]"
        if hasattr(self, 'missed_days_label'):
            self.missed_days_label.text = f"未打卡天数：[color=#ff4d4f]{missed_days}[/color]"


    
    def open_settings(self, instance):
        """打开设置界面"""
        self.manager.current = 'settings'

    def open_groups(self, instance):
        """打开团队管理界面"""
        self.manager.current = 'groups'


    def open_profile(self):
        """打开个人资料页"""
        try:
            app = App.get_running_app()
            app.profile_back_to = self.manager.current
        except Exception:
            pass
        try:
            self.manager.current = 'profile'
        except Exception:
            pass



    def open_admin(self, instance):
        """打开管理员界面"""

        app = App.get_running_app()
        role = ''
        try:
            role = str(getattr(app, 'server_role', '') or (getattr(app, 'user_data', {}) or {}).get('role') or '')
        except Exception:
            role = ''

        token = getattr(app, 'api_token', None)
        if token and role in ('admin', 'engineer'):
            self.manager.current = 'server_admin'
        else:
            self.manager.current = 'admin'


    
    def logout(self, instance):

        """退出登录"""
        # 停止GPS
        if self.gps_enabled:
            gps.stop()
            self.gps_enabled = False
        
        # 停止自动打卡
        self.disable_auto_punch()

        # 停止离线补传任务
        ev = getattr(self, '_attendance_sync_ev', None)
        if ev:
            try:
                ev.cancel()
            except Exception:
                pass
        self._attendance_sync_ev = None
        self._attendance_sync_inflight = False

        # 停止管理员提醒轮询
        ev = getattr(self, '_admin_notice_ev', None)
        if ev:
            try:
                ev.cancel()
            except Exception:
                pass
        self._admin_notice_ev = None
        self._admin_notice_inflight = False

        # 停止聊天提醒轮询
        ev = getattr(self, '_chat_notice_ev', None)
        if ev:
            try:
                ev.cancel()
            except Exception:
                pass
        self._chat_notice_ev = None
        self._chat_notice_inflight = False


        
        # 清除用户信息

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

        
        # 返回登录界面
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

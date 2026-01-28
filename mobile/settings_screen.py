# Copyright (C) [2026] [晨曦微光]
# 此软件受著作权法保护。未经明确书面许可，任何单位或个人不得复制、分发、修改或用于商业用途。
# APP名称：[晨曦智能打卡]
# 版本号：1.0.0

"""
设置界面模块
"""


from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.anchorlayout import AnchorLayout
from kivy.clock import Clock

from kivy.metrics import dp
from kivy.graphics import Color, RoundedRectangle
from datetime import datetime
from main import StyledButton, db, get_server_url, set_server_url




class SettingsScreen(Screen):
    """设置界面"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(0.0667, 0.149, 0.3098, 1)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
        self.bind(pos=self.update_bg, size=self.update_bg)
        
        # 主布局
        main_layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))



        # 标题
        title = Label(
            text='',
            font_size=dp(24),
            bold=True,
            size_hint=(None, None),
            size=(dp(200), dp(40)),
            color=(1, 1, 1, 1)
        )

        title_box = AnchorLayout(size_hint=(1, None), height=dp(50), anchor_x='center', anchor_y='center')
        title_box.add_widget(title)

        main_layout.add_widget(title_box)
        
        # 内容容器
        scroll_content = BoxLayout(orientation='vertical', spacing=dp(15), size_hint=(1, 1))

        # 服务器设置（群/公告/版本/广告依赖网络）
        server_group = self.create_setting_group("服务器设置")
        server_row = BoxLayout(size_hint=(1, None), height=dp(50), spacing=dp(10))
        server_row.add_widget(Label(text='服务器地址:', size_hint=(0.3, 1), color=(1, 1, 1, 1)))
        self.server_url_input = TextInput(
            hint_text='例如: http://192.168.1.10:8000',
            multiline=False,
            size_hint=(0.7, 1),
            padding=[dp(10), dp(12), dp(10), dp(8)]
        )
        server_row.add_widget(self.server_url_input)
        server_group.add_widget(server_row)
        scroll_content.add_widget(server_group)

        # 位置设置
        location_group = self.create_setting_group("位置设置")

        
        # 纬度输入
        lat_layout = BoxLayout(size_hint=(1, None), height=dp(50), spacing=dp(10))
        lat_layout.add_widget(Label(text='纬度:', size_hint=(0.3, 1), color=(1, 1, 1, 1)))

        self.lat_input = TextInput(
            hint_text='例如: 31.2304',
            multiline=False,
            size_hint=(0.7, 1),
            input_filter='float',
            padding=[dp(10), dp(12), dp(14), dp(14)]
        )


        lat_layout.add_widget(self.lat_input)
        location_group.add_widget(lat_layout)
        
        # 经度输入
        lon_layout = BoxLayout(size_hint=(1, None), height=dp(50), spacing=dp(10))
        lon_layout.add_widget(Label(text='经度:', size_hint=(0.3, 1), color=(1, 1, 1, 1)))

        self.lon_input = TextInput(
            hint_text='例如: 121.4737',
            multiline=False,
            size_hint=(0.7, 1),
            input_filter='float',
            padding=[dp(10), dp(12), dp(10), dp(8)]
        )


        lon_layout.add_widget(self.lon_input)
        location_group.add_widget(lon_layout)
        
        # 半径输入
        radius_layout = BoxLayout(size_hint=(1, None), height=dp(50), spacing=dp(10))
        radius_layout.add_widget(Label(text='打卡半径(米):', size_hint=(0.3, 1), color=(1, 1, 1, 1)))

        self.radius_input = TextInput(
            hint_text='例如: 100',
            multiline=False,
            size_hint=(0.7, 1),
            input_filter='int',
            padding=[dp(10), dp(12), dp(10), dp(8)]
        )


        radius_layout.add_widget(self.radius_input)
        location_group.add_widget(radius_layout)

        # 自动识别位置
        auto_location_layout = BoxLayout(size_hint=(1, None), height=dp(50), spacing=dp(10))
        auto_location_layout.add_widget(Label(text='自动识别位置:', size_hint=(0.3, 1), color=(1, 1, 1, 1)))

        self.auto_location_switch = Button(text='开启', background_color=(0.2, 0.8, 0.2, 1))
        self.auto_location_switch.bind(on_press=self.toggle_auto_location)
        auto_location_layout.add_widget(self.auto_location_switch)
        location_group.add_widget(auto_location_layout)
        
        scroll_content.add_widget(location_group)

        
        # 时间设置
        time_group = self.create_setting_group("时间设置")
        
        # 开始时间
        start_time_layout = BoxLayout(size_hint=(1, None), height=dp(50), spacing=dp(10))
        start_time_layout.add_widget(Label(text='打卡开始时间:', size_hint=(0.3, 1), color=(1, 1, 1, 1)))

        self.start_time_input = TextInput(
            hint_text='例如: 09:00',
            multiline=False,
            size_hint=(0.7, 1)
        )
        start_time_layout.add_widget(self.start_time_input)
        time_group.add_widget(start_time_layout)
        
        # 结束时间
        end_time_layout = BoxLayout(size_hint=(1, None), height=dp(50), spacing=dp(10))
        end_time_layout.add_widget(Label(text='打卡结束时间:', size_hint=(0.3, 1), color=(1, 1, 1, 1)))

        self.end_time_input = TextInput(
            hint_text='例如: 10:00',
            multiline=False,
            size_hint=(0.7, 1)
        )
        end_time_layout.add_widget(self.end_time_input)
        time_group.add_widget(end_time_layout)
        
        scroll_content.add_widget(time_group)
        
        # 自动打卡设置
        auto_group = self.create_setting_group("自动打卡设置")
        
        auto_switch_layout = BoxLayout(size_hint=(1, None), height=dp(50), spacing=dp(10))
        auto_switch_layout.add_widget(Label(text='启用自动打卡:', size_hint=(0.3, 1), color=(1, 1, 1, 1)))

        
        self.auto_switch = Button(
            text='开启',
            background_color=(0.2, 0.8, 0.2, 1)
        )

        self.auto_switch.bind(on_press=self.toggle_auto_switch)
        auto_switch_layout.add_widget(self.auto_switch)
        
        auto_group.add_widget(auto_switch_layout)
        scroll_content.add_widget(auto_group)


        # 按钮区域
        button_layout = BoxLayout(size_hint=(1, None), height=dp(70), spacing=dp(10))


        
        # 保存按钮
        save_btn = StyledButton(text='保存设置')
        save_btn.bind(on_press=self.save_settings)
        
        # 使用当前位置按钮
        use_current_btn = StyledButton(
            text='使用当前位置',
            background_color=(0.2, 0.6, 0.8, 1)
        )
        use_current_btn.bind(on_press=self.use_current_location)
        
        # 返回按钮
        back_btn = StyledButton(
            text='返回主界面',
            background_color=(0.8, 0.8, 0.8, 1)
        )
        back_btn.bind(on_press=self.go_back)
        
        button_layout.add_widget(save_btn)
        button_layout.add_widget(use_current_btn)
        button_layout.add_widget(back_btn)
        
        main_layout.add_widget(scroll_content)
        main_layout.add_widget(button_layout)


        
        self.add_widget(main_layout)
        
        # 加载现有设置
        Clock.schedule_once(self.load_settings, 0.1)
    
    def create_setting_group(self, title):
        """创建设置组"""
        group = BoxLayout(orientation='vertical', spacing=dp(10))
        
        title_label = Label(
            text=title,
            font_size=dp(16),
            bold=True,
            size_hint=(1, None),
            height=dp(30),
            color=(1, 1, 1, 1)

        )
        group.add_widget(title_label)
        
        return group
    
    def load_settings(self, dt):
        """加载用户设置"""
        app = App.get_running_app()
        if not hasattr(app, 'current_user'):
            return
        
        settings = db.get_user_settings(app.current_user)
        
        if settings:
            # 位置设置
            self.lat_input.text = str(settings.get('latitude', ''))
            self.lon_input.text = str(settings.get('longitude', ''))
            self.radius_input.text = str(settings.get('radius', '100'))
            
            # 时间设置
            self.start_time_input.text = settings.get('punch_start', '09:00')
            self.end_time_input.text = settings.get('punch_end', '10:00')
            
            # 自动打卡设置
            self.apply_auto_punch_state(settings.get('auto_punch', False), persist=False)


            # 自动识别位置
            if settings.get('auto_location', True):
                self.auto_location_switch.text = '开启'
                self.auto_location_switch.background_color = (0.2, 0.8, 0.2, 1)
            else:
                self.auto_location_switch.text = '关闭'
                self.auto_location_switch.background_color = (0.8, 0.2, 0.2, 1)

        try:
            if hasattr(self, 'server_url_input'):
                self.server_url_input.text = get_server_url() or ''
        except Exception:
            pass

        self.apply_auto_location()


    def on_enter(self):
        """进入界面时应用自动位置"""
        self.load_settings(0)
        try:
            if hasattr(self, 'server_url_input'):
                self.server_url_input.text = get_server_url() or ''
        except Exception:
            pass

        self.apply_auto_location()



    def update_bg(self, *args):
        """更新背景尺寸"""
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    
    def persist_auto_punch(self, auto_on):
        app = App.get_running_app()
        if not hasattr(app, 'current_user'):
            return
        settings = db.get_user_settings(app.current_user) or {}
        settings['auto_punch'] = auto_on
        db.save_user_settings(app.current_user, settings)

    def apply_auto_punch_state(self, auto_on, persist=False):
        self.auto_switch.text = '开启' if auto_on else '关闭'
        self.auto_switch.background_color = (0.2, 0.8, 0.2, 1) if auto_on else (0.8, 0.2, 0.2, 1)

        main_screen = self.manager.get_screen('main')
        if hasattr(main_screen, 'set_auto_punch_state'):
            main_screen.set_auto_punch_state(auto_on, save=persist)

        if persist:
            self.persist_auto_punch(auto_on)

    def toggle_auto_switch(self, instance):

        """切换自动打卡开关"""
        auto_on = instance.text == '关闭'
        self.apply_auto_punch_state(auto_on, persist=True)


    def toggle_auto_location(self, instance):
        """切换自动识别位置"""
        if instance.text == '关闭':
            instance.text = '开启'
            instance.background_color = (0.2, 0.8, 0.2, 1)
        else:
            instance.text = '关闭'
            instance.background_color = (0.8, 0.2, 0.2, 1)
        try:
            if hasattr(self, 'server_url_input'):
                self.server_url_input.text = get_server_url() or ''
        except Exception:
            pass

        self.apply_auto_location()


    def apply_auto_location(self):
        """应用自动识别位置"""
        main_screen = self.manager.get_screen('main')
        auto_on = self.auto_location_switch.text == '开启'

        self.lat_input.disabled = auto_on
        self.lon_input.disabled = auto_on

        if auto_on and main_screen.current_location:
            self.lat_input.text = str(main_screen.current_location['latitude'])
            self.lon_input.text = str(main_screen.current_location['longitude'])
    
    def use_current_location(self, instance):
        """使用当前位置"""
        app = App.get_running_app()
        main_screen = self.manager.get_screen('main')
        
        if main_screen.current_location:
            self.lat_input.text = str(main_screen.current_location['latitude'])
            self.lon_input.text = str(main_screen.current_location['longitude'])
        else:
            self.show_popup("错误", "无法获取当前位置，请确保GPS已开启")



    def save_settings(self, instance):
        """保存设置"""
        app = App.get_running_app()
        if not hasattr(app, 'current_user'):
            return
        
        try:
            # 验证输入
            def normalize_number(value):
                return value.strip().replace('，', '.').replace('。', '.')

            radius_text = normalize_number(self.radius_input.text)
            if not radius_text:
                raise ValueError("请输入打卡半径")

            auto_on = self.auto_location_switch.text == '开启'
            if auto_on:
                main_screen = self.manager.get_screen('main')
                if not main_screen.current_location:
                    raise ValueError("未获取定位，请开启定位或关闭自动识别")
                latitude = float(main_screen.current_location['latitude'])
                longitude = float(main_screen.current_location['longitude'])
            else:
                lat_text = normalize_number(self.lat_input.text)
                lon_text = normalize_number(self.lon_input.text)
                if not lat_text:
                    raise ValueError("请输入纬度")
                if not lon_text:
                    raise ValueError("请输入经度")
                latitude = float(lat_text)
                longitude = float(lon_text)

            radius = float(radius_text)
            
            # 验证时间格式
            start_time = self.start_time_input.text.strip()
            end_time = self.end_time_input.text.strip()

            if not start_time or not end_time:
                raise ValueError("请输入打卡时间")
            
            datetime.strptime(start_time, '%H:%M')
            datetime.strptime(end_time, '%H:%M')

            
            if radius <= 0:
                raise ValueError("半径必须大于0")
            
            # 保存服务器地址（用于群/公告/版本等在线功能）
            try:
                if hasattr(self, 'server_url_input'):
                    set_server_url(self.server_url_input.text)
            except Exception:
                pass

            # 保存设置（保留其他字段）
            settings = db.get_user_settings(app.current_user) or {}
            settings.update({

                'latitude': latitude,
                'longitude': longitude,
                'radius': radius,
                'punch_start': start_time,
                'punch_end': end_time,
                'auto_punch': (self.auto_switch.text == '开启'),
                'auto_location': (self.auto_location_switch.text == '开启')
            })
            
            db.save_user_settings(app.current_user, settings)
            self.apply_auto_punch_state(self.auto_switch.text == '开启', persist=False)
            
            self.show_popup("成功", "设置已保存")

            
        except ValueError as e:
            self.show_popup("输入错误", f"请检查输入格式: {str(e)}")
        except Exception as e:
            self.show_popup("保存失败", f"保存设置时出错: {str(e)}")

    
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
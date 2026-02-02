# Copyright (C) [2026] [晨曦微光]
# 此软件受著作权法保护。未经明确书面许可，任何单位或个人不得复制、分发、修改或用于商业用途。
# APP名称：[晨曦智能打卡]
# 版本号：1.0.0

"""
应用主文件和配置
"""


import os
import time
import json
import traceback
from datetime import datetime
from threading import Thread




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
from kivy.uix.floatlayout import FloatLayout

from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.utils import platform as kivy_platform
from kivy.clock import Clock
from kivy.logger import Logger
from kivy.storage.jsonstore import JsonStore

class AttendanceApp(App):
    """打卡应用主类"""

    def _diag_event(self, event_name: str, data=None):
        """轻量启动诊断：把关键生命周期事件记录到本地文件。

        HarmonyOS/华为机型“点开就回桌面/像进后台”多数情况下要靠事件时间线定位。
        """
        try:
            if not hasattr(self, '_diag_t0'):
                self._diag_t0 = time.time()
                self._diag_events = []
            ts = time.time() - self._diag_t0
            self._diag_events.append({
                'time': round(ts, 3),
                'event': event_name,
                'data': data,
            })

            # 同步输出到 logcat（release 包也能抓到），避免 /Android/data 在部分 ROM 上不可见
            try:
                Logger.info(f"DIAG t=+{round(ts, 3)} {event_name} data={data}")
            except Exception:
                pass
        except Exception:
            pass


    def _diag_save(self, *_):
        try:
            events = getattr(self, '_diag_events', None)
            if not events:
                return
            log_dir = self._get_diag_dir()
            path = os.path.join(log_dir, 'startup_diagnosis.json')

            payload = {
                'saved_at': datetime.now().isoformat(timespec='seconds'),
                'platform': kivy_platform,
                'events': events,
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

            try:
                Logger.info(f"DIAG saved {path}")
            except Exception:
                pass
        except Exception:
            pass


    def _log_exception(self, where: str):
        """把启动异常写入本地文件，方便在手机上定位“点开就回桌面/像进后台”的问题。"""
        try:
            log_dir = self._get_diag_dir()
            log_path = os.path.join(log_dir, 'startup_error.log')

            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"\n[{datetime.now().isoformat(timespec='seconds')}] {where}\n")
                f.write(traceback.format_exc())
                f.write("\n")

            # 同步输出到 logcat（release 包也能抓到）
            try:
                Logger.error(f"STARTUP {where}: {traceback.format_exc()}")
            except Exception:
                pass
        except Exception:
            # 日志写入失败时忽略（避免二次异常）
            pass


    def _build_fallback_error_view(self):
        content = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(20))
        content.add_widget(Label(text='应用启动失败', font_size=dp(20), color=(1, 1, 1, 1)))
        content.add_widget(Label(
            text='请在应用数据目录中查找 startup_error.log / startup_diagnosis.json。',
            halign='left', valign='top', color=(0.9, 0.95, 1, 1)
        ))
        btn = Button(text='退出', size_hint=(1, None), height=dp(44), background_color=(0.8, 0.2, 0.2, 1))
        btn.bind(on_press=lambda *_: self.confirm_exit(None))
        content.add_widget(btn)
        return content

    # --- Android 小窗(PiP) / 后台控制 ---
    def _get_android_activity(self):
        if kivy_platform != 'android':
            return None
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            return PythonActivity.mActivity
        except Exception:
            return None

    def _android_sdk_int(self) -> int:
        if kivy_platform != 'android':
            return 0
        try:
            from jnius import autoclass
            VERSION = autoclass('android.os.Build$VERSION')
            return int(VERSION.SDK_INT)
        except Exception:
            return 0

    def _android_package_name(self) -> str:
        act = self._get_android_activity()
        if not act:
            return ''
        try:
            return str(act.getPackageName())
        except Exception:
            return ''

    def _get_diag_dir(self) -> str:
        """选择一个“可被 adb pull / 文件管理器访问”的诊断目录。

        说明：部分华为/鸿蒙 ROM 上，`android.storage.primary_external_storage_path()` 可能异常，
        导致无法创建 `/sdcard/Android/data/<package>/files`。

        这里改为：直接尝试多个常见外部存储基准路径，并做“可写探测”。
        """
        # 非 Android：直接使用 Kivy 的 user_data_dir
        if kivy_platform != 'android':
            return getattr(self, 'user_data_dir', None) or os.getcwd()

        # 先用 Android 官方 API 获取 app 专属外部目录（最稳，且不需要存储权限）
        act = self._get_android_activity()
        if act:
            try:
                ext = act.getExternalFilesDir(None)
                if ext is not None:
                    ext_dir = str(ext.getAbsolutePath())
                    os.makedirs(ext_dir, exist_ok=True)

                    probe = os.path.join(ext_dir, '.diag_probe')
                    with open(probe, 'w', encoding='utf-8') as f:
                        f.write('ok')
                    try:
                        os.remove(probe)
                    except Exception:
                        pass

                    return ext_dir
            except Exception:
                pass

        # 兜底：尝试常见外部路径拼接（部分 ROM getExternalFilesDir 可能异常）
        pkg = self._android_package_name() or 'unknown.package'
        bases = []
        env_base = os.environ.get('EXTERNAL_STORAGE')
        if env_base:
            bases.append(env_base)
        bases.extend(['/storage/emulated/0', '/sdcard', '/storage/self/primary'])

        for base in bases:
            try:
                ext_dir = os.path.join(base, 'Android', 'data', pkg, 'files')
                os.makedirs(ext_dir, exist_ok=True)

                probe = os.path.join(ext_dir, '.diag_probe')
                with open(probe, 'w', encoding='utf-8') as f:
                    f.write('ok')
                try:
                    os.remove(probe)
                except Exception:
                    pass

                return ext_dir
            except Exception:
                continue

        # 兜底：内部目录（release 包可能无法 adb 直接读取）
        return getattr(self, 'user_data_dir', None) or os.getcwd()



    def _pip_supported(self) -> bool:
        # Picture-in-Picture 最低需要 Android 8.0 (API 26)
        return kivy_platform == 'android' and self._android_sdk_int() >= 26


    def _set_pip_close_visible(self, visible: bool):
        btn = getattr(self, '_pip_close_btn', None)
        if not btn:
            return
        btn.disabled = not visible
        btn.opacity = 1 if visible else 0

    def _enter_pip(self, reason: str = '') -> bool:
        """进入 Android 系统 PiP 小窗。

        说明：PiP 是否生效还取决于系统/ROM 设置（部分鸿蒙/华为可能限制）。
        """
        if not self._pip_supported():
            return False
        act = self._get_android_activity()
        if not act:
            return False
        try:
            # 有些 ROM 进入 PiP 会触发 on_pause；这里先标记，避免被 on_pause 结束进程
            self._in_pip = True
            self._diag_event('enter_pip', {'reason': reason})
            act.enterPictureInPictureMode()
            self._set_pip_close_visible(True)
            return True
        except Exception:
            self._in_pip = False
            self._log_exception('enterPictureInPictureMode failed')
            self._diag_event('enter_pip_failed', {'reason': reason})
            return False

    def _go_background(self, reason: str = '') -> bool:
        """把任务送入后台（最小化）。"""
        act = self._get_android_activity()
        if not act:
            return False
        try:
            self._allow_background = True
            self._diag_event('go_background', {'reason': reason})
            # True：允许把整个任务移到后台
            act.moveTaskToBack(True)
            return True
        except Exception:
            self._log_exception('moveTaskToBack failed')
            return False

    def _pip_close_pressed(self, *_):
        # 用户要求：小窗模式下提供“关闭”按键，点击后退出应用
        self._diag_event('pip_close_pressed')
        self.confirm_exit(None)

    def _build_exit_popup(self, title: str = '退出提醒'):
        """统一的退出/后台/小窗选择弹窗。"""
        content = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(20))
        content.add_widget(Label(text='请选择操作：', color=(1, 1, 1, 1)))

        # 第一行：取消 / 退出
        row1 = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        cancel_btn = Button(text='取消', background_color=(0.2, 0.6, 0.8, 1))
        exit_btn = Button(text='退出应用', background_color=(0.8, 0.2, 0.2, 1))
        row1.add_widget(cancel_btn)
        row1.add_widget(exit_btn)
        content.add_widget(row1)

        # 第二行：小窗 / 后台
        row2 = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(10))
        pip_btn = Button(text='小窗悬浮', background_color=(0.25, 0.55, 0.25, 1))
        bg_btn = Button(text='后台运行', background_color=(0.55, 0.55, 0.55, 1))
        row2.add_widget(pip_btn)
        row2.add_widget(bg_btn)
        content.add_widget(row2)

        popup = Popup(
            title=title,
            content=content,
            size_hint=(0.9, 0.42),
            background_color=(0.0667, 0.149, 0.3098, 1),
            background=''
        )

        cancel_btn.bind(on_press=lambda *_: popup.dismiss())
        exit_btn.bind(on_press=lambda *_: self.confirm_exit(popup))

        def _do_pip(*_):
            popup.dismiss()
            if not self._enter_pip('exit_popup'):
                # 不支持/失败时，退回到后台运行
                self._go_background('pip_failed_fallback')

        def _do_bg(*_):
            popup.dismiss()
            self._go_background('exit_popup')

        pip_btn.bind(on_press=_do_pip)
        bg_btn.bind(on_press=_do_bg)
        return popup

    def _init_screens(self, *_):

        """延迟导入并初始化所有屏幕，降低启动阶段卡顿/异常概率。

        说明：在华为/鸿蒙机型上，启动阶段如果主线程长时间卡在 import/main.py 解析，
        可能出现“只看到启动画面，进不去登录页，像进入后台”。

        这里把“模块导入”放到后台线程做，主线程只负责切换界面与创建 widget。
        """
        if getattr(self, '_screens_inited', False):
            return
        if getattr(self, '_init_in_progress', False):
            return

        self._init_in_progress = True
        self._diag_event('init_screens_start')

        def _import_worker():
            self._diag_event('init_import_thread_start')
            try:
                # 当 main.py 作为入口脚本在 Android 上运行时，它的顶层定义在 __main__ 模块里。
                # 直接 import main 会导致同一份代码被二次执行（__main__ 与 main 各一遍），可能引发副作用。
                # 因此：优先从 __main__ 取登录/注册页；取不到再回退 import main。
                try:
                    import __main__ as _mainmod
                except Exception:
                    _mainmod = None

                LoginScreen = getattr(_mainmod, 'LoginScreen', None) if _mainmod else None
                RegisterScreen = getattr(_mainmod, 'RegisterScreen', None) if _mainmod else None
                if LoginScreen is None or RegisterScreen is None:
                    from main import LoginScreen, RegisterScreen

                from main_screen import MainScreen
                from settings_screen import SettingsScreen
                from admin_screen import AdminScreen, AdManagerScreen, UserSearchScreen
                from group_screen import GroupScreen
                from server_admin_screen import ServerAdminScreen
                from chat_screen import ChatScreen
                from profile_screen import ProfileScreen


                self._imported_screens = {


                    'LoginScreen': LoginScreen,
                    'RegisterScreen': RegisterScreen,
                    'MainScreen': MainScreen,
                    'SettingsScreen': SettingsScreen,
                    'AdminScreen': AdminScreen,
                    'UserSearchScreen': UserSearchScreen,
                    'AdManagerScreen': AdManagerScreen,
                    'GroupScreen': GroupScreen,
                    'ServerAdminScreen': ServerAdminScreen,
                    'ChatScreen': ChatScreen,
                    'ProfileScreen': ProfileScreen,
                }



                self._diag_event('init_import_ok')
                Clock.schedule_once(self._apply_imported_screens, 0)
            except Exception:
                self._log_exception('init_import failed')
                self._diag_event('init_import_failed', {'error': 'exception'})
                Clock.schedule_once(self._show_init_error, 0)

        Thread(target=_import_worker, daemon=True).start()

    def _apply_imported_screens(self, *_):
        try:
            screens = getattr(self, '_imported_screens', None) or {}
            if not screens:
                raise RuntimeError('No imported screens')

            # 注意：不要重复添加
            pairs = [
                ('login', screens['LoginScreen'](name='login')),
                ('register', screens['RegisterScreen'](name='register')),
                ('main', screens['MainScreen'](name='main')),
                ('settings', screens['SettingsScreen'](name='settings')),
                ('groups', screens['GroupScreen'](name='groups')),
                ('chat', screens['ChatScreen'](name='chat')),
                ('profile', screens['ProfileScreen'](name='profile')),
                ('server_admin', screens['ServerAdminScreen'](name='server_admin')),
                ('admin', screens['AdminScreen'](name='admin')),

                ('user_search', screens['UserSearchScreen'](name='user_search')),

                ('ad_manager', screens['AdManagerScreen'](name='ad_manager')),
            ]

            for name, widget in pairs:
                if not self.sm.has_screen(name):
                    self.sm.add_widget(widget)

            # 尝试恢复上次登录状态（避免用户切到桌面/后台后回来需要重新登录）
            self._restore_cached_session(route=True)

            self._screens_inited = True
            self._diag_event('init_screens_ok')
        except Exception:
            self._log_exception('apply_imported_screens failed')
            self._diag_event('init_apply_failed', {'error': 'exception'})
            self._show_init_error()
        finally:
            self._init_in_progress = False
            Clock.schedule_once(self._diag_save, 0)

    def _show_init_error(self, *_):
        try:
            if self.sm and self.sm.has_screen('loading'):
                scr = self.sm.get_screen('loading')
                scr.clear_widgets()
                scr.add_widget(self._build_fallback_error_view())
                self.sm.current = 'loading'
        except Exception:
            pass
        finally:
            self._init_in_progress = False
            Clock.schedule_once(self._diag_save, 0)



    def build(self):
        """构建应用界面

        Mate 20 / HarmonyOS 上“点开就回桌面/像进入后台”常见原因：启动阶段卡顿或异常。
        这里尽量让 build() 非常快返回一个“加载中”界面，然后用 Clock 延迟导入/初始化各屏幕。
        """
        self.title = "晨曦智能打卡"
        self.app_version = "1.1.0"

        # 诊断：记录 build 开始
        self._diag_event('build_started')

        try:
            self.sm = ScreenManager()

            loading = Screen(name='loading')
            content = BoxLayout(orientation='vertical', spacing=dp(10), padding=[dp(16), dp(16), dp(16), dp(16)])

            content.add_widget(Label(
                text='晨曦智能打卡',
                font_size=dp(22),
                bold=True,
                color=(1, 1, 1, 1),
                size_hint=(1, None),
                height=dp(40),
            ))

            # 启动加载页：显示“中国地图”背景，不显示“正在加载/日志目录”
            try:
                from kivy.uix.image import Image
                map_path = os.path.join(os.path.dirname(__file__), 'assets', 'presplash.png')
                if os.path.exists(map_path):
                    content.add_widget(Image(source=map_path, allow_stretch=True, keep_ratio=True))
            except Exception:
                pass

            loading.add_widget(content)


            self.sm.add_widget(loading)
            self.sm.current = 'loading'

            # 外层容器：用于在 PiP 小窗时显示“关闭”按钮（FloatLayout 可以覆盖在 ScreenManager 上）
            root = FloatLayout()
            root.add_widget(self.sm)

            self._pip_close_btn = Button(
                text='关闭',
                size_hint=(None, None),
                size=(dp(50), dp(40)),
                pos_hint={'right': 0.995, 'top': 0.995},
                background_color=(0.85, 0.2, 0.2, 1),
            )
            self._pip_close_btn.bind(on_press=self._pip_close_pressed)
            root.add_widget(self._pip_close_btn)
            self._set_pip_close_visible(False)

            # 延迟初始化真实界面，避免 build() 阻塞太久
            Clock.schedule_once(self._init_screens, 0)
            Clock.schedule_once(self._init_screens, 0.2)

            self._diag_event('build_finished')
            return root

        except Exception:
            self._log_exception('build() failed')
            self._diag_event('build_failed', {'error': 'exception'})
            return self._build_fallback_error_view()


    
    def on_start(self):
        """应用启动时调用"""
        # 设置窗口背景色（#11264F）
        Window.clearcolor = (0.0667, 0.149, 0.3098, 1)

        self._diag_event('on_start')

        # 记录启动时间：用于区分“启动阶段的短暂 pause”与“用户把应用切到后台”
        self._startup_ts = time.time()

        # 后台运行控制：默认不允许后台；只有在“退出提醒”里点了【后台运行】才允许
        self._allow_background = False
        # PiP 小窗标记：只有我们主动调用 enterPictureInPictureMode() 才置 True
        self._in_pip = False
        self._set_pip_close_visible(False)

        # 兜底：若 build 阶段的延迟初始化未触发，则在 on_start 再触发一次

        Clock.schedule_once(self._init_screens, 0)

        # 启动后延迟保存一次诊断文件（给生命周期事件留时间）
        Clock.schedule_once(self._diag_save, 8)



        # 不允许后台运行：用户关闭/返回时提示并直接退出；应用进入后台时也不保持运行
        Window.bind(on_request_close=self.on_request_close)
        Window.bind(on_keyboard=self.on_keyboard)




        # 移动端：不强制全屏/不强制 Window.show。
        # 部分机型（如部分华为系统）在启动时强制全屏/强制 show 可能触发异常的 pause/resume，
        # 表现为“点击后立刻回到桌面/像进入后台”。
        from kivy.utils import platform as kivy_platform
        if kivy_platform not in ('android', 'ios'):
            Window.size = (360, 640)

        # 初始化默认管理员账号（仅开发环境）
        if os.environ.get('APP_DEV_MODE') == '1':
            try:
                from main import db
                db.add_user('admin', 'admin123', is_admin=True)
            except Exception:
                pass

        # 发布版不在运行时“清理文件”，避免误删导致异常
        # 如需清理，请在构建/发布流程中处理





    
    def _ensure_foreground_and_login(self, *args):
        # 兼容保留：只做界面切换，不做 Window.show/强制拉前台。
        # 如需在特定机型上拉前台，应通过 Android 端 Activity 处理。
        try:
            if getattr(self, 'sm', None):
                self.sm.current = 'login'
        except Exception:
            pass



    def on_keyboard(self, window, key, scancode, codepoint, modifiers):
        """拦截移动端返回键，避免系统默认行为把窗口直接送入后台"""
        # Android 返回键通常是 27 (ESC)
        if key in (27,):
            return self.on_request_close()
        return False

    def on_pause(self):
        """应用暂停时调用（移动端）

        需求：
        1) 默认不允许后台运行（用户切走/误触返回不应长期留后台）。
        2) 只有当用户在“退出提醒”里明确点了【后台运行】时，才允许在后台继续。
        3) 华为/鸿蒙部分机型启动阶段可能会出现一次短暂 pause 抖动，不能因此被系统杀掉。
        4) 若已进入 PiP 小窗，也必须允许（否则会退出）。
        """
        self._diag_event('on_pause', {
            'allow_background': bool(getattr(self, '_allow_background', False)),
            'in_pip': bool(getattr(self, '_in_pip', False)),
        })

        # 启动阶段抖动兜底：10 秒内一律允许
        try:
            if time.time() - getattr(self, '_startup_ts', 0) < 10:
                return True
        except Exception:
            return True

        if getattr(self, '_in_pip', False):
            return True

        if getattr(self, '_allow_background', False):
            return True

        # 默认：不允许后台，交还给系统（通常会停止/结束）
        return False





    
    def _restore_cached_session(self, route: bool = False) -> bool:
        """从 glimmer_client.json 恢复服务器登录态。

        说明：Android 上点击 Home / 切后台后，系统可能回收进程；再次打开时会重新启动。
        这里把 token/角色/服务器地址恢复到 App 属性里，避免“未点退出但登录失效”。
        """
        try:
            store = JsonStore('glimmer_client.json')
            if not store.exists('auth'):
                if route and getattr(self, 'sm', None):
                    self.sm.current = 'login'
                return False

            auth = store.get('auth') or {}
            username = str(auth.get('username') or '').strip()
            token = str(auth.get('token') or '').strip()
            role = str(auth.get('role') or 'user').strip() or 'user'
            server_url = str(auth.get('server_url') or '').strip().rstrip('/')

            if not username or not token or not server_url:
                if route and getattr(self, 'sm', None):
                    self.sm.current = 'login'
                return False

            # 写入 App 属性，供各页面调用
            self.current_user = username
            self.api_token = token
            self.server_role = role
            self.server_url = server_url
            self.user_data = {
                'role': role,
                'is_admin': role in ('admin', 'engineer'),
            }

            if route and getattr(self, 'sm', None):
                try:
                    self.sm.current = 'main'
                except Exception:
                    self.sm.current = 'login'

            return True
        except Exception:
            if route and getattr(self, 'sm', None):
                try:
                    self.sm.current = 'login'
                except Exception:
                    pass
            return False


    def on_resume(self):
        """应用恢复时调用（移动端）"""
        self._diag_event('on_resume')

        # 恢复到前台后：
        # - 认为已经退出 PiP/后台场景（再次切后台必须重新点“退出提醒”）
        self._allow_background = False
        self._in_pip = False
        self._set_pip_close_visible(False)

        # 恢复时也尝试从本地缓存恢复登录态（部分 ROM 会触发“伪重启/界面重建”）
        try:
            self._restore_cached_session(route=False)
        except Exception:
            pass

        try:
            main_screen = self.sm.get_screen('main')
            main_screen.evaluate_auto_mode()
        except Exception:
            pass





    def on_request_close(self, *args):
        """拦截返回/关闭。

        你的需求拆解：
        - 误触返回/关闭：不要退出，而是尽量进入“小窗悬浮”(PiP)。
        - 只有在“退出提醒”里点击【后台运行】才允许进入后台。
        - 小窗模式下提供【关闭】按键：点击后退出应用。
        """
        self._diag_event('on_request_close')

        if getattr(self, '_force_close', False):
            return False

        if getattr(self, '_exit_popup', None):
            return True

        current_screen = None
        try:
            current_screen = self.sm.current
        except Exception:
            current_screen = None

        # 注册页按返回：回登录页
        if current_screen == 'register':
            try:
                self.sm.current = 'login'
            except Exception:
                pass
            return True

        # 非登录页：优先进入小窗，防止误触直接退出
        if current_screen not in ('login', 'register'):
            if self._enter_pip('back_key'):
                return True

        # 登录页 / 不支持 PiP：弹出选择（退出 / 后台 / 小窗）
        popup = self._build_exit_popup('退出提醒')
        self._exit_popup = popup
        popup.bind(on_dismiss=lambda *_: setattr(self, '_exit_popup', None))
        popup.open()
        return True






    def confirm_exit(self, popup):

        if popup:
            popup.dismiss()
        self._diag_event('confirm_exit')
        self._diag_save()
        self._force_close = True
        try:
            self.stop()
        finally:
            os._exit(0)




# 应用配置

if __name__ == '__main__':
    # 设置默认管理员账号（仅开发环境）
    print("初始化数据库...")
    
    # 确保所有屏幕类都已导入
    import sys
    sys.path.append('.')
    
    # 运行应用
    AttendanceApp().run()

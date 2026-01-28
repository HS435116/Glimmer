[app]

# (str) Title of your application
title = 晨曦智能打卡

# (str) Package name
package.name = attendanceapp

# (str) Package domain (needed for android/ios packaging)
package.domain = com.chenxiAI.attendance

# (str) Source code where the main.py live
source.dir = .

# (str) Application entry point (default is main.py).
# IMPORTANT: Do not override entrypoint here. Some buildozer/p4a combinations may only package the entrypoint file,
# which would cause other modules (e.g. app_main.py) to be missing from assets/private.tar and crash on import.
#entrypoint = main.py


# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,json,ttf,ico

# (list) List of inclusions using pattern matching
#source.include_patterns = assets/*,images/*.png

# IMPORTANT: Exclude setup.py from the packaged app sources.
# Even with p4a's --ignore-setup-py, having a setup.py inside the app source dir may lead to assets/private.tar
# containing only main.pyc (missing other modules like app_main.py) and crashing on import.
source.exclude_patterns = setup.py

# (list) Source files to exclude (let empty to not exclude anything)
#source.exclude_exts = spec

# (str) Application versioning (method 1)
version = 1.1.0

# (list) Application requirements
# comma separated e.g. requirements = sqlite3,kivy
requirements = python3,kivy==2.1.0,kivymd==0.104.2,plyer==2.1.0,requests,pyjnius

# (str) Presplash of the application
presplash.filename = %(source.dir)s/assets/presplash.png

# (str) Icon of the application
icon.filename = %(source.dir)s/assets/icon.png

# (list) Supported orientations
# Valid options are: landscape, portrait, portrait-reverse or landscape-reverse
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

#
# Android specific
#

# (list) Permissions
android.permissions = WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE, CAMERA, INTERNET, ACCESS_NETWORK_STATE, ACCESS_FINE_LOCATION, ACCESS_COARSE_LOCATION, POST_NOTIFICATIONS

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK will support.
android.minapi = 21

# (int) Android NDK version to use
android.ndk = 25b

# (bool) If True, then skip trying to update the Android sdk
# This can be useful to avoid excess Internet downloads or save time
# when an update is due and you just want to test/build your package
android.skip_update = False

# (bool) If True, then automatically accept SDK license
# agreements. This is intended for automation only. If set to False,
# the default, you will be shown the license when first running
# buildozer.
android.accept_sdk_license = True

# --- Release signing (CI injects secrets at build time) ---
# IMPORTANT: Do NOT commit the real keystore or passwords.
android.release_keystore = %(source.dir)s/.keystore/release.keystore
android.release_keystore_password = __ANDROID_KEYSTORE_PASSWORD__
android.release_keyalias = __ANDROID_KEY_ALIAS__
android.release_keyalias_password = __ANDROID_KEY_ALIAS_PASSWORD__


# (str) Android entry point, default is ok for Kivy-based app
#android.entrypoint = org.renpy.android.PythonActivity

# --- Picture-in-Picture (小窗悬浮) ---
# 让 Activity 支持 PiP（Android 8.0+）。
# 注意：是否允许小窗，还取决于系统/ROM 的"画中画/小窗"开关。
android.extra_manifest_activity_arguments = android:supportsPictureInPicture="true" android:resizeableActivity="true" android:configChanges="keyboardHidden|orientation|screenSize|screenLayout|smallestScreenSize"

# (list) Android application meta-data to set (key=value format)
#android.meta_data =

# (list) Android library project to add (will be added in the
# project.properties automatically.)
#android.library_references =

# (str) Android logcat filters to use
#android.logcat_filters = *:S python:D

# (bool) Copy library instead of making a libpymodules.so
#android.copy_libs = 1

# (list) Android architectures to build for, choices: armeabi-v7a, arm64-v8a, x86, x86_64
android.archs = arm64-v8a,armeabi-v7a

#
# Python for android (p4a) specific
#

# (str) python-for-android branch to use, defaults to master
#p4a.branch = master

# (str) python-for-android specific commit to use, defaults to HEAD, must be within p4a.branch
#p4a.commit = HEAD

# (str) python-for-android git clone directory
#p4a.source_dir =

# (str) The directory in which python-for-android should look for your own build recipes (if any)
#p4a.local_recipes =

# (str) Filename to the hook for p4a
#p4a.hook =

# (str) Bootstrap to use for android builds
# p4a.bootstrap = sdl2

# (int) port number to specify an explicit --port= p4a argument (eg for bootstrap flask)
#p4a.port =

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 0

# (str) Path to build artifact storage, absolute or relative to spec file
#build_dir = ./.buildozer

# (str) Path to build output (i.e. .apk, .aab, .ipa) storage
#bin_dir = ./bin

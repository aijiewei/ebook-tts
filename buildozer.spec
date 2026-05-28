[app]
title = 电子书朗读器
package.name = ebookttsreader
package.domain = org.example
version = 1.0.0
source.dir = .
# version.regex = __version__ = ['"](.*)['"]
# version.filename = %(source.dir)s/main.py

# Python 依赖
requirements = python3,kivy==2.3.0,pypdf,ebooklib,beautifulsoup4,gtts,edge-tts

# Android 相关
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,INTERNET
android.api = 33
android.minapi = 24
android.sdk = 33
android.ndk = 25b
android.gradle_dependencies = 'com.android.support:support-annotations:28.0.0'
android.accept_sdk_license = True
android.arch = arm64-v8a

# 屏幕方向
android.orientation = portrait
android.window_soft_input_mode = adjustResize

# 图标（可自行替换）
# android.icon = icon.png

# 桌面测试
osx.python_version = 3
osx.kivy_version = 2.3.0

# python-for-android 配置
p4a.python_version = 3.11

[buildozer]
log_level = 2
warn_on_root = 1

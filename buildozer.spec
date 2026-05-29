[app]
title = Ebook TTS Reader
package.name = ebookttsreader
package.domain = org.example
version = 1.0.0
source.dir = .
# version.regex = __version__ = ['"](.*)['"]
# version.filename = %(source.dir)s/main.py

# Python deps
requirements = python3==3.11.15,hostpython3==3.11.15,kivy==2.3.0,pypdf,ebooklib,beautifulsoup4,gtts,edge-tts

# Android
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,INTERNET
android.api = 33
android.minapi = 24
android.sdk = 33
android.ndk = 25b
# android.gradle_dependencies = com.android.support:support-annotations:28.0.0
android.accept_sdk_license = True
android.arch = arm64-v8a

# Screen
android.orientation = portrait
android.window_soft_input_mode = adjustResize

# Icon (replace with your own)
# android.icon = icon.png

# Desktop test
osx.python_version = 3
osx.kivy_version = 2.3.0

# python-for-android: use master branch (supports Python 3.11)
p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 1

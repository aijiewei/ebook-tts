[app]

# (str) Title of your application
title = Ebook TTS Reader

# (str) Package name
package.name = ebookttsreader

# (str) Package domain (needed for android/ios packaging)
package.domain = org.example

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include
source.include_exts = py,png,jpg,kv,atlas,ttf,mp3,wav

# (str) Application versioning
version = 1.0.0

# (list) Application requirements
# NOTE: ebooklib version is pinned in requirements.txt, not here
requirements = python3,kivy,pypdf,ebooklib,beautifulsoup4,gtts,edge-tts

# (str) Supported orientation
orientation = landscape

#
# Android Specific
#

# (bool) Fullscreen
fullscreen = 1

# (list) Permissions
android.permissions = INTERNET, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE

# (int) Android API to use (target SDK)
android.api = 33

# (int) Minimum API
android.minapi = 24

# (str) Android NDK version
android.ndk = 25b

# (str) Android archs — FIXED: use 'archs' (plural), not 'arch' (singular)
android.archs = arm64-v8a

# (bool) AndroidX
android.enable_androidx = True

# (str) Explicit Java 17 path (fixes Gradle "requires Java 17, using Java 11")
android.java_home = /usr/lib/jvm/java-17-openjdk-amd64

# (bool) Accept SDK license
android.accept_sdk_license = True

# (str) Android app theme
android.apptheme = @android:style/Theme.NoTitleBar

# (str) Orientation override
android.orientation = landscape

[app]
title = TDM Offline
package.name = tdmoffline
package.domain = org.ahmed
source.dir = .
source.include_exts = py,png,jpg,ttf
version = 1.0
requirements = python3,kivy==2.3.0,arabic-reshaper,python-bidi==0.4.2,future
orientation = landscape
fullscreen = 1
android.api = 33
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1

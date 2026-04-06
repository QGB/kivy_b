# buildozer.spec
[app]
title = Bluetooth Scanner
package.name = bluetoothscanner
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1
requirements = python3,kivy,pyjnius,android,plyer,flask,dill,requests,psutil
orientation = portrait
osx.python_version = 3
osx.kivy_version = 2.1.0
fullscreen = 0

# Android 权限
#android.permissions = BLUETOOTH,BLUETOOTH_ADMIN,ACCESS_FINE_LOCATION,BLUETOOTH_SCAN,BLUETOOTH_CONNECT
android.permissions = INTERNET,BLUETOOTH_ADMIN,BLUETOOTH,CAMERA,READ_EXTERNAL_STORAGE,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION

android.api = 30
android.minapi = 21
android.ndk = 25b
android.sdk = 30
android.archs = arm64-v8a, armeabi-v7a


# 其他
android.p4a.extra_args = --no-clean --use-dist=bluetoothscanner

[buildozer]
#debug
log_level = 2
warn_on_root = 0
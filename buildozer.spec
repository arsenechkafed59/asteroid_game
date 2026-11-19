[app]
title = Asteroid Hunter
package.name = asteroidhunter
package.domain = org.yourname

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0

# Твоя игра использует Kivy и стандартные библиотеки (math, random)
requirements = python3,kivy==2.3.0

orientation = landscape
fullscreen = 1

# Настройки Android (можно оставить по умолчанию, но лучше указать явно)
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a

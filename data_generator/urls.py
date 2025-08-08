from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('generator.urls')),  # 包含数据生成器应用的URL
]

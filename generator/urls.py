from django.urls import path
from . import views

urlpatterns = [
    # path('', views.index, name='index'),
    # path('database-config/', views.database_config, name='database_config'),
    # path('table-selection/', views.table_selection, name='table_selection'),
    # path('field-config/', views.field_config, name='field_config'),
    # path('generate-config/', views.generate_config, name='generate_config'),
    # path('generate-data/', views.generate_data, name='generate_data'),
    # path('result/', views.result, name='result'),
    # path('reset/', views.reset, name='reset'),

    path('', views.index, name='index'),
    path('reset/', views.reset, name='reset'),
    path('database-config/', views.database_config, name='database_config'),
    path('table-selection/', views.table_selection, name='table_selection'),
    path('field-config/', views.field_config, name='field_config'),
    path('generate-config/', views.generate_config, name='generate_config'),
    path('generate-data/', views.generate_data, name='generate_data'),
    path('result/', views.result, name='result'),
    # 添加check_connection的路由配置
    path('check-connection/', views.check_connection, name='check_connection'),
    path('logs/', views.log_list, name='log_list'),
]


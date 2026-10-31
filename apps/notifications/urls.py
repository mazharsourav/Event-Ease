from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list, name='notification_list'),
    path('api/count/', views.notification_count_api, name='notification_count_api'),
    path('api/mark_all_read/', views.mark_all_read_api, name='mark_all_read_api'),
    path('mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_read'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
]

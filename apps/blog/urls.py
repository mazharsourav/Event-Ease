from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.blog_list, name='blog_list'),
    path('create/', views.blog_create, name='blog_create'),
    path('post/<int:pk>/', views.blog_detail, name='blog_detail'),
    path('post/<int:pk>/edit/', views.blog_edit, name='blog_edit'),
    path('post/<int:pk>/delete/', views.blog_delete, name='blog_delete'),
    path('post/<int:pk>/react/', views.blog_react, name='blog_react'),
    path('comment/<int:pk>/delete/', views.blog_comment_delete, name='blog_comment_delete'),
]

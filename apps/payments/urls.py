from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('process/<int:booking_id>/', views.payment_process, name='payment_process'),
    path('success/<int:payment_id>/', views.payment_success, name='payment_success'),
    path('cancel/<int:booking_id>/', views.payment_cancel, name='payment_cancel'),
    path('quick-pay/<int:booking_id>/', views.quick_pay, name='quick_pay'),
    
    # bKash Payment URLs
    path('bkash/<int:booking_id>/', views.bkash_payment, name='bkash_payment'),
    path('bkash/process/<int:booking_id>/', views.bkash_process, name='bkash_process'),
    
    # Nagad Payment URLs
    path('nagad/<int:booking_id>/', views.nagad_payment, name='nagad_payment'),
    path('nagad/process/<int:booking_id>/', views.nagad_process, name='nagad_process'),
    
    # SSL Commerz Gateway URLs
    path('ssl/success/', views.ssl_success, name='ssl_success'),
    path('ssl/fail/', views.ssl_fail, name='ssl_fail'),
    path('ssl/cancel/', views.ssl_cancel, name='ssl_cancel'),
    path('ssl/ipn/', views.ssl_ipn, name='ssl_ipn'),
]

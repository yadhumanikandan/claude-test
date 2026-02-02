from django.urls import path
from . import views

urlpatterns = [
    # Transcription URLs
    path('', views.home, name='transcription_home'),
    path('list/', views.transcription_list, name='transcription_list'),
    path('transcription/<int:pk>/', views.transcription_detail, name='transcription_detail'),
    path('transcription/<int:pk>/delete/', views.transcription_delete, name='transcription_delete'),

    # PBX Configuration URLs
    path('pbx/', views.pbx_settings, name='pbx_settings'),
    path('pbx/add/', views.pbx_add, name='pbx_add'),
    path('pbx/<int:pk>/edit/', views.pbx_edit, name='pbx_edit'),
    path('pbx/<int:pk>/delete/', views.pbx_delete, name='pbx_delete'),
    path('pbx/<int:pk>/test/', views.pbx_test_connection, name='pbx_test_connection'),
    path('pbx/<int:pk>/sync/', views.pbx_sync, name='pbx_sync'),

    # CDR URLs
    path('cdr/', views.cdr_list, name='cdr_list'),
]

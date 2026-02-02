from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='transcription_home'),
    path('list/', views.transcription_list, name='transcription_list'),
    path('<int:pk>/', views.transcription_detail, name='transcription_detail'),
    path('<int:pk>/delete/', views.transcription_delete, name='transcription_delete'),
]

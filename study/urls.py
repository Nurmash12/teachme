from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('sources/<int:pk>/', views.source_detail, name='source_detail'),
]

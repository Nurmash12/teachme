from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('sources/<int:pk>/', views.source_detail, name='source_detail'),
    path('cards/<int:pk>/edit/', views.card_edit, name='card_edit'),
    path('cards/<int:pk>/delete/', views.card_delete, name='card_delete'),
    path('cards/<int:pk>/review/', views.card_review, name='card_review'),
]

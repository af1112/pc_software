from django.urls import path
from . import views


app_name = 'organizations'

urlpatterns = [
    path('', views.organization_list, name='list'),
    path('create/', views.organization_create, name='create'),
    path('<int:pk>/edit/', views.organization_edit, name='edit'),
]

from django.urls import path
from . import views

urlpatterns = [
    path('denoise/', views.denoise_audio, name='denoise_audio'),
]
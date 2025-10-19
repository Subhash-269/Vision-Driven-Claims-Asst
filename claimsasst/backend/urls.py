from django.urls import path
from . import views

app_name = 'backend'

urlpatterns = [
    # Simple test endpoint
    path('api/test/', views.test, name='api-test'),
]

from django.urls import path
from . import views

app_name = 'backend'

urlpatterns = [
    # Simple test endpoint (app-level path). Project mounts this under /api/ so
    # the final URL becomes: /api/test/
    path('test/', views.test, name='api-test'),
    path('text-extract/', views.text_extract, name='api-text-extract'),
    path('index-finder/', views.indexfinder, name='api-index-finder'),
    
]

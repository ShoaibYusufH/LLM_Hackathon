"""
URL configuration for teamB_LLM project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include
from . import views

app_name = 'chat'

urlpatterns = [
    # Chat endpoints
    path('api/chat/sessions/', views.create_chat_session, name='create_session'),
    path('api/chat/sessions/list/', views.get_chat_sessions, name='list_sessions'),
    path('api/chat/sessions/<str:session_id>/history/', views.get_chat_history, name='chat_history'),
    path('api/chat/sessions/<str:session_id>/clear/', views.clear_chat_history, name='clear_history'),
    path('api/chat/message/', views.send_message, name='send_message'),
    
    # Data ingestion endpoints
    path('api/ingest/github/', views.ingest_github_repo, name='ingest_github'),
    path('api/ingest/web/', views.ingest_web_documents, name='ingest_web'),
    path('api/ingest/batch/', views.batch_ingest, name='batch_ingest'),
    
    # Data management endpoints
    path('api/sources/', views.get_data_sources, name='list_sources'),
    path('api/sources/<int:source_id>/', views.delete_data_source, name='delete_source'),
    
    # Search endpoints
    path('api/search/', views.search_documents, name='search_documents'),
    
    # System endpoints
    path('api/health/', views.health_check, name='health_check'),
    path('api/stats/', views.get_stats, name='stats'),
]

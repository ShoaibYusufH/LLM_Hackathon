from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

def api_root(request):
    return JsonResponse({
        'message': 'RAG Chatbot API',
        'version': '1.0',
        'endpoints': {
            'chat': '/api/chat/',
            'ingest': '/api/ingest/',
            'search': '/api/search/',
            'health': '/api/health/',
            'admin': '/admin/'
        }
    })

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', api_root, name='api_root'),
    path('', include('teamB_LLM.urls')),
]
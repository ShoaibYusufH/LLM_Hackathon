import json
import uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.core.paginator import Paginator
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .services import rag_service
from .models import ChatSession, Message, DataSource, Document

# ==================== CHAT ENDPOINTS ====================

@csrf_exempt
@api_view(['POST'])
def create_chat_session(request):
    """Create a new chat session"""
    try:
        chat_session = ChatSession.objects.create(
            user=request.user if request.user.is_authenticated else None
        )
        
        return Response({
            'session_id': str(chat_session.session_id),
            'created_at': chat_session.created_at.isoformat()
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_chat_sessions(request):
    """Get all chat sessions for user"""
    try:
        if request.user.is_authenticated:
            sessions = ChatSession.objects.filter(user=request.user)
        else:
            # For anonymous users, you might want to use session storage
            sessions = ChatSession.objects.all()[:10]  # Limit for demo
            
        sessions_data = [{
            'session_id': str(session.session_id),
            'created_at': session.created_at.isoformat(),
            'updated_at': session.updated_at.isoformat(),
            'message_count': session.messages.count()
        } for session in sessions.order_by('-created_at')]
        
        return Response({'sessions': sessions_data})
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_chat_history(request, session_id):
    """Get chat history for a session"""
    try:
        chat_session = ChatSession.objects.get(session_id=session_id)
        messages = chat_session.messages.all().order_by('timestamp')
        
        messages_data = [{
            'id': msg.id,
            'content': msg.content,
            'is_user': msg.is_user,
            'timestamp': msg.timestamp.isoformat()
        } for msg in messages]
        
        return Response({
            'session_id': str(session_id),
            'messages': messages_data
        })
        
    except ChatSession.DoesNotExist:
        return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['POST'])
def send_message(request):
    """Send a message and get AI response"""
    try:
        data = request.data
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id')
        
        if not user_message:
            return Response({'error': 'Message cannot be empty'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not session_id:
            return Response({'error': 'Session ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get or create session
        chat_session, _ = ChatSession.objects.get_or_create(
            session_id=session_id,
            defaults={'user': request.user if request.user.is_authenticated else None}
        )
        
        # Save user message
        user_msg = Message.objects.create(
            session=chat_session,
            content=user_message,
            is_user=True
        )
        
        # Generate AI response
        bot_response = rag_service.generate_response(user_message)
        
        # Save bot response
        bot_msg = Message.objects.create(
            session=chat_session,
            content=bot_response,
            is_user=False
        )
        
        return Response({
            'user_message': {
                'id': user_msg.id,
                'content': user_message,
                'timestamp': user_msg.timestamp.isoformat()
            },
            'bot_response': {
                'id': bot_msg.id,
                'content': bot_response,
                'timestamp': bot_msg.timestamp.isoformat()
            }
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['DELETE'])
def clear_chat_history(request, session_id):
    """Clear chat history for a session"""
    try:
        chat_session = ChatSession.objects.get(session_id=session_id)
        chat_session.messages.all().delete()
        
        return Response({'message': 'Chat history cleared successfully'})
        
    except ChatSession.DoesNotExist:
        return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ==================== DATA INGESTION ENDPOINTS ====================

@csrf_exempt
@api_view(['POST'])
def ingest_github_repo(request):
    """Ingest GitHub repository"""
    try:
        data = request.data
        repo_url = data.get('repo_url', '').strip()
        repo_name = data.get('repo_name', '').strip()
        
        if not repo_url:
            return Response({'error': 'Repository URL is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Extract repo name if not provided
        if not repo_name:
            repo_name = repo_url.split('/')[-1].replace('.git', '')
        
        # Create data source record
        data_source = DataSource.objects.create(
            name=repo_name,
            source_type='github',
            url=repo_url,
            status='processing'
        )
        
        # Process repository
        try:
            doc_count = rag_service.ingest_github_repo(repo_url, repo_name)
        except Exception as e:
            data_source.status = 'failed'
            data_source.save()
            return Response({'error': f'Failed to ingest repository: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'id': data_source.id,
            'message': f'Successfully ingested {doc_count} documents from {repo_name}',
            'doc_count': doc_count,
            'status': 'completed'
        })
            
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['POST'])
def ingest_web_documents(request):
    """Ingest web documents"""
    try:
        data = request.data
        urls = data.get('urls', [])
        name = data.get('name', f'Web docs ({len(urls)} URLs)')
        
        if not urls:
            return Response({'error': 'URLs are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Create data source record
        data_source = DataSource.objects.create(
            name=name,
            source_type='web',
            status='processing'
        )
        
        try:
            # Process URLs
            doc_count = rag_service.ingest_web_documents(urls, name)
            
            return Response({
                'id': data_source.id,
                'message': f'Successfully ingested {doc_count} web documents',
                'doc_count': doc_count,
                'status': 'completed'
            })
            
        except Exception as e:
            return Response({'error': f'Failed to ingest web documents: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_data_sources(request):
    """Get all data sources"""
    try:
        sources = DataSource.objects.all().order_by('-created_at')
        
        sources_data = [{
            'id': source.id,
            'name': source.name,
            'source_type': source.source_type,
            'url': source.url,
            'status': source.status,
            'document_count': source.document_count,
            'created_at': source.created_at.isoformat(),
            'updated_at': source.updated_at.isoformat(),
            'metadata': source.metadata
        } for source in sources]
        
        return Response({'sources': sources_data})
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['DELETE'])
def delete_data_source(request, source_id):
    """Delete a data source"""
    try:
        source = DataSource.objects.get(id=source_id)
        
        # Delete associated documents
        deleted_docs = rag_service.delete_source_documents(source_id)
        
        # Delete the source
        source.delete()
        
        return Response({
            'message': 'Data source deleted successfully',
            'deleted_documents': deleted_docs
        })
        
    except DataSource.DoesNotExist:
        return Response({'error': 'Data source not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ==================== SEARCH & RETRIEVAL ENDPOINTS ====================

@api_view(['POST'])
def search_documents(request):
    """Search through ingested documents"""
    try:
        data = request.data
        query = data.get('query', '').strip()
        k = data.get('k', 5)  # Number of results
        
        if not query:
            return Response({'error': 'Query is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Search documents
        docs = rag_service.search_documents(query, k=k)
        
        results = [{
            'content': doc.page_content[:500] + '...' if len(doc.page_content) > 500 else doc.page_content,
            'metadata': doc.metadata,
            'similarity_score': doc.metadata.get('similarity_score'),
            'distance': doc.metadata.get('distance')
        } for doc in docs]
        
        return Response({
            'query': query,
            'results': results,
            'count': len(results)
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ==================== STATUS & HEALTH ENDPOINTS ====================

@api_view(['GET'])
def health_check(request):
    """Health check endpoint"""
    try:
        # Check vector database
        vector_stats = rag_service.get_stats()
        
        # Check database
        total_sources = DataSource.objects.count()
        active_sources = DataSource.objects.filter(status='completed').count()
        total_sessions = ChatSession.objects.count()
        total_documents = Document.objects.count()
        
        return Response({
            'status': 'healthy',
            'vector_database': {
                'status': 'connected',
                'document_count': total_documents,
                'embedding_dimension': vector_stats.get('embedding_dimension')
            },
            'database': {
                'total_sources': total_sources,
                'active_sources': active_sources,
                'total_sessions': total_sessions,
                'total_documents': total_documents
            }
        })
        
    except Exception as e:
        return Response({
            'status': 'unhealthy',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_stats(request):
    """Get system statistics"""
    try:
        vector_stats = rag_service.get_stats()
        
        stats = {
            'data_sources': {
                'total': DataSource.objects.count(),
                'github_repos': DataSource.objects.filter(source_type='github').count(),
                'web_docs': DataSource.objects.filter(source_type='web').count(),
                'processing': DataSource.objects.filter(status='processing').count(),
                'completed': DataSource.objects.filter(status='completed').count(),
                'failed': DataSource.objects.filter(status='failed').count()
            },
            'chat_sessions': {
                'total': ChatSession.objects.count(),
                'total_messages': Message.objects.count(),
                'user_messages': Message.objects.filter(is_user=True).count(),
                'bot_messages': Message.objects.filter(is_user=False).count()
            },
            'vector_database': vector_stats
        }
        
        return Response(stats)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ==================== BATCH OPERATIONS ====================

@csrf_exempt
@api_view(['POST'])
def batch_ingest(request):
    """Batch ingest multiple sources"""
    try:
        data = request.data
        sources = data.get('sources', [])
        
        if not sources:
            return Response({'error': 'Sources list is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        results = []
        
        for source in sources:
            source_type = source.get('type')
            
            if source_type == 'github':
                try:
                    # Create a mock request with the source data
                    mock_request = type('MockRequest', (), {'data': source})()
                    result = ingest_github_repo(mock_request)
                    results.append({
                        'source': source,
                        'status': 'success',
                        'result': result.data
                    })
                except Exception as e:
                    results.append({
                        'source': source,
                        'status': 'failed',
                        'error': str(e)
                    })
            
            elif source_type == 'web':
                try:
                    # Create a mock request with the source data
                    mock_request = type('MockRequest', (), {'data': source})()
                    result = ingest_web_documents(mock_request)
                    results.append({
                        'source': source,
                        'status': 'success',
                        'result': result.data
                    })
                except Exception as e:
                    results.append({
                        'source': source,
                        'status': 'failed',
                        'error': str(e)
                    })
        
        return Response({
            'message': f'Processed {len(sources)} sources',
            'results': results
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
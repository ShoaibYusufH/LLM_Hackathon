from django.db import models
from django.contrib.auth.models import User
from pgvector.django import VectorField
import uuid

class ChatSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Session {self.session_id}"

class Message(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    content = models.TextField()
    is_user = models.BooleanField(default=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{'User' if self.is_user else 'Bot'}: {self.content[:50]}"

class DataSource(models.Model):
    SOURCE_TYPES = [
        ('github', 'GitHub Repository'),
        ('web', 'Web Document'),
        ('file', 'Uploaded File')
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ]
    
    name = models.CharField(max_length=200)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    url = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    document_count = models.IntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    
    def __str__(self):
        return f"{self.name} ({self.source_type})"
class Document(models.Model):
    """Store document chunks with vector embeddings"""
    source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='documents')
    content = models.TextField()
    embedding = VectorField(dimensions=384)  # For all-MiniLM-L6-v2
    metadata = models.JSONField(default=dict)
    chunk_index = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['source', 'chunk_index']),
        ]
    
    def __str__(self):
        return f"Document chunk {self.chunk_index} from {self.source.name}"
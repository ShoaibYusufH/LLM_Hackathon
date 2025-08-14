import os
import requests
import git
import shutil
import numpy as np
from pathlib import Path
from bs4 import BeautifulSoup
from django.conf import settings
from django.db import transaction
from pgvector.django import L2Distance

from sentence_transformers import SentenceTransformer
from langchain.document_loaders import TextLoader, DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document as LangchainDocument

from .models import DataSource, Document

class VectorRAGService:
    def __init__(self):
        # Initialize the embedding model
        self.embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        
        # Text splitter for chunking documents
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        )
    
    def generate_embedding(self, text):
        """Generate embedding for text"""
        embedding = self.embedding_model.encode(text, convert_to_tensor=False)
        return embedding.tolist()
    
    def ingest_github_repo(self, repo_url, repo_name=None):
        """Clone and ingest GitHub repository"""
        if not repo_name:
            repo_name = repo_url.split('/')[-1].replace('.git', '')
            
        temp_path = Path(settings.BASE_DIR) / 'temp' / repo_name
        
        # Clean up existing
        if temp_path.exists():
            shutil.rmtree(temp_path)
            
        try:
            # Create data source record
            data_source = DataSource.objects.create(
                name=repo_name,
                source_type='github',
                url=repo_url,
                status='processing',
                metadata={'repo_url': repo_url}
            )
            
            # Clone repository
            git.Repo.clone_from(repo_url, temp_path)
            
            # Load documents
            loader = DirectoryLoader(
                str(temp_path),
                glob="**/*.{py,js,ts,jsx,tsx,md,txt,rst,yml,yaml,json}",
                show_progress=False
            )
            documents = loader.load()
            
            # Process and store documents
            doc_count = 0
            with transaction.atomic():
                for doc in documents:
                    # Add metadata
                    doc.metadata.update({
                        "source_type": "github",
                        "repo_url": repo_url,
                        "repo_name": repo_name
                    })
                    
                    # Split document into chunks
                    chunks = self.text_splitter.split_documents([doc])
                    
                    for i, chunk in enumerate(chunks):
                        # Generate embedding
                        embedding = self.generate_embedding(chunk.page_content)
                        
                        # Store in database
                        Document.objects.create(
                            source=data_source,
                            content=chunk.page_content,
                            embedding=embedding,
                            metadata=chunk.metadata,
                            chunk_index=i
                        )
                        doc_count += 1
                
                # Update data source
                data_source.status = 'completed'
                data_source.document_count = doc_count
                data_source.save()
            
            # Cleanup
            shutil.rmtree(temp_path)
            
            return doc_count
            
        except Exception as e:
            if temp_path.exists():
                shutil.rmtree(temp_path)
            
            # Update status to failed
            if 'data_source' in locals():
                data_source.status = 'failed'
                data_source.save()
            
            raise e
    
    def ingest_web_documents(self, urls, name=None):
        """Scrape and ingest web documents"""
        if not name:
            name = f'Web docs ({len(urls)} URLs)'
            
        # Create data source record
        data_source = DataSource.objects.create(
            name=name,
            source_type='web',
            status='processing',
            metadata={'urls': urls}
        )
        
        try:
            documents = []
            
            for url in urls:
                try:
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Remove script and style elements
                    for script in soup(["script", "style"]):
                        script.decompose()
                    
                    text = soup.get_text()
                    
                    # Clean up text
                    lines = (line.strip() for line in text.splitlines())
                    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                    text = ' '.join(chunk for chunk in chunks if chunk)
                    
                    if text:
                        doc = LangchainDocument(
                            page_content=text,
                            metadata={
                                "source": url,
                                "source_type": "web"
                            }
                        )
                        documents.append(doc)
                        
                except Exception as e:
                    print(f"Error processing {url}: {e}")
                    continue
            
            # Process and store documents
            doc_count = 0
            with transaction.atomic():
                for doc in documents:
                    # Split document into chunks
                    chunks = self.text_splitter.split_documents([doc])
                    
                    for i, chunk in enumerate(chunks):
                        # Generate embedding
                        embedding = self.generate_embedding(chunk.page_content)
                        
                        # Store in database
                        Document.objects.create(
                            source=data_source,
                            content=chunk.page_content,
                            embedding=embedding,
                            metadata=chunk.metadata,
                            chunk_index=i
                        )
                        doc_count += 1
                
                # Update data source
                data_source.status = 'completed'
                data_source.document_count = doc_count
                data_source.save()
            
            return doc_count
            
        except Exception as e:
            # Update status to failed
            data_source.status = 'failed'
            data_source.save()
            raise e
    
    def search_documents(self, query, k=5, similarity_threshold=None):
        """Search for relevant documents using vector similarity"""
        if similarity_threshold is None:
            similarity_threshold = getattr(settings, 'SIMILARITY_THRESHOLD', 0.7)
        
        # Generate query embedding
        query_embedding = self.generate_embedding(query)
        
        # Search for similar documents using L2 distance
        documents = Document.objects.annotate(
            distance=L2Distance('embedding', query_embedding)
        ).filter(
            distance__lt=similarity_threshold
        ).order_by('distance')[:k]
        
        # Convert to langchain-like format for compatibility
        results = []
        for doc in documents:
            results.append(type('Document', (), {
                'page_content': doc.content,
                'metadata': {
                    **doc.metadata,
                    'source_id': doc.source.id,
                    'source_name': doc.source.name,
                    'distance': float(doc.distance),
                    'similarity_score': 1 - float(doc.distance)  # Convert distance to similarity
                }
            })())
        
        return results
    
    def generate_response(self, query):
        """Generate response using RAG"""
        # Get relevant documents
        docs = self.search_documents(query, k=3)
        
        if not docs:
            return "I don't have enough information in my knowledge base to answer that question. Please add some documents or repositories first."
        
        # Format context
        context_parts = []
        for i, doc in enumerate(docs):
            source_name = doc.metadata.get('source_name', 'Unknown source')
            source_type = doc.metadata.get('source_type', 'document')
            similarity = doc.metadata.get('similarity_score', 0)
            
            context_parts.append(
                f"[Source {i+1} - {source_type} ({source_name}) - Similarity: {similarity:.2f}]: {doc.page_content[:800]}"
            )
        
        context = "\n\n".join(context_parts)
        
        # Enhanced response generation
        response = f"""Based on the available documents, here's what I found relevant to your question:

{context}

**Summary**: The information above should help answer your question about: "{query}"

**Sources**: Found {len(docs)} relevant document sections from your knowledge base with similarity scores ranging from {min(doc.metadata.get('similarity_score', 0) for doc in docs):.2f} to {max(doc.metadata.get('similarity_score', 0) for doc in docs):.2f}."""
        
        return response
    
    def get_stats(self):
        """Get vector database statistics"""
        return {
            'total_documents': Document.objects.count(),
            'total_sources': DataSource.objects.count(),
            'documents_by_source': {
                source.name: source.documents.count() 
                for source in DataSource.objects.all()
            },
            'embedding_dimension': settings.VECTOR_DIMENSION
        }
    
    def delete_source_documents(self, source_id):
        """Delete all documents for a specific source"""
        try:
            source = DataSource.objects.get(id=source_id)
            deleted_count = source.documents.count()
            source.documents.all().delete()
            return deleted_count
        except DataSource.DoesNotExist:
            raise ValueError(f"Data source with id {source_id} not found")

# Global service instance
rag_service = VectorRAGService()
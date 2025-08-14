import os
import requests
import git
import shutil
from pathlib import Path
from bs4 import BeautifulSoup
from django.conf import settings

from langchain.document_loaders import TextLoader, DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
from langchain.schema import Document

class RAGService:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'}
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        )
        self.vectorstore_path = settings.VECTOR_STORE_PATH
        
    def get_vectorstore(self):
        """Get or create vector store"""
        if not os.path.exists(self.vectorstore_path):
            os.makedirs(self.vectorstore_path, exist_ok=True)
            
        try:
            return Chroma(
                persist_directory=str(self.vectorstore_path),
                embedding_function=self.embeddings
            )
        except:
            # Create new if doesn't exist
            return Chroma(
                persist_directory=str(self.vectorstore_path),
                embedding_function=self.embeddings
            )
    
    def ingest_github_repo(self, repo_url, repo_name=None):
        """Clone and ingest GitHub repository"""
        if not repo_name:
            repo_name = repo_url.split('/')[-1].replace('.git', '')
            
        temp_path = Path(settings.BASE_DIR) / 'temp' / repo_name
        
        # Clean up existing
        if temp_path.exists():
            shutil.rmtree(temp_path)
            
        try:
            # Clone repository
            git.Repo.clone_from(repo_url, temp_path)
            
            # Load documents
            loader = DirectoryLoader(
                str(temp_path),
                glob="**/*.{py,js,ts,jsx,tsx,md,txt,rst,yml,yaml,json}",
                show_progress=False
            )
            documents = loader.load()
            
            # Add metadata
            for doc in documents:
                doc.metadata.update({
                    "source_type": "github",
                    "repo_url": repo_url,
                    "repo_name": repo_name
                })
            
            # Process and store
            texts = self.text_splitter.split_documents(documents)
            vectorstore = self.get_vectorstore()
            vectorstore.add_documents(texts)
            vectorstore.persist()
            
            # Cleanup
            shutil.rmtree(temp_path)
            
            return len(documents)
            
        except Exception as e:
            if temp_path.exists():
                shutil.rmtree(temp_path)
            raise e
    
    def ingest_web_documents(self, urls):
        """Scrape and ingest web documents"""
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
                    doc = Document(
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
        
        if documents:
            texts = self.text_splitter.split_documents(documents)
            vectorstore = self.get_vectorstore()
            vectorstore.add_documents(texts)
            vectorstore.persist()
            
        return len(documents)
    
    def search_documents(self, query, k=3):
        """Search for relevant documents"""
        vectorstore = self.get_vectorstore()
        docs = vectorstore.similarity_search(query, k=k)
        return docs
    
    def generate_response(self, query):
        """Generate response using RAG"""
        # Get relevant documents
        docs = self.search_documents(query, k=3)
        
        if not docs:
            return "I don't have enough information in my knowledge base to answer that question. Please add some documents or repositories first."
        
        # Format context
        context_parts = []
        for i, doc in enumerate(docs):
            source_info = doc.metadata.get('source', 'Unknown source')
            source_type = doc.metadata.get('source_type', 'document')
            
            context_parts.append(
                f"[Source {i+1} - {source_type}]: {doc.page_content[:800]}"
            )
        
        context = "\n\n".join(context_parts)
        
        # Simple response generation (can be enhanced with actual LLM)
        response = f"""Based on the available documents, here's what I found relevant to your question:

{context}

**Summary**: The information above should help answer your question about: "{query}"

**Sources**: Found {len(docs)} relevant document sections from your knowledge base."""
        
        return response

# Global service instance
rag_service = RAGService()
"""
Knowledge Base - Local Document Store
========================================
Loads and indexes user documents for RAG.

Sprint 7: Gap Fixes - Knowledge Grounding
"""

import os
import json
import hashlib
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Document:
    """A document in the knowledge base."""
    doc_id: str
    title: str
    content: str
    source_path: str
    doc_type: str  # txt, md, pdf
    chunks: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


@dataclass
class Chunk:
    """A chunk of text for retrieval."""
    chunk_id: str
    doc_id: str
    content: str
    index: int
    embedding: Optional[List[float]] = None


class KnowledgeBase:
    """
    Local document store for knowledge grounding.
    
    Features:
    - Load txt, md files
    - Chunk documents
    - Simple keyword search (no embedding yet)
    - Persistent index
    """
    
    CHUNK_SIZE = 500  # characters
    CHUNK_OVERLAP = 50
    
    def __init__(self, knowledge_dir: Path = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parent.parent / "data" / "knowledge"
        
        self.knowledge_dir = Path(knowledge_dir)
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        
        self._documents: Dict[str, Document] = {}
        self._chunks: Dict[str, Chunk] = {}
        self._index_file = self.knowledge_dir / "index.json"
        
        self._load_index()
    
    def _load_index(self):
        """Load existing index."""
        if not self._index_file.exists():
            return
        
        try:
            with open(self._index_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for doc_data in data.get("documents", []):
                doc = Document(**doc_data)
                self._documents[doc.doc_id] = doc
            
            print(f"[KnowledgeBase] Loaded {len(self._documents)} documents")
            
        except Exception as e:
            print(f"[KnowledgeBase] Load error: {e}")
    
    def _save_index(self):
        """Save index to disk."""
        try:
            data = {
                "documents": [
                    {
                        "doc_id": d.doc_id,
                        "title": d.title,
                        "content": d.content[:200],  # Summary only
                        "source_path": d.source_path,
                        "doc_type": d.doc_type,
                        "chunks": d.chunks,
                        "metadata": d.metadata
                    }
                    for d in self._documents.values()
                ]
            }
            
            with open(self._index_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            print(f"[KnowledgeBase] Save error: {e}")
    
    def add_document(self, file_path: str, title: str = None) -> Optional[Document]:
        """
        Add a document to the knowledge base.
        
        Args:
            file_path: Path to document file
            title: Optional title (uses filename if not provided)
            
        Returns:
            Created Document or None
        """
        path = Path(file_path)
        
        if not path.exists():
            print(f"[KnowledgeBase] File not found: {file_path}")
            return None
        
        # Determine type
        ext = path.suffix.lower()
        if ext not in ['.txt', '.md', '.markdown']:
            print(f"[KnowledgeBase] Unsupported format: {ext}")
            return None
        
        # Read content
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            print(f"[KnowledgeBase] Read error: {e}")
            return None
        
        # Create document
        doc_id = hashlib.md5(str(path).encode()).hexdigest()[:12]
        
        doc = Document(
            doc_id=doc_id,
            title=title or path.stem,
            content=content,
            source_path=str(path),
            doc_type=ext[1:],
            metadata={"size": len(content), "added": True}
        )
        
        # Chunk document
        doc.chunks = self._chunk_text(content)
        
        self._documents[doc_id] = doc
        self._save_index()
        
        print(f"[KnowledgeBase] Added: {doc.title} ({len(doc.chunks)} chunks)")
        return doc

    def add_content(self, content: str, title: str, source: str = "memory", metadata: Dict = None) -> Optional[Document]:
        """
        Add content directly to knowledge base.
        """
        doc_id = hashlib.md5(content.encode()).hexdigest()[:12]
        
        doc = Document(
            doc_id=doc_id,
            title=title,
            content=content,
            source_path=source,
            doc_type="text",
            metadata=metadata or {}
        )
        
        # Chunk document
        doc.chunks = self._chunk_text(content)
        
        self._documents[doc_id] = doc
        self._save_index()
        
        print(f"[KnowledgeBase] Added content: {doc.title}")
        return doc
    
    def add_directory(self, dir_path: str, recursive: bool = True) -> int:
        """
        Add all documents from a directory.
        
        Returns:
            Number of documents added
        """
        path = Path(dir_path)
        if not path.exists():
            return 0
        
        count = 0
        pattern = "**/*" if recursive else "*"
        
        for file_path in path.glob(pattern):
            if file_path.suffix.lower() in ['.txt', '.md', '.markdown']:
                if self.add_document(str(file_path)):
                    count += 1
        
        return count
    
    def _chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks."""
        if len(text) <= self.CHUNK_SIZE:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.CHUNK_SIZE
            
            # Try to break at sentence boundary
            if end < len(text):
                for sep in ['. ', '.\n', '\n\n', '\n', ' ']:
                    pos = text.rfind(sep, start + 100, end)
                    if pos > start:
                        end = pos + len(sep)
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - self.CHUNK_OVERLAP
        
        return chunks
    
    def search(self, query: str, top_k: int = 3) -> List[Tuple[str, float, str]]:
        """
        Search for relevant chunks.
        
        Args:
            query: Search query
            top_k: Number of results
            
        Returns:
            List of (chunk_text, score, doc_title)
        """
        query_terms = set(query.lower().split())
        results = []
        
        for doc in self._documents.values():
            for chunk in doc.chunks:
                chunk_lower = chunk.lower()
                
                # Simple keyword matching
                matches = sum(1 for term in query_terms if term in chunk_lower)
                
                if matches > 0:
                    score = matches / len(query_terms)
                    results.append((chunk, score, doc.title))
        
        # Sort by score
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:top_k]
    
    def get_context(self, query: str, max_chars: int = 1500) -> str:
        """
        Get context for LLM prompt.
        
        Args:
            query: User query
            max_chars: Maximum context length
            
        Returns:
            Formatted context string
        """
        results = self.search(query, top_k=5)
        
        if not results:
            return ""
        
        context_parts = []
        total_chars = 0
        
        for chunk, score, title in results:
            if total_chars + len(chunk) > max_chars:
                break
            
            context_parts.append(f"[From: {title}]\n{chunk}")
            total_chars += len(chunk)
        
        return "\n\n".join(context_parts)
    
    def list_documents(self) -> List[Dict]:
        """List all documents."""
        return [
            {
                "doc_id": d.doc_id,
                "title": d.title,
                "chunks": len(d.chunks),
                "type": d.doc_type
            }
            for d in self._documents.values()
        ]
    
    def remove_document(self, doc_id: str) -> bool:
        """Remove a document."""
        if doc_id in self._documents:
            del self._documents[doc_id]
            self._save_index()
            return True
        return False


def test_knowledge_base():
    """Test knowledge base."""
    print("Knowledge Base Test")
    print("=" * 50)
    
    kb = KnowledgeBase()
    
    # Create test document
    test_file = Path(__file__).parent.parent / "data" / "knowledge" / "test.txt"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(test_file, 'w') as f:
        f.write("""
        Anasarca is a medical term for severe, generalized edema.
        It is characterized by widespread swelling of the skin due to 
        effusion of fluid into the extracellular space.
        
        Common causes include heart failure, kidney disease, and liver disease.
        Treatment depends on the underlying cause.
        """)
    
    # Add document
    kb.add_document(str(test_file), "Medical Terms")
    
    # Search
    results = kb.search("anasarca edema")
    print(f"Search results: {len(results)}")
    for chunk, score, title in results:
        print(f"  [{score:.2f}] {title}: {chunk[:50]}...")
    
    # Get context
    context = kb.get_context("What is anasarca?")
    print(f"\nContext:\n{context[:200]}...")
    
    # List
    print(f"\nDocuments: {kb.list_documents()}")


if __name__ == "__main__":
    test_knowledge_base()

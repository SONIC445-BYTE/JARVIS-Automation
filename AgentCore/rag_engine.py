"""
RAG Engine - Retrieval Augmented Generation
=============================================
Grounds LLM responses in user's knowledge.

Sprint 7: Gap Fixes - Knowledge Grounding
"""

from typing import Optional, Dict, List
from pathlib import Path

from .knowledge_base import KnowledgeBase
from .llm_engine import LLMEngine, LLMResponse
from .prompt_templates import PromptTemplates


class RAGEngine:
    """
    Retrieval-Augmented Generation for grounded answers.
    
    Flow:
    1. User query
    2. Search knowledge base
    3. Inject context into prompt
    4. Generate grounded response
    """
    
    RAG_TEMPLATE = """You are JARVIS. Use the following context to answer the question.
If the context doesn't contain the answer, say so and provide general knowledge.

CONTEXT:
{context}

QUESTION: {question}

ANSWER (be concise):"""

    NO_CONTEXT_TEMPLATE = """You are JARVIS. Answer this question briefly.

QUESTION: {question}

ANSWER:"""
    
    def __init__(self, knowledge_dir: Path = None):
        self.kb = KnowledgeBase(knowledge_dir)
        self.llm = LLMEngine()
        
        print(f"[RAGEngine] Initialized")
        print(f"[RAGEngine] Knowledge docs: {len(self.kb.list_documents())}")
        print(f"[RAGEngine] LLM available: {self.llm.is_available()}")
    
    def query(self, question: str, use_rag: bool = True) -> LLMResponse:
        """
        Answer a question with optional RAG (Local + Wikipedia).
        """
        context = ""
        source = "general knowledge"
        
        if use_rag:
            # 1. Try Local Knowledge Base
            context = self.kb.get_context(question)
            if context:
                source = "local knowledge"
            
            # 2. Live Knowledge Acquisition (Sprint 6.2)
            # Check if time-sensitive
            try:
                from .knowledge_classifier import is_time_sensitive
                if not context and is_time_sensitive(question):
                    from .knowledge import resolve_knowledge
                    
                    print(f"[RAGEngine] Time-sensitive query detected: '{question}'")
                    bundle = resolve_knowledge(question)
                    
                    if bundle.get("verdict") in ["CONFIRMED", "UNCERTAIN"]:
                        # Format context from bundle
                        parts = ["VERIFIED FACTS:"]
                        for src in bundle.get("sources", []):
                            parts.append(f"- {src.get('snippet')} (Source: {src.get('source')} - {src.get('url')})")
                        
                        context = "\n".join(parts)
                        source = f"Live Knowledge ({bundle.get('verdict')})"
            except Exception as e:
                print(f"[RAGEngine] Knowledge Error: {e}")
                # Fallback to Wikipedia (Legacy Sprint 6.1)
                if not context:
                   try:
                       import wikipedia
                       results = wikipedia.search(question, results=1)
                       if results:
                           context = wikipedia.summary(results[0], sentences=5)
                           source = f"Wikipedia/Fallback ({results[0]})"
                   except: 
                       pass
        
        if context:
            prompt = self.RAG_TEMPLATE.format(
                context=context,
                question=question
            )
            print(f"[RAGEngine] Using {source} ({len(context)} chars)")
        else:
            prompt = self.NO_CONTEXT_TEMPLATE.format(question=question)
            print("[RAGEngine] No relevant context found, using general knowledge")
        
        response = self.llm.generate(prompt, max_tokens=200)
        
        return response
    
    def add_knowledge(self, file_path: str, title: str = None) -> bool:
        """Add a document to knowledge base."""
        doc = self.kb.add_document(file_path, title)
        return doc is not None
    
    def add_knowledge_dir(self, dir_path: str) -> int:
        """Add all documents from directory."""
        return self.kb.add_directory(dir_path)
    
    def search_knowledge(self, query: str) -> List[Dict]:
        """Search knowledge base without LLM."""
        results = self.kb.search(query, top_k=5)
        return [
            {"text": text[:200], "score": score, "source": title}
            for text, score, title in results
        ]
    
    def list_knowledge(self) -> List[Dict]:
        """List all knowledge documents."""
        return self.kb.list_documents()
    
    def explain_with_knowledge(self, topic: str) -> str:
        """Get explanation grounded in knowledge base."""
        response = self.query(f"Explain {topic}")
        return response.text


def test_rag_engine():
    """Test RAG engine."""
    print("RAG Engine Test")
    print("=" * 50)
    
    rag = RAGEngine()
    
    # Create test knowledge
    test_file = Path(__file__).parent.parent / "data" / "knowledge" / "medical.txt"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(test_file, 'w') as f:
        f.write("""
        Anasarca is severe generalized edema with subcutaneous tissue swelling.
        
        Causes include:
        - Congestive heart failure
        - Liver cirrhosis
        - Nephrotic syndrome
        - Severe malnutrition
        
        Treatment focuses on the underlying cause and may include diuretics.
        """)
    
    rag.add_knowledge(str(test_file), "Medical Reference")
    
    # Test query
    print("\nQuery: What is anasarca?")
    response = rag.query("What is anasarca?")
    print(f"Answer: {response.text}")
    print(f"Tokens: {response.tokens_used}")
    
    # Search
    print("\nSearch: edema causes")
    results = rag.search_knowledge("edema causes")
    for r in results:
        print(f"  [{r['score']:.2f}] {r['source']}: {r['text'][:50]}...")


if __name__ == "__main__":
    test_rag_engine()

import faiss
from sentence_transformers import SentenceTransformer
import numpy as np

class SchemaRetriever:
    def __init__(self):
        # Ultra-fast, lightweight embedding model (runs on CPU)
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.index = None
        self.documents = []
        
    def build_index(self, schemas: dict, json_rules: list = None):
        """
        Embeds the database schemas and business rules, storing them in FAISS.
        """
        if json_rules is None:
            json_rules = []
            
        # Combine table schemas and structured JSON rules into the vector store
        self.documents = list(schemas.values()) + [str(rule) for rule in json_rules]
        
        print(f"Embedding {len(self.documents)} documents into vector memory...")
        embeddings = self.embedder.encode(self.documents)
        
        # L2 distance FAISS index
        self.index = faiss.IndexFlatL2(embeddings.shape[1])
        self.index.add(np.array(embeddings))
        print("FAISS Index successfully built.")
        
    def retrieve_context(self, question: str, top_k: int = 5) -> str:
        """
        Retrieves the top_k most relevant tables/rules for a given question.
        """
        if not self.index:
            raise ValueError("FAISS Index is empty. Call build_index first.")
            
        question_emb = self.embedder.encode([question])
        distances, indices = self.index.search(np.array(question_emb), top_k)
        
        # Retrieve the text for the matched indices
        retrieved_docs = [self.documents[idx] for idx in indices[0]]
        return "\n\n".join(retrieved_docs)

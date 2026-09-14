## Goal Description
This document is the ultimate, master architectural blueprint for the **Bane Text-to-SQL Agent**. It details a complete, enterprise-grade pipeline spanning from zero-friction user onboarding to highly optimized cloud deployment.

The architecture solves three major enterprise AI challenges:
1.  **The Onboarding Problem:** Uses a Database Introspector and a Two-Agent Semantic Enrichment layer to automatically learn and structure messy user business logic.
2.  **The Context Problem:** Uses a FAISS Vector Database to dynamically retrieve schemas via Retrieval-Augmented Generation (RAG).
3.  **The Hallucination Problem:** Aligns the LLaMA-3 model against an Execution-Feedback Sandbox using Direct Preference Optimization (DPO).

## System Architecture

```mermaid
flowchart TD
    subgraph 1. Onboarding & Semantic Enrichment (The Middleman)
        A[(User's Database)] -->|db_introspector.py| B(Extract CREATE TABLEs)
        C[User's Messy Business Logic] --> D{Enrichment Agent\nLlama-3.2-1B CPU}
        D -->|Standardized JSON Rules| E[Semantic Dictionary]
        B --> F(all-MiniLM Embedder)
        E --> F
    end

    subgraph 2. Schema RAG (Context Optimization)
        F --> G[(FAISS Vector DB)]
        H[User Question] -->|Embed| G
        G -->|Retrieve Top Tables + JSON Rules| I[prompt_builder.py]
    end

    subgraph 3. Agentic Data Generation & Training
        I --> J{LLaMA-3-8B Base}
        J -->|Predicted SQL| K[execution_validator.py Sandbox]
        K -->|Matches Ground Truth| L[Label: Chosen]
        K -->|Error / Mismatch| M[Label: Rejected]
        L --> N[(Preference Dataset)]
        M --> N
    end

    subgraph 4. DPO Alignment & Deployment
        N --> O(Unsloth DPOTrainer\nKaggle GPU)
        O -->|Fine-Tuned Weights| P[GGUF Export]
        P --> Q[FastAPI Backend\nDigitalOcean CPU Droplet]
        Q <-->|JSON Requests| R(Typer CLI Tool)
    end
```

## The 100% Free Tech Stack & Compute Limits
This entire architecture is built to cost **$0.00** by strictly adhering to the compute limits of the GitHub Student Developer Pack and open-source tools:

*   **Compute (Development): GitHub Codespaces.** Provides a browser-based VS Code environment with high-memory CPUs. (Limit: 90 free hours/month). We run the lightweight `Llama-3.2-1B` model here for Semantic Enrichment, as it runs blazingly fast on CPUs without eating into GPU limits.
*   **Compute (Training): Kaggle Notebooks.** Provides the heavy NVIDIA T4 GPUs needed to train the massive 8B parameter model. (Limit: 30 hours of free GPU time/week).
*   **Deployment (API): DigitalOcean / Azure.** Provides cloud credits (Limit: ~$100-$200). To prevent draining these credits on expensive GPU hosting, we export the final trained adapters to **GGUF format**. This allows the FastAPI server to run efficiently on a cheap, standard CPU droplet.
*   **Vector Database & Embeddings:** Meta FAISS and `all-MiniLM-L6-v2`. Both run completely locally in RAM/CPU, replacing paid APIs like Pinecone or OpenAI.
*   **Client Interface:** Python **Typer** and **Rich** for the CLI, connecting to a free **Namecheap** `.me` domain.

## How the Agent Works: Detailed Execution Flow
1. **Zero-Friction Initialization (`db_introspector.py`):** The Python CLI queries the internal `sqlite_master` table to programmatically extract every `CREATE TABLE` definition, avoiding any manual data entry.
2. **Semantic Standardization (`semantic_enrichment_agent.py`):** The user provides an unstructured YAML dictionary of company acronyms. A lightweight local **Ollama (1B)** instance translates the messy English into highly structured JSON rules.
3. **Context Indexing (`schema_rag.py`):** The extracted schemas and JSON rules are passed through the **MiniLM** embedding model and injected into a **FAISS** vector database. 
4. **Agentic Data Generation & Execution Feedback (`execution_validator.py`):** The base model predicts SQL based on the retrieved schema. The prediction is executed inside a live SQLite sandbox. Crashes are `Rejected`. Successes are `Chosen`.
5. **Direct Preference Optimization (`Bane_Final_Training.ipynb`):** The 10,000+ generated pairs are fed into HuggingFace's **TRL DPOTrainer** via **Unsloth** on Kaggle GPUs to severely penalize hallucinated columns.
6. **Cloud Deployment (`api.py` & `cli.py`):** The final adapters are exported to **GGUF** and wrapped in a **FastAPI** server on a **DigitalOcean CPU Droplet**. The end-user types `bane query "Show me sales"` in their terminal. The CLI hits the API, the FAISS index retrieves the tables, the API generates the SQL on the CPU, and the CLI executes it locally.

## Proposed Changes (The Core Codebase)

### [NEW] `src/db_introspector.py`
```python
import sqlite3
class DatabaseIntrospector:
    def __init__(self, db_path: str):
        self.db_path = db_path
    def extract_schemas(self):
        conn = sqlite3.connect(self.db_path)
        tables = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL;").fetchall()
        conn.close()
        return {name: sql for name, sql in tables}
```

### [NEW] `src/semantic_enrichment_agent.py`
```python
import json
import requests

def enrich_business_logic(messy_user_text: str) -> dict:
    prompt = f"Convert to JSON: {{'metric': str, 'sql_constraints': list[str]}}. Input: {messy_user_text}"
    response = requests.post("http://localhost:11434/api/generate", json={
        "model": "llama3.2:1b", # Ultra-lightweight CPU model
        "prompt": prompt,
        "stream": False,
        "format": "json"
    })
    return json.loads(response.json()["response"])
```

### [MODIFY] `src/schema_rag.py`
```python
import faiss
from sentence_transformers import SentenceTransformer
import numpy as np

class SchemaRetriever:
    def __init__(self):
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.index = None
        self.documents = []
        
    def build_index(self, schemas: dict, json_rules: list[dict]):
        self.documents = list(schemas.values()) + [str(rule) for rule in json_rules]
        embeddings = self.embedder.encode(self.documents)
        self.index = faiss.IndexFlatL2(embeddings.shape[1])
        self.index.add(np.array(embeddings))
```

### [NEW] `notebooks/Bane_Final_Training.ipynb`
```python
from unsloth import FastLanguageModel
from trl import DPOTrainer, DPOConfig

# Train on Kaggle GPU
model, tokenizer = FastLanguageModel.from_pretrained("unsloth/llama-3-8b-Instruct", load_in_4bit=True)
model = FastLanguageModel.get_peft_model(model, r=16, target_modules=["q_proj", "v_proj"])

trainer = DPOTrainer(model=model, tokenizer=tokenizer, train_dataset=dataset, args=DPOConfig(output_dir="outputs"))
trainer.train()

# Export to GGUF for DigitalOcean CPU Deployment
model.save_pretrained_gguf("bane_model", tokenizer, quantization_method = "q4_k_m")
```

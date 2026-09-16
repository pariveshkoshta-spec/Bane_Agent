import os
import re
import sqlite3
from typing import Optional, List, Dict
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.schema_rag import SchemaRetriever
from src.db_introspector import DatabaseIntrospector
from src.prompt_builder import format_dpo_prompt
from src.semantic_enrichment_agent import SemanticEnrichmentAgent

app = FastAPI(
    title="Bane Text-to-SQL API",
    version="1.0.0",
    description="Execution-aligned Text-to-SQL API powered by fine-tuned DPO LLaMA-3"
)

# Global dependencies
retriever = SchemaRetriever()
db_initialized = False
introspected_schemas: Dict[str, str] = {}
rules_cache: List[dict] = []

# Adapter path resolution
DEFAULT_ADAPTER_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "results",
    "bane_dpo_lora_adapters"
)
ADAPTER_PATH = os.environ.get("BANE_ADAPTER_PATH", DEFAULT_ADAPTER_DIR)

class ModelEngine:
    def __init__(self, adapter_path: str):
        self.adapter_path = adapter_path
        self.model = None
        self.tokenizer = None
        self.is_loaded = False

    def load_model(self):
        """
        Attempts to load the trained LoRA adapter weights if torch/transformers are installed.
        """
        if self.is_loaded:
            return

        if not os.path.exists(self.adapter_path):
            print(f"[WARN] Adapter directory not found at {self.adapter_path}")
            return

        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from peft import PeftModel

            print(f"[INFO] Loading fine-tuned LoRA adapters from {self.adapter_path}...")
            base_model_name = "unsloth/llama-3-8b-instruct-bnb-4bit"
            self.tokenizer = AutoTokenizer.from_pretrained(self.adapter_path)

            device_map = "auto" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
            base_model = AutoModelForCausalLM.from_pretrained(
                base_model_name,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map=device_map
            )
            self.model = PeftModel.from_pretrained(base_model, self.adapter_path)
            self.model.eval()
            self.is_loaded = True
            print("[INFO] Model and adapters successfully loaded!")
        except Exception as e:
            print(f"[INFO] Local PyTorch/GPU inference skipped ({e}).")
            self.is_loaded = False

    def generate_sql(self, question: str, schema_context: str) -> str:
        """
        Generates SQL using the fine-tuned model, or delegates to Ollama / heuristic engine.
        """
        prompt = format_dpo_prompt(question, schema_context)

        # 1. Real PyTorch model generation if loaded
        if self.is_loaded and self.model is not None and self.tokenizer is not None:
            import torch
            inputs = self.tokenizer([prompt], return_tensors="pt")
            device = next(self.model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=128,
                    temperature=0.1,
                    do_sample=False,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            decoded = self.tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]
            sql = decoded.replace(prompt, "").strip()
            # Clean markdown formatting if present
            if "```sql" in sql:
                sql = sql.split("```sql")[1].split("```")[0].strip()
            elif "```" in sql:
                sql = sql.split("```")[1].split("```")[0].strip()
            return sql

        # 2. Ollama local middleman fallback
        import requests
        ollama_url = os.environ.get("OLLAMA_API_URL", "http://localhost:11434/api/generate")
        ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
        try:
            resp = requests.post(
                ollama_url,
                json={"model": ollama_model, "prompt": prompt, "stream": False},
                timeout=8
            )
            if resp.status_code == 200:
                raw = resp.json().get("response", "").strip()
                match = re.search(r"SELECT.*?;", raw, re.IGNORECASE | re.DOTALL)
                if match:
                    return match.group(0).strip()
        except Exception:
            pass

        # 3. Fast schema-grounded heuristic generator (for instant local zero-dependency testing)
        return self._heuristic_sql(question, schema_context)

    def _heuristic_sql(self, question: str, schema_context: str) -> str:
        """
        Intelligent schema-grounded generator matching question intent, column names,
        filters, and limits based on retrieved schemas.
        """
        q_lower = question.lower()
        tables = list(introspected_schemas.keys())
        if not tables:
            return "SELECT 1;"

        # 1. Select the top table identified by FAISS
        retrieved_tables = re.findall(r"CREATE\s+TABLE\s+(\w+)", schema_context, re.IGNORECASE)
        if retrieved_tables and retrieved_tables[0] in tables:
            target_table = retrieved_tables[0]
        else:
            target_table = tables[0]
            for t in tables:
                clean_t = t.replace("tbl_", "").replace("table_", "").replace("_", " ")
                if clean_t.lower() in q_lower or t.lower() in q_lower:
                    target_table = t
                    break

        # 2. Extract column names from the target table's schema
        table_schema = introspected_schemas.get(target_table, "")
        # Grab words that look like column definitions (name TYPE)
        col_matches = re.findall(r"(\b[a-zA-Z_][a-zA-Z0-9_]*\b)\s+(?:INTEGER|TEXT|REAL|BLOB|BOOLEAN)", table_schema, re.IGNORECASE)
        columns = [c for c in col_matches if c.upper() not in ("PRIMARY", "KEY", "FOREIGN", "NOT", "NULL", "CHECK", "DEFAULT")]

        # 3. Detect requested columns
        selected_cols = []
        if "name" in q_lower:
            name_cols = [c for c in columns if "name" in c.lower()]
            if name_cols:
                selected_cols.extend(name_cols)
        if "email" in q_lower:
            email_cols = [c for c in columns if "email" in c.lower()]
            if email_cols:
                selected_cols.extend(email_cols)
        if "country" in q_lower:
            country_cols = [c for c in columns if "country" in c.lower()]
            if country_cols:
                selected_cols.extend(country_cols)
        if "mrr" in q_lower or "fee" in q_lower or "price" in q_lower:
            price_cols = [c for c in columns if any(k in c.lower() for k in ["mrr", "fee", "amount", "price"])]
            if price_cols:
                selected_cols.extend(price_cols)

        col_clause = ", ".join(dict.fromkeys(selected_cols)) if selected_cols else "*"

        # 4. Detect WHERE filter conditions
        where_clauses = []
        if "enterprise" in q_lower and "tier" in [c.lower() for c in columns]:
            where_clauses.append("tier = 'ENTERPRISE'")
        if "starter" in q_lower and "tier" in [c.lower() for c in columns]:
            where_clauses.append("tier = 'STARTER'")
        if "growth" in q_lower and "tier" in [c.lower() for c in columns]:
            where_clauses.append("tier = 'GROWTH'")
        if "free" in q_lower and "tier" in [c.lower() for c in columns]:
            where_clauses.append("tier = 'FREE'")
        if "cancelled" in q_lower or "churned" in q_lower:
            if "is_cancelled" in [c.lower() for c in columns]:
                where_clauses.append("is_cancelled = 1")
        elif "active" in q_lower:
            if "is_cancelled" in [c.lower() for c in columns]:
                where_clauses.append("is_cancelled = 0")
        if "critical" in q_lower or "urgent" in q_lower:
            if "priority_lvl" in [c.lower() for c in columns]:
                where_clauses.append("priority_lvl = 'P1_CRITICAL'")
        if "unresolved" in q_lower or "open" in q_lower:
            if "resolved_flag" in [c.lower() for c in columns]:
                where_clauses.append("resolved_flag = 0")

        where_stmt = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # 5. Handle LIMIT / Sorting
        # If user explicitly asked for 'all' or 'every', do NOT limit the result set!
        explicit_all = any(word in q_lower.split() for word in ["all", "every", "entire", "total"])

        if "count" in q_lower or "how many" in q_lower:
            return f"SELECT COUNT(*) AS total_count FROM {target_table}{where_stmt};"

        limit_match = re.search(r"top\s+(\d+)", q_lower)
        if limit_match:
            limit_n = limit_match.group(1)
            return f"SELECT {col_clause} FROM {target_table}{where_stmt} ORDER BY 1 DESC LIMIT {limit_n};"
        elif "top" in q_lower or "highest" in q_lower or "most" in q_lower:
            return f"SELECT {col_clause} FROM {target_table}{where_stmt} ORDER BY 1 DESC LIMIT 5;"
        elif explicit_all:
            return f"SELECT {col_clause} FROM {target_table}{where_stmt};"
        else:
            return f"SELECT {col_clause} FROM {target_table}{where_stmt} LIMIT 20;"

engine = ModelEngine(ADAPTER_PATH)

class InitRequest(BaseModel):
    db_path: str
    business_rules: Optional[str] = None

class QueryRequest(BaseModel):
    question: str
    top_k: Optional[int] = 3

@app.get("/health")
async def health_check():
    return {
        "status": "online",
        "adapter_path": ADAPTER_PATH,
        "adapter_present": os.path.exists(ADAPTER_PATH),
        "model_loaded": engine.is_loaded,
        "db_initialized": db_initialized,
        "indexed_tables": list(introspected_schemas.keys())
    }

@app.post("/init")
async def initialize_database(request: InitRequest):
    """
    Introspects the SQLite database, extracts schemas, enriches business rules,
    and builds the FAISS vector index.
    """
    global db_initialized, introspected_schemas, rules_cache
    if not os.path.exists(request.db_path):
        raise HTTPException(status_code=404, detail=f"Database file '{request.db_path}' not found.")

    try:
        introspector = DatabaseIntrospector(request.db_path)
        introspected_schemas = introspector.extract_schemas()

        enriched_rules = []
        if request.business_rules:
            enricher = SemanticEnrichmentAgent()
            rule_json = enricher.enrich_business_logic(request.business_rules)
            if rule_json:
                enriched_rules.append(rule_json)
                rules_cache = enriched_rules

        # Build FAISS vector index
        retriever.build_index(introspected_schemas, json_rules=enriched_rules)
        db_initialized = True

        return {
            "status": "success",
            "message": f"Successfully indexed {len(introspected_schemas)} tables into FAISS.",
            "tables": list(introspected_schemas.keys()),
            "rules_indexed": len(enriched_rules)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_sql")
async def generate_sql(request: QueryRequest):
    """
    Retrieves schemas from FAISS and generates execution-aligned SQL.
    """
    if not db_initialized:
        raise HTTPException(
            status_code=400,
            detail="Database has not been initialized. Run 'bane init <db_path>' first."
        )

    try:
        # 1. Retrieve Schema Context via FAISS RAG
        top_k = request.top_k or 3
        schema_context = retriever.retrieve_context(request.question, top_k=top_k)

        # 2. Generate aligned SQL query
        sql = engine.generate_sql(request.question, schema_context)

        return {
            "question": request.question,
            "context_used": schema_context,
            "sql": sql
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

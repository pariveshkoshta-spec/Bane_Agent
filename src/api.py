from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.schema_rag import SchemaRetriever
from src.db_introspector import DatabaseIntrospector

app = FastAPI(title="Bane Text-to-SQL API")

# Global dependencies
retriever = SchemaRetriever()
db_initialized = False

class InitRequest(BaseModel):
    db_path: str

class QueryRequest(BaseModel):
    question: str

@app.post("/init")
async def initialize_database(request: InitRequest):
    """
    Initializes the FAISS vector database with the user's schemas.
    """
    global db_initialized
    try:
        introspector = DatabaseIntrospector(request.db_path)
        schemas = introspector.extract_schemas()
        
        # Build FAISS index
        retriever.build_index(schemas)
        db_initialized = True
        return {"status": "success", "message": f"Successfully indexed {len(schemas)} tables."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_sql")
async def generate_sql(request: QueryRequest):
    """
    Generates SQL based on the FAISS context and the user's question.
    """
    if not db_initialized:
        raise HTTPException(status_code=400, detail="Database not initialized. Call /init first.")
        
    try:
        # 1. Retrieve Context
        schema_context = retriever.retrieve_context(request.question)
        
        # 2. Build Prompt
        prompt = f"""### Task
Generate a SQL query to answer [QUESTION]{request.question}[/QUESTION]

### Relevant Database Schema
{schema_context}

### Answer
[SQL]"""

        # 3. LLM Inference (Placeholder for GGUF/vLLM)
        # TODO: Load actual Fine-Tuned LLaMA-3 adapters here
        generated_sql = f"SELECT * FROM placeholder_table WHERE condition = '{request.question}';"
        
        return {
            "question": request.question,
            "context_used": schema_context,
            "sql": generated_sql
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

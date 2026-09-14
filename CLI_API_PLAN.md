## Goal Description
To elevate the Bane Agent from a "research script" to a fully usable, production-ready software product, we will wrap the trained model in a **REST API (FastAPI)** and build a **Command-Line Interface (CLI)**. 

This mirrors exactly how enterprise AI companies (like Defog) package their tools. It allows users to query their databases instantly from their terminal without writing Python code.

## User Review Required
> [!NOTE] Deployment Environment
> Running the API and CLI will require downloading the trained model weights to a machine with a GPU, or hosting the API on a cloud provider (like AWS/GCP) while running the CLI locally on your Mac.

## Proposed Changes

### 1. The FastAPI Backend Layer
We will build a high-performance REST API that loads the FAISS index and the Fine-Tuned LLaMA-3 adapters into memory once, and keeps them warm to answer queries in milliseconds.
#### [NEW] `Bane_Agent/src/api.py`
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from unsloth import FastLanguageModel
from src.schema_rag import SchemaRetriever

app = FastAPI(title="Bane Text-to-SQL API")

# Load model and FAISS globally on startup
model, tokenizer = FastLanguageModel.from_pretrained("bane_dpo_lora_adapters", load_in_4bit=True)
FastLanguageModel.for_inference(model)
retriever = SchemaRetriever() # Assuming index is already built

class QueryRequest(BaseModel):
    question: str
    db_name: str

@app.post("/generate_sql")
async def generate_sql(request: QueryRequest):
    try:
        # 1. Retrieve relevant tables using RAG
        schema = retriever.retrieve_relevant_tables(request.question)
        
        # 2. Format Prompt
        prompt = f"### Schema:\n{schema}\n\n### Question:\n{request.question}\n\n### SQL:\n"
        
        # 3. Generate Inference
        inputs = tokenizer([prompt], return_tensors="pt").to("cuda")
        outputs = model.generate(**inputs, max_new_tokens=64)
        sql_query = tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]
        
        return {"question": request.question, "sql": sql_query.replace(prompt, "").strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 2. The Command-Line Interface (CLI)
We will use the modern Python `Typer` library to build a beautiful CLI. A user on your Mac can simply open their terminal and type `bane query "how many users?"`.
#### [NEW] `Bane_Agent/cli.py`
```python
import typer
import requests
import sqlite3
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Bane: Execution-Aligned Text-to-SQL CLI")
console = Console()

API_URL = "http://localhost:8000/generate_sql"

@app.command()
def query(question: str, db_path: str = typer.Option(..., help="Path to your local SQLite .db file")):
    """
    Ask a natural language question and execute it against a local database.
    """
    console.print(f"[bold blue]Thinking... Asking Bane:[/bold blue] '{question}'")
    
    # 1. Call the FastAPI backend
    response = requests.post(API_URL, json={"question": question, "db_name": db_path})
    
    if response.status_code == 200:
        sql = response.json()["sql"]
        console.print(f"[bold green]Generated SQL:[/bold green] {sql}\n")
        
        # 2. Execute the returned SQL locally
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(sql)
            results = cursor.fetchall()
            
            # Print results beautifully
            table = Table(title="Execution Results")
            for row in results:
                table.add_row(*[str(item) for item in row])
            console.print(table)
            
        except Exception as e:
            console.print(f"[bold red]Execution Error:[/bold red] {e}")
    else:
        console.print(f"[bold red]API Error:[/bold red] {response.text}")

if __name__ == "__main__":
    app()
```

## Verification Plan
1. Start the API locally using `uvicorn src.api:app --reload` (Mocking the GPU call on your Mac for testing).
2. Run `python cli.py query "List all customers who bought shoes in 2026" --db_path test.sqlite`.
3. Verify the CLI prints a nicely formatted ASCII table with the database results.

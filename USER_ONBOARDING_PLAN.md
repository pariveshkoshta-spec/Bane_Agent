## Goal Description
We need to design the absolute easiest, "zero-friction" way for a non-technical user to point the Bane Agent at their own database. 

The user should **not** have to manually write out their schemas into text files. The agent should be able to "learn" their tables automatically.

To achieve this, we will build a **Database Introspector**.

## System Flow (The User Experience)

1.  **Install:** User runs `pip install bane-cli`.
2.  **Initialize (The Magic Step):** User runs `bane init my_database.sqlite`.
3.  **Automatic Learning:** The CLI automatically connects to the database, reads the system catalog to extract every `CREATE TABLE` definition, and instantly builds the FAISS vector index locally.
4.  **Query:** User runs `bane query "show me last month's revenue"`. The agent already knows the schema and writes the perfect SQL.

## Proposed Changes

### [NEW] `Bane_Agent/src/db_introspector.py`
This script connects to the user's database, extracts the raw schema definitions programmatically, and feeds them directly into our FAISS `SchemaRetriever`.

```python
import sqlite3
from src.schema_rag import SchemaRetriever

class DatabaseIntrospector:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.retriever = SchemaRetriever()
        
    def learn_database(self):
        """
        Connects to the database, extracts all table schemas, 
        and builds the FAISS index automatically.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Query SQLite's internal system table to get all CREATE TABLE statements
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL;")
        tables = cursor.fetchall()
        
        schema_dict = {}
        for table_name, schema_sql in tables:
            schema_dict[table_name] = schema_sql
            
        conn.close()
        
        # Feed the extracted schemas into FAISS
        print(f"Learned {len(schema_dict)} tables. Building Vector Index...")
        self.retriever.build_index(schema_dict)
        print("Database introspection complete! Bane is ready.")
        
        return self.retriever
```

### [MODIFY] `Bane_Agent/cli.py`
We will add a new `init` command to the CLI that triggers this introspection.

```python
import typer
from src.db_introspector import DatabaseIntrospector

app = typer.Typer()
retriever_cache = None

@app.command()
def init(db_path: str):
    """
    Point Bane at your database so it can automatically learn your schema.
    """
    global retriever_cache
    introspector = DatabaseIntrospector(db_path)
    retriever_cache = introspector.learn_database()
    typer.echo("[SUCCESS] Bane has mapped your database schemas into memory!")

@app.command()
def query(question: str):
    """
    Ask a question after initializing.
    """
    if not retriever_cache:
        typer.echo("[ERROR] Please run 'bane init <db_path>' first!")
        raise typer.Exit()
        
    # FAISS semantic search happens here...
    schema = retriever_cache.retrieve_relevant_tables(question)
    # LLM inference happens here...
```

## Verification Plan
1. We will create a dummy `company_data.sqlite` with 10 random tables.
2. We will run `python cli.py init company_data.sqlite`.
3. We will verify that the tool successfully extracts all 10 schemas without the user ever having to manually type out a `CREATE TABLE` command.

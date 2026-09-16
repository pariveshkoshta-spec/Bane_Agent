def format_dpo_prompt(question: str, schema: str) -> str:
    """
    Constructs the prompt exactly as our DPO-aligned LLaMA-3 model was trained.
    """
    return f"### Schema:\n{schema}\n\n### Question:\n{question}\n\n### SQL:\n"

def format_sqlcoder_prompt(question: str, schema_metadata: str) -> str:
    """
    Constructs the prompt as SQLCoder expects, injecting the schema.
    """
    prompt_template = """### Task
Generate a SQL query to answer [QUESTION]{user_question}[/QUESTION]

### Database Schema
The query will run on a database with the following schema:
{table_metadata_string}

### Answer
Given the database schema, here is the SQL query:
[SQL]"""
    return prompt_template.format(
        user_question=question, 
        table_metadata_string=schema_metadata
    )

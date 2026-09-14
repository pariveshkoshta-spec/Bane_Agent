import typer
import requests
import sqlite3
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Bane: Execution-Aligned Text-to-SQL CLI")
console = Console()

# Assume API is running locally for now
API_URL = "http://localhost:8000"

@app.command()
def init(db_path: str = typer.Argument(..., help="Path to your SQLite database")):
    """
    Introspects your database and builds the FAISS semantic index.
    """
    console.print(f"[bold blue]Initializing Bane Agent on:[/bold blue] {db_path}")
    
    response = requests.post(f"{API_URL}/init", json={"db_path": db_path})
    
    if response.status_code == 200:
        console.print(f"[bold green]Success:[/bold green] {response.json()['message']}")
    else:
        console.print(f"[bold red]Error:[/bold red] {response.text}")

@app.command()
def query(
    question: str = typer.Argument(..., help="The natural language question to ask"),
    db_path: str = typer.Option(..., "--db", help="Path to your SQLite database to execute the query")
):
    """
    Generates and executes SQL based on your question.
    """
    console.print(f"[bold blue]Asking Bane:[/bold blue] '{question}'\n")
    
    response = requests.post(f"{API_URL}/generate_sql", json={"question": question})
    
    if response.status_code == 200:
        sql = response.json()["sql"]
        console.print(f"[bold green]Generated SQL:[/bold green]\n{sql}\n")
        
        # Execute the returned SQL locally
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            results = cursor.execute(sql).fetchall()
            
            # Print results beautifully
            if results:
                table = Table(title="Execution Results", show_lines=True)
                # Just add columns dynamically based on result width
                for _ in range(len(results[0])):
                    table.add_column()
                
                for row in results:
                    table.add_row(*[str(item) for item in row])
                console.print(table)
            else:
                console.print("[yellow]Query executed successfully, but returned 0 rows.[/yellow]")
                
            conn.close()
        except Exception as e:
            console.print(f"[bold red]Execution Error:[/bold red] {str(e)}")
            
    else:
        console.print(f"[bold red]API Error:[/bold red] {response.text}")

if __name__ == "__main__":
    app()

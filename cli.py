import warnings
warnings.filterwarnings("ignore")
import os
import typer
import requests
import sqlite3
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

app = typer.Typer(
    help="Bane: Execution-Aligned Text-to-SQL Agent CLI",
    add_completion=False
)
console = Console()

API_URL = os.environ.get("BANE_API_URL", "http://localhost:8000")

@app.command()
def init(
    db_path: str = typer.Argument(..., help="Path to your SQLite database file"),
    rules: Optional[str] = typer.Option(None, "--rules", "-r", help="Optional human business logic string or rules file path")
):
    """
    Introspects your database, enriches business logic, and builds the FAISS vector index.
    """
    if not os.path.exists(db_path):
        console.print(f"[bold red]Error:[/bold red] Database file '{db_path}' does not exist.")
        raise typer.Exit(code=1)

    business_rules_text = None
    if rules:
        if os.path.exists(rules):
            with open(rules, "r") as f:
                business_rules_text = f.read()
        else:
            business_rules_text = rules

    console.print(f"\n[bold blue]⚡ Introspecting Database:[/bold blue] {os.path.abspath(db_path)}")
    try:
        payload = {"db_path": os.path.abspath(db_path)}
        if business_rules_text:
            payload["business_rules"] = business_rules_text

        response = requests.post(f"{API_URL}/init", json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()
            console.print(f"[bold green]✔ Success:[/bold green] {data.get('message')}")
            if "tables" in data:
                console.print(f"[cyan]Indexed Tables:[/cyan] {', '.join(data['tables'])}")
        else:
            console.print(f"[bold red]API Error ({response.status_code}):[/bold red] {response.text}")
    except requests.exceptions.ConnectionError:
        console.print(f"[bold red]Error:[/bold red] Could not connect to Bane API at '{API_URL}'.")
        console.print("[dim]Make sure the API server is running with: uvicorn src.api:app --reload[/dim]")

@app.command()
def query(
    question: str = typer.Argument(..., help="The natural language question to ask"),
    db_path: str = typer.Option(..., "--db", "-d", help="Path to SQLite database to execute against")
):
    """
    Retrieves schemas via FAISS, generates aligned SQL, and executes it with formatted output.
    """
    if not os.path.exists(db_path):
        console.print(f"[bold red]Error:[/bold red] Database file '{db_path}' not found.")
        raise typer.Exit(code=1)

    console.print(f"\n[bold blue]🔍 User Question:[/bold blue] [italic]{question}[/italic]")

    try:
        response = requests.post(f"{API_URL}/generate_sql", json={"question": question}, timeout=60)
        
        if response.status_code != 200:
            console.print(f"[bold red]API Error ({response.status_code}):[/bold red] {response.text}")
            return

        data = response.json()
        sql = data.get("sql", "").strip()

        console.print(Panel(f"[bold green]{sql}[/bold green]", title="[bold]Generated SQL[/bold]", border_style="green"))

        # Execute against local SQLite database
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(sql)
            results = cursor.fetchall()
            headers = [desc[0] for desc in cursor.description] if cursor.description else []
            conn.close()

            if results:
                table = Table(title="Execution Results", show_lines=True, header_style="bold magenta")
                for col in headers:
                    table.add_column(col, style="bold cyan")

                for row in results:
                    table.add_row(*[str(val) for val in row])

                console.print(table)
                console.print(f"[dim]Returned {len(results)} rows.[/dim]\n")
            else:
                console.print("[yellow]Query executed successfully, but returned 0 rows.[/yellow]\n")

        except Exception as e:
            console.print(f"[bold red]Execution Sandbox Error:[/bold red] {e}\n")

    except requests.exceptions.ConnectionError:
        console.print(f"[bold red]Error:[/bold red] Could not reach Bane API at '{API_URL}'.")
        console.print("[dim]Start the API with: uvicorn src.api:app --reload[/dim]")

if __name__ == "__main__":
    app()

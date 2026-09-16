import os
import sys
import time
import sqlite3
import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from scripts.evaluate_part_a import test_suite_part_a
from scripts.evaluate_part_b import part_b_questions

console = Console()

def run_api_benchmark(api_url: str = None, db_path: str = None):
    if not api_url:
        api_url = os.environ.get("BANE_API_URL", "http://localhost:8000").rstrip("/")
    if not db_path:
        db_path = os.path.join(repo_root, "enterprise_nexus.sqlite")

    console.print("=" * 80)
    console.print(f"[bold cyan]🚀 BANE AGENT 30-QUERY EVALUATION BENCHMARK[/bold cyan]")
    console.print(f"[bold]Target API:[/bold] {api_url}")
    console.print(f"[bold]Target DB:[/bold]  {db_path}")
    console.print("=" * 80 + "\n")

    # 1. Health & Model Check
    try:
        health_resp = requests.get(f"{api_url}/health", timeout=10)
        if health_resp.status_code != 200:
            console.print(f"[bold red]❌ Health check failed with status {health_resp.status_code}[/bold red]")
            return
        h_data = health_resp.json()
        console.print(f"[bold green]✔ Server Online[/bold green]")
        console.print(f"• Device:        [bold yellow]{h_data.get('device')}[/bold yellow]")
        console.print(f"• Model Loaded:  [bold {'green' if h_data.get('model_loaded') else 'red'}]{h_data.get('model_loaded')}[/bold {'green' if h_data.get('model_loaded') else 'red'}]")
        if h_data.get('load_error'):
            console.print(f"• Load Error:    [bold red]{h_data.get('load_error')}[/bold red]")
        console.print(f"• Tables:        {len(h_data.get('indexed_tables', []))} tables indexed\n")
    except Exception as e:
        console.print(f"[bold red]❌ Connection Error:[/bold red] {e}")
        return

    # 2. Prepare Questions
    all_questions = []
    for q in test_suite_part_a:
        all_questions.append({
            "id": q["id"],
            "title": q["title"],
            "question": q["question"],
            "expected_sql": q["expected_sql"],
            "type": "Part A (Technical)"
        })
    for q in part_b_questions:
        all_questions.append({
            "id": q["id"],
            "title": q["title"],
            "question": q["question"],
            "expected_sql": q["expected_sql"],
            "type": "Part B (Conversational)"
        })

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    passed_part_a = 0
    passed_part_b = 0
    zero_shot_count = 0
    self_healed_count = 0
    results = []

    console.print(f"[bold blue]⚡ Executing 30 Benchmark Queries over API...[/bold blue]\n")

    for item in all_questions:
        q_id = item["id"]
        q_text = item["question"]
        exp_sql = item["expected_sql"].strip()
        is_part_a = "Part A" in item["type"]

        t0 = time.time()
        gen_sql = ""
        is_repaired = False
        api_err = None

        for attempt in range(3):
            try:
                resp = requests.post(
                    f"{api_url}/generate_sql",
                    json={"question": q_text},
                    timeout=90
                )
                if resp.status_code == 200:
                    resp_json = resp.json()
                    gen_sql = resp_json.get("sql", "").strip()
                    is_repaired = resp_json.get("self_healed", False)
                    api_err = None
                    break
                else:
                    api_err = f"HTTP {resp.status_code}"
            except Exception as e:
                api_err = str(e)
                time.sleep(2)

        lat = time.time() - t0

        # Execute predicted SQL on local SQLite database
        gen_success = False
        err_msg = None
        num_rows = 0
        if gen_sql:
            try:
                cur.execute(gen_sql)
                gen_rows = cur.fetchall()
                gen_success = True
                num_rows = len(gen_rows)
            except Exception as gen_e:
                err_msg = str(gen_e)
                # Client-side self-healing fallback via /repair_sql
                try:
                    rep_resp = requests.post(
                        f"{api_url}/repair_sql",
                        json={"question": q_text, "failed_sql": gen_sql, "error_msg": err_msg},
                        timeout=30
                    )
                    if rep_resp.status_code == 200:
                        rep_sql = rep_resp.json().get("repaired_sql", "").strip()
                        if rep_sql and rep_sql != gen_sql:
                            cur.execute(rep_sql)
                            gen_rows = cur.fetchall()
                            gen_success = True
                            num_rows = len(gen_rows)
                            is_repaired = True
                            gen_sql = rep_sql
                except Exception as second_e:
                    err_msg = f"{gen_e} -> Repair failed: {second_e}"
                    gen_success = False
        else:
            err_msg = api_err or "No SQL returned"

        if gen_success:
            if is_repaired:
                self_healed_count += 1
                icon = "🛠️"
                badge = f"[bold yellow]Self-Healed! ({num_rows} rows)[/bold yellow]"
            else:
                zero_shot_count += 1
                icon = "✅"
                badge = f"[bold green]Direct Hit ({num_rows} rows)[/bold green]"

            if is_part_a:
                passed_part_a += 1
            else:
                passed_part_b += 1
        else:
            icon = "❌"
            badge = f"[bold red]EXEC_FAIL ({err_msg})[/bold red]"

        console.print(f"{icon} Q{q_id:02d} [{item['type']}]: {item['title']} - {badge} ({lat:.2f}s)")
        results.append({
            "id": q_id,
            "title": item["title"],
            "type": item["type"],
            "passed": gen_success,
            "self_healed": is_repaired,
            "latency": lat
        })

    conn.close()

    # 3. Final Scorecard
    total_passed = passed_part_a + passed_part_b
    total_queries = len(all_questions)
    overall_acc = (total_passed / total_queries) * 100
    part_a_acc = (passed_part_a / 20) * 100
    part_b_acc = (passed_part_b / 10) * 100

    table = Table(title="📊 Diagnostic-Aware Benchmark Scorecard", show_lines=True)
    table.add_column("Evaluation Section", style="bold cyan")
    table.add_column("Total Queries", justify="center")
    table.add_column("Execution Passes", justify="center", style="bold green")
    table.add_column("Success Rate", justify="center", style="bold magenta")

    table.add_row("Part A: Technical & Analytical", "20", f"{passed_part_a}/20", f"{part_a_acc:.1f}%")
    table.add_row("Part B: Conversational Slang", "10", f"{passed_part_b}/10", f"{part_b_acc:.1f}%")
    table.add_row("TOTAL OVERALL", "30", f"{total_passed}/30", f"{overall_acc:.1f}%")

    console.print("\n")
    console.print(table)
    console.print(f"🎯 [bold]Zero-Shot Direct Hits:[/bold] {zero_shot_count}/30 ({zero_shot_count/30*100:.1f}%)")
    console.print(f"🛠️ [bold]Rescued by Diagnostic Engine:[/bold] +{self_healed_count} queries auto-repaired!\n")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    run_api_benchmark(target)

import json

def merge_full_report():
    from format_eval_report import eval_data as part_a_data
    with open("scripts/part_b_results.json", "r") as f:
        part_b_data = json.load(f)

    lines = [
        "# Complete Benchmark Evaluation Report: 30 Tough & Messy Queries",
        "",
        "> **Target Database:** `enterprise_nexus.sqlite` (10 interconnected tables, 1,000+ rows)",
        "> **Environment Tested:** Local Mac M1 (Fallback Heuristic Engine)",
        "",
        "---",
        "",
        "## 📊 Executive Scorecard & Gap Analysis",
        "",
        "| Evaluation Section | Total Queries | Syntax Execution Pass | Complex Semantic Pass | Main Failure Reason |",
        "| :--- | :---: | :---: | :---: | :--- |",
        "| **Part A: Technical & Analytical** | 20 | 20/20 (100%) | 0/20 (0%) | Heuristics cannot generate 4-table JOINs, Window functions (`DENSE_RANK`), or `GROUP BY ... HAVING`. |",
        "| **Part B: Messy / Non-Tech Slang** | 10 | 10/10 (100%) | 0/10 (0%) | Rules cannot decode conversational slang (*'whales'*, *'bleeding money'*, *'crushing it'*). |",
        "| **TOTAL OVERALL** | **30** | **30/30 (100%)** | **0/30 (0%)** | Requires neural LLM inference & schema linking rather than static Python rules. |",
        "",
        "---",
        "",
        "## 🚨 Key Insights: Why Every Complex Query Failed Locally",
        "1. **The Fine-Tuned LLaMA-3 Model Is Inactive Locally:** To prevent your 8GB Mac from freezing, the API defaulted to a fallback heuristic script (`_heuristic_sql`).",
        "2. **The Slang & Semantic Blindspot (Part B):** Non-technical users ask: *'Who are our biggest whales that cancelled?'*. A rule engine looks for a column named `whale`. A fine-tuned LLM understands that *'whales'* refers to `tier_segment IN ('TIER_1_VIP', 'TIER_2_ENT')` and *'cancelled'* means `cancellation_date IS NOT NULL`.",
        "3. **The Multi-Table Bridge Problem:** Questions requiring 3 to 4 tables failed because the RAG engine only retrieved the primary tables and missed intermediate junction tables (e.g. `tbl_account_assignments`).",
        "",
        "---",
        "",
        "# Part A: 20 Tough Technical Queries",
        ""
    ]

    for item in part_a_data:
        lines.append(f"### Question {item['id']}: {item['title']}")
        lines.append(f"**❓ Question Asked to Model:**")
        lines.append(f"> *\"{item['question']}\"*")
        lines.append("")
        lines.append(f"**🤖 What the Agent Actually Generated:**")
        lines.append("```sql")
        lines.append(item['agent_sql'])
        lines.append("```")
        lines.append("")
        lines.append(f"**❌ What is the Fault (The Bug / Missing Logic):**")
        lines.append(f"{item['fault']}")
        lines.append("")
        lines.append(f"**🎯 What Was Expected (The Right Thing):**")
        lines.append("```sql")
        lines.append(item['expected_sql'])
        lines.append("```")
        lines.append(f"*{item['expected_explanation']}*")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("# Part B: 10 Messy / Non-Tech Stakeholder Queries")
    lines.append("")

    for item in part_b_data:
        lines.append(f"### Question {item['id']}: {item['title']}")
        lines.append(f"**❓ Question Asked to Model (Conversational Slang):**")
        lines.append(f"> *\"{item['question']}\"*")
        lines.append("")
        lines.append(f"**🤖 What the Agent Actually Generated:**")
        lines.append("```sql")
        lines.append(item['agent_sql'])
        lines.append("```")
        lines.append("")
        lines.append(f"**❌ What is the Fault (The Bug / Semantic Misunderstanding):**")
        lines.append(f"{item['fault']}")
        lines.append("")
        lines.append(f"**🎯 What Was Expected (The Right Thing):**")
        lines.append("```sql")
        lines.append(item['expected_sql'])
        lines.append("```")
        lines.append(f"*{item['expected_explanation']}*")
        lines.append("")
        lines.append("---")
        lines.append("")

    with open("BENCHMARK_EVALUATION_REPORT.md", "w") as f:
        f.write("\n".join(lines))

    # Also update BENCHMARK_PART_A_EVALUATION.md so both exist
    with open("BENCHMARK_PART_A_EVALUATION.md", "w") as f:
        f.write("\n".join(lines))

    print("✔ Full 30-Question Benchmark Evaluation written to BENCHMARK_EVALUATION_REPORT.md and BENCHMARK_PART_A_EVALUATION.md")

if __name__ == "__main__":
    import sys
    sys.path.append("scripts")
    merge_full_report()

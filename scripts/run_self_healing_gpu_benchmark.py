import os
import sys
import time
import json
import sqlite3
import re

def clean_sql(raw_output: str, prompt_prefix: str) -> str:
    cleaned = raw_output.replace(prompt_prefix, "").strip()
    if "```sql" in cleaned:
        cleaned = cleaned.split("```sql")[1].split("```")[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0].strip()
    # Take query up to the first terminating semicolon if trailing text exists
    if ";" in cleaned:
        cleaned = cleaned.split(";")[0].strip() + ";"
    return cleaned

def run_self_healing_benchmark():
    print("=" * 80)
    print("  BANE AGENT: FULL-SCHEMA & AGENTIC SELF-HEALING BENCHMARK (GPU)")
    print("=" * 80)

    try:
        import torch
        if not torch.cuda.is_available():
            print("[WARN] GPU not detected. Inference will run on CPU.")
        else:
            print(f"[INFO] Active GPU: {torch.cuda.get_device_name(0)} ({torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB VRAM)")
    except ImportError:
        print("[ERROR] PyTorch not installed.")
        sys.exit(1)

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 1. Locate Adapters
    adapter_candidates = [
        "/content/local_adapters",
        "/content/bane_dpo_lora_adapters",
        os.path.join(repo_root, "results", "bane_dpo_lora_adapters"),
        "/content/drive/MyDrive/bane_dpo_lora_adapters",
        "results/bane_dpo_lora_adapters"
    ]
    adapter_path = None
    for cand in adapter_candidates:
        if os.path.exists(cand) and os.path.exists(os.path.join(cand, "adapter_config.json")):
            adapter_path = cand
            break

    print(f"[INFO] Using LoRA Adapters: {adapter_path}")

    # 2. Load Model
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    base_model_id = "unsloth/llama-3-8b-instruct-bnb-4bit"
    print(f"[INFO] Loading 4-bit base model ({base_model_id}) on GPU...")
    tokenizer = AutoTokenizer.from_pretrained(adapter_path if adapter_path else base_model_id)
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto"
    )
    if adapter_path:
        print("[INFO] Attaching fine-tuned DPO LoRA weights...")
        model = PeftModel.from_pretrained(base_model, adapter_path)
    else:
        model = base_model
    model.eval()
    print("✅ Model ready in GPU VRAM!\n")

    # 3. Prepare Enterprise Database and Full Schema
    db_path = os.path.join(repo_root, "enterprise_nexus.sqlite")
    if not os.path.exists(db_path):
        from scripts.generate_enterprise_nexus import generate_enterprise_nexus
        generate_enterprise_nexus(db_path)

    from src.db_introspector import DatabaseIntrospector
    from src.prompt_builder import format_dpo_prompt
    from scripts.evaluate_part_a import test_suite_part_a
    from scripts.evaluate_part_b import part_b_questions

    introspector = DatabaseIntrospector(db_path)
    schemas = introspector.extract_schemas()

    # Concatenate all 10 table definitions for full schema relational awareness
    full_schema_context = "\n\n".join(schemas.values())
    print(f"✅ Loaded Full Relational Schema ({len(schemas)} tables, foreign keys intact).\n")

    # 4. Load 30 Benchmark Questions
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

    db_conn = sqlite3.connect(db_path)
    cursor = db_conn.cursor()

    results = []
    repaired_count = 0
    zero_shot_count = 0

    print(f"🚀 Running Full-Schema + Self-Healing Evaluation on {len(all_questions)} Queries...")
    print("-" * 80)

    for item in all_questions:
        q_id = item["id"]
        q_text = item["question"]
        exp_sql = item["expected_sql"].strip()

        # Step 1: Generate initial query with full schema context
        prompt = format_dpo_prompt(q_text, full_schema_context)
        inputs = tokenizer([prompt], return_tensors="pt")
        if torch.cuda.is_available():
            inputs = {k: v.to("cuda") for k, v in inputs.items()}

        t0 = time.time()
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=160,
                temperature=0.1,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id
            )
        initial_time = time.time() - t0
        raw_output = tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]
        gen_sql = clean_sql(raw_output, prompt)

        # Step 2: Attempt execution
        exec_status = "SUCCESS"
        err_str = None
        gen_rows = []
        is_repaired = False

        try:
            cursor.execute(gen_sql)
            gen_rows = cursor.fetchall()
            zero_shot_count += 1
        except Exception as initial_err:
            # Trigger Agentic Self-Correction Loop
            err_str = str(initial_err)
            repair_prompt = f"""### Database Schema:
{full_schema_context}

### User Question:
{q_text}

### Attempted SQL:
{gen_sql}

### SQLite Execution Error:
{err_str}

### Instructions:
The attempted SQL query produced an execution error. Rewrite and fix the query so that it executes cleanly on SQLite. Return ONLY the valid SQL query.

### Corrected SQL:
"""
            repair_inputs = tokenizer([repair_prompt], return_tensors="pt")
            if torch.cuda.is_available():
                repair_inputs = {k: v.to("cuda") for k, v in repair_inputs.items()}

            with torch.no_grad():
                repair_outputs = model.generate(
                    **repair_inputs,
                    max_new_tokens=160,
                    temperature=0.1,
                    do_sample=False,
                    pad_token_id=tokenizer.eos_token_id
                )
            repaired_raw = tokenizer.batch_decode(repair_outputs, skip_special_tokens=True)[0]
            repaired_sql = clean_sql(repaired_raw, repair_prompt)

            try:
                cursor.execute(repaired_sql)
                gen_rows = cursor.fetchall()
                exec_status = "SUCCESS (Self-Healed)"
                gen_sql = repaired_sql
                err_str = None
                repaired_count += 1
                is_repaired = True
            except Exception as second_err:
                exec_status = "EXEC_ERROR"
                err_str = f"Initial: {initial_err} | Repair: {second_err}"

        # Execute expected SQL
        cursor.execute(exp_sql)
        exp_rows = cursor.fetchall()

        if "SUCCESS" in exec_status:
            icon = "🛠️" if is_repaired else "✅"
        else:
            icon = "❌"

        status_label = f"[{icon}] Q{q_id:02d} [{item['type']}]: {item['title']} ({initial_time:.2f}s | {len(gen_rows)} rows)"
        if is_repaired:
            status_label += " [Self-Healed!]"
        print(status_label)
        if exec_status == "EXEC_ERROR":
            print(f"      Error: {err_str}")

        results.append({
            "id": q_id,
            "title": item["title"],
            "type": item["type"],
            "question": q_text,
            "agent_sql": gen_sql,
            "expected_sql": exp_sql,
            "status": exec_status,
            "error": err_str,
            "gen_rows": len(gen_rows),
            "exp_rows": len(exp_rows),
            "is_repaired": is_repaired
        })

    db_conn.close()

    # Summary
    total = len(results)
    pass_count = sum(1 for r in results if "SUCCESS" in r["status"])
    part_a_pass = sum(1 for r in results if "Part A" in r["type"] and "SUCCESS" in r["status"])
    part_b_pass = sum(1 for r in results if "Part B" in r["type"] and "SUCCESS" in r["status"])

    print("\n" + "=" * 80)
    print("📊 FULL-SCHEMA + AGENTIC SELF-HEALING SCORECARD:")
    print(f"   • Zero-Shot Clean Passes:   {zero_shot_count}/{total} ({zero_shot_count/total*100:.1f}%)")
    print(f"   • Self-Healed on Retry:     +{repaired_count} queries auto-repaired!")
    print(f"   • Total Execution Passes:   {pass_count}/{total} ({pass_count/total*100:.1f}%)")
    print(f"   • Part A (Technical):       {part_a_pass}/20 ({part_a_pass/20*100:.1f}%)")
    print(f"   • Part B (Conversational):  {part_b_pass}/10 ({part_b_pass/10*100:.1f}%)")
    print("=" * 80)

    # Save output report
    report_path = os.path.join(repo_root, "SELF_HEALING_GPU_REPORT.md")
    report_lines = [
        "# Agentic Self-Healing GPU Benchmark Report",
        "",
        f"> **Total Pass Rate:** {pass_count}/{total} ({pass_count/total*100:.1f}%)",
        f"> **Zero-Shot Passes:** {zero_shot_count}/{total}",
        f"> **Queries Rescued by Self-Healing Loop:** +{repaired_count}",
        "",
        "| Section | Total | Execution Passes | Success Rate |",
        "| :--- | :---: | :---: | :---: |",
        f"| Part A (Technical) | 20 | **{part_a_pass}/20** | **{part_a_pass/20*100:.1f}%** |",
        f"| Part B (Conversational) | 10 | **{part_b_pass}/10** | **{part_b_pass/10*100:.1f}%** |",
        f"| **TOTAL** | **30** | **{pass_count}/30** | **{pass_count/30*100:.1f}%** |",
        "",
        "---",
        ""
    ]
    for r in results:
        report_lines.append(f"### Q{r['id']}: {r['title']} ({r['type']})")
        report_lines.append(f"**Question:** *\"{r['question']}\"*")
        report_lines.append(f"**Status:** `{r['status']}` | Rows: {r['gen_rows']} (Target: {r['exp_rows']})")
        report_lines.append("```sql")
        report_lines.append(r['agent_sql'])
        report_lines.append("```")
        if r['error']:
            report_lines.append(f"*Error:* `{r['error']}`")
        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")

    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))
    print(f"✔ Full report written to: {report_path}")

if __name__ == "__main__":
    run_self_healing_benchmark()

import os
import sys
import time
import json
import sqlite3
import re

def run_gpu_benchmark():
    print("=" * 75)
    print("  BANE AGENT: NEURAL DPO BENCHMARK EVALUATOR (GPU)")
    print("=" * 75)

    # 1. Detect GPU
    try:
        import torch
        if not torch.cuda.is_available():
            print("[WARN] NVIDIA CUDA GPU not detected! This script is designed for GPU environments (Kaggle/Colab).")
            print("       Running on CPU may be slow or fail if 4-bit bnb is loaded.")
        else:
            print(f"[INFO] Detected GPU: {torch.cuda.get_device_name(0)} ({torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB VRAM)")
    except ImportError:
        print("[ERROR] PyTorch not installed. Run: pip install torch")
        sys.exit(1)

    # 2. Locate LoRA Adapters
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    adapter_candidates = [
        os.path.join(repo_root, "results", "bane_dpo_lora_adapters"),
        "/kaggle/working/bane_dpo_lora_adapters",
        "/kaggle/working/outputs/checkpoint-375",
        "/kaggle/input/bane-dpo-lora-adapters",
        "results/bane_dpo_lora_adapters",
        "bane_dpo_lora_adapters"
    ]

    adapter_path = None
    for cand in adapter_candidates:
        if os.path.exists(cand) and os.path.exists(os.path.join(cand, "adapter_config.json")):
            adapter_path = cand
            break

    print(f"[INFO] Target LoRA Adapter Path: {adapter_path}")

    # 3. Load Model via Unsloth or PEFT
    print("\n[INFO] Loading fine-tuned model weights...")
    model = None
    tokenizer = None

    try:
        from unsloth import FastLanguageModel
        print("[INFO] Using Unsloth FastLanguageModel engine...")
        model_name = adapter_path if adapter_path else "unsloth/llama-3-8b-Instruct"
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_name,
            max_seq_length=2048,
            dtype=None,
            load_in_4bit=True
        )
        FastLanguageModel.for_inference(model)
    except Exception as unsloth_err:
        print(f"[INFO] Unsloth load skipped ({unsloth_err}). Trying standard transformers + peft...")
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel
        base_name = "unsloth/llama-3-8b-instruct-bnb-4bit"
        tokenizer = AutoTokenizer.from_pretrained(adapter_path if adapter_path else base_name)
        base_model = AutoModelForCausalLM.from_pretrained(
            base_name,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto"
        )
        if adapter_path:
            model = PeftModel.from_pretrained(base_model, adapter_path)
        else:
            model = base_model
        model.eval()

    print("✅ Model successfully loaded into VRAM!\n")

    # 4. Database and FAISS Indexing
    db_path = os.path.join(repo_root, "enterprise_nexus.sqlite")
    if not os.path.exists(db_path):
        print(f"[INFO] Generating enterprise_nexus.sqlite at {db_path}...")
        gen_script = os.path.join(repo_root, "scripts", "generate_enterprise_nexus.py")
        import subprocess
        subprocess.run([sys.executable, gen_script], check=True, cwd=repo_root)

    from src.db_introspector import DatabaseIntrospector
    from src.schema_rag import SchemaRetriever
    from src.prompt_builder import format_dpo_prompt

    introspector = DatabaseIntrospector(db_path)
    schemas = introspector.extract_schemas()
    retriever = SchemaRetriever()
    retriever.build_index(schemas)
    print(f"✅ Indexed {len(schemas)} tables into FAISS vector space.\n")

    # 5. Load Benchmark Questions
    from scripts.evaluate_part_a import test_suite_part_a
    from scripts.evaluate_part_b import part_b_questions

    all_questions = []
    for q in test_suite_part_a:
        all_questions.append({
            "id": q["id"],
            "title": q["title"],
            "question": q["question"],
            "expected_sql": q["expected_sql"],
            "section": "Part A (Technical)"
        })
    for q in part_b_questions:
        all_questions.append({
            "id": q["id"],
            "title": q["title"],
            "question": q["question"],
            "expected_sql": q["expected_sql"],
            "section": "Part B (Conversational)"
        })

    # 6. Execute Benchmark
    db_conn = sqlite3.connect(db_path)
    cursor = db_conn.cursor()

    results = []
    print(f"🚀 Evaluating {len(all_questions)} queries against enterprise_nexus.sqlite on GPU...")
    print("-" * 75)

    for item in all_questions:
        q_id = item["id"]
        q_text = item["question"]
        exp_sql = item["expected_sql"].strip()

        # Retrieve RAG schema context
        context = retriever.retrieve_context(q_text, top_k=3)
        prompt = format_dpo_prompt(q_text, context)

        # Generate on GPU
        inputs = tokenizer([prompt], return_tensors="pt")
        if torch.cuda.is_available():
            inputs = {k: v.to("cuda") for k, v in inputs.items()}

        t0 = time.time()
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=128,
                temperature=0.1,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id
            )
        latency = time.time() - t0

        raw_sql = tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]
        gen_sql = raw_sql.replace(prompt, "").strip()

        # Clean markdown formatting if present
        if "```sql" in gen_sql:
            gen_sql = gen_sql.split("```sql")[1].split("```")[0].strip()
        elif "```" in gen_sql:
            gen_sql = gen_sql.split("```")[1].split("```")[0].strip()

        # Strip semicolons and extra comments for clean comparison
        gen_sql_clean = gen_sql.split(";")[0].strip() + ";"

        # Execute on Database
        exec_status = "SUCCESS"
        err_str = None
        gen_rows = []
        try:
            cursor.execute(gen_sql)
            gen_rows = cursor.fetchall()
        except Exception as e:
            exec_status = "EXECUTION_ERROR"
            err_str = str(e)

        # Execute ground truth
        cursor.execute(exp_sql)
        exp_rows = cursor.fetchall()

        icon = "✅" if exec_status == "SUCCESS" else "❌"
        print(f"[{icon}] Q{q_id:02d} [{item['section']}]: {item['title']} ({latency:.2f}s, {len(gen_rows)} rows)")
        if exec_status != "SUCCESS":
            print(f"      Err: {err_str}")

        results.append({
            "id": q_id,
            "title": item["title"],
            "section": item["section"],
            "question": q_text,
            "agent_sql": gen_sql,
            "expected_sql": exp_sql,
            "execution_status": exec_status,
            "error": err_str,
            "gen_rows_count": len(gen_rows),
            "exp_rows_count": len(exp_rows),
            "latency_sec": round(latency, 2)
        })

    db_conn.close()

    # 7. Generate Scorecard
    total = len(results)
    success_count = sum(1 for r in results if r["execution_status"] == "SUCCESS")
    part_a_succ = sum(1 for r in results if "Part A" in r["section"] and r["execution_status"] == "SUCCESS")
    part_b_succ = sum(1 for r in results if "Part B" in r["section"] and r["execution_status"] == "SUCCESS")

    out_file = os.path.join(repo_root, "KAGGLE_GPU_BENCHMARK_REPORT.md")
    report_lines = [
        "# Kaggle GPU Neural Benchmark Evaluation Report",
        "",
        f"> **Hardware:** {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}",
        f"> **Model / LoRA:** {adapter_path or 'Base Model'}",
        f"> **Execution Pass Rate:** {success_count}/{total} ({success_count/total*100:.1f}%)",
        "",
        "## Scorecard",
        f"- **Part A (Technical):** {part_a_succ}/20 ({part_a_succ/20*100:.1f}%)",
        f"- **Part B (Conversational):** {part_b_succ}/10 ({part_b_succ/10*100:.1f}%)",
        "",
        "---",
        ""
    ]

    for r in results:
        report_lines.append(f"### Q{r['id']}: {r['title']} ({r['section']})")
        report_lines.append(f"**Prompt:** *\"{r['question']}\"*")
        report_lines.append("")
        report_lines.append("```sql")
        report_lines.append(r['agent_sql'])
        report_lines.append("```")
        report_lines.append(f"* **Status:** `{r['execution_status']}` | Rows: {r['gen_rows_count']} (Expected: {r['exp_rows_count']}) | Latency: {r['latency_sec']}s")
        if r['error']:
            report_lines.append(f"* **Error:** `{r['error']}`")
        report_lines.append("")
        report_lines.append("**Expected SQL:**")
        report_lines.append("```sql")
        report_lines.append(r['expected_sql'])
        report_lines.append("```")
        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")

    with open(out_file, "w") as f:
        f.write("\n".join(report_lines))

    # Also save JSON
    json_out = os.path.join(repo_root, "kaggle_gpu_results.json")
    with open(json_out, "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 75)
    print(f"🎉 Benchmark complete! Summary:")
    print(f"   • Overall Execution Success: {success_count}/{total} ({success_count/total*100:.1f}%)")
    print(f"   • Part A (Technical):        {part_a_succ}/20 ({part_a_succ/20*100:.1f}%)")
    print(f"   • Part B (Conversational):   {part_b_succ}/10 ({part_b_succ/10*100:.1f}%)")
    print(f"   • Report written to: {out_file}")
    print("=" * 75)

if __name__ == "__main__":
    run_gpu_benchmark()

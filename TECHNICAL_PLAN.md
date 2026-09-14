## Goal Description
Create a comprehensive technical roadmap for building the **Bane** (Execution-Aligned Text-to-SQL Agent) by surgically extracting the most critical logic from the three cloned repositories: `defog/sqlcoder`, `DAMO-ConvAI` (BIRD-SQL), and `unsloth`.

## User Review Required
> [!IMPORTANT] Hardware Constraints
> The final training scripts generated in this plan are strictly intended to be executed in Kaggle (T4 x2) or Colab. Running the DPO notebook locally will result in a hard OOM (Out Of Memory) crash.

## Proposed Changes
Below is the technical breakdown of the code we will extract from each repository and how we will assemble it in our own scripts.

---

### Component 1: Prompt Formatting (From Defog SQLCoder)
We need to format the raw database schemas into a highly optimized string format that the LLM understands, matching how SQLCoder beat GPT-4.
*   **Source File:** `Bane_Agent/references/sqlcoder/inference.py` and `prompt.md`
*   **Action:** We will extract the exact logic they use in `generate_prompt()` to format the table metadata and user question.
#### [NEW] `Bane_Agent/src/prompt_builder.py`
```python
# Extracted from defog/sqlcoder/inference.py
def generate_prompt(question, prompt_file="prompt.md", metadata_file="metadata.sql"):
    with open(prompt_file, "r") as f:
        prompt = f.read()
    
    with open(metadata_file, "r") as f:
        table_metadata_string = f.read()

    # We will adapt this to load from a dictionary/dataframe 
    # instead of static files for our BIRD-SQL dataset loop.
    prompt = prompt.format(
        user_question=question, table_metadata_string=table_metadata_string
    )
    return prompt
```

---

### Component 2: Execution Evaluation (From Alibaba BIRD-SQL)
To create the DPO preference dataset, we need to know if the LLM's SQL query actually runs and returns the correct data.
*   **Source File:** `Bane_Agent/references/DAMO-ConvAI/bird/llm/src/evaluation.py`
*   **Action:** We will extract the `execute_sql(predicted_sql, ground_truth, db_path)` function.
#### [NEW] `Bane_Agent/src/execution_validator.py`
```python
import sqlite3

# Extracted & simplified from DAMO-ConvAI/bird/llm/src/evaluation.py
def execute_sql(predicted_sql, ground_truth_sql, db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Execute generated SQL
        cursor.execute(predicted_sql)
        pred_res = cursor.fetchall()
        
        # Execute ground truth SQL
        cursor.execute(ground_truth_sql)
        gt_res = cursor.fetchall()
        
        conn.close()
        
        # Return True if the data matches, False otherwise
        return set(pred_res) == set(gt_res)
    except Exception as e:
        # If the SQL is syntactically invalid or hallucinates columns
        return False
```
*   **Usage:** We will use this function to iterate over our base model's predictions. If it returns `True`, it becomes the `Chosen` response for DPO. If `False`, it becomes the `Rejected` response.

---

### Component 3: DPO Fine-Tuning (From Unsloth)
We will leverage `unsloth` to patch Hugging Face's `trl` library, making it possible to train LLaMA-3-8B in 4-bit precision on a free GPU.
*   **Source Logic:** Unsloth patches `trl.DPOTrainer` dynamically.
#### [NEW] `Bane_Agent/notebooks/Bane_DPO_Kaggle.ipynb`
```python
# The core training cell that you will run on Kaggle
from unsloth import FastLanguageModel
from trl import DPOTrainer
from transformers import TrainingArguments

# 1. Load model in 4-bit
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/llama-3-8b-Instruct",
    load_in_4bit = True,
)

# 2. Add LoRA adapters (targeting SQL generation attention heads)
model = FastLanguageModel.get_peft_model(
    model,
    r = 16,
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj"],
    lora_alpha = 16,
)

# 3. DPO Trainer (Using the dataset we generated in Component 2)
trainer = DPOTrainer(
    model = model,
    ref_model = None, # Unsloth handles the reference model implicitly for memory
    tokenizer = tokenizer,
    train_dataset = dpo_dataset, # The {prompt, chosen, rejected} data
    args = TrainingArguments(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 4,
        max_steps = 200,
        output_dir = "outputs",
    ),
)
trainer.train()
```

## Verification Plan
1. **Local Verification:** We will execute `execution_validator.py` on a dummy `.sqlite` file locally to ensure the Python script correctly flags SQL errors.
2. **Kaggle Verification:** We will push the dataset and notebook to Kaggle, run it, and verify that the `DPOTrainer` completes 1 epoch without a CUDA Out-Of-Memory error.

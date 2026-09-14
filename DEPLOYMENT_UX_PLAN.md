## Goal Description
To make the Bane Agent truly useful, we must consider the end-user's environment. The biggest barrier in open-source AI is hardware compatibility. We need to package this tool so that:
1. Enterprise users can deploy it securely on Cloud GPUs.
2. Individual users (like someone with an M1 Mac) can run it locally without a heavy NVIDIA GPU.

## User Review Required
> [!IMPORTANT] Deployment Strategy Decision
> We have two distinct paths for deployment. I recommend implementing **both** to maximize the tool's reach and the impressiveness of your resume.

## Proposed Changes

### Strategy 1: The Enterprise Path (Docker)
For users who want to host the API on a dedicated GPU server (AWS, RunPod, GCP), we will containerize the FastAPI backend. This eliminates "dependency hell" (CUDA versions, PyTorch mismatches).

#### [NEW] `Bane_Agent/Dockerfile`
```dockerfile
# Use official NVIDIA PyTorch image as base
FROM nvcr.io/nvidia/pytorch:23.10-py3

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"

# Copy API code and model weights
COPY src/ /app/src/
COPY bane_dpo_lora_adapters/ /app/model/

# Expose API port
EXPOSE 8000

# Run FastAPI
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
```
*   **User Experience:** The user simply runs `docker-compose up` on their cloud server, and the API is instantly live.

---

### Strategy 2: The Local Mac Path (GGUF & Ollama)
For users who want to run this purely locally on their MacBook (like your M1 Air) without renting a cloud GPU, we must convert our fine-tuned model into the **GGUF format**.

#### [NEW] `Bane_Agent/scripts/export_gguf.py`
We will add a script that leverages Unsloth's built-in GGUF exporter.
```python
from unsloth import FastLanguageModel

# Load our fine-tuned adapters
model, tokenizer = FastLanguageModel.from_pretrained("bane_dpo_lora_adapters")

# Export to GGUF format (Q4_K_M is the optimal balance of speed and quality for Macs)
model.save_pretrained_gguf("bane_model", tokenizer, quantization_method = "q4_k_m")
```
*   **User Experience:** Once exported to GGUF, a user can load the model into **Ollama** or **LM Studio**. They can literally open their Mac terminal and type `ollama run bane-sql`, and the model will execute purely on their Mac's unified memory (Apple Silicon) without crashing.

---

### Strategy 3: The Client UX (PyPI CLI Package)
Regardless of whether the user is querying the Docker API or their local Ollama instance, the terminal interface must be universally installable.

#### [NEW] `Bane_Agent/setup.py`
We will package the CLI using standard Python tools.
```python
from setuptools import setup, find_packages

setup(
    name='bane-cli',
    version='1.0.0',
    packages=find_packages(),
    install_requires=[
        'typer',
        'rich',
        'requests'
    ],
    entry_points='''
        [console_scripts]
        bane=cli:app
    ''',
)
```
*   **User Experience:** A user just types `pip install bane-cli` on their computer. They can now type `bane query "Show me sales"` from anywhere in their terminal, and the CLI will route the request to their preferred backend (Docker or Ollama) and print the SQL results.

## Verification Plan
1. **Docker Test:** We will write a `docker-compose.yml` to verify the API builds correctly.
2. **GGUF Test:** We will run the GGUF export script in the final Kaggle notebook so that the `.gguf` file is generated automatically alongside the adapters.
3. **CLI Test:** We will run `pip install -e .` locally to test the CLI commands.

# Codespace Handoff Context
*This file contains the complete context of our local chat session. Give this to the AI assistant inside your GitHub Codespace so it knows exactly where we left off!*

## 1. Project State
We are building **Bane / OptiQuery**, an Enterprise Execution-Aligned Text-to-SQL AI Agent. 
*   **The Architecture:** It uses FAISS for Schema RAG, a local 1B LLM for Semantic Enrichment, and a LLaMA-3-8B model fine-tuned using Direct Preference Optimization (DPO) to stop schema hallucinations.
*   **Current Progress:** The 10,000-row synthetic data generation and Unsloth DPO training (Phase 3) is currently running in the background on a Kaggle T4 GPU.
*   **The Codebase:** We have already written the complete Python structure for the CLI (`cli.py`), the FastAPI backend (`src/api.py`), the FAISS vector DB (`src/schema_rag.py`), and the Semantic Middleman (`src/semantic_enrichment_agent.py`).

## 2. Why We Are in Codespaces
We pushed the repository to GitHub and moved to Codespaces because the user is on an M1 MacBook Air with 8GB RAM. To avoid OOM crashes, we are using the GitHub Student Developer Pack's free high-memory cloud CPUs to test the pipeline and run the local `Ollama` Semantic Middleman.

## 3. Immediate Next Steps (To Do Right Now)
The user has just opened this repo in their Codespace. The AI should guide them through the following exact steps in the Codespace terminal:

1.  **Install the Tool:** 
    ```bash
    pip install -r requirements.txt
    pip install -e .
    ```
2.  **Setup the Middleman Agent:**
    *   Install Ollama in the Linux Codespace (using the standard Linux install command).
    *   Run `ollama pull llama3.2:1b`.
3.  **Create a Dummy Database:**
    *   Write a quick Python one-liner to generate a `test.sqlite` database.
4.  **Test the CLI End-to-End:**
    *   Run `bane init test.sqlite` to trigger the Introspector and FAISS.
    *   Run `bane query "Show me all users"` to hit the (currently mock) FastAPI server and print the Rich ASCII table.

## 4. Resume Status
The user has finalized their 4 elite resume bullets (calibrated perfectly to 135 characters each). They are ready to insert into LaTeX once testing is complete.

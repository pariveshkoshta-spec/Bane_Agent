import json
import requests

class SemanticEnrichmentAgent:
    def __init__(self, ollama_url: str = "http://localhost:11434/api/generate", model: str = "llama3.2:1b"):
        self.ollama_url = ollama_url
        self.model = model
        
    def enrich_business_logic(self, messy_user_text: str) -> dict:
        """
        Uses a local LLM to translate unstructured human business rules into 
        strict JSON format for the Text-to-SQL system.
        """
        prompt = f"""
        You are a Semantic Parsing Agent. Convert the user's unstructured business logic into strict JSON.
        The JSON must follow this exact schema:
        {{
            "business_metric": "string",
            "sql_constraints": ["list of strings"]
        }}
        
        User Input: {messy_user_text}
        """
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        
        try:
            print(f"Asking local {self.model} to structure the business logic...")
            response = requests.post(self.ollama_url, json=payload)
            response.raise_for_status()
            
            # Extract the JSON string from the response
            response_text = response.json().get("response", "{}")
            return json.loads(response_text)
            
        except Exception as e:
            print(f"[ERROR] Failed to communicate with Ollama: {e}")
            return {}

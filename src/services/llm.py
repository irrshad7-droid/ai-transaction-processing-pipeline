import json
import structlog
from openai import AsyncOpenAI
from src.core.config import settings

logger = structlog.get_logger(__name__)

# Predefined taxonomy ensures downstream analytical consistency
CATEGORIES = [
    "Food", "Transport", "Shopping", "Entertainment", 
    "Bills", "Healthcare", "Travel", "Income", 
    "Transfer", "Fraud", "Other"
]

class LLMService:
    def __init__(self):
        # Uses standard OpenAI SDK, but injects base_url from env.
        # Why: This allows swapping the provider to ANY OpenAI-compatible API
        # (e.g. Together AI, vLLM, LocalAI) without changing application code.
        self.client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )
        self.model = settings.LLM_MODEL
        
    async def categorize_transactions(self, transactions: list[dict]) -> dict[str, str]:
        """
        Categorizes a batch of transactions using a predefined taxonomy.
        Returns a mapping of transaction ID to category string.
        """
        if not transactions:
            return {}
            
        system_prompt = (
            "You are a strict financial categorization engine. "
            f"You MUST map each transaction to EXACTLY ONE of these predefined categories: {', '.join(CATEGORIES)}. "
            "Return a JSON object where keys are transaction IDs and values are the exact category strings. "
            "Respond ONLY with valid JSON. No markdown formatting."
        )
        
        user_prompt = json.dumps([
            {
                "id": str(t["id"]), 
                "amount": t["amount"], 
                "description": t["description"]
            } for t in transactions
        ])
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,  # Zero temperature for deterministic categorization
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            logger.error("llm_categorization_failed", error=str(e), exc_info=True)
            # Graceful degradation: Fallback to "Other" so the pipeline doesn't halt
            return {str(t["id"]): "Other" for t in transactions}

    async def generate_summary(self, stats: dict) -> dict:
        """
        Generates a summary of the processed job based on aggregated stats,
        avoiding token bloat from raw transaction lists.
        """
        system_prompt = (
            "You are a financial analyst AI. "
            "Given the following aggregate statistics for a batch of transactions, "
            "provide a JSON object with a concise analysis containing two keys: "
            "'key_insights' (a short summary string of interesting behavior) and "
            "'risk_assessment' (one of: Low, Medium, High)."
        )
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(stats)}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            logger.error("llm_summary_failed", error=str(e), exc_info=True)
            return {
                "key_insights": "Failed to generate LLM summary.",
                "risk_assessment": "Unknown"
            }

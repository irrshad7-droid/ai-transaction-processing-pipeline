import json
import structlog
from openai import AsyncOpenAI
from src.core.config import settings

logger = structlog.get_logger(__name__)

# Predefined taxonomy exactly as specified in the assignment
CATEGORIES = [
    "Food", "Shopping", "Travel", "Transport", 
    "Utilities", "Cash Withdrawal", "Entertainment", "Other"
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
        
    async def categorize_transactions(self, transactions: list[dict]) -> dict:
        """
        Categorizes a batch of transactions using a predefined taxonomy.
        Implements 3x exponential backoff on failure.
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
                "merchant": t.get("merchant", ""),
                "notes": t.get("notes", "")
            } for t in transactions
        ])
        
        import asyncio
        for attempt in range(1, 4):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content
                return {"categories": json.loads(content), "llm_failed": False}
            except Exception as e:
                logger.warning("llm_categorization_attempt_failed", attempt=attempt, error=str(e))
                if attempt == 3:
                    logger.error("llm_categorization_failed_all_retries", error=str(e), exc_info=True)
                    return {"categories": {}, "llm_failed": True}
                await asyncio.sleep(2 ** attempt)  # Exponential backoff: 2s, 4s
                
        return {"categories": {}, "llm_failed": True}

    async def generate_summary(self, stats: dict) -> dict:
        """
        Generates a summary of the processed job based on aggregated stats.
        Assignment requirement: total spend by currency, top 3 merchants, anomaly count, narrative, risk_level.
        """
        system_prompt = (
            "You are a financial analyst AI. "
            "Given the following aggregate statistics for a batch of transactions, "
            "provide a JSON object exactly matching this structure:\n"
            "{\n"
            '  "total_spend_by_currency": {"USD": 100, "INR": 5000},\n'
            '  "top_3_merchants": ["Merchant A", "Merchant B", "Merchant C"],\n'
            '  "anomaly_count": 0,\n'
            '  "spending_narrative": "A 2-3 sentence spending narrative based on the data.",\n'
            '  "risk_level": "low/medium/high"\n'
            "}"
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
                "total_spend_by_currency": {},
                "top_3_merchants": [],
                "anomaly_count": stats.get("anomaly_count", 0),
                "spending_narrative": "Failed to generate narrative due to LLM error.",
                "risk_level": "unknown"
            }

    async def close(self):
        """
        Closes the underlying httpx client to prevent 'Event loop is closed' errors 
        when the asyncio event loop shuts down.
        """
        await self.client.close()

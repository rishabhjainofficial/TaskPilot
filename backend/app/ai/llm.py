import os
import json
from typing import List, Dict, Any, Optional, Tuple
from openai import OpenAI
from app.config import get_settings
from app.ai.tools import TOOL_DEFINITIONS

settings = get_settings()


class LLMResult:
    def __init__(
        self,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: str = "mock-model",
    ):
        self.content = content
        self.tool_calls = tool_calls or []
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.model = model


def get_llm_config() -> Tuple[Optional[str], Optional[str], str]:
    api_key = (
        os.getenv("GROQ_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("GROK_API_KEY")
        or settings.GROQ_API_KEY
        or settings.OPENAI_API_KEY
    )
    if not api_key or api_key.startswith("your_") or "placeholder" in api_key:
        return None, None, "mock"

    api_key = api_key.strip("'\"")

    if api_key.startswith("gsk_"):
        base_url = "https://api.groq.com/openai/v1"
        model = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")
    elif api_key.startswith("xai-"):
        base_url = "https://api.x.ai/v1"
        model = os.getenv("LLM_MODEL", "grok-2-latest")
    else:
        base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    return api_key, base_url, model


def call_llm(
    messages: List[Dict[str, str]],
    tools: Optional[List[Dict[str, Any]]] = None,
    mock_response: Optional[LLMResult] = None,
) -> LLMResult:
    """
    Executes an LLM chat completion with tool calling.
    Falls back gracefully to mock behavior during testing or if no API key is provided.
    """
    if mock_response:
        return mock_response

    if os.getenv("ENVIRONMENT") == "test" or settings.ENVIRONMENT == "test":
        # Heuristic mock for tests
        last_user_msg = ""
        for m in reversed(messages):
            if m["role"] == "user":
                last_user_msg = m["content"].lower()
                break

        if "create task" in last_user_msg or "new task" in last_user_msg:
            return LLMResult(
                content="I have prepared a proposal to create this task.",
                tool_calls=[{
                    "id": "call_mock_1",
                    "type": "function",
                    "function": {
                        "name": "create_task",
                        "arguments": json.dumps({"title": "Mock Generated Task", "priority": "high"})
                    }
                }],
                input_tokens=150,
                output_tokens=40,
                model="test-mock-agent",
            )
        elif "list" in last_user_msg:
            return LLMResult(
                content="Here are the tasks.",
                tool_calls=[{
                    "id": "call_mock_list",
                    "type": "function",
                    "function": {
                        "name": "list_tasks",
                        "arguments": "{}"
                    }
                }],
                input_tokens=120,
                output_tokens=30,
                model="test-mock-agent",
            )
        else:
            return LLMResult(
                content="Hello! I am TaskPilot AI. How can I help you organize your tasks today?",
                tool_calls=[],
                input_tokens=100,
                output_tokens=25,
                model="test-mock-agent",
            )

    api_key, base_url, model = get_llm_config()
    if not api_key:
        return LLMResult(
            content="API key not configured. Please provide a valid GROQ_API_KEY or OPENAI_API_KEY in backend/.env.",
            model="none",
        )

    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools or TOOL_DEFINITIONS,
        tool_choice="auto",
    )
    choice = resp.choices[0]
    raw_calls = []
    if choice.message.tool_calls:
        for tc in choice.message.tool_calls:
            raw_calls.append({
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
            })

    usage = resp.usage
    return LLMResult(
        content=choice.message.content or "",
        tool_calls=raw_calls,
        input_tokens=usage.prompt_tokens if usage else 0,
        output_tokens=usage.completion_tokens if usage else 0,
        model=model,
    )

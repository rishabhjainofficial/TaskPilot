import os
import json
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

BASE_SYSTEM_PROMPT = (
    "You are a friendly task-planning assistant. "
    "If the user describes things they need to do, call suggest_tasks "
    "with clear, actionable tasks. If a task is larger or involves multiple steps, "
    "break it down into smaller subtasks (subtasks are optional for simple tasks). Otherwise, reply normally."
)

TOOLS = [{
    "type": "function",
    "function": {
        "name": "suggest_tasks",
        "description": "Turn the user's request into actionable tasks with optional subtasks",
        "parameters": {
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                            "subtasks": {
                                "type": "array",
                                "description": "Optional list of smaller subtasks if the task is complex or has multiple steps",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "title": {"type": "string"}
                                    },
                                    "required": ["title"]
                                }
                            }
                        },
                        "required": ["title"],
                    },
                }
            },
            "required": ["tasks"],
        },
    },
}]

def is_duplicate_task(suggested_title: str, existing_titles: list[str]) -> bool:
    if not existing_titles or not suggested_title:
        return False

    clean_s = re.sub(r"[^\w\s]", "", suggested_title.lower()).strip()
    words_s = set(clean_s.split())
    if not words_s:
        return False

    for existing in existing_titles:
        clean_e = re.sub(r"[^\w\s]", "", existing.lower()).strip()
        if clean_s == clean_e:
            return True
        words_e = set(clean_e.split())
        if words_s == words_e:
            return True
        # Match slight variations like "renew passport" vs "renew your passport"
        if words_s.issubset(words_e) and len(words_e - words_s) <= 1:
            return True
        if words_e.issubset(words_s) and len(words_s - words_e) <= 1:
            return True
    return False

def build_system_prompt(existing_tasks: list[str] | None = None) -> str:
    prompt = BASE_SYSTEM_PROMPT
    if existing_tasks:
        task_bullets = "\n".join(f"- {t}" for t in existing_tasks if t.strip())
        if task_bullets:
            prompt += (
                f"\n\nExisting tasks already saved on the user's list:\n{task_bullets}\n\n"
                "CRITICAL RULE: Do NOT suggest any task that is already on this list or essentially the same. "
                "Only suggest NEW tasks. If all tasks mentioned are already present on the list, "
                "do not call suggest_tasks; reply conversationally that those tasks are already saved."
            )
    return prompt

def get_llm_config():
    api_key = (
        os.getenv("GROQ_API_KEY")
        or os.getenv("GROK_API_KEY")
        or os.getenv("XAI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    if not api_key or api_key.startswith("your_") or "placeholder" in api_key:
        return None, None, None

    # Strip quotes if wrapped in quotes in .env
    api_key = api_key.strip("'\"")

    # Auto-detect provider based on key prefix or explicit settings
    if api_key.startswith("gsk_"):
        # Free Groq API
        base_url = os.getenv("LLM_BASE_URL") or os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1"
        model = os.getenv("LLM_MODEL") or os.getenv("GROQ_MODEL") or "openai/gpt-oss-20b"
    elif api_key.startswith("xai-"):
        # xAI Grok API
        base_url = os.getenv("LLM_BASE_URL") or os.getenv("XAI_BASE_URL") or "https://api.x.ai/v1"
        model = os.getenv("LLM_MODEL") or os.getenv("GROK_MODEL") or "grok-2-latest"
    else:
        # Default fallback
        base_url = os.getenv("LLM_BASE_URL") or os.getenv("GROQ_BASE_URL") or os.getenv("XAI_BASE_URL") or "https://api.groq.com/openai/v1"
        model = os.getenv("LLM_MODEL") or os.getenv("GROQ_MODEL") or os.getenv("GROK_MODEL") or "openai/gpt-oss-20b"

    return api_key, base_url, model

def _init_client():
    api_key, base_url, _ = get_llm_config()
    if api_key:
        return OpenAI(api_key=api_key, base_url=base_url)
    return None

client = _init_client()

def run_agent(history: list[dict], existing_tasks: list[str] | None = None) -> dict:
    global client
    api_key, base_url, model = get_llm_config()

    if not api_key and client is None:
        return {
            "reply": "API Key is not configured. Please add your Groq/Grok API key in backend/.env.",
            "suggested_tasks": []
        }

    if client is None:
        client = OpenAI(api_key=api_key, base_url=base_url)

    target_model = model or "openai/gpt-oss-20b"
    system_prompt = build_system_prompt(existing_tasks)
    messages = [{"role": "system", "content": system_prompt}] + history

    resp = client.chat.completions.create(
        model=target_model,
        messages=messages,
        tools=TOOLS
    )
    msg = resp.choices[0].message

    if msg.tool_calls:
        args = json.loads(msg.tool_calls[0].function.arguments)
        raw_tasks = args.get("tasks", [])

        # Filter out tasks that are already in the user's task list
        if existing_tasks:
            filtered_tasks = [
                t for t in raw_tasks
                if not is_duplicate_task(t.get("title", ""), existing_tasks)
            ]
        else:
            filtered_tasks = raw_tasks

        # If all suggested tasks were already present in tasks
        if not filtered_tasks and raw_tasks:
            return {
                "reply": "You already have those tasks on your list!",
                "suggested_tasks": []
            }

        return {
            "reply": "Here are some tasks I'd suggest. Add the ones you want:",
            "suggested_tasks": filtered_tasks,
        }
    return {"reply": msg.content or "", "suggested_tasks": []}

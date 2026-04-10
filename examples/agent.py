"""
XSOAR AI Agent — interactive command-line interface.

Supports 13 AI providers out of the box.

Usage:
    pip install "xsoar-mcp[agent]"
    cd examples
    python agent.py

Environment variables (.env):
    XSOAR_URL        - XSOAR server address
    XSOAR_API_KEY    - XSOAR API key
    XSOAR_VERIFY_SSL - SSL verification (true/false)

    # Set these for your chosen provider, or select interactively at startup:
    AI_PROVIDER  - openai | azure | claude | gemini | groq | mistral |
                   together | deepseek | perplexity | xai | cohere |
                   ollama | lmstudio
    AI_API_KEY   - API key for the selected provider
    AI_MODEL     - Model name (optional, defaults are provided per provider)
    AI_BASE_URL  - Only needed for azure, ollama, lmstudio
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
from openai import OpenAI
from xsoar_mcp.client import XSOARClient
from xsoar_tools import TOOLS, execute_tool

load_dotenv()

# ── Provider registry ─────────────────────────────────────────────────────────
# (name, label, base_url, default_model, api_key_hint, api_key_url)
PROVIDERS = {
    "openai":      ("OpenAI",          "https://api.openai.com/v1",                                          "gpt-4o",                              "OPENAI_API_KEY",      "https://platform.openai.com/api-keys"),
    "azure":       ("Azure OpenAI",    None,                                                                  "gpt-4o",                              "AZURE_API_KEY",       "https://portal.azure.com"),
    "claude":      ("Claude",          None,                                                                  "claude-sonnet-4-6",                   "ANTHROPIC_API_KEY",   "https://console.anthropic.com/settings/keys"),
    "gemini":      ("Google Gemini",   "https://generativelanguage.googleapis.com/v1beta/openai",            "gemini-2.0-flash",                    "GEMINI_API_KEY",      "https://aistudio.google.com/app/apikey"),
    "groq":        ("Groq",            "https://api.groq.com/openai/v1",                                     "llama-3.3-70b-versatile",             "GROQ_API_KEY",        "https://console.groq.com/keys"),
    "mistral":     ("Mistral AI",      "https://api.mistral.ai/v1",                                          "mistral-large-latest",                "MISTRAL_API_KEY",     "https://console.mistral.ai/api-keys"),
    "together":    ("Together AI",     "https://api.together.xyz/v1",                                        "meta-llama/Llama-3-70b-chat-hf",      "TOGETHER_API_KEY",    "https://api.together.ai/settings/api-keys"),
    "deepseek":    ("DeepSeek",        "https://api.deepseek.com/v1",                                        "deepseek-chat",                       "DEEPSEEK_API_KEY",    "https://platform.deepseek.com/api_keys"),
    "perplexity":  ("Perplexity AI",   "https://api.perplexity.ai",                                          "llama-3.1-sonar-large-128k-online",   "PERPLEXITY_API_KEY",  "https://www.perplexity.ai/settings/api"),
    "xai":         ("xAI (Grok)",      "https://api.x.ai/v1",                                                "grok-3-mini",                         "XAI_API_KEY",         "https://console.x.ai"),
    "cohere":      ("Cohere",          "https://api.cohere.com/compatibility/v1",                            "command-r-plus",                      "COHERE_API_KEY",      "https://dashboard.cohere.com/api-keys"),
    "ollama":      ("Ollama (local)",  os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/v1",       "llama3.3",                            None,                  "https://ollama.com"),
    "lmstudio":    ("LM Studio (local)", os.environ.get("LMSTUDIO_URL", "http://localhost:1234") + "/v1",   "local-model",                         None,                  "https://lmstudio.ai"),
}

PROVIDER_LIST = list(PROVIDERS.keys())

SYSTEM_PROMPT = """You are a security operations assistant managing Palo Alto Cortex XSOAR.
Use the provided tools for incident management, IOC investigation, and playbook execution.

Rules:
- For destructive or irreversible actions (closing, deleting incidents), ask the user for confirmation first.
- Present tool results in a clear, summarized format.
- On error, inform the user and suggest an alternative.
"""


# ── Claude adapter ────────────────────────────────────────────────────────────
# Claude uses a different API format. This adapter converts messages/tools
# to Anthropic format and normalizes the response back to OpenAI shape,
# so the main agent loop needs no changes.

class ClaudeAdapter:
    def __init__(self, api_key: str, model: str):
        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            print("ERROR: 'anthropic' package not installed.")
            print("Run: pip install anthropic")
            sys.exit(1)
        self.model = model

    def _convert_tools(self, tools):
        return [
            {"name": t["function"]["name"],
             "description": t["function"]["description"],
             "input_schema": t["function"]["parameters"]}
            for t in tools
        ]

    def _convert_messages(self, messages):
        system = ""
        converted = []
        i = 0
        while i < len(messages):
            msg = messages[i]
            if msg["role"] == "system":
                system = msg["content"]
                i += 1
                continue
            if msg["role"] == "tool":
                # Collect consecutive tool results into one user message
                tool_blocks = []
                while i < len(messages) and messages[i]["role"] == "tool":
                    m = messages[i]
                    tool_blocks.append({"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]})
                    i += 1
                converted.append({"role": "user", "content": tool_blocks})
                continue
            if msg["role"] == "assistant" and msg.get("tool_calls"):
                content = []
                if msg.get("content"):
                    content.append({"type": "text", "text": msg["content"]})
                for tc in msg["tool_calls"]:
                    content.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": json.loads(tc["function"]["arguments"]),
                    })
                converted.append({"role": "assistant", "content": content})
                i += 1
                continue
            converted.append({"role": msg["role"], "content": msg["content"]})
            i += 1
        return system, converted

    def chat_completions_create(self, messages, tools):
        """Returns an OpenAI-compatible response object (as a dict)."""
        system, converted = self._convert_messages(messages)
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=converted,
            tools=self._convert_tools(tools),
        )
        # Normalize to OpenAI shape
        text = ""
        tool_calls = []
        for block in resp.content:
            if block.type == "text":
                text = block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "type": "function",
                    "function": {"name": block.name, "arguments": json.dumps(block.input)},
                })
        return _FakeResponse(text, tool_calls)


class _FakeResponse:
    """Thin OpenAI-compatible wrapper around a Claude response."""
    def __init__(self, content, tool_calls):
        self.choices = [_FakeChoice(content, tool_calls)]


class _FakeChoice:
    def __init__(self, content, tool_calls):
        self.message = _FakeMessage(content, tool_calls)


class _FakeMessage:
    def __init__(self, content, tool_calls):
        self.content = content or None
        self.tool_calls = [_FakeTool(tc) for tc in tool_calls] if tool_calls else None


class _FakeTool:
    def __init__(self, tc):
        self.id = tc["id"]
        self.function = _FakeFunction(tc["function"]["name"], tc["function"]["arguments"])


class _FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


# ── Provider selection ────────────────────────────────────────────────────────

def select_provider() -> tuple:
    """Interactive provider menu. Returns (provider_key, ai_client, model)."""
    # Check .env first
    env_provider = os.environ.get("AI_PROVIDER", "").lower()
    if env_provider in PROVIDERS:
        return _build_client(env_provider)

    print("\nSelect AI provider:")
    for i, key in enumerate(PROVIDER_LIST, 1):
        label, _, default_model, _, key_url = PROVIDERS[key]
        print(f"  [{i:>2}] {label:<20}  (default model: {default_model})")

    print()
    choice = input("Choice (number or name): ").strip().lower()

    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(PROVIDER_LIST):
            provider = PROVIDER_LIST[idx]
        else:
            print("Invalid choice, defaulting to openai.")
            provider = "openai"
    elif choice in PROVIDERS:
        provider = choice
    else:
        print(f"Unknown provider '{choice}', defaulting to openai.")
        provider = "openai"

    return _build_client(provider)


def _build_client(provider: str):
    label, base_url, default_model, env_key_name, key_url = PROVIDERS[provider]
    model = os.environ.get("AI_MODEL", default_model)

    print(f"  -> Provider: {label}  |  Model: {model}")

    # Claude: use dedicated adapter
    if provider == "claude":
        api_key = os.environ.get("AI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            api_key = input(f"  Enter Anthropic API key ({key_url}): ").strip()
        return provider, ClaudeAdapter(api_key, model), model

    # Azure: needs custom base_url from env
    if provider == "azure":
        base_url = os.environ.get("AI_BASE_URL") or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        if not base_url:
            base_url = input("  Enter Azure OpenAI endpoint URL: ").strip()

    # All OpenAI-compatible providers
    api_key = os.environ.get("AI_API_KEY", "")
    if not api_key and env_key_name:
        api_key = os.environ.get(env_key_name, "")
    if not api_key and env_key_name:
        api_key = input(f"  Enter API key ({key_url}): ").strip()
    if not api_key:
        api_key = "no-key-needed"  # ollama / lmstudio

    client = OpenAI(base_url=base_url, api_key=api_key)
    return provider, client, model


# ── Agent loop ────────────────────────────────────────────────────────────────

def run_agent_loop(provider: str, ai_client, model: str, xsoar: XSOARClient):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    print("\n" + "=" * 60)
    print("  XSOAR AI Agent")
    print("  Type 'exit' or press Ctrl+C to quit")
    print("=" * 60)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if user_input.lower() in ("exit", "quit"):
            print("Goodbye!")
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        while True:
            # Claude uses adapter; all others use OpenAI SDK directly
            if provider == "claude":
                response = ai_client.chat_completions_create(messages, TOOLS)
            else:
                response = ai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                )

            msg = response.choices[0].message
            messages.append(_msg_to_dict(msg))

            if not msg.tool_calls:
                print(f"\nAI: {msg.content}")
                break

            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                print(f"\n[Tool: {tool_name}({_fmt_args(args)})]")
                result = execute_tool(tool_name, args, xsoar)
                print("[Done]")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })


def _msg_to_dict(msg) -> dict:
    d = {"role": "assistant"}
    if msg.content:
        d["content"] = msg.content
    if msg.tool_calls:
        d["tool_calls"] = [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls
        ]
    return d


def _fmt_args(args: dict) -> str:
    return ", ".join(f"{k}={repr(v)[:30]}" for k, v in args.items())


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    missing = [v for v in ("XSOAR_URL", "XSOAR_API_KEY") if not os.environ.get(v)]
    if missing:
        print(f"ERROR: Missing environment variables: {', '.join(missing)}")
        print("See .env.example for a template.")
        return

    xsoar = XSOARClient()
    provider, ai_client, model = select_provider()
    run_agent_loop(provider, ai_client, model, xsoar)


if __name__ == "__main__":
    main()

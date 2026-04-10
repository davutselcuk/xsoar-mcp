"""
XSOAR AI Agent — interactive command-line interface.

Usage:
    pip install "xsoar-mcp[agent]"
    cd examples
    python agent.py

Environment variables (.env file):
    XSOAR_URL        - XSOAR server address
    XSOAR_API_KEY    - XSOAR API key
    XSOAR_VERIFY_SSL - SSL verification (true/false)
    AI_BASE_URL      - OpenAI-compatible API base URL
    AI_API_KEY       - AI API key
    AI_MODEL         - Model name to use
"""

import os
import sys
import json

# Allow running directly from this directory
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
from openai import OpenAI
from xsoar_mcp.client import XSOARClient
from xsoar_tools import TOOLS, execute_tool

load_dotenv()

SYSTEM_PROMPT = """You are a security operations assistant managing Palo Alto Cortex XSOAR.
Use the provided tools for incident management, IOC investigation, and playbook execution.

Important rules:
- For destructive or irreversible actions (closing, deleting incidents), ask the user for confirmation first.
- Present tool results in a clear, summarized format.
- On error, inform the user and suggest an alternative.
"""


def run_agent_loop(ai_client: OpenAI, xsoar: XSOARClient, model: str):
    """Main agent loop: user message → AI → tool call → XSOAR → AI → response."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    print("=" * 60)
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

        # Agentic loop: continue while AI is calling tools
        while True:
            response = ai_client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
            )

            msg = response.choices[0].message
            messages.append(msg)

            # No tool call → respond to user
            if not msg.tool_calls:
                print(f"\nAI: {msg.content}")
                break

            # Process tool calls
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                print(f"\n[Tool call: {tool_name}({_fmt_args(args)})]")
                result = execute_tool(tool_name, args, xsoar)
                print("[Result received]")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })


def _fmt_args(args: dict) -> str:
    parts = [f"{k}={repr(v)[:30]}" for k, v in args.items()]
    return ", ".join(parts)


def main():
    missing = []
    for var in ("XSOAR_URL", "XSOAR_API_KEY", "AI_BASE_URL", "AI_API_KEY", "AI_MODEL"):
        if not os.environ.get(var):
            missing.append(var)

    if missing:
        print(f"ERROR: Missing environment variables: {', '.join(missing)}")
        print("See .env.example for a template.")
        return

    ai_client = OpenAI(
        base_url=os.environ["AI_BASE_URL"],
        api_key=os.environ["AI_API_KEY"],
    )
    model = os.environ["AI_MODEL"]
    xsoar = XSOARClient()

    run_agent_loop(ai_client, xsoar, model)


if __name__ == "__main__":
    main()

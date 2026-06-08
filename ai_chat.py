import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from util.combine_sql_util import CombineSqlUtil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
TOOLS_PATH = os.path.join(BASE_DIR, "config", "tools.json")

load_dotenv(ENV_PATH)

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", ""),
    base_url=os.getenv("OPENAI_BASE_URL", "https://xcode.best/v1"),
)
sql_util = CombineSqlUtil()

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

# Session history keyed by websocket session id.
session_history = {}

with open(TOOLS_PATH, "r", encoding="utf-8") as f:
    TOOLS = json.load(f)

TOOL_NAMES = [
    tool.get("function", {}).get("name")
    for tool in TOOLS
    if tool.get("function", {}).get("name")
]

SYSTEM_PROMPT = " ".join(
    [
        "\u4f60\u662f\u4e00\u4e2a\u56fe\u5c42\u6570\u636e\u67e5\u8be2\u52a9\u624b\uff0c\u53ea\u80fd\u5e2e\u7528\u6237\u67e5\u8be2\u56fe\u5c42\u76f8\u5173\u7684\u6570\u636e\u3002",
        "\u652f\u6301\u7684\u529f\u80fd\u6709\uff1a\u67e5\u8be2\u6240\u6709\u56fe\u5c42\u5217\u8868\u3001\u67e5\u8be2\u6307\u5b9a\u56fe\u5c42\u7684\u6570\u636e\u6761\u6570\u3001\u67e5\u8be2\u6307\u5b9a\u56fe\u5c42\u7684\u6570\u636e\u5217\u8868\u3001\u67e5\u8be2\u6307\u5b9a\u56fe\u5c42\u4e2d\u67d0\u6761\u6570\u636e\u7684\u8be6\u60c5\u3002",
        "\u91cd\u8981\uff1a\u5982\u679c\u9700\u8981\u67e5\u8be2\u6570\u636e\uff0c\u76f4\u63a5\u8c03\u7528\u5de5\u5177\uff0c\u4e0d\u8981\u8bf4'\u6211\u4f1a\u67e5\u8be2'\u6216'\u63a5\u4e0b\u6765\u67e5\u8be2'\u7b49\u8bdd\u3002",
        "\u67e5\u8be2\u5b8c\u6210\u5c31\u76f4\u63a5\u8f93\u51fa\u7ed3\u679c\u3002",
    ]
)


def _serialize_assistant_message(message):
    payload = {"role": "assistant"}

    if message.content is not None:
        payload["content"] = message.content

    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": tool_call.type,
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in message.tool_calls
        ]

    return payload


def _extract_text(content):
    if isinstance(content, str):
        return content

    if not content:
        return ""

    texts = []
    for part in content:
        part_type = part.get("type") if isinstance(part, dict) else getattr(part, "type", None)
        if part_type != "text":
            continue

        text_value = part.get("text") if isinstance(part, dict) else getattr(part, "text", "")
        if isinstance(text_value, str):
            texts.append(text_value)
        elif hasattr(text_value, "value"):
            texts.append(text_value.value)

    return "".join(texts)


def execute_tool(name: str, arguments: dict) -> str:
    """Execute a configured SQL tool and return JSON text."""
    try:
        if name in TOOL_NAMES:
            tool_config = None
            for tool in TOOLS:
                if tool.get("function", {}).get("name") == name:
                    tool_config = tool["function"]["parameters"]
                    break

            if not tool_config:
                return json.dumps({"error": f"Tool config not found: {name}"})

            param = {}
            properties = tool_config.get("properties", {})

            for prop_name, prop_config in properties.items():
                if prop_name == "sqls":
                    param["sqls"] = arguments.get("sqls", prop_config.get("default", []))
                    continue

                default_value = prop_config.get("default")
                if prop_name in arguments:
                    param[prop_name] = arguments[prop_name]
                elif default_value is not None:
                    param[prop_name] = default_value

            result = sql_util.execute_combine_sql(param)
            return json.dumps(result, ensure_ascii=False)

        return json.dumps({"error": f"Unknown tool: {name}"})
    except Exception as e:
        print(f"Tool execution error: {e}")
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


async def chat_stream(user_message: str, send_func, session_id: str = "default"):
    """
    Stream chat responses with tool calling and per-session context.

    send_func: async callback used to push chunks to the websocket client.
    session_id: conversation key for multi-user websocket sessions.
    """
    try:
        if session_id not in session_history:
            session_history[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

        messages = session_history[session_id].copy()
        messages.append({"role": "user", "content": user_message})

        final_response_text = ""
        completed_in_non_stream = False

        max_iterations = 5
        for iteration in range(max_iterations):
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                stream=False,
                max_tokens=2000,
                temperature=0.7,
            )

            message = response.choices[0].message
            messages.append(_serialize_assistant_message(message))

            if not message.tool_calls:
                final_response_text = _extract_text(message.content)
                if final_response_text:
                    await send_func(final_response_text)
                completed_in_non_stream = True
                break

            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)

                print(f"[Function Calling {iteration + 1}] {func_name}({func_args})")

                tool_desc = ""
                for tool in TOOLS:
                    if tool.get("function", {}).get("name") == func_name:
                        tool_desc = tool["function"].get("description", "")
                        break

                await send_func(f"\n\n[Tool] {func_name}: {tool_desc}\n\n")

                tool_result = execute_tool(func_name, func_args)
                print(f"[Function Result {iteration + 1}] {tool_result}")

                messages.append(
                    {
                        "role": "tool",
                        "content": tool_result,
                        "tool_call_id": tool_call.id,
                    }
                )

        if not completed_in_non_stream:
            stream_response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                stream=True,
                max_tokens=2000,
                temperature=0.7,
            )

            for chunk in stream_response:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                reasoning_text = getattr(delta, "reasoning_content", None)
                if reasoning_text:
                    await send_func(f"[THINKING]{reasoning_text}")

                content = getattr(delta, "content", None)
                if content:
                    final_response_text += content
                    await send_func(content)

        messages.append({"role": "assistant", "content": final_response_text})
        session_history[session_id] = messages

        if len(session_history[session_id]) > 21:
            session_history[session_id] = [session_history[session_id][0]] + session_history[session_id][-20:]

    except Exception as e:
        print(f"chat_stream error: {e}")
        await send_func(f"Service error: {str(e)}")

    await send_func("[DONE]")

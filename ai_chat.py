import os
import json
from zai import ZhipuAiClient
from dotenv import load_dotenv
from db import query_layer_count

load_dotenv()

client = ZhipuAiClient(api_key=os.getenv("ZHIPU_API_KEY", ""))

MODEL = "glm-5"
# MODEL = "glm-4-flash"


# Function Calling 工具定义
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_layer_count",
            "description": "查询指定图层（如网吧、加油站、学校）的数据总条数",
            "parameters": {
                "type": "object",
                "properties": {
                    "layerName": {
                        "type": "string",
                        "description": "图层名称，例如：网吧、加油站、学校"
                    }
                },
                "required": ["layerName"]
            }
        }
    }
]


def execute_tool(name: str, arguments: dict) -> str:
    """执行工具调用，返回结果字符串"""
    if name == "query_layer_count":
        result = query_layer_count(arguments.get("layerName", ""))
        return json.dumps(result, ensure_ascii=False)
    return json.dumps({"error": f"未知工具: {name}"})


async def chat_stream(user_message: str, send_func):
    """
    流式聊天，支持 Function Calling。
    send_func: 异步回调，用于逐块推送内容给客户端
    """
    messages = [{"role": "user", "content": user_message}]

    # 第一次请求：非流式，检测是否触发 Function Calling
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        stream=False
    )

    message = response.choices[0].message
    messages.append(message.model_dump())

    # 处理 Function Calling
    if message.tool_calls:
        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)

            print(f"[Function Calling] {func_name}({func_args})")
            tool_result = execute_tool(func_name, func_args)
            print(f"[Function Result] {tool_result}")

            messages.append({
                "role": "tool",
                "content": tool_result,
                "tool_call_id": tool_call.id
            })

        # 第二次请求：流式，让模型根据工具结果组织回复
        stream_response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            stream=True
        )
        for chunk in stream_response:
            delta = chunk.choices[0].delta
            if delta.content:
                await send_func(delta.content)

    else:
        # 无 Function Calling，直接流式输出
        stream_response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            stream=True
        )
        for chunk in stream_response:
            delta = chunk.choices[0].delta
            if delta.content:
                await send_func(delta.content)

    # 发送结束标志
    await send_func("[DONE]")

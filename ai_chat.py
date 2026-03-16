import os
import json
from zai import ZhipuAiClient
from dotenv import load_dotenv
from util.combine_sql_util import CombineSqlUtil

load_dotenv()

client = ZhipuAiClient(api_key=os.getenv("ZHIPU_API_KEY", ""))
sql_util = CombineSqlUtil()

MODEL = "glm-5"
# MODEL = "glm-4-flash"

# 从配置文件加载工具定义
with open("config/tools.json", "r", encoding="utf-8") as f:
    TOOLS = json.load(f)


def execute_tool(name: str, arguments: dict) -> str:
    """执行工具调用，返回结果字符串"""
    try:
        if name in ["query_layer_count", "query_layer_data", "query_all_layers"]:
            # 从 TOOLS 配置中获取默认值
            default_sqls = []
            default_limit = None
            for tool in TOOLS:
                if tool.get("function", {}).get("name") == name:
                    default_sqls = tool["function"]["parameters"]["properties"]["sqls"]["default"]
                    limit_prop = tool["function"]["parameters"]["properties"].get("limit", {})
                    default_limit = limit_prop.get("default")
                    break
            
            param = {
                "layerName": arguments.get("layerName", ""),
                "sqls": arguments.get("sqls", default_sqls)
            }
            
            # 如果配置中有 limit 默认值，则添加到参数中
            if default_limit is not None:
                param["limit"] = arguments.get("limit", default_limit)
            
            result = sql_util.execute_combine_sql(param)
            return json.dumps(result, ensure_ascii=False)
        return json.dumps({"error": f"未知工具: {name}"})
    except Exception as e:
        print(f"执行工具异常: {e}")
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


async def chat_stream(user_message: str, send_func):
    """
    流式聊天，支持 Function Calling。
    send_func: 异步回调，用于逐块推送内容给客户端
    """
    try:
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
                if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                    await send_func(f"[THINKING]{delta.reasoning_content}")
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
                if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                    await send_func(f"[THINKING]{delta.reasoning_content}")
                if delta.content:
                    await send_func(delta.content)

    except Exception as e:
        print(f"chat_stream 异常: {e}")
        await send_func(f"服务异常: {str(e)}")

    # 发送结束标志
    await send_func("[DONE]")

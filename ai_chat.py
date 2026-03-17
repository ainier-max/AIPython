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

# 会话历史管理
session_history = {}

# 从配置文件加载工具定义
with open("config/tools.json", "r", encoding="utf-8") as f:
    TOOLS = json.load(f)

# 从配置中动态获取所有工具名称
TOOL_NAMES = [tool.get("function", {}).get("name") for tool in TOOLS if tool.get("function", {}).get("name")]


def execute_tool(name: str, arguments: dict) -> str:
    """执行工具调用，返回结果字符串"""
    try:
        if name in TOOL_NAMES:
            # 从 TOOLS 配置中获取工具定义
            tool_config = None
            for tool in TOOLS:
                if tool.get("function", {}).get("name") == name:
                    tool_config = tool["function"]["parameters"]
                    break
            
            if not tool_config:
                return json.dumps({"error": f"未找到工具配置: {name}"})
            
            # 动态构建 param，遍历 properties
            param = {}
            properties = tool_config.get("properties", {})
            
            for prop_name, prop_config in properties.items():
                if prop_name == "sqls":
                    # sqls 特殊处理，使用默认值
                    param["sqls"] = arguments.get("sqls", prop_config.get("default", []))
                else:
                    # 其他参数从 arguments 获取，如果有 default 则使用默认值
                    default_value = prop_config.get("default")
                    if prop_name in arguments:
                        param[prop_name] = arguments[prop_name]
                    elif default_value is not None:
                        param[prop_name] = default_value
                    elif prop_name in arguments:
                        param[prop_name] = arguments[prop_name]
            
            result = sql_util.execute_combine_sql(param)
            return json.dumps(result, ensure_ascii=False)
        return json.dumps({"error": f"未知工具: {name}"})
    except Exception as e:
        print(f"执行工具异常: {e}")
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


async def chat_stream(user_message: str, send_func, session_id: str = "default"):
    """
    流式聊天，支持 Function Calling 和上下文管理。
    send_func: 异步回调，用于逐块推送内容给客户端
    session_id: 会话ID，用于区分不同用户的对话历史
    """
    try:
        # 获取或初始化会话历史
        if session_id not in session_history:
            session_history[session_id] = [
                {
                    "role": "system",
                    "content": "你是一个图层数据查询助手，只能帮用户查询图层相关的数据。支持的功能有：查询所有图层列表、查询指定图层的数据条数、查询指定图层的数据列表、查询指定图层中某条数据的详情。如果用户的问题与图层数据查询无关，请友好地告知用户：'抱歉，我只支持图层数据相关的查询，暂不支持该问题。'不要尝试回答无关问题。"
                }
            ]
        
        messages = session_history[session_id].copy()
        messages.append({"role": "user", "content": user_message})

        # 第一次请求：非流式，检测是否触发 Function Calling
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            stream=False,
            max_tokens=2000,
            temperature=0.7
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
                stream=True,
                max_tokens=2000,
                temperature=0.7
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
                stream=True,
                max_tokens=2000,
                temperature=0.7
            )
            for chunk in stream_response:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                    await send_func(f"[THINKING]{delta.reasoning_content}")
                if delta.content:
                    await send_func(delta.content)

        # 保存用户消息和 AI 回复到历史
        session_history[session_id].append({"role": "user", "content": user_message})
        if message.tool_calls:
            # 有工具调用，保存完整的 messages
            session_history[session_id].append(message.model_dump())
            for msg in messages[len(session_history[session_id]):]:
                if msg.get("role") in ["tool", "assistant"]:
                    session_history[session_id].append(msg)
        else:
            # 无工具调用，保存 AI 回复
            session_history[session_id].append({"role": "assistant", "content": message.content or ""})
        
        # 限制历史长度，保留最近 10 轮对话
        if len(session_history[session_id]) > 21:  # system + 10轮(user+assistant)
            session_history[session_id] = [session_history[session_id][0]] + session_history[session_id][-20:]

    except Exception as e:
        print(f"chat_stream 异常: {e}")
        await send_func(f"服务异常: {str(e)}")

    # 发送结束标志
    await send_func("[DONE]")

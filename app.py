import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from ai_chat import chat_stream

app = FastAPI(title="AI Chat Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/api/ai/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket 连接建立")
    
    # 为每个连接生成唯一会话ID
    import uuid
    session_id = str(uuid.uuid4())
    
    try:
        while True:
            user_message = await websocket.receive_text()
            print(f"收到消息: {user_message}")

            async def send(text: str):
                await websocket.send_text(text)

            await chat_stream(user_message, send, session_id)

    except WebSocketDisconnect:
        print("WebSocket 连接断开")
    except Exception as e:
        print(f"WebSocket 错误: {e}")
        try:
            await websocket.send_text(f"Error: {str(e)}")
            await websocket.send_text("[DONE]")
        except Exception:
            pass


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8088, reload=True)

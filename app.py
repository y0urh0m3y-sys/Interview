import os
import gc
import time
import asyncio
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 8 AI Models Fallback Chain (Fastest to Backup)
AI_MODELS = [
    {"provider": "groq", "model": "llama-3.3-70b-versatile", "url": "https://api.groq.com/openai/v1/chat/completions", "key": os.getenv("GROQ_API_KEY")},
    {"provider": "groq", "model": "llama-3.1-8b-instant", "url": "https://api.groq.com/openai/v1/chat/completions", "key": os.getenv("GROQ_API_KEY")},
    {"provider": "groq", "model": "mixtral-8x7b-32768", "url": "https://api.groq.com/openai/v1/chat/completions", "key": os.getenv("GROQ_API_KEY")},
    {"provider": "groq", "model": "gemma2-9b-it", "url": "https://api.groq.com/openai/v1/chat/completions", "key": os.getenv("GROQ_API_KEY")},
    {"provider": "cerebras", "model": "llama3.1-70b", "url": "https://api.cerebras.ai/v1/chat/completions", "key": os.getenv("CEREBRAS_API_KEY")},
    {"provider": "openrouter", "model": "meta-llama/llama-3.1-8b-instruct:free", "url": "https://openrouter.ai/api/v1/chat/completions", "key": os.getenv("OPENROUTER_API_KEY")},
    {"provider": "openrouter", "model": "mistralai/mistral-7b-instruct:free", "url": "https://openrouter.ai/api/v1/chat/completions", "key": os.getenv("OPENROUTER_API_KEY")},
    {"provider": "openrouter", "model": "google/gemma-2-9b-it:free", "url": "https://openrouter.ai/api/v1/chat/completions", "key": os.getenv("OPENROUTER_API_KEY")},
]

SYSTEM_PROMPT = """
You are Prince Kumar from Meerut, Uttar Pradesh, appearing in a live online job interview.
Profile:
- Education: MBA from AKTU (2022), BBA from CCS University (2020).
- Skills: MS Excel, MS Word, Email Writing, Communication.
- Target Role: Customer Servicing & Project Management (Fresher, quick learner, responsible, flexible).

Strict Rules to sound 100% human and avoid AI detection:
1. Never use robotic AI words ('delve', 'tapestry', 'crucial', 'moreover', 'furthermore', 'testament').
2. Speak in natural, polite Indian corporate English. Use simple spoken transitions like 'Honestly,', 'Actually,', 'From my experience,'.
3. If tag is [INTERVIEWER], answer the question directly in first-person ('I', 'my') within 30 to 45 words.
4. If tag is [CANDIDATE_FIX], rewrite Prince's rough/broken English or Hinglish into fluent, confident spoken English keeping his exact intended meaning.
5. Output ONLY the exact spoken words. No quotes, no markdown, no labels.
"""

async def ram_cleaner():
    while True:
        await asyncio.sleep(30)
        gc.collect()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(ram_cleaner())

async def get_ai_response(user_text: str, mode: str) -> dict:
    prompt = f"[{mode.upper()}] {user_text}"
    start_time = time.time()
    
    async with httpx.AsyncClient(timeout=6.0) as client:
        for idx, bot in enumerate(AI_MODELS):
            if not bot["key"]:
                continue
            try:
                headers = {
                    "Authorization": f"Bearer {bot['key']}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": bot["model"],
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.5,
                    "max_tokens": 120
                }
                res = await client.post(bot["url"], json=payload, headers=headers)
                if res.status_code == 200:
                    reply = res.json()["choices"][0]["message"]["content"].strip().replace('"', '')
                    gc.collect()
                    return {
                        "reply": reply,
                        "model": f"M{idx+1}:{bot['model']}",
                        "latency": round(time.time() - start_time, 2)
                    }
            except Exception:
                continue

    return {
        "reply": "Sorry, could you please repeat that once? My audio dipped slightly.",
        "model": "Fallback",
        "latency": round(time.time() - start_time, 2)
    }

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/health")
async def health_check():
    return {"status": "online", "models": len(AI_MODELS)}

@app.websocket("/ws/interview")
async def interview_socket(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            text = data.get("text", "").strip()
            mode = data.get("mode", "INTERVIEWER")
            if text and len(text) > 2:
                result = await get_ai_response(text, mode)
                await websocket.send_json(result)
    except WebSocketDisconnect:
        gc.collect()

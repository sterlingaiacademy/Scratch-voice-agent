import os
import uuid
import base64
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from google.cloud import texttospeech
from debate_agent import DebateAgent

app = FastAPI(title="GForce Debate Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)
app.mount("/static", StaticFiles(directory="static"), name="static")

tts_client = texttospeech.TextToSpeechClient()
sessions: dict[str, DebateAgent] = {}

def text_to_speech(text: str) -> str:
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-IN",
        name="en-IN-Neural2-B",
        ssml_gender=texttospeech.SsmlVoiceGender.MALE,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.05,
        pitch=0.0
    )
    response = tts_client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config
    )
    return base64.b64encode(response.audio_content).decode("utf-8")

class RespondRequest(BaseModel):
    session_id: str
    text: str

@app.get("/")
async def home():
    return FileResponse("static/index.html")

@app.post("/session/start")
async def start_session():
    sid = str(uuid.uuid4())[:8]
    agent = DebateAgent(session_id=sid)
    sessions[sid] = agent
    opening = agent.get_opening()
    audio = text_to_speech(opening)
    return {"session_id": sid, "text": opening, "audio": audio}

@app.post("/session/respond")
async def respond(req: RespondRequest):
    agent = sessions.get(req.session_id)
    if not agent:
        raise HTTPException(404, "Session not found")
    reply = agent.respond(req.text)
    audio = text_to_speech(reply)
    return {"text": reply, "audio": audio, "round": agent.round}

@app.get("/session/summary/{session_id}")
async def get_summary(session_id: str):
    agent = sessions.get(session_id)
    if not agent:
        raise HTTPException(404, "Session not found")
    summary = agent.get_summary()
    audio = text_to_speech(summary)
    return {
        "summary": summary,
        "audio": audio,
        "total_rounds": agent.round,
        "transcript": agent.history
    }

@app.delete("/session/{session_id}")
async def end_session(session_id: str):
    if session_id in sessions:
        del sessions[session_id]
    return {"message": "Session ended"}

@app.get("/health")
async def health():
    return {"status": "ok", "active_sessions": len(sessions)}

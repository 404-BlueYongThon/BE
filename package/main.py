"""
Emergency AI Call Server - Twilio Media Streams + Gemini Live API

Architecture:
  NestJS → POST /broadcast → Twilio calls hospitals → <Connect><Stream> → WebSocket
  Each hospital call creates a Twilio WebSocket → this server → Gemini Live session
  Gemini AI briefs the hospital, confirms accept/reject via Function Calling
  Results are sent back to NestJS via POST callback

Audio pipeline:
  Twilio (mulaw 8kHz) → decode → resample 16kHz → Gemini Live (PCM 16kHz)
  Gemini Live (PCM 24kHz) → resample 8kHz → encode mulaw → Twilio
"""

import asyncio
import audioop
import base64
import json
import logging
import os
import uuid

import httpx
import numpy as np
## samplerate removed — numpy interp used instead (no C compiler needed)
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Response, WebSocket
from pydantic import BaseModel
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import VoiceResponse
from google import genai
from google.genai import types

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("emergency-ai")
logging.getLogger("websockets").setLevel(logging.WARNING)

app = FastAPI(title="Emergency AI Call Server")

# --- Configuration ---
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")
BASE_URL = os.getenv("BASE_URL")  # e.g. your-server.com (no https://)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_ID = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-native-audio-latest")

twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
gemini_client = genai.Client(api_key=GOOGLE_API_KEY)

# --- In-memory state ---
# emergency_batches[emergency_id] = { "data": req_data, "results": {hospital_id: status}, "is_finalized": bool }
emergency_batches: dict = {}
# active_calls[call_sid] = { "hospital_id": int, "emergency_id": str }
active_calls: dict = {}

# --- System prompt for the AI agent ---
SYSTEM_PROMPT = """당신은 응급 의료 상황실의 AI 전화 요원입니다. 병원에 전화를 걸어 응급 환자의 수용 여부를 확인하는 역할입니다.

행동 규칙:
1. 전화가 연결되면 즉시 환자 상태를 간결하게 브리핑합니다.
2. 병원 측의 응답을 듣고 수용 여부를 파악합니다.
3. 수용 의사를 표현하면: "수용 확정하겠습니다. 맞으시죠?" 라고 더블체크합니다. 확인되면 update_hospital_decision 도구를 status='accepted'로 호출합니다.
4. 거절 의사를 표현하면: "네 알겠습니다. 혹시 간단히 사유를 여쭤봐도 될까요?" 라고 물어봅니다. 사유를 핵심 단어로 요약하여 update_hospital_decision 도구를 status='rejected'로 호출합니다.
5. 애매한 응답이면 한 번만 재확인합니다. ("수용 가능하신 건가요, 아니면 어려우신 건가요?")
6. 도구 호출 후에는 짧은 인사("감사합니다")와 함께 대화를 마무리합니다.

말투:
- 간결하고 전문적인 어조를 유지합니다.
- 한국어로 대화합니다.
- 불필요한 잡담은 하지 않습니다.
"""

# --- Function declaration for Gemini Live ---
DECISION_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="update_hospital_decision",
            description="병원의 최종 수용/거절 결정을 기록합니다. 반드시 병원 측의 명확한 의사 확인 후 호출하세요.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "status": types.Schema(
                        type="STRING",
                        description="병원의 결정. 'accepted' (수용) 또는 'rejected' (거절)",
                        enum=["accepted", "rejected"],
                    ),
                    "reason": types.Schema(
                        type="STRING",
                        description="거절 시 사유를 핵심 단어로 요약 (예: '병상부족', '전문의부재'). 수용 시 빈 문자열.",
                    ),
                },
                required=["status"],
            ),
        )
    ]
)


# --- Pydantic models ---
class Hospital(BaseModel):
    hospitalId: int
    phone: str


class EmergencyRequest(BaseModel):
    hospitals: list[Hospital]
    patientId: int
    age: str
    sex: str
    category: str
    symptom: str
    remarks: str
    grade: int
    callback_url: str


# --- Business logic (from backup.py) ---
async def update_hospital_decision(
    emergency_id: str, hospital_id: int, status: str, reason: str = ""
):
    """Process hospital decision and trigger batch result if needed."""
    batch = emergency_batches.get(emergency_id)
    if not batch or batch["is_finalized"]:
        return "already_processed"

    batch["results"][hospital_id] = {"status": status, "reason": reason}
    logger.info(f"[Decision] Hospital {hospital_id}: {status} (reason: {reason})")

    if status == "accepted":
        asyncio.create_task(send_batch_result(emergency_id))
        asyncio.create_task(terminate_others(emergency_id))
    elif status == "rejected":
        all_responded = all(
            isinstance(v, dict) for v in batch["results"].values()
        )
        if all_responded:
            asyncio.create_task(send_batch_result(emergency_id))

    return f"{status} recorded"


async def send_batch_result(emergency_id: str):
    """Send all hospital results to NestJS callback."""
    batch = emergency_batches.get(emergency_id)
    if not batch or batch["is_finalized"]:
        return
    batch["is_finalized"] = True

    payload = {
        "patientId": batch["data"]["patientId"],
        "results": [
            {"hospitalId": h_id, "status": res["status"]}
            if isinstance(res, dict)
            else {"hospitalId": h_id, "status": "no_answer"}
            for h_id, res in batch["results"].items()
        ],
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                batch["data"]["callback_url"], json=payload, timeout=5.0
            )
            logger.info(
                f"[Callback] Sent to NestJS: {resp.status_code} for {emergency_id}"
            )
        except Exception as e:
            logger.error(f"[Callback] Failed: {e}")


async def terminate_others(emergency_id: str):
    """Hang up all other calls in the same emergency batch."""
    for sid in list(active_calls.keys()):
        info = active_calls.get(sid)
        if info and info["emergency_id"] == emergency_id:
            try:
                twilio_client.calls(sid).update(status="completed")
                del active_calls[sid]
                logger.info(f"[Terminate] Hung up call {sid}")
            except Exception as e:
                logger.warning(f"[Terminate] Failed for {sid}: {e}")


# --- Endpoints ---
@app.post("/broadcast")
async def start_broadcast(req: EmergencyRequest):
    """Start calling hospitals in parallel (called by NestJS)."""
    emergency_id = str(uuid.uuid4())
    emergency_batches[emergency_id] = {
        "data": req.dict(),
        "results": {h.hospitalId: "calling" for h in req.hospitals},
        "is_finalized": False,
    }
    logger.info(
        f"[Broadcast] ID: {emergency_id}, {len(req.hospitals)} hospitals"
    )

    for hospital in req.hospitals:
        try:
            target_url = (
                f"https://{BASE_URL}/voice-twiml"
                f"?emergency_id={emergency_id}"
                f"&hospital_id={hospital.hospitalId}"
            )
            call = twilio_client.calls.create(
                to=hospital.phone,
                from_=TWILIO_NUMBER,
                url=target_url,
                method="POST",
            )
            active_calls[call.sid] = {
                "hospital_id": hospital.hospitalId,
                "emergency_id": emergency_id,
            }
            logger.info(f"[Call] {hospital.phone} -> SID: {call.sid}")
        except Exception as e:
            emergency_batches[emergency_id]["results"][hospital.hospitalId] = {
                "status": "failed",
                "reason": str(e),
            }
            logger.error(f"[Call] Failed {hospital.phone}: {e}")

    return {"status": "processing", "emergency_id": emergency_id}


@app.post("/voice-twiml")
async def voice_twiml(emergency_id: str, hospital_id: int):
    """Return TwiML that connects the call to our WebSocket for Media Streams."""
    response = VoiceResponse()
    connect = response.connect()
    stream = connect.stream(url=f"wss://{BASE_URL}/media-stream")
    stream.parameter(name="emergency_id", value=emergency_id)
    stream.parameter(name="hospital_id", value=str(hospital_id))
    return Response(content=response.to_xml(), media_type="application/xml")


# --- Audio conversion utilities ---
def _resample_numpy(arr_float: np.ndarray, ratio: float) -> np.ndarray:
    """Resample using numpy linear interpolation (no C library needed)."""
    n_in = len(arr_float)
    if n_in == 0:
        return arr_float
    n_out = int(n_in * ratio)
    if n_out == 0:
        return np.array([], dtype=np.float32)
    x_old = np.linspace(0, 1, n_in)
    x_new = np.linspace(0, 1, n_out)
    return np.interp(x_new, x_old, arr_float).astype(np.float32)


def mulaw_to_pcm_16k(chunk_ulaw: bytes) -> bytes:
    """Convert mulaw 8kHz to PCM 16-bit 16kHz."""
    # mulaw -> PCM 16-bit 8kHz
    pcm_8k = audioop.ulaw2lin(chunk_ulaw, 2)
    # Resample 8kHz -> 16kHz
    arr_8k = np.frombuffer(pcm_8k, dtype=np.int16)
    arr_float = arr_8k.astype(np.float32) / 32768.0
    arr_16k = _resample_numpy(arr_float, ratio=2.0)
    result = (arr_16k * 32767).astype(np.int16)
    return result.tobytes()


def pcm_24k_to_mulaw(chunk_pcm: bytes) -> bytes:
    """Convert PCM 16-bit 24kHz to mulaw 8kHz."""
    # Resample 24kHz -> 8kHz
    arr_24k = np.frombuffer(chunk_pcm, dtype=np.int16)
    arr_float = arr_24k.astype(np.float32) / 32768.0
    arr_8k = _resample_numpy(arr_float, ratio=(8000.0 / 24000.0))
    pcm_8k = (arr_8k * 32767).astype(np.int16).tobytes()
    # PCM -> mulaw
    return audioop.lin2ulaw(pcm_8k, 2)


# --- WebSocket: 3-task architecture ---
async def handle_twilio_to_gemini(
    websocket: WebSocket,
    audio_in_q: asyncio.Queue,
    call_state: dict,
):
    """Task 1: Receive Twilio audio, convert mulaw→PCM, push to queue."""
    async for message_str in websocket.iter_text():
        try:
            msg = json.loads(message_str)

            if msg["event"] == "start":
                params = msg["start"].get("customParameters", {})
                call_state["stream_sid"] = msg["start"]["streamSid"]
                call_state["emergency_id"] = params.get("emergency_id")
                call_state["hospital_id"] = int(params.get("hospital_id", 0))
                call_state["active"] = True
                logger.info(
                    f"[Stream] Started: hospital={call_state['hospital_id']}"
                )

            elif msg["event"] == "media":
                if not call_state.get("active"):
                    continue
                chunk_ulaw = base64.b64decode(msg["media"]["payload"])
                pcm_16k = mulaw_to_pcm_16k(chunk_ulaw)
                await audio_in_q.put(pcm_16k)

            elif msg["event"] == "stop":
                call_state["active"] = False
                logger.info("[Stream] Stopped")
                break

        except Exception as e:
            logger.error(f"[Twilio→Gemini] Error: {e}")
            break


async def handle_gemini_to_twilio(
    websocket: WebSocket,
    audio_out_q: asyncio.Queue,
    call_state: dict,
):
    """Task 2: Receive Gemini audio from queue, convert PCM→mulaw, send to Twilio."""
    while True:
        try:
            chunk_pcm = await asyncio.wait_for(audio_out_q.get(), timeout=1.0)
            if chunk_pcm and call_state.get("active"):
                mulaw_data = pcm_24k_to_mulaw(chunk_pcm)
                payload = base64.b64encode(mulaw_data).decode("utf-8")
                sid = call_state.get("stream_sid")
                if sid:
                    await websocket.send_json(
                        {
                            "event": "media",
                            "streamSid": sid,
                            "media": {"payload": payload},
                        }
                    )
        except asyncio.TimeoutError:
            if not call_state.get("active", True):
                break
        except Exception as e:
            logger.error(f"[Gemini→Twilio] Error: {e}")
            continue


async def conversation_loop(
    audio_in_q: asyncio.Queue,
    audio_out_q: asyncio.Queue,
    call_state: dict,
):
    """Task 3: Manage Gemini Live session — send audio, receive audio + tool calls."""
    # Wait for Twilio stream to start
    while not call_state.get("active"):
        await asyncio.sleep(0.1)

    emergency_id = call_state["emergency_id"]
    hospital_id = call_state["hospital_id"]
    batch = emergency_batches.get(emergency_id)

    if not batch:
        logger.error(f"[Gemini] No batch found for {emergency_id}")
        return

    # Build initial briefing text
    data = batch["data"]
    sex_kr = "남성" if data["sex"] == "male" else "여성"
    intro_text = (
        f"병원에 전화가 연결되었습니다. 다음 내용으로 브리핑하세요: "
        f"{data['age']} {sex_kr} 환자, "
        f"증상: {data['category']} - {data['symptom']}, "
        f"KTAS {data['grade']}등급. "
        f"특이사항: {data['remarks']}. "
        f"수용 가능 여부를 확인해 주세요."
    )

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=SYSTEM_PROMPT,
        tools=[DECISION_TOOL],
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                disabled=False,
                start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
                end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                prefix_padding_ms=20,
                silence_duration_ms=500,
            )
        ),
    )

    try:
        async with gemini_client.aio.live.connect(
            model=MODEL_ID, config=config
        ) as session:
            logger.info(
                f"[Gemini] Connected for hospital {hospital_id}"
            )

            # Send initial briefing — this triggers the AI to start speaking
            await session.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[types.Part(text=intro_text)],
                ),
                turn_complete=True,
            )
            logger.info(f"[Gemini] Briefing sent: {intro_text[:80]}...")

            # --- Sender: push audio from queue to Gemini ---
            async def sender():
                while call_state.get("active"):
                    try:
                        chunk = await asyncio.wait_for(
                            audio_in_q.get(), timeout=0.5
                        )
                        await session.send_realtime_input(
                            audio=types.Blob(
                                data=chunk, mime_type="audio/pcm;rate=16000"
                            )
                        )
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        logger.error(f"[Sender] Error: {e}")
                        break

            # --- Receiver: get audio + tool calls from Gemini ---
            async def receiver():
                async for response in session.receive():
                    if not call_state.get("active"):
                        break

                    # Handle audio output
                    if sc := response.server_content:
                        if mt := sc.model_turn:
                            for part in mt.parts:
                                if id_data := part.inline_data:
                                    if id_data.mime_type and id_data.mime_type.startswith("audio/"):
                                        await audio_out_q.put(id_data.data)

                    # Handle function calls
                    if response.tool_call:
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            status = fc.args.get("status", "rejected")
                            reason = fc.args.get("reason", "")
                            logger.info(
                                f"[Tool] Hospital {hospital_id}: {status} ({reason})"
                            )
                            result = await update_hospital_decision(
                                emergency_id=emergency_id,
                                hospital_id=hospital_id,
                                status=status,
                                reason=reason,
                            )
                            fn_responses.append(
                                types.FunctionResponse(
                                    name=fc.name,
                                    id=fc.id,
                                    response={"result": result},
                                )
                            )
                        await session.send_tool_response(
                            function_responses=fn_responses
                        )

            # Run sender and receiver concurrently
            sender_task = asyncio.create_task(sender())
            receiver_task = asyncio.create_task(receiver())

            done, pending = await asyncio.wait(
                [sender_task, receiver_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()

    except asyncio.CancelledError:
        logger.info(f"[Gemini] Session cancelled for hospital {hospital_id}")
    except Exception as e:
        logger.error(f"[Gemini] Session error for hospital {hospital_id}: {e}")

    # If no decision was made (e.g. timeout), mark as no_answer
    batch = emergency_batches.get(emergency_id)
    if batch and not batch["is_finalized"]:
        current = batch["results"].get(hospital_id)
        if not isinstance(current, dict):
            batch["results"][hospital_id] = {
                "status": "no_answer",
                "reason": "call_ended_without_decision",
            }
            # Check if all hospitals responded
            all_responded = all(
                isinstance(v, dict) for v in batch["results"].values()
            )
            if all_responded:
                asyncio.create_task(send_batch_result(emergency_id))


# --- Main WebSocket endpoint ---
@app.websocket("/media-stream")
async def websocket_media_stream(websocket: WebSocket):
    """Bridge Twilio Media Stream to Gemini Live API."""
    await websocket.accept()
    logger.info("[WS] Twilio WebSocket connected")

    call_state = {"active": False, "stream_sid": None}
    audio_in_q: asyncio.Queue = asyncio.Queue()
    audio_out_q: asyncio.Queue = asyncio.Queue()

    tasks = [
        asyncio.create_task(
            handle_twilio_to_gemini(websocket, audio_in_q, call_state)
        ),
        asyncio.create_task(
            handle_gemini_to_twilio(websocket, audio_out_q, call_state)
        ),
        asyncio.create_task(
            conversation_loop(audio_in_q, audio_out_q, call_state)
        ),
    ]

    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        call_state["active"] = False
        for t in tasks:
            t.cancel()
        logger.info("[WS] Cleanup complete")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

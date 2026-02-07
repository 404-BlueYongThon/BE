import asyncio
import os
import uuid
import json
import base64
from fastapi import FastAPI, WebSocket, Response
from pydantic import BaseModel
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from google import genai
import httpx

load_dotenv()

# --- 1. 설정 ---
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER") 
BASE_URL = os.getenv("BASE_URL") # 예: my-app.ngrok-free.app (http 제거)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
genai_client = genai.Client(api_key=GOOGLE_API_KEY)
app = FastAPI()

emergency_batches = {}
active_calls = {}

class Hospital(BaseModel):
    id: int
    phone: str

class EmergencyRequest(BaseModel):
    hospitals: list[Hospital]
    age: str
    sex: str
    category: str
    symptom: str
    remarks: str
    grade: int
    callback_url: str

# --- 2. Gemini 도구(Function Calling) 정의 ---
async def update_hospital_decision(emergency_id: str, hospital_id: int, status: str, reason: str = None):
    """
    병원의 최종 결정을 기록합니다. 
    status: 'accepted' (수용), 'rejected' (거절)
    reason: 거절 시에만 기입하는 간단한 요약 사유
    """
    batch = emergency_batches.get(emergency_id)
    if not batch or batch["is_finalized"]:
        return "이미 처리된 요청입니다."

    # 데이터 업데이트
    batch["results"][hospital_id] = {"status": status, "reason": reason or ""}
    print(f"📍 [의사결정 기록] 병원 {hospital_id}: {status} / 사유: {reason}")

    if status == "accepted":
        # 승인 시 즉시 보고 및 타 병원 종료
        asyncio.create_task(send_batch_result(emergency_id))
        # 특정 CallSid를 알 수 없으므로 전체 종료 로직 활용 (함수 내에서 필터링)
        asyncio.create_task(terminate_others(emergency_id))
    
    elif status == "rejected":
        # 모든 병원이 응답했는지 체크
        all_responded = all(isinstance(v, dict) for v in batch["results"].values())
        if all_responded:
            asyncio.create_task(send_batch_result(emergency_id))
            
    return f"{status} 상태로 정상 기록되었습니다."

# --- 3. 핵심 비즈니스 로직 ---
async def send_batch_result(emergency_id: str):
    batch = emergency_batches.get(emergency_id)
    if not batch or batch["is_finalized"]: return
    batch["is_finalized"] = True
    
    payload = {
        "emergency_id": emergency_id,
        "results": [{"id": h_id, **res} if isinstance(res, dict) else {"id": h_id, "status": "no_answer"} 
                    for h_id, res in batch["results"].items()]
    }
    
    async with httpx.AsyncClient() as client:
        try:
            await client.post(batch["data"]["callback_url"], json=payload, timeout=5.0)
            print(f"📡 [최종 보고 완료] ID: {emergency_id}")
        except Exception as e:
            print(f"❌ [보고 실패] {e}")

async def terminate_others(emergency_id: str):
    for sid in list(active_calls.keys()):
        if active_calls[sid]["emergency_id"] == emergency_id:
            try:
                twilio_client.calls(sid).update(status="completed")
                del active_calls[sid]
            except: pass

# --- 4. 엔드포인트: 방송 시작 ---
@app.post("/broadcast")
async def start_broadcast(req: EmergencyRequest):
    emergency_id = str(uuid.uuid4())
    emergency_batches[emergency_id] = {
        "data": req.dict(),
        "results": {h.id: "calling" for h in req.hospitals},
        "is_finalized": False
    }

    for hospital in req.hospitals:
        try:
            # TwiML 주소에 정보를 담아 보냄
            target_url = f"https://{BASE_URL}/voice-twiml?emergency_id={emergency_id}&hospital_id={hospital.id}"
            call = twilio_client.calls.create(
                to=hospital.phone, from_=TWILIO_NUMBER, url=target_url, method="POST"
            )
            active_calls[call.sid] = {"hospital_id": hospital.id, "emergency_id": emergency_id}
        except Exception as e:
            print(f"❌ 발신 실패: {e}")

    return {"emergency_id": emergency_id}

# --- 5. TwiML: Media Stream 연결 ---
@app.post("/voice-twiml")
async def voice_twiml(emergency_id: str, hospital_id: int):
    response = VoiceResponse()
    connect = response.connect()
    # WebSocket 엔드포인트로 오디오 스트리밍 시작
    stream = connect.stream(url=f"wss://{BASE_URL}/media-stream")
    stream.parameter(name="emergency_id", value=emergency_id)
    stream.parameter(name="hospital_id", value=str(hospital_id))
    return Response(content=response.to_xml(), media_type="application/xml")

# --- 6. WebSocket: Gemini 실시간 대화 중계 ---
@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    await websocket.accept()
    print("✅ Twilio 웹소켓 연결됨")
    
    emergency_id, hospital_id, stream_sid = None, None, None

    # 모델명은 리스트에서 확인된 bidi 지원 모델을 유지합니다.
    async with genai_client.aio.live.connect(
        model="gemini-2.5-flash-native-audio-latest",
        config={
            "tools": [update_hospital_decision],
            "system_instruction": "당신은 응급 의료 상황실의 AI 요원입니다. 병원 측에 환자 상태를 브리핑하고 수용 여부를 확인하세요. 상대방이 수용하겠다고 하면 '수용 확정하겠습니다'라고 더블체크한 뒤 update_hospital_decision 도구를 호출하세요. 거절할 경우 반드시 거절 사유를 물어보고, 사유를 핵심 단어로 요약하여 도구를 호출하세요.",
            "generation_config": {
                "response_modalities": ["AUDIO"],
                "speech_config": {
                    "voice_config": {"prebuilt_voice_config": {"voice_name": "Aoede"}}
                }
            }
        }
    ) as session:

        async def send_to_gemini():
            nonlocal emergency_id, hospital_id, stream_sid
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    
                    if data['event'] == 'start':
                        stream_sid = data['start']['streamSid']
                        params = data['start']['customParameters']
                        emergency_id, hospital_id = params['emergency_id'], int(params['hospital_id'])
                        
                        # [수정 1] 첫 텍스트 전송: 리스트가 아닌 '순수 문자열'로 전달
                        batch_data = emergency_batches[emergency_id]["data"]
                        intro_text = f"응급 환자 발생. {batch_data['age']}세 {batch_data['sex']}, 증상은 {batch_data['symptom']}입니다. 수용 가능한가요?"
                        
                        # 명시적으로 input 키워드에 문자열만 전달
                        await session.send(input=intro_text, end_of_turn=True)
                        print(f"📢 브리핑 시작: {intro_text}")

                    elif data['event'] == 'media':
                        # [수정 2] 오디오 전송: mime_type에서 하이픈 제거 및 데이터 구조 단순화
                        # Twilio 오디오 페이로드를 base64 디코딩하여 바이너리로 전송
                        audio_data = base64.b64decode(data['media']['payload'])
                        await session.send(
                            input={
                                "data": audio_data,
                                "mime_type": "audio/mulaw"
                            }
                        )
            except Exception as e:
                print(f"❌ 송신 루프 오류: {e}")

        async def receive_from_gemini():
            try:
                # [수정 3] 비동기 제너레이터를 통한 안정적인 수신 루프
                async for response in session.receive():
                    if response.data:
                        # Gemini의 오디오 데이터를 Twilio가 이해하는 base64로 변환하여 전송
                        await websocket.send_json({
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {"payload": base64.b64encode(response.data).decode('utf-8')}
                        })
                    
                    # 도구 호출(Tool Calling) 발생 시 처리
                    if response.server_content and response.server_content.model_turn:
                        for part in response.server_content.model_turn.parts:
                            if part.call:
                                fn_call = part.call
                                args = {**dict(fn_call.args), "emergency_id": emergency_id, "hospital_id": hospital_id}
                                print(f"📞 Gemini가 함수 호출: {fn_call.name} -> {args['status']}")
                                
                                result = await update_hospital_decision(**args)
                                
                                # 실행 결과 환류 (이 과정이 있어야 AI가 대화를 마무리함)
                                await session.send(
                                    input=genai.types.LiveClientToolResponse(
                                        function_responses=[genai.types.LiveClientFunctionResponse(
                                            name=fn_call.name, id=fn_call.id, response={"result": result}
                                        )]
                                    )
                                )
            except Exception as e:
                print(f"❌ 수신 루프 오류: {e}")

        # 두 비동기 루프를 동시에 실행하여 전이중 통신(Full-duplex) 구현
        await asyncio.gather(send_to_gemini(), receive_from_gemini())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
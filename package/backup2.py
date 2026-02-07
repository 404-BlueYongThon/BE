import asyncio
import os
import uuid  # 고유 ID 생성을 위해 추가
import traceback
from fastapi import FastAPI, Request, Form, Response
from pydantic import BaseModel
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
import httpx

load_dotenv()

# --- 1. 설정 ---
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER") 
BASE_URL = os.getenv("BASE_URL")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
app = FastAPI()

# 여러 건의 방송을 동시에 처리하기 위해 딕셔너리로 변경
emergency_db = {}  # {emergency_id: 환자정보}
active_calls = {}  # {call_sid: 병원이름}
# 각 방송별 확정 상태 관리
dispatch_status = {} # {emergency_id: bool}

class Hospital(BaseModel):
    name: str
    phone: str

class EmergencyRequest(BaseModel):
    hospitals: list[Hospital]
    age: int
    gender: str
    symptoms: str
    severity: str
    eta: str
    callback_url: str  # <--- 결과를 받을 클라이언트 백엔드 API 주소

# --- 결과 전송용 비동기 함수 ---
async def send_result_to_client(callback_url: str, payload: dict):
    """클라이언트 백엔드로 최종 수용 결과를 전송합니다."""
    print(f"🚀 [결과 전송 시작] {callback_url}")
    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(callback_url, json=payload, timeout=10.0)
            print(f"✅ [결과 전송 완료] 상태코드: {res.status_code}")
        except Exception as e:
            print(f"❌ [결과 전송 실패] {e}")

# --- 로깅 미들웨어 생략 (기존과 동일) ---

# --- 2. [엔드포인트] 방송 시작 ---
@app.post("/broadcast")
async def start_broadcast(req: EmergencyRequest):
    global active_calls
    # 1. 고유 ID 생성 (클라이언트 백엔드가 여러 요청을 보낼 때 구분용)
    emergency_id = str(uuid.uuid4())
    
    # 2. 데이터 저장
    emergency_db[emergency_id] = req.dict()
    dispatch_status[emergency_id] = False
    
    print(f"📢 [방송 시작] ID: {emergency_id} / 환자: {req.age}세 {req.gender}")

    for hospital in req.hospitals:
        try:
            # Twilio가 접속할 때 emergency_id를 들고 오게 함
            target_url = f"{BASE_URL}/voice?emergency_id={emergency_id}"
            call = twilio_client.calls.create(
                to=hospital.phone,
                from_=TWILIO_NUMBER,
                url=target_url,
                method="POST"
            )
            active_calls[call.sid] = hospital.name
            print(f"📞 발신: {hospital.name}")
        except Exception as e:
            print(f"❌ {hospital.name} 실패: {e}")

    # 클라이언트에게는 즉시 접수 완료와 ID를 보냄
    return {"status": "processing", "emergency_id": emergency_id}

# --- 3. [TwiML] 전화 응답 ---
@app.post("/voice")
async def voice_response(emergency_id: str):
    try:
        response = VoiceResponse()
        data = emergency_db.get(emergency_id)

        if not data:
            response.say("정보가 만료되었습니다.", language='ko-KR')
        else:
            script = (
                f"응급상황 발생. {data['age']}세 {data['gender']} 환자 수용 문의드립니다. "
                f"주증상은 {data['symptoms']}이며, KTAS 단계는 {data['severity']}입니다. "
                f"수용 가능하시면 1번, 거부하시려면 2번을 눌러주세요."
            )
            # handle-gather 주소에도 ID를 전달
            gather = response.gather(
                num_digits=1, 
                action=f"/handle-gather?emergency_id={emergency_id}", 
                method="POST"
            )
            gather.say(script, language='ko-KR', voice='Polly.Seoyeon')
        
        return Response(content=response.to_xml(), media_type="application/xml")
    except Exception as e:
        print(traceback.format_exc())
        return Response(content="Error", status_code=500)

# --- 4. [엔드포인트] 키패드 입력 처리 ---
@app.post("/handle-gather")
async def handle_gather(emergency_id: str, Digits: str = Form(...), CallSid: str = Form(...)):
    hospital_name = active_calls.get(CallSid, "알 수 없는 병원")
    data = emergency_db.get(emergency_id)
    response = VoiceResponse()

    # 해당 방송이 아직 수락되지 않았고, 1번을 누른 경우
    if Digits == "1" and not dispatch_status.get(emergency_id):
        dispatch_status[emergency_id] = True
        print(f"✅ [수용 확정] {hospital_name} (ID: {emergency_id})")
        
        # 클라이언트 백엔드에 결과 전송 (비동기 호출)
        if data and data.get("callback_url"):
            payload = {
                "emergency_id": emergency_id,
                "status": "accepted",
                "accepted_hospital": hospital_name,
                "patient_info": {
                    "age": data["age"],
                    "symptoms": data["symptoms"]
                }
            }
            # 전화를 끊는 로직과 별개로 백그라운드에서 실행
            asyncio.create_task(send_result_to_client(data["callback_url"], payload))

        response.say(f"{hospital_name}으로 확정되었습니다. 감사합니다.", language='ko-KR', voice='Polly.Seoyeon')
        response.hangup()
        asyncio.create_task(terminate_others(CallSid))
    else:
        response.say("이미 마감되었거나 거절되었습니다.", language='ko-KR', voice='Polly.Seoyeon')
        response.hangup()

    return Response(content=response.to_xml(), media_type="application/xml")

# --- 5. 나머지 전화 종료 (기존과 동일) ---
async def terminate_others(exclude_sid):
    for sid in list(active_calls.keys()):
        if sid != exclude_sid:
            try:
                twilio_client.calls(sid).update(status="completed")
            except: pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
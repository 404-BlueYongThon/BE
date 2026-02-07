import asyncio
import os
import traceback
from fastapi import FastAPI, Request, Form
from pydantic import BaseModel
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from fastapi import Response
import httpx

load_dotenv()

# --- 1. 설정 (본인 정보로 수정) ---
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER") 
BASE_URL = os.getenv("BASE_URL")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
app = FastAPI()

emergency_db = {"current": None}
active_calls = {}
is_dispatched = False

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
    

# --- 로깅용 미들웨어 (모든 요청을 감시) ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"🔍 [접근 로그] {request.method} {request.url}")
    try:
        response = await call_next(request)
        print(f"✅ [응답 성공] 상태코드: {response.status_code}")
        return response
    except Exception as e:
        # 에러 발생 시 터미널에 아주 자세히 출력
        print("🚨🚨 [서버 내부 에러 발생] 🚨🚨")
        print(traceback.format_exc()) 
        return Response(content="Internal Server Error", status_code=500)

# --- 2. [엔드포인트] 방송 시작 ---
@app.post("/broadcast")
async def start_broadcast(req: EmergencyRequest):
    global is_dispatched, active_calls
    print(f"📢 [방송 시작] 환자 정보 수신: {req.age}세 {req.gender}")
    
    is_dispatched = False
    active_calls = {}
    emergency_db["current"] = req.dict()

    # broadcast 함수 내의 발신 부분을 이렇게 수정해서 로그를 보세요
    for hospital in req.hospitals:
        try:
            # Twilio에게 가라고 시키는 최종 주소 확인용 로그
            target_url = f"{BASE_URL}/voice"
            print(f"🚀 [발신 준비] Twilio가 접속할 주소: {target_url}")

            call = twilio_client.calls.create(
                to=hospital.phone,
                from_=TWILIO_NUMBER,
                url=target_url,
                method="POST"
            )
            # ... 이하 동일
            active_calls[call.sid] = hospital.name
            print(f"📞 발신 성공: {hospital.name} (SID: {call.sid})")
        except Exception as e:
            print(f"❌ {hospital.name} 발신 실패: {e}")

    return {"status": "success", "calls_count": len(active_calls)}

# --- 3. [TwiML] 전화 응답 ---
@app.post("/voice")
async def voice_response():
    print("📞 [Twilio 접속] /voice 엔드포인트에 Twilio가 들어왔습니다.")
    try:
        response = VoiceResponse()
        data = emergency_db.get("current")

        if not data:
            print("⚠️ [경고] emergency_db['current']가 비어있습니다!")
            response.say("환자 정보를 찾을 수 없습니다.", language='ko-KR')
        else:
            print(f"🎙️ [TTS 생성] {data['age']}세 {data['gender']} 데이터로 음성 생성 중")
            script = (
                f"응급상황 발생. {data['age']}세 {data['gender']} 환자 수용 문의드립니다. "
                f"주증상은 {data['symptoms']}이며, KTAS 단계는 {data['severity']}입니다. "
                f"수용 가능하시면 1번, 거부하시려면 2번을 눌러주세요."
            )
            gather = response.gather(num_digits=1, action="/handle-gather", method="POST")
            gather.say(script, language='ko-KR', voice='Polly.Seoyeon')
        
        xml_content = response.to_xml()
        print(f"📤 [응답 전송] 생성된 TwiML: {xml_content[:50]}...")
        return Response(content=xml_content, media_type="application/xml")
    
    except Exception as e:
        print("🚨 [/voice 에러 발생]")
        print(traceback.format_exc())
        return Response(content="Error in TwiML", status_code=500)

# --- 5. [엔드포인트] 키패드 입력 처리 ---
@app.post("/handle-gather")
async def handle_gather(Digits: str = Form(...), CallSid: str = Form(...)):
    print(f"🎯 [키패드 입력] 사용자가 {Digits}번을 눌렀습니다. (CallSid: {CallSid})")
    
    global is_dispatched
    # 전화 건 목록에서 병원 이름을 가져옴
    hospital_name = active_calls.get(CallSid, "알 수 없는 병원")
    response = VoiceResponse()

    try:
        if Digits == "1" and not is_dispatched:
            # 1번을 누른 경우: 수용 확정
            is_dispatched = True
            print(f"✅ [수용 확정] {hospital_name}에서 환자를 받기로 했습니다!")
            
            response.say(f"{hospital_name}으로 확정되었습니다. 즉시 준비 부탁드립니다. 감사합니다.", language='ko-KR', voice='Polly.Seoyeon')
            response.hangup()
            
            # 나머지 병원 전화는 즉시 끊기 (비동기 처리)
            asyncio.create_task(terminate_others(CallSid))
            
        elif Digits == "2":
            # 2번을 누른 경우: 거절
            print(f"❌ [수용 거절] {hospital_name}에서 수용을 거절했습니다.")
            response.say("수용 거절을 선택하셨습니다. 통화를 종료합니다.", language='ko-KR', voice='Polly.Seoyeon')
            response.hangup()
            
        else:
            # 이미 다른 곳에서 수락했거나 오입력
            print(f"⚠️ [처리 불가] 이미 다른 병원에서 수락했거나 잘못된 입력입니다.")
            response.say("죄송합니다. 이미 마감되었거나 잘못된 입력입니다.", language='ko-KR', voice='Polly.Seoyeon')
            response.hangup()

        return Response(content=response.to_xml(), media_type="application/xml")

    except Exception as e:
        print("🚨 [/handle-gather 에러 발생]")
        print(traceback.format_exc())
        return Response(content="Error processing input", status_code=500)

# --- 6. 나머지 전화 종료 함수 (이것도 꼭 있는지 확인!) ---
async def terminate_others(exclude_sid):
    print("📢 나머지 통화를 모두 종료합니다...")
    for sid in list(active_calls.keys()):
        if sid != exclude_sid:
            try:
                VoiceResponse("타 병원에서 환자가 수용되었습니다. 통화를 종료합니다.")
                twilio_client.calls(sid).update(status="completed")
                print(f"📴 통화 종료 시도: {sid}")
            except Exception as e:
                print(f"⚠️ 종료 실패 (이미 끊겼을 수 있음): {sid}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
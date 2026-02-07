import asyncio
import os
import uuid
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

# --- 데이터 관리 구조 ---
# emergency_batches: { emergency_id: { "data": req_data, "results": { hospital_id: status }, "is_finalized": bool } }
emergency_batches = {}
# active_calls: { call_sid: { "hospital_id": id, "emergency_id": eid } }
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
    callback_url: str  # 결과 보고를 받을 클라이언트 주소

# --- 결과 전송 함수 ---
async def send_batch_result(emergency_id: str):
    """배치 내 모든 병원의 응답 상태를 클라이언트 백엔드로 전송"""
    batch = emergency_batches.get(emergency_id)
    if not batch or batch["is_finalized"]:
        return

    batch["is_finalized"] = True
    payload = {
        "emergency_id": emergency_id,
        "results": [
            {"id": h_id, "status": status} 
            for h_id, status in batch["results"].items()
        ]
    }
    
    async with httpx.AsyncClient() as client:
        try:
            await client.post(batch["data"]["callback_url"], json=payload, timeout=5.0)
            print(f"📡 [최종 보고 완료] ID: {emergency_id}")
        except Exception as e:
            print(f"❌ [보고 실패] {e}")

# --- 2. [엔드포인트] 방송 시작 ---
@app.post("/broadcast")
async def start_broadcast(req: EmergencyRequest):
    emergency_id = str(uuid.uuid4())
    
    # 배치 초기화 (모든 병원의 초기 상태는 'calling')
    emergency_batches[emergency_id] = {
        "data": req.dict(),
        "results": {h.id: "no_answer" for h in req.hospitals},
        "is_finalized": False
    }

    print(f"📢 [새 배치 시작] ID: {emergency_id} / {len(req.hospitals)}개 병원")

    for hospital in req.hospitals:
        try:
            target_url = f"{BASE_URL}/voice?emergency_id={emergency_id}&hospital_id={hospital.id}"
            call = twilio_client.calls.create(
                to=hospital.phone,
                from_=TWILIO_NUMBER,
                url=target_url,
                method="POST"
            )
            active_calls[call.sid] = {"hospital_id": hospital.id, "emergency_id": emergency_id}
        except Exception as e:
            emergency_batches[emergency_id]["results"][hospital.id] = "failed"
            print(f"❌ ID {hospital.id} 발신 실패: {e}")

    return {"status": "processing", "emergency_id": emergency_id}

# --- 3. [TwiML] 전화 응답 ---
@app.post("/voice")
async def voice_response(emergency_id: str, hospital_id: int):
    response = VoiceResponse()
    batch = emergency_batches.get(emergency_id)

    if not batch or batch["is_finalized"]:
        response.say("이미 상황이 종료되었습니다.", language='ko-KR')
        return Response(content=response.to_xml(), media_type="application/xml")

    data = batch["data"]
    script = (
        f"응급 환자 발생. {data['age']}세 {'남성' if data['sex']=='male' else '여성'}, 증상은 {data['symptom']}이며 "
        f"케이티에이에스 {data['grade']}등급입니다. "
        f"특이사항으로는 {data['remarks']}가 있습니다. "
        f"수용 가능하면 1번, 수용할 수 없으면 2번을 눌러주세요."
    )
    
    gather = response.gather(
        num_digits=1, 
        action=f"/handle-gather?emergency_id={emergency_id}&hospital_id={hospital_id}", 
        method="POST"
    )
    gather.say(script, language='ko-KR', voice='Polly.Seoyeon')
    return Response(content=response.to_xml(), media_type="application/xml")

# --- 4. [엔드포인트] 키패드 입력 처리 ---
@app.post("/handle-gather")
async def handle_gather(emergency_id: str, hospital_id: int, Digits: str = Form(...), CallSid: str = Form(...)):
    batch = emergency_batches.get(emergency_id)
    response = VoiceResponse()

    if not batch or batch["is_finalized"]:
        response.say("종료된 요청입니다.", language='ko-KR')
        response.hangup()
        return Response(content=response.to_xml(), media_type="application/xml")

    if Digits == "1":
        # 승인 시: 해당 병원 'accepted' 처리 후 즉시 보고 및 나머지 종료
        batch["results"][hospital_id] = "accepted"
        print(f"✅ [ID {hospital_id}] 승인")
        response.say("수용 확정되었습니다. 감사합니다.", language='ko-KR')
        asyncio.create_task(send_batch_result(emergency_id))
        asyncio.create_task(terminate_others(emergency_id, CallSid))
    
    elif Digits == "2":
        # 거절 시: 해당 병원 'rejected' 처리
        batch["results"][hospital_id] = "rejected"
        print(f"❌ [ID {hospital_id}] 거절")
        response.say("거절 처리되었습니다.", language='ko-KR')
        
        # 모든 병원이 응답을 마쳤는지 확인 (모두 거절된 경우 보고)
        if all(status in ["rejected", "failed", "no_answer"] for status in batch["results"].values()):
            if not any(status == "calling" for status in batch["results"].values()):
                 asyncio.create_task(send_batch_result(emergency_id))

    response.hangup()
    return Response(content=response.to_xml(), media_type="application/xml")

async def terminate_others(emergency_id, exclude_sid):
    """동일 배치 내 다른 모든 전화 강제 종료 (수정 완료)"""
    # 딕셔너리 변경 에러 방지를 위해 list()로 감싸서 복사본으로 루프를 돕니다.
    for sid in list(active_calls.keys()):
        info = active_calls[sid]
        # 해당 사건(emergency_id)에 속한 전화이고, 수락한 전화(exclude_sid)가 아닌 경우만 종료
        if info["emergency_id"] == emergency_id and sid != exclude_sid:
            try:
                # 불필요한 VoiceResponse 코드는 삭제하고 즉시 종료 명령만 내립니다.
                twilio_client.calls(sid).update(status="completed")
                print(f"📴 타 병원 수락으로 인한 통화 종료: {sid}")
                # 종료된 호출은 목록에서 삭제
                del active_calls[sid]
            except Exception as e:
                print(f"⚠️ 통화 종료 시도 중 오류: {e}")
    print("📢 해당 배치의 나머지 통화 정리가 완료되었습니다.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
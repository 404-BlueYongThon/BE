import asyncio
import os
import httpx
from fastapi import FastAPI, Request, BackgroundTasks
from pydantic import BaseModel
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# 1. 초기 설정
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini_model = genai.GenerativeModel('gemini-pro')

app = FastAPI()

VAPI_KEY = os.getenv("VAPI_PRIVATE_KEY")
ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID")
VAPI_URL = "https://api.vapi.ai/call/phone"

# 실시간 상태 관리 
active_calls = {}  # {call_id: hospital_name}
is_dispatched = False
winning_hospital = None

# 2. 데이터 모델
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

# 3. 템플릿 기반 스크립트 생성
def generate_script(data: EmergencyRequest):
    # 정해진 양식에 변수만 삽입
    script = (
        f"응급상황 발생. {data.age}세 {data.gender} 환자 수용 문의드립니다. "
        f"주증상은 {data.symptoms}이며, 중증도는 {data.severity}입니다. "
        f"현재 위치에서 도착까지 약 {data.eta} 소요 예정입니다. "
        f"우물 정자를 누른 후, 수용 가능하시면 1번, 수용이 불가하시면 2번을 눌러주세요."
    )
    return script

# 4. 개별 병원 호출 함수 (비동기)
async def call_hospital(hospital: Hospital, script: str):
    headers = {"Authorization": f"Bearer {VAPI_KEY}", "Content-Type": "application/json"}
    payload = {
        "assistantId": ASSISTANT_ID,
        "customer": {"number": hospital.phone, "name": hospital.name},
        "assistantOverrides": {
            "firstMessage": script,
        }
    }
    
    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(VAPI_URL, json=payload, headers=headers)
            
            # --- 여기 디버깅 로그 추가 ---
            print(f"\n[DEBUG] 병원: {hospital.name}")
            print(f"[DEBUG] 응답 코드: {res.status_code}")
            print(f"[DEBUG] 응답 내용: {res.text}") 
            # --------------------------

            if res.status_code != 201:
                print(f"❌ Vapi 호출 실패 ({hospital.name}): {res.status_code}")
                return None, hospital.name

            call_data = res.json()
            return call_data.get("id"), hospital.name
        except Exception as e:
            print(f"Error calling {hospital.name}: {e}")
            return None, hospital.name

# 5. [엔드포인트 1] 병렬 방송 시작
@app.post("/broadcast")
async def start_broadcast(req: EmergencyRequest):
    global is_dispatched, winning_hospital, active_calls
    is_dispatched = False
    winning_hospital = None
    active_calls = {}

    # 멘트 생성
    script = generate_script(req)
    print(f"멘트: {script}")

    # 모든 병원에 동시에 전화 걸기 (Parallel)
    tasks = [call_hospital(h, script) for h in req.hospitals]
    results = await asyncio.gather(*tasks)

    # 호출 성공한 통화들 기록
    for call_id, name in results:
        if call_id:
            active_calls[call_id] = name

    return {"message": f"{len(active_calls)}곳의 병원에 병렬 호출을 시작했습니다."}

# 6. [엔드포인트 2] Vapi 결과 수신 (Webhook)
@app.post("/vapi-webhook")
async def handle_webhook(request: Request):
    global is_dispatched, winning_hospital
    
    data = await request.json()
    call_id = data.get("message", {}).get("call", {}).get("id")
    
    # Vapi 에이전트가 분석한 결과값 추출 (Vapi 대시보드 설정 필요)
    # 예: 에이전트가 "accepted" 상태를 감지했을 때
    analysis = data.get("message", {}).get("analysis", {}).get("structuredData", {})
    status = analysis.get("acceptance") # 'accepted' or 'rejected'

    if status == "accepted" and not is_dispatched:
        is_dispatched = True
        winning_hospital = active_calls.get(call_id)
        print(f"{winning_hospital}에서 환자를 수락했습니다.")

        # 나머지 모든 통화 종료 시도 (Background Task)
        asyncio.create_task(terminate_others(exclude_id=call_id))
        
        # 여기서 팀원(백엔드) API로 "최종 확정 병원" 정보를 쏴주면 됨
        return {"result": "confirmed", "hospital": winning_hospital}

    return {"status": "processing"}

async def terminate_others(exclude_id):
    """나머지 모든 통화 강제 종료"""
    headers = {"Authorization": f"Bearer {VAPI_KEY}"}
    async with httpx.AsyncClient() as client:
        for call_id in list(active_calls.keys()):
            if call_id != exclude_id:
                await client.post(f"https://api.vapi.ai/call/{call_id}/terminate", headers=headers)
    print("나머지 모든 통화를 종료했습니다.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


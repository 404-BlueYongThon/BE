import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

# 클라이언트 생성
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

print("--- 사용 가능한 모델 목록 ---")
# supported_methods를 supported_actions로 수정
for model in client.models.list():
    print(f"모델명: {model.name}")
    print(f"지원 액션: {model.supported_actions}")
    print("-" * 30)
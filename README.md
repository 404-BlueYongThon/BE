# 404 Found: Emergency AI Call System

![404 Found Banner](./assets/banner.png)

[![Vercel](https://img.shields.io/badge/Frontend-Vercel-success)](https://emergency-ai-call.log8.kr)
[![AWS](https://img.shields.io/badge/Backend-AWS-blue)](https://github.com/404-BlueYongThon/BE)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> 응급 환자를 위한 병원을, AI가 찾아드립니다

AI 음성 전화를 통해 여러 병원에 동시 연락하고 실시간으로 수용 가능한 응급실을 매칭하는 시스템입니다.

---

## Tech Stack

| Category | Technology | Version |
|----------|-----------|---------|
| **Framework** | NestJS | 11.0.0 |
| **Language** | TypeScript | 5.0+ |
| **AI & Voice** | Python FastAPI | 3.10+ |
| **Database** | MySQL (Prisma) | 8.4 |
| **Voice API** | Twilio | - |
| **Speech** | Google Cloud TTS/STT | - |
| **AI Model** | OpenAI GPT-4o | - |
| **Cloud** | AWS EC2, RDS | - |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                   │
│              emergency-ai-call.log8.kr                  │
└────────────────────┬────────────────────────────────────┘
                     │ HTTPS
┌────────────────────▼────────────────────────────────────┐
│                  Backend (NestJS)                       │
│                   AWS EC2                               │
├──────────────┬──────────────┬───────────────────────────┤
│ Voice Module │ Hospital API │ Emergency Manager         │
└──────┬───────┴──────┬───────┴───────────────────────────┘
       │              │
       ▼              ▼
┌─────────────┐  ┌────────────────────┐
│   Python    │  │      Database      │
│   FastAPI   │  │ query optimization │
├─────────────┤  ├────────────────────┤
│ - STT       │  │ - Distance         │
│ - TTS       │  │ - Priority         │
│ - GPT-4o    │  │                    │
└──────┬──────┘  └──────┬─────────────┘
       │                │
       └────────┬───────┘
                ▼
        ┌──────────────┐
        │    Twilio    │
        │  Voice API   │
        └──────┬───────┘
               │
               ▼
        ┌──────────────┐
        │   Hospitals  │
        └──────────────┘
```

---

## Getting Started

### Prerequisites

- Node.js >= 22
- Python >= 3.10
- Twilio Account
- Google Cloud Account (Speech API)

### Installation

```bash
# 1. Clone repository
git clone https://github.com/404-BlueYongThon/BE.git
cd BE

# 2. Install dependencies
npm install
pip install -r package/requirements.txt

# 3. Environment setup
cp .env.example .env
# Edit .env with your credentials

# 4. Database setup
npx prisma migrate dev
npx prisma generate
```

### Environment Variables

```env
# Database
DATABASE_URL=mysql://user:password@localhost:5432/emergency_db

# Twilio
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=xxxxx
TWILIO_NUMBER=+1xxxxxxxxxx

# Google Cloud (Speech API)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

---

## Project Structure

```
BE/
├── src/                   # NestJS Backend
│   ├── dto/               # 전달 객체
│   ├── app.controller.ts  # 병원 관리
│   ├── app.module.ts
│   ├── app.service.ts     # 응급 요청 관리
│   ├── emergency-sse.service.ts  
│   ├── prisma.ts
│   └── main.ts
│
├── package/               # Python & C++
│   ├── requirements.txt
│   └── twiliospeach.py   # Twilio 통합
│
├── prisma/                # Database Schema
│   └── schema.prisma
│
├── test/                  # Tests
└── README.md
```

---

## API Documentation

### 1. Emergency Request

```http
POST /api/emergency/broadcast
Content-Type: application/json

{
  "hospitals": [
    { "id": 1, "phone": "+821012345678" },
    { "id": 2, "phone": "+821087654321" }
  ],
  "age": "27",
  "sex": "male",
  "category": "trauma",
  "symptom": "복부 출혈",
  "remarks": "의식 명료, 활력 징후 안정",
  "grade": 2,
  "callback_url": "https://example.com/callback"
}
```

**Response:**
```json
{
    "success": true,
    "message": "매칭 프로세스가 시작되었습니다.",
    "patientId": 18,
    "channel": "patient-18"
}
```

### 2. Call Status

```http
POST /api/emergency/callback
```

**Response:**
```json
{
  "emergency_id": "c4a19f5c-2571-41a4-b5db-a56c5beb4a55",
  "patientId": 1,
  "results": [
    {
      "hospitalId": 1,
      "status": "accepted"
    },
    {
      "hospitalId": 2,
      "status": "rejected"
    },
    {
      "hospitalId": 3,
      "status": "no_answer"
    }
  ]
}
```

---

## Development

### Build

```bash
# NestJS
npm run build

# Python
python python twiliospeach.py


### Test

```bash
# Unit tests
npm run test

# E2E tests
npm run test:e2e

# Coverage
npm run test:cov
```

### Linting

```bash
npm run lint
npm run format
```

---

## Performance

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Hospital Matching Time | 10+ min | < 1 min | **90% ↓** |
| Call Efficiency | Sequential (avg 7 calls) | Parallel (10 calls) | **300% ↑** |
| Paramedic Workload | Patient + Calling | Patient Only | **50% ↓** |
| Golden Time Utilization | 10 min wasted | 9 min saved | **Survival Rate ↑** |

---

### Branch Strategy

- `main`: Production-ready code
- `dev`: Development integration
- `feature/<description>`: Feature branches

### Commit Convention

```
feat: Add new feature
fix: Bug fix
docs: Documentation updates
refactor: Code refactoring
test: Test updates
chore: Build/tooling changes
```

---

## Team

| Name | Role | GitHub |
|------|------|--------|
| 김덕환 | Full Stack | [@sweetheart](https://github.com/sweetheart) |
| 정현승 | Backend & Infra | [@cau20232907](https://github.com/cau20232907) |
| 김대준 | AI & Algorithm | [@maximum-0000](https://github.com/maximum-0000) |
| 최대영 | Backend | [@meojun](https://github.com/meojun) |

---

## License

MIT License - see [LICENSE](LICENSE) file

---

## Contact

- **Website**: [emergency-ai-call.log8.kr](https://emergency-ai-call.log8.kr)
- **Email**: sachi009955@gmail.com
- **Organization**: [@404-BlueYongThon](https://github.com/404-BlueYongThon)

---

## Acknowledgments

- **중앙대학교 청룡톤 2026**
- **UNIVERSITY MAKEUS CHALLENGE CAU**
- **Google Developer Groups (On Campus · Chung-Ang University)**

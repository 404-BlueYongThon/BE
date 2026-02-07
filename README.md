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
| **Framework** | NestJS | 10.x |
| **Language** | TypeScript | 5.0+ |
| **AI & Voice** | Python FastAPI | 3.10+ |
| **Algorithm** | C++ | 17+ |
| **Database** | PostgreSQL (Prisma) | 15.x |
| **Voice API** | Twilio | - |
| **Speech** | Google Cloud TTS/STT | - |
| **AI Model** | OpenAI GPT-4o | - |
| **Container** | Docker Compose | - |
| **Cloud** | AWS EC2, RDS, S3 | - |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                    │
│              emergency-ai-call.log8.kr                   │
└────────────────────┬────────────────────────────────────┘
                     │ HTTPS
┌────────────────────▼────────────────────────────────────┐
│                  Backend (NestJS)                        │
│                   AWS EC2 + Docker                       │
├──────────────┬──────────────┬──────────────────────────┤
│ Voice Module │ Hospital API │ Emergency Manager         │
└──────┬───────┴──────┬───────┴──────────────────────────┘
       │              │
       ▼              ▼
┌─────────────┐  ┌──────────────┐
│   Python    │  │     C++      │
│   FastAPI   │  │   Library    │
├─────────────┤  ├──────────────┤
│ - STT       │  │ - Distance   │
│ - TTS       │  │ - Priority   │
│ - GPT-4o    │  │ - Async      │
└──────┬──────┘  └──────┬───────┘
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

- Node.js >= 18
- Python >= 3.10
- Docker & Docker Compose
- Twilio Account
- Google Cloud Account (Speech API)
- OpenAI API Key

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

# 5. Run with Docker
docker-compose up
```

### Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/emergency_db

# Twilio
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=xxxxx
TWILIO_NUMBER=+1xxxxxxxxxx

# Google Cloud (Speech API)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# OpenAI
OPENAI_API_KEY=sk-xxxxx

# AWS
AWS_REGION=ap-northeast-2
AWS_ACCESS_KEY_ID=xxxxx
AWS_SECRET_ACCESS_KEY=xxxxx
```

---

## Project Structure

```
BE/
├── src/                    # NestJS Backend
│   ├── voice/             # Twilio 음성 처리
│   ├── hospital/          # 병원 관리
│   ├── emergency/         # 응급 요청 관리
│   ├── app.module.ts
│   └── main.ts
│
├── package/               # Python & C++
│   ├── ai/
│   │   ├── stt.py        # Google STT
│   │   ├── tts.py        # Google TTS
│   │   └── gpt.py        # GPT-4o
│   ├── hospital/
│   │   └── distance.cpp  # C++ 거리 계산
│   └── twiliospeach.py   # Twilio 통합
│
├── prisma/                # Database Schema
│   └── schema.prisma
│
├── test/                  # Tests
├── docker-compose.yml
├── Dockerfile
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
  "status": "processing",
  "emergency_id": "uuid-here"
}
```

### 2. Call Status

```http
GET /api/emergency/status/:emergency_id
```

**Response:**
```json
{
  "emergency_id": "uuid-here",
  "results": [
    { "hospital_id": 1, "status": "accepted" },
    { "hospital_id": 2, "status": "rejected" }
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
python -m compileall package/

# C++
cd package/hospital && g++ -o distance distance.cpp -std=c++17
```

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

## Deployment

### Docker

```bash
# Build images
docker-compose build

# Run containers
docker-compose up -d

# View logs
docker-compose logs -f

# Stop containers
docker-compose down
```

### AWS EC2

```bash
# 1. SSH to EC2 instance
ssh -i key.pem ubuntu@ec2-xx-xx-xx-xx.compute.amazonaws.com

# 2. Pull latest code
git pull origin main

# 3. Rebuild and restart
docker-compose up -d --build

# 4. Check status
docker-compose ps
```

---

## CI/CD

### GitHub Actions

- **CI**: PR 생성 시 자동 빌드 및 테스트
- **CD**: `main` 브랜치 머지 시 AWS EC2 자동 배포

`.github/workflows/ci.yml`:
```yaml
name: CI
on: [pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm install
      - run: npm run build
      - run: npm test
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

## Contributing

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

### Pull Request

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Create Pull Request

---

## Team

| Name | Role | GitHub |
|------|------|--------|
| 김덕환 | Full Stack | [@sweetheart](https://github.com/sweetheart) |
| 김대준 | Backend & Infra | [@cau20232907](https://github.com/cau20232907) |
| 정현승 | Backend | [@maximum-0000](https://github.com/maximum-0000) |
| 최대영 | AI & Algorithm | [@meojun](https://github.com/meojun) |

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

import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { prisma } from './prisma';
import { EmergencySseService } from './emergency-sse.service';

@Injectable()
export class AppService {
  private readonly logger = new Logger(AppService.name);

  constructor(
    private readonly sseService: EmergencySseService,
    private readonly configService: ConfigService,
  ) {}

  // 1. 환자가 매칭 요청을 보낼 때 호출
  async startMatching(
    age: string,
    sex: string,
    category: string,
    symptom: string,
    remarks: string,
    grade: number,
    lat: number,
    lng: number,
  ) {
    // DB에 환자 정보 생성
    const patient = await prisma.patient.create({
      data: {
        age,
        sex,
        category,
        symptom,
        remarks,
        grade,
        createdAt: new Date(),
      },
    });

    const patientId = patient.id;
    const patientChannel = `patient-${patientId}`;
    this.logger.log(`환자 생성 완료: ${patientChannel}`);

    // 근처 병원 조회 (거리순, 5개)
    const hospitals: any[] = await prisma.$queryRaw`
      SELECT id, name, number, latitude, longitude,
      ST_Distance_Sphere(point(longitude, latitude), point(${lng}, ${lat})) AS distance
      FROM hospital
      WHERE min_grade <= ${grade} AND max_grade >= ${grade}
      ORDER BY distance ASC
      LIMIT 5
    `;

    if (hospitals.length === 0) {
      return {
        success: false,
        message: '매칭 가능한 병원이 없습니다.',
        patientId,
        channel: patientChannel,
      };
    }

    // 각 병원에 대해 HospitalRequest 레코드 생성
    for (const hospital of hospitals) {
      await prisma.hospitalRequest.create({
        data: {
          patientId,
          hospitalId: hospital.id,
          accepted: null,
          createdAt: new Date(),
        },
      });
    }

    // AI 서버(localhost:8000)로 병원 + 환자 정보 전송
    const aiServerUrl = this.configService.get<string>('AI_SERVER_URL') || 'http://localhost:8000';
    const callbackBaseUrl = this.configService.get<string>('CALLBACK_BASE_URL') || 'http://localhost:3000';

    const payload = {
      hospitals: hospitals.map((h) => ({
        id: h.id,
        phone: h.number,
      })),
      patientId,
      age,
      sex,
      category,
      symptom,
      remarks,
      grade,
      callback_url: `${callbackBaseUrl}/emergency/callback`,
    };

    this.logger.log(`AI 서버로 매칭 요청 전송: ${aiServerUrl}`);

    // 비동기로 AI 서버에 전송 (응답 대기하지 않음)
    fetch(aiServerUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(async (res) => {
        const body = await res.json();
        this.logger.log(`AI 서버 응답: ${res.status} ${JSON.stringify(body)}`);
      })
      .catch((err) => {
        this.logger.error(`AI 서버 요청 실패: ${err.message}`);
        this.sseService.emit(patientChannel, {
          message: 'AI 서버 연결에 실패했습니다.',
          status: 'AI_SERVER_ERROR',
        });
      });

    return {
      success: true,
      message: '매칭 프로세스가 시작되었습니다.',
      patientId,
      channel: patientChannel,
    };
  }

  // 2. AI 서버에서 병원들의 수락/거절 결과를 한꺼번에 콜백할 때 호출
  async handleCallback(results: { hospitalId: number; patientId: number; status: string }[]) {
    const processed: any[] = [];

    // 수락(accepted)을 먼저 처리하기 위해 정렬
    const sorted = [...results].sort((a, b) => {
      if (a.status === 'accepted') return -1;
      if (b.status === 'accepted') return 1;
      return 0;
    });

    for (const result of sorted) {
      const res = await this.processResult(result.hospitalId, result.patientId, result.status);
      processed.push({ hospitalId: result.hospitalId, ...res });

      // 수락된 게 있으면 나머지는 자동 거절 처리됨
      if (result.status === 'accepted') break;
    }

    return { success: true, processed };
  }

  // 개별 병원 결과 처리
  private async processResult(hospitalId: number, patientId: number, status: string) {
    const patientChannel = `patient-${patientId}`;

    if (status === 'no_answer') {
      // 무응답 → 거절과 동일 처리
      await prisma.hospitalRequest.updateMany({
        where: { hospitalId, patientId, accepted: null },
        data: { accepted: false },
      });

      const hospital = await prisma.hospital.findUnique({ where: { id: hospitalId } });
      if (hospital) {
        this.sseService.emit(patientChannel, {
          message: `${hospital.name} 병원이 응답하지 않았습니다.`,
          hospitalId: hospital.id,
          hospitalName: hospital.name,
          status: 'no_answer',
        });
      }
      return { status: 'no_answer' };
    }

    const accepted = status === 'accepted';

    // 해당 요청의 상태 업데이트
    const request = await prisma.hospitalRequest.updateMany({
      where: { hospitalId, patientId, accepted: null },
      data: { accepted },
    });

    if (request.count === 0) {
      return { status: 'already_processed' };
    }

    const hospital = await prisma.hospital.findUnique({
      where: { id: hospitalId },
    });

    if (!hospital) {
      return { status: 'hospital_not_found' };
    }

    if (accepted) {
      // 나머지 대기 중인 요청을 모두 거절로 변경
      await prisma.hospitalRequest.updateMany({
        where: { patientId, accepted: null },
        data: { accepted: false },
      });

      // 수락 → SSE로 응급대원에게 알림 후 연결 종료
      this.sseService.emit(patientChannel, {
        message: `${hospital.name} 병원이 수용을 수락했습니다!`,
        hospitalId: hospital.id,
        hospitalName: hospital.name,
        hospitalNumber: hospital.number,
        status: 'accepted',
      });
      this.logger.log(`병원 ${hospital.name}(${hospitalId})이 환자 ${patientId} 수용 수락`);

      this.sseService.unsubscribe(patientChannel);
      return { status: 'accepted' };
    } else {
      // 거절 → SSE로 응급대원에게 알림
      this.sseService.emit(patientChannel, {
        message: `${hospital.name} 병원이 수용을 거절했습니다.`,
        hospitalId: hospital.id,
        hospitalName: hospital.name,
        status: 'rejected',
      });
      this.logger.log(`병원 ${hospital.name}(${hospitalId})이 환자 ${patientId} 수용 거절`);

      // 모든 병원이 거절했는지 확인
      const pendingCount = await prisma.hospitalRequest.count({
        where: { patientId, accepted: null },
      });
      const acceptedCount = await prisma.hospitalRequest.count({
        where: { patientId, accepted: true },
      });

      if (pendingCount === 0 && acceptedCount === 0) {
        this.sseService.emit(patientChannel, {
          message: '모든 병원이 거절했습니다. 추가 조치가 필요합니다.',
          status: 'all_rejected',
        });
      }

      return { status: 'rejected' };
    }
  }

  getHello(): string {
    return 'Hello World!';
  }
}

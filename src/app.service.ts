import { Injectable } from '@nestjs/common';
// import { PrismaService } from './prisma.service';
import { prisma } from './prisma';
import { EmergencySseService } from './emergency-sse.service';

@Injectable()
export class AppService {
  constructor(
    // private readonly prisma: PrismaService,
    private readonly sseService: EmergencySseService,
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
    console.log(patientChannel);

    // 백그라운드에서 비동기로 확산 로직 실행 (await 없이)
    // Promise를 시작하고 에러 핸들링만 추가
    this.escalateMatching(patientId, grade, lat, lng, 1).catch((err) => {
      console.error('매칭 에스컬레이션 오류:', err);
      this.sseService.emit(patientChannel, {
        message: '매칭 중 오류가 발생했습니다.',
        error: err.message,
      });
    });
    console.log('매칭 확산 로직 시작됨');

    return {
      success: true,
      message: '매칭 프로세스가 시작되었습니다.',
      patientId,
      channel: patientChannel,
    };
  }

  // 2. 단계적으로 범위를 넓히며 병원들에게 요청을 보내는 핵심 로직
  private async escalateMatching(
    patientId: number,
    grade: number,
    lat: number,
    lng: number,
    page: number,
  ) {
    const limit = 5;
    const offset = (page - 1) * limit;
    const patientChannel = `patient-${patientId}`;

    // 이미 수락된 요청이 있는지 확인 (있으면 중단)
    const existingRequest = await prisma.hospitalRequest.findFirst({
      where: { patientId, accepted: true },
    });
    if (existingRequest) return;

    // 현재 페이지(5개)의 가장 가까운 병원 조회
    const hospitals: any[] = await prisma.$queryRaw`
      SELECT id, name, number, latitude, longitude,
      ST_Distance_Sphere(point(longitude, latitude), point(${lng}, ${lat})) AS distance
      FROM hospital
      WHERE min_grade <= ${grade} AND max_grade >= ${grade}
      ORDER BY distance ASC
      LIMIT ${limit} OFFSET ${offset}
    `;

    if (hospitals.length === 0) {
      this.sseService.emit(patientChannel, {
        message: '더 이상 매칭 가능한 병원이 없습니다.',
      });
      return;
    }

    this.sseService.emit(patientChannel, {
      message: `${page}차 매칭 시도 중: 주변 ${hospitals.length}개의 병원에 요청을 보냈습니다.`,
      hospitals,
    });

    // 각 병원에게 요청 생성 및 알림 (실제로는 병원용 SSE 채널로 전송)
    for (const hospital of hospitals) {
      await prisma.hospitalRequest.create({
        data: {
          patientId,
          hospitalId: hospital.id,
          accepted: null, // 대기 상태
          createdAt: new Date(),
        },
      });
      // 병원에게 알림 (병원용 channel: hospital-{id})
      this.sseService.emit(`hospital-${hospital.id}`, {
        message: '새로운 응급 환자 수용 요청이 왔습니다!',
        patientId,
        grade,
      });
    }

    // 60초 대기 후, 아무도 수락하지 않았으면 다음 페이지로 확산
    setTimeout(async () => {
      const accepted = await prisma.hospitalRequest.findFirst({
        where: { patientId, accepted: true },
      });

      if (!accepted) {
        this.sseService.emit(patientChannel, {
          message: '응답이 없어 검색 범위를 넓힙니다...',
        });
        this.escalateMatching(patientId, grade, lat, lng, page + 1);
      }
    }, 60000); // 60초
  }

  // 3. 병원이 수락을 눌렀을 때 호출
  async acceptRequest(hospitalId: number, patientId: number) {
    // 해당 요청을 수락 상태로 변경
    const request = await prisma.hospitalRequest.updateMany({
      where: { hospitalId, patientId, accepted: null },
      data: { accepted: true },
    });

    if (request.count > 0) {
      const hospital = await prisma.hospital.findUnique({
        where: { id: hospitalId },
      });

      if (!hospital) {
        return { success: false, message: '병원을 찾을 수 없습니다.' };
      }

      // 환자에게 수락 알림 전송
      this.sseService.emit(`patient-${patientId}`, {
        message: '병원이 수용을 수락했습니다!',
        hospitalName: hospital.name,
        hospitalNumber: hospital.number,
        status: 'ACCEPTED',
      });
      return { success: true };
    }
    return {
      success: false,
      message: '이미 처리되었거나 존재하지 않는 요청입니다.',
    };
  }

  getHello(): string {
    return 'Hello World!';
  }
}

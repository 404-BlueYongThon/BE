import {
  Body,
  Controller,
  Get,
  Post,
  Sse,
  MessageEvent,
  Param,
} from '@nestjs/common';
import { AppService } from './app.service';
import { EmergencySseService } from './emergency-sse.service';
import { Observable } from 'rxjs';

@Controller()
export class AppController {
  constructor(
    private readonly appService: AppService,
    private readonly sseService: EmergencySseService,
  ) {}

  @Get()
  getHello(): string {
    return this.appService.getHello();
  }

  // 1. 실시간 알림을 위한 SSE 연결 엔드포인트
  // /sse/patient-1 또는 /sse/hospital-5 등으로 연결
  @Sse('sse/:id')
  sse(@Param('id') id: string): Observable<MessageEvent> {
    return this.sseService.subscribe(id);
  }

  // 2. 매칭 시작 요청 (환자가 호출)
  @Sse('matching/start')
  async startMatching(
    @Body('age') age: string,
    @Body('category') category: string,
    @Body('symptom') symptom: string,
    @Body('remarks') remarks: string,
    @Body('grade') grade: number,
    @Body('lat') lat: number,
    @Body('lng') lng: number,
  ) {
    const result = await this.appService.startMatching(
      age,
      category,
      symptom,
      remarks,
      grade,
      lat,
      lng,
    );
    console.log('startMatching result:', result);
    return result;
  }

  // 3. 수용 수락 (병원이 호출)
  @Post('matching/accept')
  async acceptRequest(
    @Body('hospitalId') hospitalId: number,
    @Body('patientId') patientId: number,
  ) {
    return this.appService.acceptRequest(hospitalId, patientId);
  }
}

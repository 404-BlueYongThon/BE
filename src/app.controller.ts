import {
  Body,
  Controller,
  Get,
  Post,
  Sse,
  MessageEvent,
  Param,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse, ApiParam } from '@nestjs/swagger';
import { AppService } from './app.service';
import { EmergencySseService } from './emergency-sse.service';
import { Observable } from 'rxjs';
import { StartMatchingDto } from './dto/start-matching.dto';
import { AcceptRequestDto } from './dto/accept-request.dto';

@Controller()
export class AppController {
  constructor(
    private readonly appService: AppService,
    private readonly sseService: EmergencySseService,
  ) {}

  @Get()
  @ApiOperation({ summary: '헬스 체크', description: '서버 상태 확인용 엔드포인트' })
  @ApiResponse({ status: 200, description: 'Hello World 반환' })
  getHello(): string {
    return this.appService.getHello();
  }

  // 1. 실시간 알림을 위한 SSE 연결 엔드포인트
  // /sse/patient-1 또는 /sse/hospital-5 등으로 연결
  @Sse('sse/:id')
  @ApiTags('SSE')
  @ApiOperation({
    summary: 'SSE 실시간 알림 연결',
    description: '환자 또는 병원이 실시간 알림을 받기 위한 SSE 연결. /sse/patient-1 또는 /sse/hospital-5 형태로 사용',
  })
  @ApiParam({ name: 'id', description: '클라이언트 식별자 (예: patient-1, hospital-5)', example: 'patient-1' })
  sse(@Param('id') id: string): Observable<MessageEvent> {
    return this.sseService.subscribe(id);
  }

  // 2. 매칭 시작 요청 (환자가 호출)
  @Sse('matching/start')
  @ApiTags('매칭')
  @ApiOperation({
    summary: '매칭 시작 요청',
    description: '환자가 응급 매칭을 요청합니다. 가까운 병원부터 단계적으로 매칭을 시도합니다.',
  })
  @ApiResponse({ status: 200, description: '매칭 프로세스가 시작되고 SSE 스트림을 통해 결과 수신' })
  async startMatching(@Body() dto: StartMatchingDto) {
    const result = await this.appService.startMatching(
      dto.age,
      dto.sex,
      dto.category,
      dto.symptom,
      dto.remarks,
      dto.grade,
      dto.lat,
      dto.lng,
    );
    console.log('startMatching result:', result);
    return result;
  }

  // 3. 수용 수락 (병원이 호출)
  @Post('matching/accept')
  @ApiTags('매칭')
  @ApiOperation({
    summary: '수용 수락',
    description: '병원이 응급 환자 수용 요청을 수락합니다.',
  })
  @ApiResponse({ status: 200, description: '수락 처리 결과 반환' })
  async acceptRequest(@Body() dto: AcceptRequestDto) {
    return this.appService.acceptRequest(dto.hospitalId, dto.patientId);
  }
}

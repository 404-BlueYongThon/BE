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
  @ApiTags('헬스')
  @ApiOperation({
    summary: '헬스 체크',
    description: '서버 상태 확인용 엔드포인트',
  })
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
    description:
      '응급대원이 매칭 결과(수락/거절)를 실시간으로 받기 위한 SSE 연결. /sse/patient-{patientId} 형태로 사용. matching/start 응답의 channel 값을 사용합니다.',
  })
  @ApiParam({
    name: 'id',
    description: '채널 식별자 (matching/start 응답의 channel 값)',
    example: 'patient-1',
  })
  sse(@Param('id') id: string): Observable<MessageEvent> {
    return this.sseService.subscribe(id);
  }

  // 2. 매칭 시작 요청 (응급대원이 호출)
  @Post('matching/start')
  @ApiTags('매칭')
  @ApiOperation({
    summary: '매칭 시작 요청',
    description:
      '응급대원이 환자 정보와 위치를 전송하면 근처 병원 5개를 조회하여 AI 서버(localhost:8000)로 전달합니다. 응답의 channel 값으로 SSE 연결하여 결과를 수신하세요.',
  })
  @ApiResponse({
    status: 200,
    description:
      'patientId와 SSE channel 반환. 이후 /sse/{channel}로 SSE 연결 필요',
  })
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

  // 3. 수락/거절 배치 콜백 (AI 서버가 호출)
  @Post('emergency/callback')
  @ApiTags('콜백')
  @ApiOperation({
    summary: '병원 수락/거절 배치 콜백',
    description: `AI 서버(localhost:8000)에서 병원들의 수락/거절/무응답 결과를 한꺼번에 콜백합니다.
results 배열에 각 병원의 결과가 담겨옵니다.
- accepted: 수락 → 응급대원에게 SSE로 수락 알림 + 나머지 요청 자동 거절 + SSE 종료
- rejected: 거절 → 응급대원에게 SSE로 거절 알림 (전부 거절 시 all_rejected 알림)
- no_answer: 무응답 → 거절과 동일 처리`,
  })
  @ApiResponse({ status: 200, description: '각 병원별 처리 결과 배열 반환' })
  async acceptRequest(@Body() dto: AcceptRequestDto) {
    return this.appService.handleCallback(dto.patientId, dto.results);
  }
}

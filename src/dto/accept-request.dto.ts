import { ApiProperty } from '@nestjs/swagger';

export class CallbackResultDto {
  @ApiProperty({ description: '병원 ID', example: 1 })
  hospitalId: number;

  @ApiProperty({
    description: '수락/거절 상태',
    example: 'accepted',
    enum: ['accepted', 'rejected', 'no_answer', 'calling'],
  })
  status: string;
}

export class AcceptRequestDto {
  @ApiProperty({
    description: '응급 사건 ID',
    example: 'c4a19f5c-2571-41a4-b5db-a56c5beb4a55',
  })
  emergency_id: string;

  @ApiProperty({ description: '환자 ID', example: 1 })
  patientId: number;

  @ApiProperty({
    description: '병원별 수락/거절 결과 배열',
    type: [CallbackResultDto],
    example: [
      { hospitalId: 1, status: 'accepted' },
      { hospitalId: 2, status: 'rejected' },
      { hospitalId: 3, status: 'no_answer' },
    ],
  })
  results: CallbackResultDto[];
}

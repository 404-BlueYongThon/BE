import { ApiProperty } from '@nestjs/swagger';

export class AcceptRequestDto {
  @ApiProperty({ description: '병원 ID', example: 1 })
  hospitalId: number;

  @ApiProperty({ description: '환자 ID', example: 1 })
  patientId: number;

  @ApiProperty({ description: '수락/거절 상태', example: 'accepted', enum: ['accepted', 'rejected'] })
  status: string;
}

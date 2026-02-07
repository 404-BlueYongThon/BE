import { ApiProperty } from '@nestjs/swagger';

export class AcceptRequestDto {
  @ApiProperty({ description: '병원 ID', example: 1 })
  hospitalId: number;

  @ApiProperty({ description: '환자 ID', example: 1 })
  patientId: number;
}

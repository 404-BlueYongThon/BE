import { ApiProperty } from '@nestjs/swagger';

export class StartMatchingDto {
  @ApiProperty({ description: '환자 나이', example: '30대' })
  age: string;

  @ApiProperty({ description: '환자 성별', example: 'male', enum: ['male', 'female'] })
  sex: string;

  @ApiProperty({ description: '응급 카테고리', example: '외상' })
  category: string;

  @ApiProperty({ description: '증상', example: '골절' })
  symptom: string;

  @ApiProperty({ description: '비고/특이사항', example: '의식 있음' })
  remarks: string;

  @ApiProperty({ description: '응급 등급 (1~5)', example: 3 })
  grade: number;

  @ApiProperty({ description: '환자 위치 위도', example: 37.5665 })
  lat: number;

  @ApiProperty({ description: '환자 위치 경도', example: 126.978 })
  lng: number;
}

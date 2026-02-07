import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  app.enableCors({
    origin: [
      'http://localhost:3000',
      'http://localhost:3333',
      'https://emergency-ai-call.log8.kr',
    ],
  });

  const config = new DocumentBuilder()
    .setTitle('응급 매칭 API')
    .setDescription('응급 환자-병원 매칭 시스템 API 문서')
    .setVersion('1.0')
    .addTag('헬스', '서버 상태 확인')
    .addTag('매칭', '환자-병원 매칭 관련 API')
    .addTag('SSE', '실시간 알림 관련 API')
    .addTag('콜백', '병원 수락/거절 콜백')
    .build();

  const document = SwaggerModule.createDocument(app, config);

  // 컨트롤러 이름 기반 자동 태그("App") 제거 → 메서드별 @ApiTags만 남김
  if (document.paths) {
    for (const pathItem of Object.values(document.paths)) {
      for (const operation of Object.values(pathItem as Record<string, any>)) {
        if (operation?.tags) {
          operation.tags = operation.tags.filter(
            (tag: string) => tag !== 'App',
          );
        }
      }
    }
  }
  // "App" 태그 정의도 제거
  if (document.tags) {
    document.tags = document.tags.filter((tag: any) => tag.name !== 'App');
  }

  SwaggerModule.setup('api', app, document);

  await app.listen(process.env.PORT ?? 3000);
}
bootstrap();

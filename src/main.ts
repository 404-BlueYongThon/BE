import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  const config = new DocumentBuilder()
    .setTitle('응급 매칭 API')
    .setDescription('응급 환자-병원 매칭 시스템 API 문서')
    .setVersion('1.0')
    .addTag('매칭', '환자-병원 매칭 관련 API')
    .addTag('SSE', '실시간 알림 관련 API')
    .build();

  const document = SwaggerModule.createDocument(app, config);
  SwaggerModule.setup('api', app, document);

  await app.listen(process.env.PORT ?? 3000);
}
bootstrap();

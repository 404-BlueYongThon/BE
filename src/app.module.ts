import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
// import { PrismaService } from './prisma';
import { EmergencySseService } from './emergency-sse.service';
import { ConfigModule } from '@nestjs/config';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true, // 전역 사용 가능
      envFilePath: '.env',
    }),
  ],
  controllers: [AppController],
  providers: [AppService, EmergencySseService],
})
export class AppModule {}

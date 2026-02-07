import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
// import { PrismaService } from './prisma';
import { EmergencySseService } from './emergency-sse.service';

@Module({
  imports: [],
  controllers: [AppController],
  providers: [AppService, EmergencySseService],
})
export class AppModule {}

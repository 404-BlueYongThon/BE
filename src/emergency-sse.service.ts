import { Injectable, MessageEvent } from '@nestjs/common';
import { Observable, Subject } from 'rxjs';

@Injectable()
export class EmergencySseService {
  // 클라이언트(환자 앱/병원 앱)별로 이벤트를 전송하기 위한 Subject 맵
  private clients = new Map<string, Subject<MessageEvent>>();

  // 클라이언트가 SSE 연결을 맺을 때 호출
  subscribe(id: string): Observable<MessageEvent> {
    return new Observable<MessageEvent>((subscriber) => {
      const subject = new Subject<MessageEvent>();
      this.clients.set(id, subject);

      const subscription = subject.subscribe(subscriber);

      // 연결 직후 이벤트 (Postman 등에서 연결 확인용)
      subscriber.next({ data: { message: 'connected' } });

      return () => {
        subscription.unsubscribe();
        this.clients.delete(id);
      };
    });
  }

  // 특정 클라이언트에게 이벤트 전송
  emit(id: string, data: any) {
    const client = this.clients.get(id);
    if (client) {
      client.next({ data });
    }
  }

  // 연결 종료 시 정리
  unsubscribe(id: string) {
    const client = this.clients.get(id);
    if (client) {
      client.complete(); // Observable 종료
      this.clients.delete(id);
    }
  }
}

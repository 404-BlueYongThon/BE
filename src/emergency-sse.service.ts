import { Injectable } from '@nestjs/common';
import { Subject, Observable, filter, map } from 'rxjs';

export interface SseEvent {
  patientId: number;
  data: any;
}

@Injectable()
export class EmergencySseService {
  private eventSubject = new Subject<SseEvent>();

  // 병원이 수락/거절했을 때 이 메서드를 호출합니다.
  emitEvent(patientId: number, data: any) {
    this.eventSubject.next({ patientId, data });
  }

  // 구급요원이 SSE 연결을 했을 때 호출되는 스트림입니다.
  getEventStream(patientId: number): Observable<any> {
    return this.eventSubject.asObservable().pipe(
      // 해당 환자 ID에 맞는 이벤트만 필터링해서 보냅니다.
      filter((event) => event.patientId === patientId),
      map((event) => ({ data: event.data })),
    );
  }
}

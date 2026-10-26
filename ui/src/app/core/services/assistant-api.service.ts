import { HttpClient, HttpHeaders } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';
import { AssistantRequest, AssistantResponse } from '../models/assistant.models';

@Injectable({ providedIn: 'root' })
export class AssistantApiService {
  private readonly http = inject(HttpClient);
  chat(request: AssistantRequest, session: string) {
    return this.http.post<AssistantResponse>(`${environment.apiBaseUrl}/assistant/chat`, request, {
      headers: new HttpHeaders().set('X-Assistant-Session', session),
    });
  }
}

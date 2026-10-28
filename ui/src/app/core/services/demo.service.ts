import { HttpClient } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { AuthService } from './auth.service';
import { environment } from '../../../environments/environment';

export interface DemoConfig {
  enabled: boolean;
  label: string;
  assistant_enabled: boolean;
  questions: { id: string; label: string }[];
}

@Injectable({ providedIn: 'root' })
export class DemoService {
  private readonly auth = inject(AuthService);
  get readOnly(): boolean { return this.auth.enabled && !this.auth.user(); }
  get canWrite(): boolean { return !this.auth.enabled || this.auth.user()?.role === 'admin'; }
  readonly config = signal<DemoConfig | null>(null);
  constructor() {
    if (environment.production) {
      inject(HttpClient).get<DemoConfig>(`${environment.apiBaseUrl}/demo/config`).subscribe({
        next: (config) => this.config.set(config),
        error: () => this.config.set(null),
      });
    }
  }
}

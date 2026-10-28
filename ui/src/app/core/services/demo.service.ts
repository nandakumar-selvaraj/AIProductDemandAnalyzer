import { HttpClient } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { environment } from '../../../environments/environment';

export interface DemoConfig {
  enabled: boolean;
  label: string;
  assistant_enabled: boolean;
  questions: { id: string; label: string }[];
}

@Injectable({ providedIn: 'root' })
export class DemoService {
  readonly readOnly = environment.production;
  readonly config = signal<DemoConfig | null>(null);
  constructor() {
    if (this.readOnly) {
      inject(HttpClient).get<DemoConfig>(`${environment.apiBaseUrl}/demo/config`).subscribe({
        next: (config) => this.config.set(config),
        error: () => this.config.set(null),
      });
    }
  }
}

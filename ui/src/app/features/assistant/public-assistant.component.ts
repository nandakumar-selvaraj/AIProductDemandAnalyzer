import { HttpClient } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { environment } from '../../../environments/environment';
import { AssistantResponse } from '../../core/models/assistant.models';
import { DemoService } from '../../core/services/demo.service';

@Component({
  selector: 'app-public-assistant',
  template: `
    <section class="panel" aria-labelledby="demo-assistant-heading">
      <h1 id="demo-assistant-heading">AI Business Assistant</h1>
      <p>Explore historical synthetic demo data with a few guided questions.</p>
      @if (demo.config()?.assistant_enabled) {
        <p>Each question is independent. Availability is limited by a shared daily allowance.</p>
        @for (question of demo.config()?.questions ?? []; track question.id) {
          <button type="button" class="btn btn-outline-primary m-1"
            [disabled]="pending()" (click)="ask(question.id)">{{ question.label }}</button>
        }
      } @else {
        <p role="status">Demo AI is currently disabled. Sales and forecast reports remain available.</p>
      }
      @if (pending()) { <p role="status">Checking verified demo evidence…</p> }
      @if (error()) { <p role="alert">{{ error() }}</p> }
      @if (response(); as result) {
        <article aria-label="Assistant answer" style="white-space: pre-wrap">{{ result.answer }}</article>
        @for (warning of result.warnings; track warning) { <p>{{ warning }}</p> }
      }
    </section>
  `,
})
export class PublicAssistantComponent {
  protected readonly demo = inject(DemoService);
  private readonly http = inject(HttpClient);
  protected readonly pending = signal(false);
  protected readonly response = signal<AssistantResponse | null>(null);
  protected readonly error = signal('');
  protected ask(id: string): void {
    if (this.pending() || !this.demo.config()?.assistant_enabled) return;
    this.pending.set(true);
    this.error.set('');
    this.response.set(null);
    this.http.post<AssistantResponse>(`${environment.apiBaseUrl}/demo/assistant`, {
      question_id: id,
    }).subscribe({
      next: (response) => { this.response.set(response); this.pending.set(false); },
      error: () => {
        this.error.set('The demo assistant is unavailable or its allowance has been reached. Please try later.');
        this.pending.set(false);
      },
    });
  }
}

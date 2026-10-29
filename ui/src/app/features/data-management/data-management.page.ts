import { HttpClient, HttpEventType } from '@angular/common/http';
import { Component, DestroyRef, effect, ElementRef, inject, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AlertComponent, CardComponent, CardBodyComponent } from '@coreui/angular';
import { Subscription } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthService } from '../../core/services/auth.service';

export interface IngestionSummary {
  records_read: number; inserted: number; updated: number; rejected: number;
  skipped: number; validation_only: boolean; issues: { row: number; reason: string }[];
}

@Component({
  selector: 'app-data-management',
  imports: [AlertComponent, CardComponent, CardBodyComponent],
  templateUrl: './data-management.page.html',
  styles: [`:host { display: block; max-width: 960px; } input { max-width: 100%; }
    progress { width: 100%; } .actions { display: flex; flex-wrap: wrap; gap: 1rem; margin: 1rem 0; }
    dl { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; } dd { margin: 0; }
    .issues { max-height: 20rem; overflow: auto; }`],
})
export class DataManagementPage {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);
  private upload?: Subscription;
  private readonly input = viewChild<ElementRef<HTMLInputElement>>('csvInput');
  protected readonly limit = signal<number | null>(null);
  protected readonly file = signal<File | null>(null);
  protected readonly pending = signal(false);
  protected readonly progress = signal<number | null>(null);
  protected readonly error = signal('');
  protected readonly summary = signal<IngestionSummary | null>(null);

  constructor() {
    this.http.get<{ max_upload_bytes: number }>(`${environment.apiBaseUrl}/ingestion/config`)
      .pipe(takeUntilDestroyed()).subscribe({
        next: (config) => this.limit.set(config.max_upload_bytes),
        error: () => this.error.set('Upload limits could not be loaded. Reload the page to retry.'),
      });
    effect(() => {
      if (this.auth.enabled && this.auth.user()?.role !== 'admin') {
        this.upload?.unsubscribe();
        this.pending.set(false);
        this.file.set(null);
        this.summary.set(null);
      }
    });
  }

  protected select(event: Event): void {
    if (this.pending()) return;
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;
    this.file.set(null);
    this.error.set('');
    this.summary.set(null);
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.csv')) this.error.set('Select a .csv file.');
    else if (!file.size) this.error.set('The CSV file is empty.');
    else if (this.limit() === null) this.error.set('Wait for the upload limits to load.');
    else if (file.size > this.limit()!) this.error.set('The CSV exceeds the server upload limit.');
    else this.file.set(file);
    if (!this.file()) input.value = '';
  }

  protected submit(): void {
    const file = this.file();
    if (this.pending() || !file || this.limit() === null
      || (this.auth.enabled && this.auth.user()?.role !== 'admin')) return;
    this.pending.set(true);
    this.error.set('');
    this.summary.set(null);
    this.progress.set(null);
    const body = new FormData();
    body.append('file', file, file.name);
    this.upload = this.http.post<IngestionSummary>(`${environment.apiBaseUrl}/ingestion/sales`, body,
      { observe: 'events', reportProgress: true }).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
        next: (event) => {
          if (event.type === HttpEventType.UploadProgress && event.total) {
            this.progress.set(Math.round(event.loaded * 100 / event.total));
          } else if (event.type === HttpEventType.Response) {
            this.summary.set(event.body);
            this.pending.set(false);
            this.file.set(null);
            const input = this.input()?.nativeElement;
            if (input) input.value = '';
          }
        },
        error: (error: unknown) => {
          this.pending.set(false);
          const message = error instanceof Error ? error.message : 'CSV upload failed. Please try again.';
          this.error.set(message);
        },
      });
  }
}

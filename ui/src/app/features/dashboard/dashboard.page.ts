import { Component, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { catchError, map, of, startWith, Subject, switchMap } from 'rxjs';
import { AlertComponent, SpinnerComponent } from '@coreui/angular';
import { AnalyticsApiService } from '../../core/services/analytics-api.service';
import { DashboardSummary } from '../../core/models/analytics.models';
@Component({
  selector: 'app-dashboard-page',
  imports: [DatePipe, DecimalPipe, AlertComponent, SpinnerComponent],
  templateUrl: './dashboard.page.html',
  styleUrl: './dashboard.page.scss',
})
export class DashboardPage {
  protected readonly chartNumber = new Intl.NumberFormat('en', {
    notation: 'compact',
    maximumSignificantDigits: 3,
  });
  private readonly api = inject(AnalyticsApiService);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly summary = signal<DashboardSummary | null>(null);
  private readonly reload = new Subject<void>();

  constructor() {
    this.reload
      .pipe(
        startWith(undefined),
        switchMap(() =>
          this.api.getDashboardSummary().pipe(
            map((summary) => ({ status: 'success', summary }) as const),
            catchError((error: unknown) =>
              of({
                status: 'error',
                message:
                  error instanceof Error && error.message
                    ? error.message
                    : 'Dashboard summary could not be loaded.',
              } as const),
            ),
            startWith({ status: 'loading' } as const),
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((state) => {
        this.loading.set(state.status === 'loading');
        this.error.set(state.status === 'error' ? state.message : null);
        this.summary.set(state.status === 'success' ? state.summary : null);
      });
  }

  protected loadSummary(): void {
    this.reload.next();
  }
  protected get monthlySales(): [string, number][] {
    return this.summary()?.monthly_sales.slice(-6) ?? [];
  }
  protected get maxMonthlySales(): number {
    return Math.max(1, ...this.monthlySales.map(([, value]) => value));
  }
}

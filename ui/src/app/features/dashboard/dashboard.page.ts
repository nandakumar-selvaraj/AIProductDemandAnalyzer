import { Component, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { finalize } from 'rxjs';
import { AlertComponent, SpinnerComponent } from '@coreui/angular';
import { AnalyticsApiService } from '../../core/services/analytics-api.service';
import { DashboardSummary } from '../../core/models/analytics.models';
@Component({ selector: 'app-dashboard-page', imports: [DecimalPipe, AlertComponent, SpinnerComponent], templateUrl: './dashboard.page.html', styleUrl: './dashboard.page.scss' })
export class DashboardPage {
  private readonly api = inject(AnalyticsApiService);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly summary = signal<DashboardSummary | null>(null);
  constructor() { this.loadSummary(); }
  protected loadSummary(): void {
    this.loading.set(true); this.error.set(null);
    this.api.getDashboardSummary().pipe(finalize(() => this.loading.set(false))).subscribe({ next: (summary) => this.summary.set(summary), error: (error: Error) => this.error.set(error.message || 'Dashboard summary could not be loaded.') });
  }
  protected get monthlySales(): [string, number][] { return this.summary()?.monthly_sales.slice(-6) ?? []; }
  protected get maxMonthlySales(): number { return Math.max(1, ...this.monthlySales.map(([, value]) => value)); }
}
import { DecimalPipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { AlertComponent, SpinnerComponent } from '@coreui/angular';
import { map, of, Subject, switchMap } from 'rxjs';
import { ProductAnalyticsResponse, SalesPoint } from '../../core/models/analytics.models';
import { AnalyticsApiService } from '../../core/services/analytics-api.service';
import { CatalogPickerComponent } from '../demand-analysis/catalog-picker.component';
import { validateFilters } from '../demand-analysis/demand-analysis.helpers';
import { AppliedFilters, CatalogChoice } from '../demand-analysis/demand-analysis.models';
import { HistoricalChartComponent } from '../demand-analysis/historical-chart.component';
import { LoadState, requestState } from '../forecasts/forecast.helpers';
import { CsvDownloadService } from './csv-export';
import { CsvCell } from './report.models';
import { ReportTableComponent } from './report-table.component';

interface HistoricalReport {
  filters: AppliedFilters;
  generatedAt: string;
  data: ProductAnalyticsResponse;
}
@Component({
  selector: 'app-historical-sales-report',
  imports: [
    FormsModule,
    DecimalPipe,
    AlertComponent,
    SpinnerComponent,
    CatalogPickerComponent,
    HistoricalChartComponent,
    ReportTableComponent,
  ],
  templateUrl: './historical-sales-report.component.html',
  styleUrl: './reports.scss',
})
export class HistoricalSalesReportComponent {
  private readonly api = inject(AnalyticsApiService);
  private readonly csv = inject(CsvDownloadService);
  private readonly requests = new Subject<AppliedFilters | null>();
  private readonly applied = signal<AppliedFilters | null>(null);
  protected readonly product = signal<CatalogChoice | null>(null);
  protected readonly store = signal<CatalogChoice | null>(null);
  protected readonly start = signal('');
  protected readonly end = signal('');
  protected readonly errors = signal<string[]>([]);
  protected readonly downloadMessage = signal('');
  protected readonly downloadError = signal('');
  protected readonly state = signal<LoadState<HistoricalReport>>({ status: 'idle' });
  protected readonly result = computed(() => {
    const state = this.state();
    return state.status === 'success' ? state.data : null;
  });
  protected readonly page = signal(1);
  protected readonly pages = computed(() =>
    Math.max(1, Math.ceil((this.result()?.data.daily_sales.length ?? 0) / 25)),
  );
  protected readonly dailyTable = computed(() => ({
    headers: ['date', 'units_sold'],
    rows: (this.result()?.data.daily_sales ?? [])
      .slice((this.page() - 1) * 25, this.page() * 25)
      .map((row) => [row.period, row.units_sold]),
  }));
  protected readonly changed = computed(() => {
    const applied = this.applied();
    return (
      !!applied &&
      (applied.product.id !== this.product()?.id ||
        (applied.store?.id ?? null) !== (this.store()?.id ?? null) ||
        applied.startDate !== this.start() ||
        applied.endDate !== this.end())
    );
  });
  protected readonly canRefresh = computed(
    () => !!this.applied() && this.state().status !== 'loading',
  );
  constructor() {
    this.requests
      .pipe(
        switchMap((filters) => {
          if (!filters) return of<LoadState<HistoricalReport>>({ status: 'idle' });
          const generatedAt = new Date().toISOString();
          return requestState(
            this.api
              .getProductAnalytics(filters.product.id, {
                storeId: filters.store?.id,
                startDate: filters.startDate,
                endDate: filters.endDate,
              })
              .pipe(
                map((data) => {
                  if (
                    data.product_id !== filters.product.id ||
                    data.store_id !== (filters.store?.id ?? null)
                  )
                    throw new Error(
                      'Historical response does not match the requested product/store.',
                    );
                  return { filters, generatedAt, data };
                }),
              ),
          );
        }),
        takeUntilDestroyed(),
      )
      .subscribe((state) => {
        this.state.set(state);
        this.page.set(1);
      });
  }
  protected generate(): void {
    const product = this.product();
    this.errors.set(validateFilters(product?.id ?? null, this.start(), this.end()));
    this.downloadMessage.set('');
    this.downloadError.set('');
    if (!product || this.errors().length) {
      this.applied.set(null);
      this.requests.next(null);
      return;
    }
    const filters: AppliedFilters = {
      product: { ...product },
      store: this.store() ? { ...this.store()! } : null,
      startDate: this.start(),
      endDate: this.end(),
    };
    this.applied.set(filters);
    this.requests.next(filters);
  }
  protected refresh(): void {
    const filters = this.applied();
    if (filters) {
      this.downloadMessage.set('');
      this.downloadError.set('');
      this.requests.next(filters);
    }
  }
  protected changePage(page: number): void {
    if (page > 0 && page <= this.pages()) this.page.set(page);
  }
  protected exportCsv(granularity: 'daily' | 'monthly'): void {
    const snapshot = this.result();
    if (!snapshot) return;
    const points: SalesPoint[] =
      granularity === 'daily' ? snapshot.data.daily_sales : snapshot.data.monthly_sales;
    if (!points.length) return;
    const { filters, data } = snapshot;
    const context: Record<string, CsvCell> = {
      report_type: 'historical_sales',
      export_scope: `all_returned_${granularity}_observations`,
      generated_at: snapshot.generatedAt,
      product_id: filters.product.id,
      product_name: filters.product.name,
      product_code: filters.product.code,
      store_id: filters.store?.id ?? 'all',
      store_name: filters.store?.name ?? 'All Stores',
      store_code: filters.store?.code ?? 'all',
      requested_start_date: filters.startDate || 'backend_default',
      requested_end_date: filters.endDate || 'backend_default',
      observed_start_date: data.start_date,
      observed_end_date: data.end_date,
      observed_sales_dates: data.observed_dates,
      total_units_sold: data.total_units_sold,
    };
    try {
      this.csv.download(
        `historical-sales-product-${filters.product.id}-store-${filters.store?.id ?? 'all'}-${filters.startDate || 'default'}-to-${filters.endDate || 'default'}-${granularity}.csv`,
        {
          headers: ['period', 'units_sold'],
          rows: points.map((point) => [point.period, point.units_sold]),
        },
        context,
      );
      this.downloadError.set('');
      this.downloadMessage.set(
        `Downloaded all ${points.length} returned ${granularity} observations for product #${filters.product.id}.`,
      );
    } catch (error) {
      this.downloadError.set(error instanceof Error ? error.message : 'CSV download failed.');
    }
  }
}

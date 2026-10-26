import { DatePipe, DecimalPipe } from '@angular/common';
import {
  afterNextRender,
  Component,
  computed,
  ElementRef,
  inject,
  Injector,
  signal,
  viewChild,
  viewChildren,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { AlertComponent, SpinnerComponent } from '@coreui/angular';
import { catchError, map, of, startWith, Subject, switchMap } from 'rxjs';
import { ApiRequestError } from '../../core/api-error.interceptor';
import { AnalyticsApiService } from '../../core/services/analytics-api.service';
import { CatalogPickerComponent } from './catalog-picker.component';
import { observedDayAverage, sortedObservations, validateFilters } from './demand-analysis.helpers';
import { AnalysisState, AppliedFilters, CatalogChoice } from './demand-analysis.models';
import { HistoricalChartComponent } from './historical-chart.component';

type HistoryState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'success'; start: string | null; end: string | null };

@Component({
  selector: 'app-demand-analysis-page',
  imports: [
    FormsModule,
    DatePipe,
    DecimalPipe,
    AlertComponent,
    SpinnerComponent,
    CatalogPickerComponent,
    HistoricalChartComponent,
  ],
  templateUrl: './demand-analysis.page.html',
  styleUrl: './demand-analysis.page.scss',
})
export class DemandAnalysisPage {
  private readonly api = inject(AnalyticsApiService);
  private readonly injector = inject(Injector);
  private readonly catalogs = viewChildren(CatalogPickerComponent);
  private readonly errorSummary = viewChild<ElementRef<HTMLElement>>('filterErrors');
  private readonly requests = new Subject<AppliedFilters | null>();
  private readonly historyRequests = new Subject<void>();
  private readonly lastRequest = signal<AppliedFilters | null>(null);
  protected readonly product = signal<CatalogChoice | null>(null);
  protected readonly store = signal<CatalogChoice | null>(null);
  protected readonly startDate = signal('');
  protected readonly endDate = signal('');
  protected readonly errors = signal<string[]>([]);
  protected readonly state = signal<AnalysisState>({ status: 'idle' });
  protected readonly history = signal<HistoryState>({ status: 'loading' });
  protected readonly tablePage = signal(1);
  protected readonly newestFirst = signal(false);
  protected readonly pageSize = 25;
  protected readonly result = computed(() => {
    const state = this.state();
    return state.status === 'success' ? state : null;
  });
  protected readonly observations = computed(() =>
    sortedObservations(this.result()?.data.daily_sales ?? [], this.newestFirst()),
  );
  protected readonly tablePages = computed(() =>
    Math.max(1, Math.ceil(this.observations().length / this.pageSize)),
  );
  protected readonly visibleObservations = computed(() =>
    this.observations().slice(
      (this.tablePage() - 1) * this.pageSize,
      this.tablePage() * this.pageSize,
    ),
  );
  protected readonly average = computed(() => {
    const data = this.result()?.data;
    return data ? observedDayAverage(data.total_units_sold, data.observed_dates) : null;
  });
  protected readonly filtersChanged = computed(() => {
    const applied = this.lastRequest();
    return (
      !!applied &&
      (applied.product.id !== this.product()?.id ||
        (applied.store?.id ?? null) !== (this.store()?.id ?? null) ||
        applied.startDate !== this.startDate() ||
        applied.endDate !== this.endDate())
    );
  });
  protected readonly dateErrors = computed(() =>
    this.errors().some((message) => !message.startsWith('Select a product')),
  );

  constructor() {
    this.requests
      .pipe(
        switchMap((filters) =>
          filters
            ? this.api
                .getProductAnalytics(filters.product.id, {
                  storeId: filters.store?.id,
                  startDate: filters.startDate,
                  endDate: filters.endDate,
                })
                .pipe(
                  map((data): AnalysisState => ({ status: 'success', filters, data })),
                  catchError((error: unknown) =>
                    of<AnalysisState>({
                      status: 'error',
                      filters,
                      message:
                        error instanceof ApiRequestError && error.status === 404
                          ? 'The selected product was not found. Search the catalog and choose another product.'
                          : error instanceof Error
                            ? error.message
                            : 'Historical sales could not be loaded.',
                    }),
                  ),
                  startWith({ status: 'loading', filters } as const),
                )
            : of<AnalysisState>({ status: 'idle' }),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((state) => {
        this.state.set(state);
        this.tablePage.set(1);
      });

    this.historyRequests
      .pipe(
        startWith(undefined),
        switchMap(() =>
          this.api.getSalesSummary().pipe(
            // The overview is global context only; do not retain/render its unbounded daily array.
            map((data): HistoryState => ({
              status: 'success',
              start: data.start_date,
              end: data.end_date,
            })),
            catchError((error: unknown) =>
              of<HistoryState>({
                status: 'error',
                message:
                  error instanceof Error ? error.message : 'Overall history could not be loaded.',
              }),
            ),
            startWith({ status: 'loading' } as const),
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((state) => this.history.set(state));
  }

  protected applyFilters(): void {
    const product = this.product();
    const errors = validateFilters(product?.id ?? null, this.startDate(), this.endDate());
    this.errors.set(errors);
    if (errors.length || !product) {
      this.lastRequest.set(null);
      this.requests.next(null);
      afterNextRender(() => this.errorSummary()?.nativeElement.focus(), {
        injector: this.injector,
      });
      return;
    }
    const filters = {
      product: { ...product },
      store: this.store() ? { ...this.store()! } : null,
      startDate: this.startDate(),
      endDate: this.endDate(),
    };
    this.lastRequest.set(filters);
    this.requests.next(filters);
  }

  protected resetFilters(): void {
    this.product.set(null);
    this.store.set(null);
    this.startDate.set('');
    this.endDate.set('');
    this.errors.set([]);
    this.lastRequest.set(null);
    this.requests.next(null);
    this.newestFirst.set(false);
    for (const catalog of this.catalogs()) catalog.reset();
  }

  protected retry(): void {
    const filters = this.lastRequest();
    if (filters) this.requests.next(filters);
  }
  protected retryHistory(): void {
    this.historyRequests.next();
  }
  protected sortDates(newest: boolean): void {
    this.newestFirst.set(newest);
    this.tablePage.set(1);
  }
  protected changeTablePage(page: number): void {
    if (page >= 1 && page <= this.tablePages()) this.tablePage.set(page);
  }
}

import { Component, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AlertComponent, SpinnerComponent } from '@coreui/angular';
import { catchError, map, of, startWith, Subject, switchMap } from 'rxjs';
import { ForecastRunItem } from '../../core/models/forecast.models';
import { twoDecimals } from '../../shared/number-format';
import { LoadState, requestState } from '../forecasts/forecast.helpers';
import { RunOverviewComponent } from '../forecasts/run-overview.component';
import { COMPLETE_EXPORT_LIMIT } from './complete-export';
import { CsvDownloadService } from './csv-export';
import { ReportDataService } from './report-data.service';
import { runContext, runFilename } from './report-formatters';
import {
  CsvCell,
  ForecastReportType,
  GeneratedForecastReport,
  REPORT_LABELS,
  RunReportContext,
} from './report.models';
import { ReportTableComponent } from './report-table.component';
import { ReportRunPickerComponent } from './run-picker.component';

type ExportState =
  | { status: 'idle' | 'cancelled' }
  | { status: 'loading'; loaded: number; total: number }
  | { status: 'success'; message: string }
  | { status: 'error'; message: string };
interface ReportQuery {
  context: RunReportContext;
  page: number;
}
@Component({
  selector: 'app-forecast-report',
  imports: [
    AlertComponent,
    SpinnerComponent,
    RunOverviewComponent,
    ReportTableComponent,
    ReportRunPickerComponent,
  ],
  templateUrl: './forecast-report.component.html',
  styleUrl: './reports.scss',
})
export class ForecastReportComponent {
  readonly kind = input.required<ForecastReportType>();
  protected readonly decimal = twoDecimals;
  private readonly facade = inject(ReportDataService);
  private readonly csv = inject(CsvDownloadService);
  private readonly queries = new Subject<ReportQuery | null>();
  private readonly exports = new Subject<GeneratedForecastReport | null>();
  private readonly applied = signal<ReportQuery | null>(null);
  protected readonly selected = signal<ForecastRunItem | null>(null);
  protected readonly validation = signal('');
  protected readonly state = signal<LoadState<GeneratedForecastReport>>({ status: 'idle' });
  protected readonly exportState = signal<ExportState>({ status: 'idle' });
  protected readonly result = computed(() => {
    const state = this.state();
    return state.status === 'success' ? state.data : null;
  });
  protected readonly table = computed(() => {
    const snapshot = this.result();
    return snapshot ? this.facade.table(snapshot.report) : { headers: [], rows: [] };
  });
  protected readonly paged = computed(() => {
    const report = this.result()?.report;
    return report && report.kind !== 'evaluation' ? report.data : null;
  });
  protected readonly title = computed(() => REPORT_LABELS[this.kind()]);
  protected readonly changed = computed(
    () => !!this.applied() && this.applied()?.context.run.id !== this.selected()?.id,
  );
  protected readonly canRefresh = computed(
    () => !!this.applied() && this.state().status !== 'loading',
  );
  protected readonly exporting = computed(() => this.exportState().status === 'loading');
  protected readonly limit = COMPLETE_EXPORT_LIMIT;
  protected readonly canComplete = computed(() => {
    const data = this.paged();
    return (
      !!data && data.total_records > 0 && data.total_records <= this.limit && !this.exporting()
    );
  });
  constructor() {
    this.queries
      .pipe(
        switchMap((query) =>
          query
            ? requestState(
                this.facade
                  .generate(this.kind(), query.context.run.id, query.page)
                  .pipe(map((report) => ({ context: query.context, report }))),
              )
            : of<LoadState<GeneratedForecastReport>>({ status: 'idle' }),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((state) => this.state.set(state));
    this.exports
      .pipe(
        switchMap((snapshot) =>
          snapshot
            ? this.facade.completeExport(snapshot).pipe(
                map((event): ExportState => {
                  if (event.status === 'progress')
                    return { status: 'loading', loaded: event.loaded, total: event.total };
                  this.csv.download(
                    runFilename(snapshot.report.kind, snapshot.context, 'complete'),
                    event.table,
                    this.csvContext(snapshot, 'complete_report', event.total),
                  );
                  return {
                    status: 'success',
                    message: `Downloaded complete ${snapshot.report.kind} report for run #${snapshot.context.run.id}: ${event.total} rows.`,
                  };
                }),
                catchError((error: unknown) =>
                  of<ExportState>({
                    status: 'error',
                    message:
                      error instanceof Error
                        ? error.message
                        : 'Export failed. No file was downloaded.',
                  }),
                ),
                startWith({
                  status: 'loading',
                  loaded: 0,
                  total:
                    snapshot.report.kind === 'evaluation' ? 1 : snapshot.report.data.total_records,
                } as const),
              )
            : of<ExportState>({ status: 'idle' }),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((state) => this.exportState.set(state));
  }
  protected generate(): void {
    const run = this.selected();
    if (this.state().status === 'loading' && run?.id === this.applied()?.context.run.id) return;
    this.cancelExport(false);
    if (!run || run.status !== 'completed') {
      this.validation.set('Select a completed forecast run.');
      this.applied.set(null);
      this.queries.next(null);
      return;
    }
    this.validation.set('');
    const query = { context: { run: { ...run }, generatedAt: new Date().toISOString() }, page: 1 };
    this.applied.set(query);
    this.queries.next(query);
  }
  protected refresh(): void {
    const applied = this.applied();
    if (!applied) return;
    this.cancelExport(false);
    const query = {
      ...applied,
      context: { ...applied.context, generatedAt: new Date().toISOString() },
    };
    this.applied.set(query);
    this.queries.next(query);
  }
  protected page(page: number): void {
    const applied = this.applied();
    const data = this.paged();
    if (
      !applied ||
      !data ||
      page < 1 ||
      page > data.total_pages ||
      this.state().status === 'loading'
    )
      return;
    this.cancelExport(false);
    const query = { ...applied, page };
    this.applied.set(query);
    this.queries.next(query);
  }
  protected exportPage(): void {
    const snapshot = this.result();
    if (!snapshot || !this.table().rows.length || this.exporting()) return;
    const data = snapshot.report;
    const scope =
      data.kind === 'evaluation'
        ? 'evaluation_result'
        : `current_page_${data.data.page}_of_${data.data.total_pages}`;
    try {
      this.csv.download(
        runFilename(
          data.kind,
          snapshot.context,
          data.kind === 'evaluation' ? 'evaluation' : `page-${data.data.page}`,
        ),
        this.facade.table(data),
        this.csvContext(snapshot, scope, this.table().rows.length),
      );
      this.exportState.set({
        status: 'success',
        message: `Downloaded ${scope.replaceAll('_', ' ')} for run #${snapshot.context.run.id}: ${this.table().rows.length} rows.`,
      });
    } catch (error) {
      this.exportState.set({
        status: 'error',
        message: error instanceof Error ? error.message : 'CSV download failed.',
      });
    }
  }
  protected exportComplete(): void {
    const snapshot = this.result();
    if (snapshot && this.canComplete()) this.exports.next(snapshot);
  }
  protected cancelExport(showMessage = true): void {
    this.exports.next(null);
    if (showMessage) this.exportState.set({ status: 'cancelled' });
  }
  private csvContext(
    snapshot: GeneratedForecastReport,
    scope: string,
    rows: number,
  ): Record<string, CsvCell> {
    const report = snapshot.report;
    return {
      report_type: report.kind,
      ...runContext(snapshot.context, scope),
      exported_rows: rows,
      ...(report.kind !== 'evaluation' ? { total_report_rows: report.data.total_records } : {}),
      ...(report.kind === 'recommendations'
        ? {
            increase_threshold_percent: report.data.increase_threshold_percent,
            reduce_threshold_percent: report.data.reduce_threshold_percent,
          }
        : {}),
    };
  }
}

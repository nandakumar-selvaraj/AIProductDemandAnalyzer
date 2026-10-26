import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Type } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { apiErrorInterceptor } from '../../core/api-error.interceptor';
import { ProductAnalyticsResponse } from '../../core/models/analytics.models';
import {
  ForecastRunItem,
  PredictionPage,
  RecommendationPage,
} from '../../core/models/forecast.models';
import { CsvDownloadService } from './csv-export';
import { ForecastReportComponent } from './forecast-report.component';
import { HistoricalSalesReportComponent } from './historical-sales-report.component';
import { ReportsPage } from './reports.page';
import { ReportRunPickerComponent } from './run-picker.component';

const run: ForecastRunItem = {
  id: 7,
  model_name: 'trailing_30_day_average',
  model_version: '1',
  training_cutoff: '2017-12-31',
  horizon_days: 30,
  status: 'completed',
  created_at: '2018-01-01T00:00:00Z',
  started_at: null,
  completed_at: '2018-01-01T00:01:00Z',
  metrics_json: null,
};
const run2 = { ...run, id: 8 };
const historical: ProductAnalyticsResponse = {
  product_id: 1,
  store_id: null,
  start_date: '2017-01-01',
  end_date: '2017-01-03',
  total_units_sold: 30,
  observed_dates: 2,
  daily_sales: [
    { period: '2017-01-01', units_sold: 10 },
    { period: '2017-01-03', units_sold: 20 },
  ],
  monthly_sales: [{ period: '2017-01-01', units_sold: 30 }],
};
function runs(page = 1, items = [run, run2]) {
  return { page, page_size: 10, total_records: 12, total_pages: 2, items };
}
function predictions(id = 7, page = 1, total = 501, size = 50): PredictionPage {
  const offset = (page - 1) * size;
  return {
    run_id: id,
    page,
    page_size: size,
    total_records: total,
    total_pages: Math.ceil(total / size),
    items: Array.from({ length: Math.max(0, Math.min(size, total - offset)) }, (_, n) => ({
      id: offset + n + 1,
      forecast_run_id: id,
      product_id: n + 1,
      store_id: 2,
      forecast_date: '2018-01-01',
      predicted_units: '123.123456789123456789',
    })),
  };
}
function recommendations(id = 7, page = 1, total = 51, size = 50): RecommendationPage {
  const offset = (page - 1) * size;
  return {
    forecast_run_id: id,
    page,
    page_size: size,
    total_records: total,
    total_pages: Math.ceil(total / size),
    increase_threshold_percent: '10',
    reduce_threshold_percent: '-10',
    items: Array.from({ length: Math.max(0, Math.min(size, total - offset)) }, (_, n) => ({
      product_id: offset + n + 1,
      store_id: 2,
      recommendation: (['increase', 'maintain', 'reduce', 'insufficient_data'] as const)[n % 4],
      historical_daily_average: n % 4 === 3 ? null : '0.000',
      forecast_daily_average: '12.123456789',
      change_percent: n % 4 === 3 ? null : '0.000',
      forecast_horizon_days: 30,
      historical_coverage_days: n % 4 === 3 ? 12 : 30,
      historical_window_start: '2017-12-02',
      historical_window_end: '2017-12-31',
      reason: 'Returned reason, with "quotes" and Unicode தமிழ்',
    })),
  };
}
const evaluation = {
  forecast_run_id: 7,
  forecast_cutoff: run.training_cutoff,
  horizon_days: 30,
  total_predictions: 10,
  evaluated_predictions: 0,
  unmatched_predictions: 10,
  coverage_percent: '0.000',
  total_actual_units: 0,
  total_predicted_units: '0.000',
  mae: null,
  wape_percent: null,
  evaluation_status: 'unavailable',
};

describe('Reports workspace', () => {
  let http: HttpTestingController;
  let destroy: (() => void) | undefined;
  let download: ReturnType<typeof vi.fn>;
  const base = environment.apiBaseUrl;
  beforeEach(() => {
    download = vi.fn();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([apiErrorInterceptor])),
        provideHttpClientTesting(),
        { provide: CsvDownloadService, useValue: { download } },
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => {
    destroy?.();
    http.verify();
  });
  async function setup<T>(component: Type<T>, inputs: Record<string, unknown> = {}) {
    const fixture = TestBed.createComponent(component);
    destroy = () => fixture.destroy();
    Object.entries(inputs).forEach(([key, value]) => fixture.componentRef.setInput(key, value));
    fixture.detectChanges();
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    const button = (label: string) => {
      const found = Array.from(root.querySelectorAll<HTMLButtonElement>('button')).find(
        (node) => node.getAttribute('aria-label') === label || node.textContent?.trim() === label,
      );
      expect(found, label).toBeDefined();
      return found!;
    };
    const click = (label: string) => {
      button(label).click();
      fixture.detectChanges();
    };
    const select = async (id: string, text: string) => {
      const node = root.querySelector<HTMLSelectElement>(`#${id}`)!;
      const option = Array.from(node.options).find((option) => option.textContent?.includes(text));
      expect(option, text).toBeDefined();
      node.value = option!.value;
      node.dispatchEvent(new Event('change'));
      fixture.detectChanges();
      await fixture.whenStable();
    };
    const input = async (id: string, value: string) => {
      const node = root.querySelector<HTMLInputElement>(`#${id}`)!;
      node.value = value;
      node.dispatchEvent(new Event('input', { bubbles: true }));
      fixture.detectChanges();
      await fixture.whenStable();
    };
    const submit = () => {
      root
        .querySelector('form')!
        .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      fixture.detectChanges();
    };
    return { fixture, root, button, click, select, input, submit };
  }
  function request(path: string, page?: number, size?: number) {
    return http.expectOne(
      (req) =>
        req.url === `${base}${path}` &&
        (page === undefined || req.params.get('page') === String(page)) &&
        (size === undefined || req.params.get('page_size') === String(size)),
    );
  }
  function catalogs() {
    request('/products', 1, 50).flush({
      page: 1,
      page_size: 50,
      total_records: 2,
      total_pages: 1,
      items: [
        { id: 1, item_code: 'A', name: 'Apples' },
        { id: 2, item_code: 'B', name: '=Unsafe Product' },
      ],
    });
    request('/stores', 1, 50).flush({
      page: 1,
      page_size: 50,
      total_records: 1,
      total_pages: 1,
      items: [{ id: 3, store_code: 'S3', name: 'North Store' }],
    });
  }
  async function historicalUi() {
    const ui = await setup(HistoricalSalesReportComponent);
    catalogs();
    ui.fixture.detectChanges();
    await ui.select('products-catalog-select', 'Apples');
    return ui;
  }
  async function forecastUi(kind: 'predictions' | 'evaluation' | 'recommendations') {
    const ui = await setup(ForecastReportComponent, { kind });
    request('/forecasts/runs', 1, 10).flush(runs());
    ui.fixture.detectChanges();
    await ui.select('report-run', '#7');
    return ui;
  }

  describe('Categories and completed-run choices', () => {
    it('defaults to historical and switches categories without retaining old requests', async () => {
      const ui = await setup(ReportsPage);
      const oldProducts = request('/products');
      const oldStores = request('/stores');
      ui.click('Forecast Predictions');
      await ui.fixture.whenStable();
      expect(oldProducts.cancelled).toBe(true);
      expect(oldStores.cancelled).toBe(true);
      const oldRuns = request('/forecasts/runs');
      expect(oldRuns.request.params.get('status')).toBe('completed');
      ui.click('Forecast Evaluation');
      await ui.fixture.whenStable();
      expect(oldRuns.cancelled).toBe(true);
      request('/forecasts/runs').flush(runs());
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('Forecast Evaluation Report');
      ui.click('Recommendations');
      await ui.fixture.whenStable();
      request('/forecasts/runs').flush(runs());
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('Demand Recommendations Report');
      expect(ui.root.querySelector('[role="group"][aria-label="Report category"]')).not.toBeNull();
      expect(ui.root.querySelectorAll('.category-card')).toHaveLength(4);
      expect(
        ui.root.querySelector('.category-card[aria-pressed="true"]')?.getAttribute('aria-label'),
      ).toBe('Recommendations');
    });
    it('cancels report data and active exports when category changes', async () => {
      const ui = await setup(ReportsPage);
      catalogs();
      ui.fixture.detectChanges();
      ui.click('Forecast Predictions');
      await ui.fixture.whenStable();
      request('/forecasts/runs').flush(runs());
      ui.fixture.detectChanges();
      await ui.select('report-run', '#7');
      ui.click('Generate Report');
      const pending = request('/forecasts/7/predictions');
      ui.click('Forecast Evaluation');
      await ui.fixture.whenStable();
      expect(pending.cancelled).toBe(true);
      request('/forecasts/runs').flush(runs());
      ui.fixture.detectChanges();
      ui.click('Forecast Predictions');
      await ui.fixture.whenStable();
      request('/forecasts/runs').flush(runs());
      ui.fixture.detectChanges();
      await ui.select('report-run', '#7');
      ui.click('Generate Report');
      request('/forecasts/7/predictions').flush(predictions());
      ui.fixture.detectChanges();
      ui.click('Export Complete Report');
      const exportPage = request('/forecasts/7/predictions', 1, 500);
      ui.click('Historical Sales');
      await ui.fixture.whenStable();
      expect(exportPage.cancelled).toBe(true);
      expect(download).not.toHaveBeenCalled();
      catalogs();
    });
    it('pages completed run choices while preserving a pinned selection', async () => {
      const ui = await setup(ReportRunPickerComponent);
      const first = request('/forecasts/runs', 1, 10);
      expect(first.request.params.get('status')).toBe('completed');
      first.flush(runs());
      ui.fixture.detectChanges();
      await ui.select('report-run', '#7');
      ui.click('Next run choices');
      request('/forecasts/runs', 2, 10).flush(runs(2, [{ ...run, id: 6 }]));
      ui.fixture.detectChanges();
      expect(
        ui.root.querySelector<HTMLSelectElement>('#report-run')!.selectedOptions[0].textContent,
      ).toContain('#7');
      ui.click('Refresh run choices');
      const pending = request('/forecasts/runs', 2);
      ui.fixture.destroy();
      expect(pending.cancelled).toBe(true);
    });
    it('shows completed-run loading, error/retry and empty states', async () => {
      const ui = await setup(ReportRunPickerComponent);
      expect(ui.root.textContent).toContain('Loading completed runs');
      request('/forecasts/runs').flush(
        { detail: 'Runs unavailable' },
        { status: 503, statusText: 'Unavailable' },
      );
      ui.fixture.detectChanges();
      expect(ui.root.querySelector('[role="alert"]')?.textContent).toContain('Runs unavailable');
      ui.click('Retry completed runs');
      request('/forecasts/runs').flush({ ...runs(1, []), total_records: 0, total_pages: 0 });
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('No completed forecast runs');
    });
  });

  describe('Historical Sales Report', () => {
    it('validates product, date order and inclusive 365-day limit before generation', async () => {
      const ui = await setup(HistoricalSalesReportComponent);
      catalogs();
      ui.fixture.detectChanges();
      ui.submit();
      expect(ui.root.querySelector('[role="alert"]')?.textContent).toContain('Select a product');
      await ui.select('products-catalog-select', 'Apples');
      await ui.input('report-start', '2017-02-01');
      await ui.input('report-end', '2017-01-01');
      ui.submit();
      expect(ui.root.textContent).toContain('Start date must not be after end date');
      await ui.input('report-start', '2016-01-01');
      await ui.input('report-end', '2017-01-01');
      ui.submit();
      expect(ui.root.textContent).toContain('at most 365 calendar days');
      http.expectNone((req) => req.url.includes('/analytics'));
      await ui.input('report-start', '2017-01-01');
      await ui.input('report-end', '2017-12-31');
      ui.submit();
      const pending = request('/products/1/analytics');
      expect(pending.request.params.get('start_date')).toBe('2017-01-01');
      expect(pending.request.params.get('end_date')).toBe('2017-12-31');
      pending.flush(historical);
    });
    it('supports product/store/date filters and omits blank optional parameters', async () => {
      const ui = await historicalUi();
      ui.submit();
      const all = request('/products/1/analytics');
      expect(all.request.params.keys()).toEqual([]);
      all.flush(historical);
      ui.fixture.detectChanges();
      await ui.select('stores-catalog-select', 'North Store');
      await ui.input('report-start', '2017-01-01');
      await ui.input('report-end', '2017-01-31');
      ui.submit();
      const scoped = request('/products/1/analytics');
      expect(scoped.request.params.keys().sort()).toEqual(['end_date', 'start_date', 'store_id']);
      expect(scoped.request.params.get('store_id')).toBe('3');
      scoped.flush({ ...historical, store_id: 3 });
    });
    it('renders observed dates, daily/monthly charts and complete returned observation exports', async () => {
      const ui = await historicalUi();
      ui.submit();
      expect(ui.root.textContent).toContain('Generating historical report');
      request('/products/1/analytics').flush(historical);
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('Observed sales dates');
      expect(ui.root.textContent).toContain('not calendar days');
      expect(ui.root.querySelectorAll('svg[role="img"]')).toHaveLength(2);
      expect(ui.root.querySelector('caption')?.textContent).toBeTruthy();
      ui.click('Export Daily CSV');
      expect(download.mock.lastCall?.[1].rows).toEqual([
        ['2017-01-01', 10],
        ['2017-01-03', 20],
      ]);
      expect(download.mock.lastCall?.[2]).toMatchObject({
        product_id: 1,
        product_name: 'Apples',
        store_id: 'all',
        observed_sales_dates: 2,
        export_scope: 'all_returned_daily_observations',
      });
      ui.click('Export Monthly CSV');
      expect(download.mock.lastCall?.[1].rows).toEqual([['2017-01-01', 30]]);
      expect(download.mock.lastCall?.[0]).toContain('monthly.csv');
    });
    it('exports applied context after draft filters change and refreshes the applied request', async () => {
      const ui = await historicalUi();
      ui.submit();
      request('/products/1/analytics').flush(historical);
      ui.fixture.detectChanges();
      await ui.select('products-catalog-select', '=Unsafe Product');
      await ui.select('stores-catalog-select', 'North Store');
      await ui.input('report-start', '2017-05-01');
      expect(ui.root.textContent).toContain('Filters have changed');
      ui.click('Export Daily CSV');
      expect(download.mock.lastCall?.[2]).toMatchObject({
        product_id: 1,
        store_id: 'all',
        requested_start_date: 'backend_default',
      });
      ui.click('Refresh Report');
      const refresh = request('/products/1/analytics');
      expect(refresh.request.params.keys()).toEqual([]);
      refresh.flush(historical);
    });
    it('cancels obsolete generations, clears stale errors/results and retries applied filters', async () => {
      const ui = await historicalUi();
      ui.submit();
      const old = request('/products/1/analytics');
      await ui.select('products-catalog-select', '=Unsafe Product');
      ui.submit();
      expect(old.cancelled).toBe(true);
      const current = request('/products/2/analytics');
      current.flush(
        { detail: 'Analytics unavailable' },
        { status: 503, statusText: 'Unavailable' },
      );
      ui.fixture.detectChanges();
      expect(ui.root.querySelector('app-report-table')).toBeNull();
      expect(ui.root.textContent).toContain('Analytics unavailable');
      ui.click('Retry Report');
      request('/products/2/analytics').flush({ ...historical, product_id: 2 });
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('Applied product #2');
      ui.click('Refresh Report');
      const pending = request('/products/2/analytics');
      ui.fixture.destroy();
      expect(pending.cancelled).toBe(true);
    });
    it('handles empty data, download failures, and no fabricated observations', async () => {
      const ui = await historicalUi();
      ui.submit();
      request('/products/1/analytics').flush({
        ...historical,
        start_date: null,
        end_date: null,
        observed_dates: 0,
        total_units_sold: 0,
        daily_sales: [],
        monthly_sales: [],
      });
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('No historical observations');
      expect(ui.button('Export Daily CSV').disabled).toBe(true);
      expect(ui.root.querySelector('svg')).toBeNull();
      ui.click('Refresh Report');
      request('/products/1/analytics').flush(historical);
      ui.fixture.detectChanges();
      download.mockImplementationOnce(() => {
        throw new Error('Download blocked');
      });
      ui.click('Export Daily CSV');
      expect(ui.root.textContent).toContain('Download blocked');
      ui.click('Export Daily CSV');
      expect(ui.root.textContent).toContain('Downloaded all 2');
    });
    it('paginates displayed observations while exporting the entire bounded response', async () => {
      const ui = await historicalUi();
      const daily = Array.from({ length: 31 }, (_, n) => ({
        period: `2017-01-${String(n + 1).padStart(2, '0')}`,
        units_sold: n,
      }));
      ui.submit();
      request('/products/1/analytics').flush({
        ...historical,
        daily_sales: daily,
        observed_dates: 31,
      });
      ui.fixture.detectChanges();
      expect(ui.root.querySelectorAll('app-report-table tbody tr')).toHaveLength(25);
      ui.click('Next observations');
      expect(ui.root.querySelectorAll('app-report-table tbody tr')).toHaveLength(6);
      ui.click('Export Daily CSV');
      expect(download.mock.lastCall?.[1].rows).toHaveLength(31);
    });
  });

  describe('Forecast Predictions Report', () => {
    it('requires a completed run and displays rounded, page-scoped predictions', async () => {
      const ui = await setup(ForecastReportComponent, { kind: 'predictions' });
      request('/forecasts/runs').flush(runs());
      ui.fixture.detectChanges();
      ui.click('Generate Report');
      expect(ui.root.textContent).toContain('Select a completed forecast run');
      http.expectNone((req) => req.url.includes('/predictions'));
      await ui.select('report-run', '#7');
      ui.click('Generate Report');
      expect(ui.root.textContent).toContain('Generating Forecast Predictions Report');
      request('/forecasts/7/predictions', 1, 50).flush(predictions());
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('123.12');
      expect(ui.root.textContent).toContain('current page only');
      expect(ui.root.textContent).toContain(run.model_name);
      ui.click('Export Current Page');
      expect(download.mock.lastCall?.[0]).toContain(
        'run-7-cutoff-2017-12-31-horizon-30-page-1.csv',
      );
      expect(download.mock.lastCall?.[1].rows).toHaveLength(50);
      expect(download.mock.lastCall?.[2]).toMatchObject({
        forecast_run_id: 7,
        export_scope: 'current_page_1_of_11',
        exported_rows: 50,
        total_report_rows: 501,
      });
    });
    it('pages on the server and clears rows while loading or on page failure', async () => {
      const ui = await forecastUi('predictions');
      ui.click('Generate Report');
      request('/forecasts/7/predictions', 1).flush(predictions());
      ui.fixture.detectChanges();
      ui.click('Next report page');
      expect(ui.root.querySelector('app-report-table')).toBeNull();
      request('/forecasts/7/predictions', 2, 50).flush(
        { detail: 'Page unavailable' },
        { status: 503, statusText: 'Unavailable' },
      );
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('Page unavailable');
      ui.click('Retry Report');
      request('/forecasts/7/predictions', 2).flush(predictions(7, 2));
      ui.fixture.detectChanges();
      ui.click('Export Current Page');
      expect(download.mock.lastCall?.[2].export_scope).toBe('current_page_2_of_11');
    });
    it('preserves generated run context after selection edits and cancels old requests on Generate', async () => {
      const ui = await forecastUi('predictions');
      ui.click('Generate Report');
      request('/forecasts/7/predictions').flush(predictions());
      ui.fixture.detectChanges();
      await ui.select('report-run', '#8');
      expect(ui.root.textContent).toContain('Run selection has changed');
      ui.click('Export Current Page');
      expect(download.mock.lastCall?.[2].forecast_run_id).toBe(7);
      ui.click('Refresh Report');
      const old = request('/forecasts/7/predictions');
      ui.click('Generate Report');
      expect(old.cancelled).toBe(true);
      request('/forecasts/8/predictions', 1).flush(predictions(8));
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('Applied run #8');
    });
    it('handles empty responses without offering an empty complete report', async () => {
      const ui = await forecastUi('predictions');
      ui.click('Generate Report');
      request('/forecasts/7/predictions').flush(predictions(7, 1, 0));
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('No rows are available');
      expect(ui.button('Export Complete Report').disabled).toBe(true);
      expect(ui.button('Export Current Page').disabled).toBe(true);
    });
    it('collects all pages before downloading, captures run context and exposes progress', async () => {
      const ui = await forecastUi('predictions');
      ui.click('Generate Report');
      request('/forecasts/7/predictions').flush(predictions());
      ui.fixture.detectChanges();
      ui.click('Export Complete Report');
      const first = request('/forecasts/7/predictions', 1, 500);
      expect(download).not.toHaveBeenCalled();
      expect(ui.button('Export Current Page').disabled).toBe(true);
      first.flush(predictions(7, 1, 501, 500));
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('500 / 501');
      expect(ui.root.querySelector('progress')?.getAttribute('aria-label')).toBe(
        'Complete CSV export progress',
      );
      await ui.select('report-run', '#8');
      request('/forecasts/7/predictions', 2, 500).flush(predictions(7, 2, 501, 500));
      ui.fixture.detectChanges();
      expect(download).toHaveBeenCalledOnce();
      expect(download.mock.lastCall?.[0]).toContain('run-7');
      expect(download.mock.lastCall?.[0]).toContain('complete.csv');
      expect(download.mock.lastCall?.[1].rows).toHaveLength(501);
      expect(download.mock.lastCall?.[2]).toMatchObject({
        forecast_run_id: 7,
        export_scope: 'complete_report',
        exported_rows: 501,
      });
      expect(ui.root.textContent).toContain('Downloaded complete predictions report for run #7');
    });
    it('disables complete export above the documented limit without silently truncating', async () => {
      const ui = await forecastUi('predictions');
      ui.click('Generate Report');
      request('/forecasts/7/predictions').flush(predictions(7, 1, 20001));
      ui.fixture.detectChanges();
      expect(ui.button('Export Complete Report').disabled).toBe(true);
      expect(ui.root.textContent).toContain('backend streaming export API');
      ui.click('Export Complete Report');
      http.expectNone((req) => req.params.get('page_size') === '500');
      ui.click('Export Current Page');
      expect(download.mock.lastCall?.[1].rows).toHaveLength(50);
    });
    it('cancels a complete export and permits an explicit retry', async () => {
      const ui = await forecastUi('predictions');
      ui.click('Generate Report');
      request('/forecasts/7/predictions').flush(predictions());
      ui.fixture.detectChanges();
      ui.click('Export Complete Report');
      request('/forecasts/7/predictions', 1, 500).flush(predictions(7, 1, 501, 500));
      const old = request('/forecasts/7/predictions', 2, 500);
      ui.fixture.detectChanges();
      ui.click('Cancel Export');
      expect(old.cancelled).toBe(true);
      expect(download).not.toHaveBeenCalled();
      expect(ui.root.textContent).toContain('Export cancelled');
      ui.click('Export Complete Report');
      const retried = request('/forecasts/7/predictions', 1, 500);
      ui.fixture.destroy();
      expect(retried.cancelled).toBe(true);
    });
    it('does not download partial results when a later export page fails and can retry from page one', async () => {
      const ui = await forecastUi('predictions');
      ui.click('Generate Report');
      request('/forecasts/7/predictions').flush(predictions());
      ui.fixture.detectChanges();
      ui.click('Export Complete Report');
      request('/forecasts/7/predictions', 1, 500).flush(predictions(7, 1, 501, 500));
      request('/forecasts/7/predictions', 2, 500).flush(
        { detail: 'Export page failed' },
        { status: 503, statusText: 'Unavailable' },
      );
      ui.fixture.detectChanges();
      expect(download).not.toHaveBeenCalled();
      expect(ui.root.textContent).toContain('Export page failed');
      expect(ui.root.textContent).toContain('No partial report was downloaded');
      ui.click('Export Complete Report');
      const current = request('/forecasts/7/predictions', 1, 500);
      ui.fixture.destroy();
      expect(current.cancelled).toBe(true);
    });
    it('cancels active export on report refresh and cancels active data on teardown', async () => {
      const ui = await forecastUi('predictions');
      ui.click('Generate Report');
      request('/forecasts/7/predictions').flush(predictions());
      ui.fixture.detectChanges();
      ui.click('Export Complete Report');
      const exportRequest = request('/forecasts/7/predictions', 1, 500);
      ui.click('Refresh Report');
      expect(exportRequest.cancelled).toBe(true);
      const dataRequest = request('/forecasts/7/predictions', 1, 50);
      ui.fixture.destroy();
      expect(dataRequest.cancelled).toBe(true);
      expect(download).not.toHaveBeenCalled();
    });
  });

  describe('Evaluation Report', () => {
    it('generates manually, prevents duplicate requests and exports N/A metrics without zero substitution', async () => {
      const ui = await forecastUi('evaluation');
      http.expectNone(`${base}/forecasts/evaluate`);
      ui.click('Generate Report');
      ui.click('Generate Report');
      const pending = request('/forecasts/evaluate');
      expect(pending.request.method).toBe('POST');
      expect(pending.request.body).toEqual({ forecast_run_id: 7 });
      http.expectNone(`${base}/forecasts/evaluate`);
      pending.flush(evaluation);
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('N/A');
      expect(ui.root.textContent).toContain('Partial or unavailable coverage limits');
      expect(ui.root.textContent).toContain('0.00');
      ui.click('Export Evaluation CSV');
      expect(download.mock.lastCall?.[1].rows).toEqual([
        ['unavailable', 10, 0, 10, '0.000', null, null, 0, '0.000'],
      ]);
      expect(download.mock.lastCall?.[2].export_scope).toBe('evaluation_result');
      expect(ui.root.textContent).not.toContain('Export Complete Report');
    });
    it.each([404, 409, 422, 503])(
      'handles evaluation HTTP %s and retries the generated run',
      async (status) => {
        const ui = await forecastUi('evaluation');
        ui.click('Generate Report');
        request('/forecasts/evaluate').flush(
          { detail: 'Evaluation unavailable' },
          { status, statusText: 'Error' },
        );
        ui.fixture.detectChanges();
        expect(ui.root.textContent).toContain('Evaluation unavailable');
        await ui.select('report-run', '#8');
        ui.click('Retry Report');
        const pending = request('/forecasts/evaluate');
        expect(pending.request.body).toEqual({ forecast_run_id: 7 });
        pending.flush(evaluation);
      },
    );
    it('shows precise measured metrics and partial matching counts', async () => {
      const ui = await forecastUi('evaluation');
      ui.click('Generate Report');
      request('/forecasts/evaluate').flush({
        ...evaluation,
        evaluated_predictions: 5,
        unmatched_predictions: 5,
        coverage_percent: '50.000',
        mae: '1.234567891',
        wape_percent: '12.34567891',
        total_actual_units: 50,
        total_predicted_units: '55.123456789',
        evaluation_status: 'partial',
      });
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('1.23');
      expect(ui.root.textContent).toContain('55.12');
      expect(ui.root.textContent).toContain('partial');
      expect(ui.root.querySelectorAll('th[scope="col"]')).toHaveLength(9);
    });
  });

  describe('Recommendations Report', () => {
    it('shows all trend labels, N/A, exact decimals, coverage and reasons with a scoped page export', async () => {
      const ui = await forecastUi('recommendations');
      ui.click('Generate Report');
      const pending = request('/recommendations', 1, 50);
      expect(pending.request.params.get('forecast_run_id')).toBe('7');
      pending.flush(recommendations());
      ui.fixture.detectChanges();
      const text = ui.root.textContent!;
      for (const label of [
        'Increase',
        'Maintain',
        'Reduce',
        'Insufficient Data',
        'N/A',
        '12.12',
        'Returned reason',
        'not inventory levels',
      ])
        expect(text).toContain(label);
      expect(ui.root.querySelectorAll('.status-chip.insufficient_data').length).toBeGreaterThan(0);
      ui.click('Export Current Page');
      expect(download.mock.lastCall?.[1].rows).toHaveLength(50);
      expect(download.mock.lastCall?.[2]).toMatchObject({
        forecast_run_id: 7,
        export_scope: 'current_page_1_of_2',
        increase_threshold_percent: '10',
        reduce_threshold_percent: '-10',
      });
    });
    it('paginates, retries errors and handles an empty recommendation report', async () => {
      const ui = await forecastUi('recommendations');
      ui.click('Generate Report');
      request('/recommendations', 1).flush(recommendations());
      ui.fixture.detectChanges();
      ui.click('Next report page');
      request('/recommendations', 2).flush(
        { detail: 'Recommendations unavailable' },
        { status: 503, statusText: 'Unavailable' },
      );
      ui.fixture.detectChanges();
      expect(ui.root.querySelector('app-report-table')).toBeNull();
      ui.click('Retry Report');
      request('/recommendations', 2).flush(recommendations(7, 2));
      ui.fixture.detectChanges();
      expect(ui.root.querySelectorAll('tbody tr')).toHaveLength(1);
      await ui.select('report-run', '#8');
      ui.click('Generate Report');
      request('/recommendations', 1).flush(recommendations(8, 1, 0));
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('No rows are available');
      expect(ui.button('Export Current Page').disabled).toBe(true);
    });
    it('exports all recommendations with exact nullable values and validates response thresholds', async () => {
      const ui = await forecastUi('recommendations');
      ui.click('Generate Report');
      request('/recommendations', 1, 50).flush(recommendations());
      ui.fixture.detectChanges();
      ui.click('Export Complete Report');
      request('/recommendations', 1, 500).flush(recommendations(7, 1, 51, 500));
      ui.fixture.detectChanges();
      expect(download.mock.lastCall?.[1].rows).toHaveLength(51);
      expect(download.mock.lastCall?.[2].export_scope).toBe('complete_report');
      download.mockClear();
      ui.click('Export Complete Report');
      request('/recommendations', 1, 500).flush({
        ...recommendations(7, 1, 51, 500),
        increase_threshold_percent: '20',
      });
      ui.fixture.detectChanges();
      expect(download).not.toHaveBeenCalled();
      expect(ui.root.textContent).toContain('pagination changed');
    });
    it('rejects mismatched run responses instead of showing another run under the selected label', async () => {
      const ui = await forecastUi('recommendations');
      ui.click('Generate Report');
      request('/recommendations').flush(recommendations(8));
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('does not match the requested run');
      expect(ui.root.querySelector('app-report-table')).toBeNull();
    });
  });
});

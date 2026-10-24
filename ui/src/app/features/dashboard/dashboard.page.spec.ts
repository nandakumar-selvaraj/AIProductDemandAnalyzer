import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { apiErrorInterceptor } from '../../core/api-error.interceptor';
import { DashboardSummary } from '../../core/models/analytics.models';
import { DashboardPage } from './dashboard.page';

const summary: DashboardSummary = {
  product_count: 2,
  store_count: 1,
  historical_start_date: '2024-01-01',
  historical_end_date: '2024-02-29',
  total_units_sold: 1700,
  monthly_sales: [
    ['2024-01-01', 1100],
    ['2024-02-01', 600],
  ],
  latest_forecast: {
    forecast_run_id: 7,
    training_cutoff: '2024-02-29',
    horizon_days: 30,
    forecast_demand_total: 100,
    recommendation_counts: { increase: 1, maintain: 0, reduce: 0, insufficient_data: 0 },
  },
};

describe('DashboardPage', () => {
  let fixture: ComponentFixture<DashboardPage>;
  let root: HTMLElement;
  let http: HttpTestingController;
  const request = () => http.expectOne(`${environment.apiBaseUrl}/dashboard/summary`);

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [DashboardPage],
      providers: [
        provideHttpClient(withInterceptors([apiErrorInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(DashboardPage);
    root = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
  });
  afterEach(() => {
    fixture.destroy();
    http.verify();
  });

  it('shows loading status, a neutral heading, and a disabled refresh control', () => {
    expect(root.querySelector('h1')?.textContent).toBe('Demand Overview');
    expect(root.querySelector('[role="status"]')?.textContent).toContain('Loading dashboard');
    expect(root.querySelector<HTMLButtonElement>('.refresh-button')?.disabled).toBe(true);
    expect(root.querySelector('.metric-grid')).toBeNull();
    request().flush(summary);
  });

  it('renders API metrics, forecast details, and accessible exact chart values', () => {
    request().flush(summary);
    fixture.detectChanges();
    expect(root.querySelector('.loading-state')).toBeNull();
    expect(
      Array.from(root.querySelectorAll('.metric-value'), (node) => node.textContent?.trim()),
    ).toEqual(['2', '1', '1,700', '100']);
    expect(root.querySelector('.forecast-details')?.textContent).toContain('#7');
    const chart = root.querySelector('[role="img"]');
    expect(chart?.getAttribute('aria-describedby')).toBe('sales-chart-description');
    expect(root.querySelector('#sales-chart-description')?.textContent).toContain(
      '2 recorded months',
    );
    const table = root.querySelector('table');
    expect(table?.querySelector('caption')?.textContent?.trim()).toBe('Monthly sales values');
    expect(table?.textContent).toContain('January 2024');
    expect(table?.textContent).toContain('1,100');
    expect(root.querySelector('.trend-up')?.textContent).toContain('Increase:');
  });

  it('shows genuine empty states when the API has no sales or completed forecast', () => {
    request().flush({
      ...summary,
      product_count: 0,
      store_count: 0,
      total_units_sold: 0,
      historical_start_date: null,
      historical_end_date: null,
      monthly_sales: [],
      latest_forecast: null,
    });
    fixture.detectChanges();
    expect(root.textContent).toContain('No sales history yet');
    expect(root.textContent).toContain('No forecast available');
    expect(root.querySelector('[role="img"]')).toBeNull();
    expect(root.querySelector('[role="alert"]')).toBeNull();
  });

  it('shows a normalized error and recovers through retry', () => {
    request().flush(
      { detail: 'Dashboard is temporarily unavailable' },
      { status: 503, statusText: 'Unavailable' },
    );
    fixture.detectChanges();
    expect(root.querySelector('[role="alert"]')?.textContent).toContain(
      'Dashboard is temporarily unavailable',
    );
    expect(root.querySelector('.metric-grid')).toBeNull();
    expect(root.querySelector('.loading-state')).toBeNull();
    root.querySelector<HTMLButtonElement>('.retry-link')!.click();
    fixture.detectChanges();
    expect(root.querySelector('.loading-state')).not.toBeNull();
    expect(root.querySelector('[role="alert"]')).toBeNull();
    request().flush(summary);
    fixture.detectChanges();
    expect(root.querySelector('.metric-grid')).not.toBeNull();
    expect(root.querySelector('[role="alert"]')).toBeNull();
  });

  it('clears previous metrics when a refresh fails', () => {
    request().flush(summary);
    fixture.detectChanges();
    root.querySelector<HTMLButtonElement>('.refresh-button')!.click();
    fixture.detectChanges();
    expect(root.querySelector('.metric-grid')).toBeNull();
    request().flush(null, { status: 500, statusText: 'Error' });
    fixture.detectChanges();
    expect(root.querySelector('[role="alert"]')).not.toBeNull();
    expect(root.querySelector('.metric-grid')).toBeNull();
  });

  it('cancels its in-flight HTTP request when destroyed', () => {
    const pending = request();
    fixture.destroy();
    expect(pending.cancelled).toBe(true);
  });
});

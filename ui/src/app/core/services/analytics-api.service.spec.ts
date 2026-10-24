import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { AnalyticsApiService } from './analytics-api.service';
import { environment } from '../../../environments/environment';

describe('AnalyticsApiService', () => {
  let service: AnalyticsApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [AnalyticsApiService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AnalyticsApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('requests the dashboard summary from the configured API base URL', () => {
    service.getDashboardSummary().subscribe();
    const request = http.expectOne(`${environment.apiBaseUrl}/dashboard/summary`);
    expect(request.request.method).toBe('GET');
    request.flush({ product_count: 0, store_count: 0, historical_start_date: null, historical_end_date: null, total_units_sold: 0, monthly_sales: [], latest_forecast: null });
  });

  it('encodes product catalog pagination and search through HttpParams', () => {
    service.getProducts(2, 10, 'tea & coffee').subscribe();
    const request = http.expectOne((candidate) => candidate.url === `${environment.apiBaseUrl}/products`);
    expect(request.request.params.get('page')).toBe('2');
    expect(request.request.params.get('page_size')).toBe('10');
    expect(request.request.params.get('search')).toBe('tea & coffee');
    request.flush({ page: 2, page_size: 10, total_records: 0, total_pages: 0, items: [] });
  });
});
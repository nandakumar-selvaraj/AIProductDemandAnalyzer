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
    request.flush({
      product_count: 0,
      store_count: 0,
      historical_start_date: null,
      historical_end_date: null,
      total_units_sold: 0,
      monthly_sales: [],
      latest_forecast: null,
    });
  });

  it('encodes product catalog pagination and search through HttpParams', () => {
    service.getProducts(2, 10, 'tea & coffee').subscribe();
    const request = http.expectOne(
      (candidate) => candidate.url === `${environment.apiBaseUrl}/products`,
    );
    expect(request.request.params.get('page')).toBe('2');
    expect(request.request.params.get('page_size')).toBe('10');
    expect(request.request.params.get('search')).toBe('tea & coffee');
    request.flush({ page: 2, page_size: 10, total_records: 0, total_pages: 0, items: [] });
  });

  it('loads paginated stores with an encoded search', () => {
    service.getStores(3, 50, ' North & West ').subscribe();
    const request = http.expectOne((req) => req.url === `${environment.apiBaseUrl}/stores`);
    expect(request.request.params.keys().sort()).toEqual(['page', 'page_size', 'search']);
    expect(request.request.params.get('page')).toBe('3');
    expect(request.request.params.get('page_size')).toBe('50');
    expect(request.request.params.get('search')).toBe('North & West');
    request.flush({ page: 3, page_size: 50, total_records: 0, total_pages: 0, items: [] });
  });

  it('sends only the verified product analytics filter names', () => {
    service
      .getProductAnalytics(17, { storeId: 3, startDate: '2024-01-01', endDate: '2024-01-31' })
      .subscribe();
    const request = http.expectOne(
      (req) => req.url === `${environment.apiBaseUrl}/products/17/analytics`,
    );
    expect(request.request.params.keys().sort()).toEqual(['end_date', 'start_date', 'store_id']);
    expect(request.request.params.get('store_id')).toBe('3');
    expect(request.request.params.get('start_date')).toBe('2024-01-01');
    expect(request.request.params.get('end_date')).toBe('2024-01-31');
    request.flush({});
  });

  it('omits blank dates and All Stores rather than serializing undefined or null', () => {
    service.getProductAnalytics(17, { startDate: '', endDate: '' }).subscribe();
    const request = http.expectOne(`${environment.apiBaseUrl}/products/17/analytics`);
    expect(request.request.params.keys()).toEqual([]);
    request.flush({});
  });

  it('supports partial date ranges without inventing the other date', () => {
    service.getProductAnalytics(17, { endDate: '2024-04-01' }).subscribe();
    const request = http.expectOne((req) => req.url.endsWith('/17/analytics'));
    expect(request.request.params.keys()).toEqual(['end_date']);
    request.flush({});
  });

  it('uses the real sales summary endpoint without speculative filters', () => {
    service.getSalesSummary().subscribe();
    const request = http.expectOne(`${environment.apiBaseUrl}/sales/summary`);
    expect(request.request.method).toBe('GET');
    expect(request.request.params.keys()).toEqual([]);
    request.flush({
      start_date: null,
      end_date: null,
      total_sales: 0,
      store_count: 0,
      product_count: 0,
      daily_sales: [],
    });
  });
});

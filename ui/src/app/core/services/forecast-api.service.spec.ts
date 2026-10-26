import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { ForecastApiService } from './forecast-api.service';

describe('ForecastApiService contracts', () => {
  let api: ForecastApiService;
  let http: HttpTestingController;
  const base = environment.apiBaseUrl;
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    api = TestBed.inject(ForecastApiService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('accepts no latest completed run without substituting a run', () => {
    const result = vi.fn();
    api.getLatestCompleted().subscribe(result);
    const request = http.expectOne(`${base}/forecasts/latest`);
    expect(request.request.method).toBe('GET');
    request.flush(null);
    expect(result).toHaveBeenCalledWith(null);
  });
  it('omits All status and uses bounded server history pages', () => {
    api.getRuns().subscribe();
    const request = http.expectOne((req) => req.url === `${base}/forecasts/runs`);
    expect(request.request.params.keys().sort()).toEqual(['page', 'page_size']);
    expect(request.request.params.get('page')).toBe('1');
    expect(request.request.params.get('page_size')).toBe('10');
    request.flush({});
  });
  it.each(['pending', 'running', 'completed', 'failed'] as const)(
    'sends the verified %s status and page',
    (status) => {
      api.getRuns(3, status).subscribe();
      const request = http.expectOne((req) => req.url === `${base}/forecasts/runs`);
      expect(request.request.params.get('status')).toBe(status);
      expect(request.request.params.get('page')).toBe('3');
      request.flush({});
    },
  );
  it('posts the forecast cutoff as start_date, including a null backend default', () => {
    for (const cutoff of [null, '2017-12-31']) {
      api.createForecast({ horizon_days: 30, start_date: cutoff }).subscribe();
      const request = http.expectOne(`${base}/forecasts`);
      expect(request.request.method).toBe('POST');
      expect(request.request.body).toEqual({ horizon_days: 30, start_date: cutoff });
      request.flush({});
    }
  });
  it('fetches only the selected predictions page and preserves decimal precision', () => {
    const result = vi.fn();
    api.getPredictions(9, 2).subscribe(result);
    const request = http.expectOne((req) => req.url === `${base}/forecasts/9/predictions`);
    expect(request.request.params.toString()).toBe('page=2&page_size=50');
    const response = {
      run_id: 9,
      page: 2,
      page_size: 50,
      total_records: 51,
      total_pages: 2,
      items: [
        {
          id: 51,
          forecast_run_id: 9,
          store_id: 1,
          product_id: 3,
          forecast_date: '2018-01-02',
          predicted_units: '123456789.123456789',
        },
      ],
    };
    request.flush(response);
    expect(result).toHaveBeenCalledWith(response);
  });
  it('evaluates the selected persisted run using the exact request field', () => {
    api.evaluate(9).subscribe();
    const request = http.expectOne(`${base}/forecasts/evaluate`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ forecast_run_id: 9 });
    request.flush({});
  });
  it('fetches recommendations with run identity and bounded server pagination', () => {
    api.getRecommendations(9, 3).subscribe();
    const request = http.expectOne((req) => req.url === `${base}/recommendations`);
    expect(request.request.params.keys().sort()).toEqual(['forecast_run_id', 'page', 'page_size']);
    expect(request.request.params.get('forecast_run_id')).toBe('9');
    expect(request.request.params.get('page')).toBe('3');
    expect(request.request.params.get('page_size')).toBe('50');
    request.flush({});
  });
  it('backtests with cutoff_date rather than the creation start_date or run ID', () => {
    api.backtest({ cutoff_date: '2017-11-30', horizon_days: 7 }).subscribe();
    const request = http.expectOne(`${base}/forecasts/backtest`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ cutoff_date: '2017-11-30', horizon_days: 7 });
    request.flush({});
  });
  it('supports verified 500-row export batches without changing default UI page sizes', () => {
    api.getPredictions(9, 2, 500).subscribe();
    const predictions = http.expectOne((req) => req.url === `${base}/forecasts/9/predictions`);
    expect(predictions.request.params.toString()).toBe('page=2&page_size=500');
    predictions.flush({});
    api.getRecommendations(9, 2, 500).subscribe();
    const recommendations = http.expectOne((req) => req.url === `${base}/recommendations`);
    expect(recommendations.request.params.get('page_size')).toBe('500');
    expect(recommendations.request.params.get('page')).toBe('2');
    expect(recommendations.request.params.get('forecast_run_id')).toBe('9');
    recommendations.flush({});
  });

  it('cancels an unsubscribed HTTP request', () => {
    const sub = api.getPredictions(1).subscribe();
    const request = http.expectOne((req) => req.url.endsWith('/1/predictions'));
    sub.unsubscribe();
    expect(request.cancelled).toBe(true);
  });
});

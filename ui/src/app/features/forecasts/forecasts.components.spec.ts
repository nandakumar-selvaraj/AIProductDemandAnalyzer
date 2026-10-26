import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Type } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { apiErrorInterceptor } from '../../core/api-error.interceptor';
import {
  AccuracyMetrics,
  ForecastCreated,
  ForecastRunItem,
  PredictionPage,
  RecommendationItem,
} from '../../core/models/forecast.models';
import { BacktestingComponent } from './backtesting.component';
import { CreateForecastComponent } from './create-forecast.component';
import { EvaluationComponent } from './evaluation.component';
import { ForecastsPage } from './forecasts.page';
import { PredictionsComponent } from './predictions.component';
import { RecommendationsComponent } from './recommendations.component';
import { RunHistoryComponent } from './run-history.component';
import { RunOverviewComponent } from './run-overview.component';

const run: ForecastRunItem = {
  id: 7,
  status: 'completed',
  model_name: 'trailing_30_day_average',
  model_version: '1',
  training_cutoff: '2017-12-31',
  horizon_days: 30,
  created_at: '2018-01-01T00:00:00Z',
  started_at: '2018-01-01T00:00:00Z',
  completed_at: '2018-01-01T00:01:00Z',
  metrics_json: { series_processed: 500, series_excluded: 0, predictions_created: 15000 },
};
const created: ForecastCreated = {
  run_id: 8,
  status: 'completed',
  forecast_cutoff: run.training_cutoff,
  horizon_days: 30,
  series_processed: 500,
  series_excluded: 0,
  predictions_created: 15000,
  created_at: run.created_at,
  started_at: run.started_at,
  completed_at: run.completed_at,
};
const metrics: AccuracyMetrics = {
  evaluated_predictions: 1,
  unmatched_predictions: 1,
  coverage_percent: '50.000',
  total_actual_units: 10,
  total_predicted_units: '12.123456789',
  mae: '2.123456789',
  wape_percent: '21.23456789',
  evaluation_status: 'partial',
};
const evaluation = {
  ...metrics,
  forecast_run_id: 7,
  forecast_cutoff: run.training_cutoff,
  horizon_days: 30,
  total_predictions: 2,
};
function history(page = 1, items = [run]) {
  return { page, page_size: 10, total_records: 21, total_pages: 3, items };
}
function predictions(id = 7, page = 1): PredictionPage {
  return {
    run_id: id,
    page,
    page_size: 50,
    total_records: 15000,
    total_pages: 300,
    items: [
      {
        id: page,
        forecast_run_id: id,
        store_id: 2,
        product_id: 3,
        forecast_date: '2018-01-01',
        predicted_units: '123456789.123456789',
      },
    ],
  };
}
function recommendations(id = 7, page = 1, items?: RecommendationItem[]) {
  return {
    forecast_run_id: id,
    page,
    page_size: 50,
    total_records: 500,
    total_pages: 10,
    increase_threshold_percent: '10',
    reduce_threshold_percent: '-10',
    items: items ?? [
      {
        store_id: 2,
        product_id: 3,
        recommendation: 'increase',
        reason: 'Forecast demand increased.',
        historical_daily_average: '10.000',
        forecast_daily_average: '12.123456789',
        change_percent: '21.23456789',
        forecast_horizon_days: 30,
        historical_coverage_days: 30,
        historical_window_start: '2017-12-02',
        historical_window_end: '2017-12-31',
      },
    ],
  };
}

describe('Forecast workspace components', () => {
  let http: HttpTestingController;
  let destroy: (() => void) | undefined;
  const base = environment.apiBaseUrl;
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([apiErrorInterceptor])),
        provideHttpClientTesting(),
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
    for (const [key, value] of Object.entries(inputs)) fixture.componentRef.setInput(key, value);
    fixture.detectChanges();
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    const button = (label: string) => {
      const node = Array.from(root.querySelectorAll<HTMLButtonElement>('button')).find(
        (node) => node.textContent?.trim() === label,
      );
      expect(node, label).toBeDefined();
      return node!;
    };
    const click = (label: string) => {
      button(label).click();
      fixture.detectChanges();
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
    const setInput = async (name: string, value: unknown) => {
      fixture.componentRef.setInput(name, value);
      fixture.detectChanges();
      await fixture.whenStable();
    };
    return { fixture, root, button, click, input, submit, setInput };
  }
  function get(path: string, page?: number) {
    return http.expectOne(
      (req) =>
        req.url === `${base}${path}` &&
        (page === undefined || req.params.get('page') === String(page)),
    );
  }
  function fail(path: string, status = 503, detail = 'Service unavailable') {
    get(path).flush({ detail }, { status, statusText: 'Request failed' });
  }

  describe('Create Forecast', () => {
    it('defaults to 30 days, blocks duplicate submissions and emits actual synchronous results', async () => {
      const ui = await setup(CreateForecastComponent);
      const emitted = vi.fn();
      ui.fixture.componentInstance.created.subscribe(emitted);
      expect(ui.root.querySelector<HTMLInputElement>('#forecast-horizon')!.value).toBe('30');
      ui.submit();
      ui.submit();
      const request = get('/forecasts');
      expect(request.request.body).toEqual({ horizon_days: 30, start_date: null });
      expect(ui.button('Create Forecast').disabled).toBe(true);
      expect(ui.root.textContent).toContain('computes and saves the run before responding');
      http.expectNone(`${base}/forecasts`);
      request.flush(created);
      ui.fixture.detectChanges();
      expect(emitted).toHaveBeenCalledExactlyOnceWith(created);
      expect(ui.root.textContent).toContain('#8');
      expect(ui.root.textContent).toContain('15,000');
      expect(ui.root.textContent).toContain('Not provided in this response');
      expect(ui.button('Create Forecast').disabled).toBe(false);
    });
    it('validates horizon before requesting and passes the optional training cutoff', async () => {
      const ui = await setup(CreateForecastComponent);
      await ui.input('forecast-horizon', '31');
      ui.submit();
      expect(ui.root.querySelector('[role="alert"]')?.textContent).toContain(
        'whole number from 1 to 30',
      );
      http.expectNone(`${base}/forecasts`);
      await ui.input('forecast-horizon', '7');
      await ui.input('forecast-cutoff', '2017-11-30');
      ui.submit();
      const request = get('/forecasts');
      expect(request.request.body).toEqual({ horizon_days: 7, start_date: '2017-11-30' });
      request.flush({ ...created, horizon_days: 7 });
    });
    it('shows backend validation errors, clears old success and permits a corrected retry', async () => {
      const ui = await setup(CreateForecastComponent);
      ui.submit();
      get('/forecasts').flush(created);
      ui.fixture.detectChanges();
      ui.submit();
      expect(ui.root.querySelector('app-run-overview')).toBeNull();
      fail('/forecasts', 422, 'Cutoff cannot be after latest sales');
      ui.fixture.detectChanges();
      expect(ui.root.querySelector('[role="alert"]')?.textContent).toContain(
        'Cutoff cannot be after latest sales',
      );
      await ui.input('forecast-cutoff', '2017-11-30');
      ui.submit();
      get('/forecasts').flush(created);
    });
    it('warns about uncertain completion after a network failure and cancels on teardown', async () => {
      const ui = await setup(CreateForecastComponent);
      ui.submit();
      get('/forecasts').error(new ProgressEvent('error'));
      ui.fixture.detectChanges();
      expect(ui.root.textContent?.toLowerCase()).toContain('history');
      ui.submit();
      const pending = get('/forecasts');
      ui.fixture.destroy();
      expect(pending.cancelled).toBe(true);
    });
  });

  describe('Run history', () => {
    it('renders loading, selected state and bounded server pagination', async () => {
      const ui = await setup(RunHistoryComponent, { selectedId: 7 });
      expect(ui.root.textContent).toContain('Loading forecast runs');
      get('/forecasts/runs', 1).flush(history());
      ui.fixture.detectChanges();
      expect(ui.root.querySelector('caption')?.textContent).toContain('local timezone');
      expect(ui.root.querySelector('[aria-pressed="true"]')?.getAttribute('aria-label')).toBe(
        'View details for run #7',
      );
      const selected = vi.fn();
      ui.fixture.componentInstance.runSelected.subscribe(selected);
      ui.click('View Details');
      expect(selected).toHaveBeenCalledExactlyOnceWith(run);
      expect(ui.button('Previous runs').disabled).toBe(true);
      ui.click('Next runs');
      const pending = get('/forecasts/runs', 2);
      expect(pending.request.params.get('page_size')).toBe('10');
      expect(ui.root.querySelector('table')).toBeNull();
      pending.flush(history(2, [{ ...run, id: 6 }]));
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('#6');
      expect(ui.root.querySelector('[aria-pressed="true"]')).toBeNull();
    });
    it('resets status filters to page one and cancels obsolete pages and filters', async () => {
      const ui = await setup(RunHistoryComponent);
      get('/forecasts/runs', 1).flush(history());
      ui.fixture.detectChanges();
      ui.click('Next runs');
      const old = get('/forecasts/runs', 2);
      const select = ui.root.querySelector<HTMLSelectElement>('#run-status')!;
      select.value = 'completed';
      select.dispatchEvent(new Event('change'));
      ui.fixture.detectChanges();
      expect(old.cancelled).toBe(true);
      const completed = get('/forecasts/runs', 1);
      expect(completed.request.params.get('status')).toBe('completed');
      select.value = 'failed';
      select.dispatchEvent(new Event('change'));
      ui.fixture.detectChanges();
      expect(completed.cancelled).toBe(true);
      const failed = get('/forecasts/runs', 1);
      expect(failed.request.params.get('status')).toBe('failed');
      failed.flush(history(1, []));
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('No forecast runs match');
    });
    it('retries failures with the same query and cancels on destruction', async () => {
      const ui = await setup(RunHistoryComponent);
      fail('/forecasts/runs');
      ui.fixture.detectChanges();
      expect(ui.root.querySelector('table')).toBeNull();
      expect(ui.root.querySelector('[role="alert"]')?.textContent).toContain('Service unavailable');
      ui.click('Retry runs');
      get('/forecasts/runs', 1).flush(history());
      ui.fixture.detectChanges();
      ui.click('Refresh runs');
      const pending = get('/forecasts/runs', 1);
      ui.fixture.destroy();
      expect(pending.cancelled).toBe(true);
    });
  });

  describe('Predictions', () => {
    it('uses rounded decimals, accessible page-scoped charts and server pages', async () => {
      const ui = await setup(PredictionsComponent, { runId: 7 });
      expect(ui.root.textContent).toContain('Loading predictions');
      get('/forecasts/7/predictions', 1).flush(predictions());
      ui.fixture.detectChanges();
      expect(ui.root.querySelector('table')?.textContent).toContain('123,456,789.12');
      expect(ui.root.querySelector('svg[role="img"]')?.getAttribute('aria-labelledby')).toContain(
        'prediction-chart-description',
      );
      expect(ui.root.textContent).toContain('not a whole-run total');
      expect(ui.root.querySelectorAll('svg rect')).toHaveLength(1);
      expect(ui.button('Previous predictions').disabled).toBe(true);
      ui.click('Next predictions');
      const request = get('/forecasts/7/predictions', 2);
      expect(request.request.params.get('page_size')).toBe('50');
      expect(ui.root.querySelector('table')).toBeNull();
      request.flush(predictions(7, 2));
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('Page 2 of 300');
    });
    it('cancels an obsolete page when another run is selected and resets to page one', async () => {
      const ui = await setup(PredictionsComponent, { runId: 7 });
      get('/forecasts/7/predictions', 1).flush(predictions());
      ui.fixture.detectChanges();
      ui.click('Next predictions');
      const old = get('/forecasts/7/predictions', 2);
      await ui.setInput('runId', 8);
      expect(old.cancelled).toBe(true);
      expect(ui.root.querySelector('table')).toBeNull();
      const current = get('/forecasts/8/predictions', 1);
      current.flush(predictions(8));
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('Run #8');
      expect(ui.root.textContent).toContain('Page 1 of 300');
    });
    it('clears failed results, retries the current page and handles empty responses', async () => {
      const ui = await setup(PredictionsComponent, { runId: 7 });
      get('/forecasts/7/predictions', 1).flush(predictions());
      ui.fixture.detectChanges();
      ui.click('Next predictions');
      fail('/forecasts/7/predictions', 404, 'Run not found');
      ui.fixture.detectChanges();
      expect(ui.root.querySelector('table')).toBeNull();
      expect(ui.root.querySelector('[role="alert"]')?.textContent).toContain('Run not found');
      ui.click('Retry predictions');
      get('/forecasts/7/predictions', 2).flush({ ...predictions(7, 2), items: [] });
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('No predictions are available');
      expect(ui.root.querySelector('svg')).toBeNull();
    });
    it('cancels pending predictions on component destruction', async () => {
      const ui = await setup(PredictionsComponent, { runId: 7 });
      const request = get('/forecasts/7/predictions');
      ui.fixture.destroy();
      expect(request.cancelled).toBe(true);
    });
  });

  describe('Evaluation', () => {
    it('runs manually, prevents duplicate evaluation and describes partial coverage honestly', async () => {
      const ui = await setup(EvaluationComponent, { run });
      http.expectNone(`${base}/forecasts/evaluate`);
      ui.click('Evaluate run');
      ui.click('Evaluate run');
      const request = get('/forecasts/evaluate');
      expect(request.request.body).toEqual({ forecast_run_id: 7 });
      expect(ui.button('Evaluate run').disabled).toBe(true);
      http.expectNone(`${base}/forecasts/evaluate`);
      request.flush(evaluation);
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('2.12');
      expect(ui.root.textContent).toContain('21.23%');
      expect(ui.root.textContent).toContain('matching observations only');
      expect(ui.root.textContent).toContain('50.00%');
    });
    it('does not evaluate incomplete runs', async () => {
      const ui = await setup(EvaluationComponent, { run: { ...run, status: 'running' } });
      expect(ui.button('Evaluate run').disabled).toBe(true);
      ui.click('Evaluate run');
      http.expectNone(`${base}/forecasts/evaluate`);
      expect(ui.root.textContent).toContain('Complete this run');
    });
    it('represents null metrics as unavailable and keeps genuine zero metrics', async () => {
      const ui = await setup(EvaluationComponent, { run });
      ui.click('Evaluate run');
      get('/forecasts/evaluate').flush({
        ...evaluation,
        mae: null,
        wape_percent: null,
        evaluated_predictions: 0,
        coverage_percent: '0',
        evaluation_status: 'unavailable',
      });
      ui.fixture.detectChanges();
      expect(ui.root.querySelectorAll('dd').length).toBeGreaterThan(0);
      expect(
        Array.from(ui.root.querySelectorAll('dd')).filter(
          (node) => node.textContent?.trim() === 'Unavailable',
        ),
      ).toHaveLength(2);
      ui.click('Evaluate run');
      get('/forecasts/evaluate').flush({ ...evaluation, mae: '0.000', wape_percent: '0.000' });
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('0.00%');
    });
    it.each([404, 409, 422, 503])(
      'shows an actionable %s error and retries the same run',
      async (status) => {
        const ui = await setup(EvaluationComponent, { run });
        ui.click('Evaluate run');
        fail('/forecasts/evaluate', status, 'Actuals unavailable');
        ui.fixture.detectChanges();
        expect(ui.root.querySelector('[role="alert"]')?.textContent).toContain(
          'Actuals unavailable',
        );
        expect(ui.root.querySelector('app-accuracy-metrics')).toBeNull();
        ui.click('Retry evaluation');
        get('/forecasts/evaluate').flush(evaluation);
      },
    );
    it('cancels obsolete evaluations and clears metrics when the selected run changes', async () => {
      const ui = await setup(EvaluationComponent, { run });
      ui.click('Evaluate run');
      const old = get('/forecasts/evaluate');
      await ui.setInput('run', { ...run, id: 8 });
      expect(old.cancelled).toBe(true);
      expect(ui.root.querySelector('app-accuracy-metrics')).toBeNull();
      ui.click('Evaluate run');
      const current = get('/forecasts/evaluate');
      expect(current.request.body).toEqual({ forecast_run_id: 8 });
      ui.fixture.destroy();
      expect(current.cancelled).toBe(true);
    });
  });

  describe('Recommendations', () => {
    it('displays textual trend labels, insufficient history, exact decimals and true zero', async () => {
      const ui = await setup(RecommendationsComponent, { run });
      expect(ui.root.textContent).toContain('Loading recommendations');
      const item = recommendations().items[0] as RecommendationItem;
      const items = (['increase', 'maintain', 'reduce', 'insufficient_data'] as const).map(
        (recommendation, index) => ({
          ...item,
          product_id: index + 1,
          recommendation,
          historical_daily_average: index === 3 ? null : '0.000',
          change_percent: index === 3 ? null : '0.000',
          historical_coverage_days: index === 3 ? 12 : 30,
          reason: index === 3 ? 'Incomplete historical coverage.' : item.reason,
        }),
      );
      get('/recommendations').flush(recommendations(7, 1, items));
      ui.fixture.detectChanges();
      expect(
        Array.from(ui.root.querySelectorAll('.status-chip')).map((node) => node.textContent),
      ).toEqual(['Increase', 'Maintain', 'Reduce', 'Insufficient data']);
      expect(ui.root.textContent).toContain('Unavailable');
      expect(ui.root.textContent).toContain('0.00%');
      expect(ui.root.textContent).toContain('12/30 historical days');
      expect(ui.root.textContent).toContain('12.12');
      expect(ui.root.textContent).toContain('Incomplete historical coverage.');
      expect(ui.root.textContent).toContain('not purchase orders');
      expect(ui.root.querySelector('caption')).not.toBeNull();
    });
    it('pages on the server and resets/cancels when the run changes', async () => {
      const ui = await setup(RecommendationsComponent, { run });
      get('/recommendations', 1).flush(recommendations());
      ui.fixture.detectChanges();
      ui.click('Next recommendations');
      const old = get('/recommendations', 2);
      expect(old.request.params.get('forecast_run_id')).toBe('7');
      await ui.setInput('run', { ...run, id: 8 });
      expect(old.cancelled).toBe(true);
      const current = get('/recommendations', 1);
      expect(current.request.params.get('forecast_run_id')).toBe('8');
      expect(current.request.params.get('page_size')).toBe('50');
      current.flush(recommendations(8));
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('Run #8');
    });
    it('handles errors and empty data with a retry and no stale table', async () => {
      const ui = await setup(RecommendationsComponent, { run });
      get('/recommendations', 1).flush(recommendations());
      ui.fixture.detectChanges();
      ui.click('Next recommendations');
      fail('/recommendations', 503);
      ui.fixture.detectChanges();
      expect(ui.root.querySelector('table')).toBeNull();
      ui.click('Retry recommendations');
      get('/recommendations', 2).flush(recommendations(7, 2, []));
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('No recommendations are available');
    });
    it('does not request recommendations for incomplete runs and cancels on destruction', async () => {
      const ui = await setup(RecommendationsComponent, { run: { ...run, status: 'failed' } });
      http.expectNone((req) => req.url === `${base}/recommendations`);
      expect(ui.root.textContent).toContain('completed runs only');
      await ui.setInput('run', run);
      const request = get('/recommendations');
      ui.fixture.destroy();
      expect(request.cancelled).toBe(true);
    });
  });

  describe('Backtesting', () => {
    it('requires cutoff, validates horizon, and compares actual returned baselines without creating a run', async () => {
      const ui = await setup(BacktestingComponent);
      ui.submit();
      expect(ui.root.querySelector('[role="alert"]')?.textContent).toContain(
        'Enter a historical cutoff',
      );
      http.expectNone(`${base}/forecasts/backtest`);
      await ui.input('backtest-cutoff', '2017-11-30');
      await ui.input('backtest-horizon', '0');
      ui.submit();
      http.expectNone(`${base}/forecasts/backtest`);
      await ui.input('backtest-horizon', '7');
      ui.submit();
      ui.submit();
      const request = get('/forecasts/backtest');
      expect(request.request.body).toEqual({ cutoff_date: '2017-11-30', horizon_days: 7 });
      expect(ui.button('Run Backtest').disabled).toBe(true);
      http.expectNone(`${base}/forecasts/backtest`);
      http.expectNone(`${base}/forecasts`);
      request.flush({
        cutoff_date: '2017-11-30',
        horizon_days: 7,
        holdout_start: '2017-12-01',
        holdout_end: '2017-12-07',
        missing_dates: [],
        models: {
          trailing_average: { ...metrics, evaluated_series: 1, total_series: 2 },
          seasonal_naive: {
            ...metrics,
            mae: null,
            wape_percent: null,
            evaluated_series: 0,
            total_series: 2,
            evaluation_status: 'unavailable',
          },
        },
        assumptions: ['Missing dates are never zero-filled.'],
      });
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('trailing_average');
      expect(ui.root.textContent).toContain('seasonal_naive');
      expect(ui.root.textContent).toContain('Unavailable');
      expect(ui.root.textContent).toContain('Missing dates are never zero-filled.');
      expect(ui.root.textContent).toContain('does not create a persisted forecast run');
      expect(ui.root.querySelectorAll('app-accuracy-metrics')).toHaveLength(2);
    });
    it.each([422, 503])('reports a %s backtest failure and permits retry', async (status) => {
      const ui = await setup(BacktestingComponent);
      await ui.input('backtest-cutoff', '2017-11-30');
      ui.submit();
      fail('/forecasts/backtest', status, 'Holdout dates unavailable');
      ui.fixture.detectChanges();
      expect(ui.root.querySelector('[role="alert"]')?.textContent).toContain(
        'Holdout dates unavailable',
      );
      ui.submit();
      const request = get('/forecasts/backtest');
      ui.fixture.destroy();
      expect(request.cancelled).toBe(true);
    });
  });

  describe('Overview and workspace integration', () => {
    it('distinguishes missing recorded metadata from zero counts', async () => {
      const ui = await setup(RunOverviewComponent, {
        run: {
          ...run,
          model_version: null,
          started_at: null,
          metrics_json: { series_excluded: 0 },
        },
      });
      expect(ui.root.textContent).toContain('Not recorded');
      expect(ui.root.querySelectorAll('dd').length).toBeGreaterThan(6);
      expect(
        Array.from(ui.root.querySelectorAll('dd')).some((node) => node.textContent?.trim() === '0'),
      ).toBe(true);
    });
    it('handles no latest run and keeps backtesting independently available', async () => {
      const ui = await setup(ForecastsPage);
      get('/forecasts/latest').flush(null);
      get('/forecasts/runs', 1).flush(history(1, []));
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('No completed forecast run');
      expect(ui.root.querySelector('app-backtesting')).not.toBeNull();
      http.expectNone((req) => req.url.endsWith('/predictions'));
    });
    it('retries latest-run errors and automatically selects a completed latest run', async () => {
      const ui = await setup(ForecastsPage);
      fail('/forecasts/latest');
      get('/forecasts/runs', 1).flush(history());
      ui.fixture.detectChanges();
      expect(ui.root.textContent).toContain('Service unavailable');
      ui.click('Retry latest run');
      get('/forecasts/latest').flush(run);
      ui.fixture.detectChanges();
      await ui.fixture.whenStable();
      get('/forecasts/7/predictions').flush(predictions());
      get('/recommendations').flush(recommendations());
      ui.fixture.detectChanges();
      expect(ui.root.querySelector('#selected-run-heading')?.textContent).toContain('#7');
    });
    it('preserves selection across history pages and cancels detail requests when selecting another run', async () => {
      const ui = await setup(ForecastsPage);
      get('/forecasts/latest').flush(run);
      get('/forecasts/runs', 1).flush(history());
      ui.fixture.detectChanges();
      await ui.fixture.whenStable();
      const oldPredictions = get('/forecasts/7/predictions');
      const oldRecommendations = get('/recommendations');
      ui.click('Next runs');
      get('/forecasts/runs', 2).flush(history(2, [{ ...run, id: 6 }]));
      ui.fixture.detectChanges();
      expect(ui.root.querySelector('#selected-run-heading')?.textContent).toContain('#7');
      ui.click('View Details');
      await ui.fixture.whenStable();
      expect(oldPredictions.cancelled).toBe(true);
      expect(oldRecommendations.cancelled).toBe(true);
      get('/forecasts/6/predictions').flush(predictions(6));
      get('/recommendations').flush(recommendations(6));
      ui.fixture.detectChanges();
      expect(ui.root.querySelector('#selected-run-heading')?.textContent).toContain('#6');
      ui.click('Refresh latest');
      get('/forecasts/latest').flush(run);
      ui.fixture.detectChanges();
      expect(ui.root.querySelector('#selected-run-heading')?.textContent).toContain('#6');
    });
    it('refreshes history at All/page one after creation and selects the actual returned ID', async () => {
      const ui = await setup(ForecastsPage);
      get('/forecasts/latest').flush(null);
      get('/forecasts/runs', 1).flush(history());
      ui.fixture.detectChanges();
      const select = ui.root.querySelector<HTMLSelectElement>('#run-status')!;
      select.value = 'failed';
      select.dispatchEvent(new Event('change'));
      ui.fixture.detectChanges();
      get('/forecasts/runs', 1).flush(history(1, []));
      ui.fixture.detectChanges();
      ui.submit();
      get('/forecasts').flush(created);
      ui.fixture.detectChanges();
      await ui.fixture.whenStable();
      const refreshed = get('/forecasts/runs', 1);
      expect(refreshed.request.params.has('status')).toBe(false);
      expect(select.value).toBe('');
      refreshed.flush(history(1, [{ ...run, id: 8 }]));
      get('/forecasts/latest').flush({ ...run, id: 8 });
      ui.fixture.detectChanges();
      await ui.fixture.whenStable();
      get('/forecasts/8/predictions').flush(predictions(8));
      get('/recommendations').flush(recommendations(8));
      ui.fixture.detectChanges();
      expect(ui.root.querySelector('#selected-run-heading')?.textContent).toContain('#8');
      expect(ui.root.querySelector('#selected-run-heading')?.getAttribute('tabindex')).toBe('-1');
      ui.click('Back to run history');
      expect(document.activeElement?.id).toBe('run-history-heading');
    });
  });
});

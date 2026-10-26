import { of, throwError } from 'rxjs';
import { RunContext } from '../../core/models/forecast.models';
import {
  createdContext,
  exactDecimal,
  predictionBars,
  recordedCount,
  requestState,
  validateForecast,
} from './forecast.helpers';

describe('Forecast validation and display helpers', () => {
  it.each([null, 0, -1, 1.5, 31, NaN, Infinity])('rejects invalid horizon %s', (horizon) => {
    expect(validateForecast(horizon, '')).toContain(
      'Forecast horizon must be a whole number from 1 to 30 days.',
    );
  });
  it.each([1, 30])('accepts boundary horizon %s and an optional blank cutoff', (horizon) => {
    expect(validateForecast(horizon, '')).toEqual([]);
  });
  it('requires a historical cutoff only for backtests', () => {
    expect(validateForecast(30, '', true)).toEqual(['Enter a historical cutoff date.']);
    expect(validateForecast(30, '2024-02-29', true)).toEqual([]);
  });
  it.each(['2023-02-29', '2024-04-31', 'bad', '2024-13-01', '0000-01-01'])(
    'rejects a non-calendar cutoff %s',
    (cutoff) => {
      expect(validateForecast(30, cutoff)).toContain(
        'Enter a valid cutoff date in YYYY-MM-DD format.',
      );
    },
  );
  it('distinguishes unavailable from recorded zero and retains decimal strings', () => {
    expect(exactDecimal(null)).toBe('Unavailable');
    expect(exactDecimal('0.000')).toBe('0.000');
    expect(exactDecimal('123456789.123456789')).toBe('123456789.123456789');
  });
  it('does not invent model metadata for a creation response or treat missing counts as zero', () => {
    const context = createdContext({
      run_id: 4,
      status: 'completed',
      forecast_cutoff: '2017-12-31',
      horizon_days: 30,
      series_processed: 2,
      series_excluded: 0,
      predictions_created: 60,
      created_at: '2018-01-01T00:00:00Z',
      started_at: null,
      completed_at: null,
    });
    expect(context.id).toBe(4);
    expect(context.model_name).toBeNull();
    expect(context.training_cutoff).toBe('2017-12-31');
    expect(recordedCount(context, 'series_excluded')).toBe(0);
    expect(recordedCount(context, 'missing')).toBeNull();
    expect(
      recordedCount({ ...context, metrics_json: { count: '2' } } as RunContext, 'count'),
    ).toBeNull();
  });
  it('charts individual page rows without aggregation or fabricated invalid values', () => {
    const items = [0, 10, 20, NaN].map((value, index) => ({
      id: index,
      forecast_run_id: 1,
      store_id: 1,
      product_id: 2,
      forecast_date: '2018-01-01',
      predicted_units: String(value),
    }));
    const bars = predictionBars(items);
    expect(bars.map((bar) => bar.row)).toEqual([1, 2, 3]);
    expect(bars[0].height).toBe(0);
    expect(bars[2].height).toBe(180);
    expect(items[2].predicted_units).toBe('20');
  });
  it('clears old data during loading and keeps failed streams retryable', () => {
    const success: unknown[] = [];
    requestState(of(7)).subscribe((state) => success.push(state));
    expect(success).toEqual([{ status: 'loading' }, { status: 'success', data: 7 }]);
    const failure: unknown[] = [];
    requestState(throwError(() => new Error('Unavailable'))).subscribe((state) =>
      failure.push(state),
    );
    expect(failure).toEqual([{ status: 'loading' }, { status: 'error', message: 'Unavailable' }]);
  });
});

import { catchError, map, Observable, of, startWith } from 'rxjs';
import {
  ApiDecimal,
  ForecastCreated,
  ForecastPrediction,
  RunContext,
} from '../../core/models/forecast.models';

export type LoadState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'success'; data: T };

export function requestState<T>(source: Observable<T>): Observable<LoadState<T>> {
  return source.pipe(
    map((data): LoadState<T> => ({ status: 'success', data })),
    catchError((error: unknown) =>
      of<LoadState<T>>({
        status: 'error',
        message:
          error instanceof Error && error.message
            ? error.message
            : 'The request could not be completed.',
      }),
    ),
    startWith({ status: 'loading' } as const),
  );
}
export function validateForecast(
  horizon: number | null,
  cutoff: string,
  cutoffRequired = false,
): string[] {
  const errors: string[] = [];
  if (horizon === null || !Number.isInteger(horizon) || horizon < 1 || horizon > 30)
    errors.push('Forecast horizon must be a whole number from 1 to 30 days.');
  if (!cutoff && cutoffRequired) errors.push('Enter a historical cutoff date.');
  if (cutoff) {
    const date = new Date(`${cutoff}T00:00:00Z`);
    if (
      !/^\d{4}-\d{2}-\d{2}$/.test(cutoff) ||
      cutoff.startsWith('0000') ||
      !Number.isFinite(date.getTime()) ||
      date.toISOString().slice(0, 10) !== cutoff
    )
      errors.push('Enter a valid cutoff date in YYYY-MM-DD format.');
  }
  return errors;
}
export function exactDecimal(value: ApiDecimal | null): string {
  return value === null ? 'Unavailable' : String(value);
}
export function recordedCount(run: RunContext, key: string): number | null {
  const value = run.metrics_json?.[key];
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 ? value : null;
}
export function createdContext(run: ForecastCreated): RunContext {
  return {
    id: run.run_id,
    status: run.status,
    training_cutoff: run.forecast_cutoff,
    horizon_days: run.horizon_days,
    model_name: null,
    model_version: null,
    created_at: run.created_at,
    started_at: run.started_at,
    completed_at: run.completed_at,
    metrics_json: {
      series_processed: run.series_processed,
      series_excluded: run.series_excluded,
      predictions_created: run.predictions_created,
    },
  };
}
export function predictionBars(items: readonly ForecastPrediction[]) {
  const valid = items
    .map((item, index) => ({ item, index, value: Number(item.predicted_units) }))
    .filter(({ value }) => Number.isFinite(value) && value >= 0);
  const maximum = valid.reduce((max, row) => Math.max(max, row.value), 1);
  return valid.map(({ item, index, value }) => ({
    id: item.id,
    row: index + 1,
    x: items.length > 1 ? 70 + (index / (items.length - 1)) * 860 : 500,
    y: 230 - (value / maximum) * 180,
    height: (value / maximum) * 180,
  }));
}

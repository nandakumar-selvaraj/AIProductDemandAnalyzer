import { SalesPoint } from '../../core/models/analytics.models';
import { ChartBar } from './demand-analysis.models';

const DAY_MS = 86_400_000;

function dateValue(value: string): number | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000')) return null;
  const time = Date.parse(`${value}T00:00:00Z`);
  return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === value ? time : null;
}

export function validateFilters(productId: number | null, start: string, end: string): string[] {
  const errors: string[] = [];
  if (productId === null) errors.push('Select a product before applying filters.');
  const startTime = start ? dateValue(start) : null;
  const endTime = end ? dateValue(end) : null;
  if (start && startTime === null) errors.push('Enter a valid start date in YYYY-MM-DD format.');
  if (end && endTime === null) errors.push('Enter a valid end date in YYYY-MM-DD format.');
  if (startTime !== null && endTime !== null) {
    if (startTime > endTime) errors.push('Start date must not be after end date.');
    else if (endTime - startTime > 364 * DAY_MS)
      errors.push('Select at most 365 calendar days, including both endpoints.');
  }
  return errors;
}

export function sortedObservations(
  points: readonly SalesPoint[],
  descending = false,
): SalesPoint[] {
  return [...points].sort((a, b) => (descending ? -1 : 1) * a.period.localeCompare(b.period));
}

export function observedDayAverage(total: number, observedDates: number): number | null {
  return observedDates > 0 ? total / observedDates : null;
}

/** Plot only returned observations. Time-based positions preserve gaps without inserting zeros. */
export function toChartBars(
  points: readonly SalesPoint[],
  granularity: 'daily' | 'monthly',
): ChartBar[] {
  const sorted = sortedObservations(points);
  if (!sorted.length) return [];
  const index = (period: string) =>
    granularity === 'daily'
      ? (dateValue(period) ?? 0) / DAY_MS
      : Number(period.slice(0, 4)) * 12 + Number(period.slice(5, 7)) - 1;
  const first = index(sorted[0].period);
  const span = index(sorted[sorted.length - 1].period) - first;
  const max = sorted.reduce((maximum, point) => Math.max(maximum, point.units_sold), 1);
  const width = Math.max(1, Math.min(24, (860 / (span + 1)) * 0.7));
  return sorted.map((point) => {
    const center = span ? 80 + ((index(point.period) - first) / span) * 860 : 510;
    const height = (point.units_sold / max) * 200;
    return {
      period: point.period,
      units: point.units_sold,
      x: center - width / 2,
      y: 240 - height,
      width,
      height,
    };
  });
}

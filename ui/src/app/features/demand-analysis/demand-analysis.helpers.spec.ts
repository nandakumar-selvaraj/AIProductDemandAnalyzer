import {
  observedDayAverage,
  sortedObservations,
  toChartBars,
  validateFilters,
} from './demand-analysis.helpers';

describe('Demand Analysis calculations', () => {
  it('requires a selected product', () => {
    expect(validateFilters(null, '', '')).toEqual(['Select a product before applying filters.']);
  });
  it.each([
    ['', ''],
    ['2024-02-01', ''],
    ['', '2024-02-01'],
    ['2024-02-01', '2024-02-01'],
    ['2023-01-01', '2023-12-31'],
  ])('accepts supported date boundaries %s / %s', (start, end) => {
    expect(validateFilters(1, start, end)).toEqual([]);
  });
  it('rejects reverse ranges and more than 365 inclusive days, including leap years', () => {
    expect(validateFilters(1, '2024-02-02', '2024-02-01').join()).toContain('must not be after');
    expect(validateFilters(1, '2024-01-01', '2024-12-31').join()).toContain('at most 365');
    expect(validateFilters(1, '2024-01-01', '2024-12-30')).toEqual([]);
  });
  it.each(['2024-02-30', '2024-13-01', '0000-01-01', 'not-a-date'])(
    'rejects invalid ISO dates: %s',
    (date) => {
      expect(validateFilters(1, date, '').join()).toContain('valid start date');
      expect(validateFilters(1, '', date).join()).toContain('valid end date');
    },
  );
  it('calculates an observed-day average, including recorded zero sales and no observations', () => {
    expect(observedDayAverage(30, 3)).toBe(10);
    expect(observedDayAverage(0, 3)).toBe(0);
    expect(observedDayAverage(0, 0)).toBeNull();
  });
  it('sorts dates without mutating the API response', () => {
    const points = [
      { period: '2024-01-03', units_sold: 10 },
      { period: '2024-01-01', units_sold: 5 },
    ];
    expect(sortedObservations(points).map((point) => point.period)).toEqual([
      '2024-01-01',
      '2024-01-03',
    ]);
    expect(sortedObservations(points, true)).toEqual(points);
    expect(points[0].period).toBe('2024-01-03');
  });
  it('preserves missing daily gaps without generating zero observations', () => {
    const bars = toChartBars(
      [
        { period: '2024-01-07', units_sold: 10 },
        { period: '2024-01-01', units_sold: 5 },
        { period: '2024-01-03', units_sold: 0 },
      ],
      'daily',
    );
    expect(bars).toHaveLength(3);
    expect(bars.map((bar) => bar.units)).toEqual([5, 0, 10]);
    expect(bars[1].height).toBe(0);
    expect(bars[2].x - bars[1].x).toBeCloseTo(2 * (bars[1].x - bars[0].x));
    expect(bars[2].height).toBe(200);
  });
  it('uses returned monthly totals and preserves missing months', () => {
    const bars = toChartBars(
      [
        { period: '2024-03-01', units_sold: 300 },
        { period: '2024-01-01', units_sold: 100 },
      ],
      'monthly',
    );
    expect(bars.map((bar) => [bar.period, bar.units])).toEqual([
      ['2024-01-01', 100],
      ['2024-03-01', 300],
    ]);
    expect(bars[0].height).toBeCloseTo(200 / 3);
  });
  it('handles empty, single-point, and all-zero chart series without invalid coordinates', () => {
    expect(toChartBars([], 'daily')).toEqual([]);
    const bars = toChartBars([{ period: '2024-01-01', units_sold: 0 }], 'daily');
    expect(bars[0].height).toBe(0);
    expect(bars[0].x + bars[0].width / 2).toBe(510);
    expect(Number.isFinite(bars[0].y)).toBe(true);
  });
});

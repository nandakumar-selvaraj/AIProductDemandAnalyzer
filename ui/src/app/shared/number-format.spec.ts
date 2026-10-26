import { twoDecimals } from './number-format';
import { displayCell, predictionTable } from '../features/reports/report-formatters';
import { reportCsv } from '../features/reports/csv-export';

describe('Two-decimal display formatting', () => {
  it.each([
    ['12.123456789', '12.12'],
    ['12.129', '12.13'],
    ['9.999', '10.00'],
    ['1.005', '1.01'],
    ['-1.235', '-1.24'],
    ['0.000', '0.00'],
    [7, '7.00'],
    ['123456789.123456789', '123,456,789.12'],
  ])('formats %s as %s', (value, expected) => {
    expect(twoDecimals(value)).toBe(expected);
  });
  it('keeps missing values distinct from zero', () => {
    expect(twoDecimals(null)).toBe('N/A');
    expect(twoDecimals(null, 'Unavailable')).toBe('Unavailable');
    expect(twoDecimals('invalid')).toBe('N/A');
  });
  it('formats only decimal report columns, preserving IDs, counts, dates and text', () => {
    expect(displayCell('12.129', 'predicted_units')).toBe('12.13');
    expect(displayCell(null, 'mae')).toBe('N/A');
    expect(displayCell(7, 'product_id')).toBe('7');
    expect(displayCell(500, 'total_predictions')).toBe('500');
    expect(displayCell('2017-12-31', 'forecast_date')).toBe('2017-12-31');
    expect(displayCell('12.129', 'reason')).toBe('12.129');
  });
  it('retains original prediction precision in the CSV after display formatting', () => {
    const table = predictionTable([
      {
        id: 1,
        forecast_run_id: 7,
        product_id: 2,
        store_id: 3,
        forecast_date: '2018-01-01',
        predicted_units: '12.129123456789',
      },
    ]);
    expect(displayCell(table.rows[0][4], 'predicted_units')).toBe('12.13');
    expect(table.rows[0][4]).toBe('12.129123456789');
    expect(reportCsv(table, { run_id: 7 })).toContain('"12.129123456789"');
  });
});

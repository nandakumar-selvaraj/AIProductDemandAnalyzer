import { TestBed } from '@angular/core/testing';
import { CsvDownloadService, csvCell, MAX_EXPORT_BYTES, reportCsv } from './csv-export';

describe('CSV safety and browser downloads', () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });
  it('quotes commas, quotes, line breaks and Unicode with deterministic CRLF records', () => {
    const csv = reportCsv(
      { headers: ['name', 'value'], rows: [['Tea, "紅茶"\nதமிழ்', '1.2300000000000000001']] },
      { report_type: 'test', forecast_run_id: 7 },
    );
    expect(csv).toBe(
      '\ufeff"report_type","forecast_run_id","name","value"\r\n"test","7","Tea, ""紅茶""\nதமிழ்","1.2300000000000000001"\r\n',
    );
  });
  it.each([
    '=SUM(A1:A2)',
    '+cmd|x',
    '-1+2',
    '@SUM(A1)',
    '  =2+2',
    '\t=2+2',
    '\r=1',
    '\n+SUM(1)',
    '\u0000=1',
  ])('neutralizes formula text %j', (value) => {
    expect(csvCell(value).startsWith('"\'')).toBe(true);
  });
  it('preserves dates, strict decimal strings, recorded zero and unavailable metrics', () => {
    expect(csvCell('2017-12-31')).toBe('"2017-12-31"');
    expect(csvCell('-123.123456789123456789')).toBe('"-123.123456789123456789"');
    expect(csvCell('0.000')).toBe('"0.000"');
    expect(csvCell(null)).toBe('"N/A"');
  });
  it('also protects repeated context values and column headers', () => {
    const csv = reportCsv({ headers: ['=header'], rows: [['safe']] }, { product_name: '=EVIL()' });
    expect(csv).toContain('"\'=header"');
    expect(csv).toContain('"\'=EVIL()"');
  });
  it('creates a UTF-8 CSV download and releases its object URL after the click', () => {
    vi.useFakeTimers();
    const create = vi.fn(() => 'blob:report');
    const revoke = vi.fn();
    vi.stubGlobal('URL', { createObjectURL: create, revokeObjectURL: revoke });
    const clicks: HTMLAnchorElement[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clicks.push(this);
    });
    TestBed.inject(CsvDownloadService).download(
      'report-run-7-page-2.csv',
      { headers: ['units'], rows: [['1.230']] },
      { run_id: 7 },
    );
    expect(create).toHaveBeenCalledOnce();
    expect(create.mock.calls[0].length).toBe(1);
    expect(clicks[0].download).toBe('report-run-7-page-2.csv');
    expect(clicks[0].href).toBe('blob:report');
    expect(document.querySelector('a[download]')).toBeNull();
    expect(revoke).not.toHaveBeenCalled();
    vi.runAllTimers();
    expect(revoke).toHaveBeenCalledExactlyOnceWith('blob:report');
  });
  it('revokes URLs even if initiating the download throws', () => {
    vi.useFakeTimers();
    const revoke = vi.fn();
    vi.stubGlobal('URL', { createObjectURL: () => 'blob:failed', revokeObjectURL: revoke });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {
      throw new Error('blocked');
    });
    expect(() =>
      TestBed.inject(CsvDownloadService).download(
        'test.csv',
        { headers: ['value'], rows: [[1]] },
        {},
      ),
    ).toThrow('blocked');
    expect(document.querySelector('a[download]')).toBeNull();
    vi.runAllTimers();
    expect(revoke).toHaveBeenCalledWith('blob:failed');
  });
  it('rejects oversized CSV before allocating an object URL', () => {
    const create = vi.fn();
    vi.stubGlobal('URL', { createObjectURL: create });
    expect(() =>
      TestBed.inject(CsvDownloadService).download(
        'large.csv',
        { headers: ['text'], rows: [['x'.repeat(MAX_EXPORT_BYTES)]] },
        {},
      ),
    ).toThrow('16 MiB');
    expect(create).not.toHaveBeenCalled();
  });
});

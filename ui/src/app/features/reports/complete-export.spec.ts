import { HttpClient, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { PagedResult } from '../../core/models/forecast.models';
import { collectCompleteReport, COMPLETE_EXPORT_LIMIT } from './complete-export';

interface Row {
  id: number;
  text?: string;
}
describe('Bounded complete report collection', () => {
  let http: HttpTestingController;
  let client: HttpClient;
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    client = TestBed.inject(HttpClient);
  });
  afterEach(() => http.verify());
  function start(total = 501, validate: (page: PagedResult<Row>) => boolean = () => true) {
    const events = vi.fn();
    const error = vi.fn();
    const sub = collectCompleteReport<Row, PagedResult<Row>>(
      (page) => client.get<PagedResult<Row>>(`/export?page=${page}`),
      total,
      validate,
      (row) => String(row.id),
    ).subscribe({ next: events, error });
    return { sub, events, error };
  }
  function page(index: number, total = 501) {
    const offset = (index - 1) * 500;
    return {
      page: index,
      page_size: 500,
      total_records: total,
      total_pages: Math.ceil(total / 500),
      items: Array.from({ length: Math.min(500, total - offset) }, (_, n) => ({
        id: offset + n + 1,
      })),
    };
  }
  it('fetches sequential pages and emits complete only after the full exact count is available', () => {
    const exportRun = start();
    const first = http.expectOne('/export?page=1');
    http.expectNone('/export?page=2');
    first.flush(page(1));
    expect(exportRun.events).toHaveBeenCalledExactlyOnceWith({
      status: 'progress',
      loaded: 500,
      total: 501,
    });
    http.expectOne('/export?page=2').flush(page(2));
    const complete = exportRun.events.mock.calls[1][0];
    expect(complete.status).toBe('complete');
    expect(complete.items).toHaveLength(501);
    expect(complete.items[500].id).toBe(501);
    expect(exportRun.error).not.toHaveBeenCalled();
  });
  it('accepts the documented limit without fetching beyond it', () => {
    const exportRun = start(COMPLETE_EXPORT_LIMIT);
    for (let index = 1; index <= 40; index++)
      http.expectOne(`/export?page=${index}`).flush(page(index, COMPLETE_EXPORT_LIMIT));
    expect(exportRun.events.mock.lastCall?.[0].items).toHaveLength(COMPLETE_EXPORT_LIMIT);
    http.expectNone('/export?page=41');
  });
  it.each([0, -1, 1.5, COMPLETE_EXPORT_LIMIT + 1])(
    'rejects unsupported row count %s without fetching',
    (total) => {
      const exportRun = start(total);
      expect(exportRun.error).toHaveBeenCalledOnce();
      expect(exportRun.events).not.toHaveBeenCalled();
      http.expectNone('/export?page=1');
    },
  );
  it('cancels an in-flight page and never starts later pages', () => {
    const exportRun = start(1500);
    http.expectOne('/export?page=1').flush(page(1, 1500));
    const pending = http.expectOne('/export?page=2');
    exportRun.sub.unsubscribe();
    expect(pending.cancelled).toBe(true);
    http.expectNone('/export?page=3');
    expect(exportRun.events.mock.calls.map((call) => call[0].status)).toEqual(['progress']);
  });
  it('fails a later page without emitting a complete result or fetching subsequent pages', () => {
    const exportRun = start(1500);
    http.expectOne('/export?page=1').flush(page(1, 1500));
    http.expectOne('/export?page=2').flush({}, { status: 503, statusText: 'Unavailable' });
    expect(exportRun.error).toHaveBeenCalledOnce();
    http.expectNone('/export?page=3');
    expect(exportRun.events.mock.calls.map((call) => call[0].status)).toEqual(['progress']);
  });
  it.each([
    { total_records: 502 },
    { total_pages: 3 },
    { page_size: 50 },
    { page: 3 },
    { items: [] },
    { items: [{ id: 1 }] },
  ])('rejects changed pagination or duplicate data: %j', (override) => {
    const exportRun = start();
    http.expectOne('/export?page=1').flush(page(1));
    http.expectOne('/export?page=2').flush({ ...page(2), ...override });
    expect(exportRun.error).toHaveBeenCalledOnce();
    expect(exportRun.events.mock.calls.some((call) => call[0].status === 'complete')).toBe(false);
  });
  it('rejects mismatched context before requesting another page', () => {
    const exportRun = start(501, () => false);
    http.expectOne('/export?page=1').flush(page(1));
    expect(exportRun.error).toHaveBeenCalledOnce();
    http.expectNone('/export?page=2');
  });
  it('guards response memory before accepting a giant row', () => {
    const exportRun = start(1);
    http
      .expectOne('/export?page=1')
      .flush({ ...page(1, 1), items: [{ id: 1, text: 'x'.repeat(16 * 1024 * 1024) }] });
    expect(exportRun.error.mock.calls[0][0].message).toContain('memory guard');
    expect(exportRun.events).not.toHaveBeenCalled();
  });
});

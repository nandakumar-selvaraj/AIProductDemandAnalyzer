import { defer, EMPTY, expand, map, Observable } from 'rxjs';
import { PagedResult } from '../../core/models/forecast.models';
import { MAX_EXPORT_BYTES } from './csv-export';

export const COMPLETE_EXPORT_LIMIT = 20_000;
export const EXPORT_PAGE_SIZE = 500;
export type ExportProgress<T> =
  | { status: 'progress'; loaded: number; total: number }
  | { status: 'complete'; items: T[]; total: number };

/** Sequential bounded reads. Unsubscription cancels the current HTTP request and future pages. */
export function collectCompleteReport<T, P extends PagedResult<T>>(
  fetchPage: (page: number) => Observable<P>,
  expectedTotal: number,
  validateContext: (page: P) => boolean,
  rowKey: (row: T) => string,
): Observable<ExportProgress<T>> {
  return defer(() => {
    if (
      !Number.isInteger(expectedTotal) ||
      expectedTotal < 1 ||
      expectedTotal > COMPLETE_EXPORT_LIMIT
    )
      throw new Error(
        `Complete export supports 1–${COMPLETE_EXPORT_LIMIT} rows. A backend streaming export is needed for larger reports.`,
      );
    const items: T[] = [];
    const keys = new Set<string>();
    let nextPage = 1;
    let bytes = 0;
    const totalPages = Math.ceil(expectedTotal / EXPORT_PAGE_SIZE);
    return fetchValidated(1).pipe(
      expand((page) => (page.page < totalPages ? fetchValidated(page.page + 1) : EMPTY), 1),
      map((): ExportProgress<T> =>
        items.length === expectedTotal
          ? { status: 'complete', items, total: expectedTotal }
          : { status: 'progress', loaded: items.length, total: expectedTotal },
      ),
    );
    function fetchValidated(pageNumber: number): Observable<P> {
      return fetchPage(pageNumber).pipe(
        map((page) => {
          const expectedRows = Math.min(EXPORT_PAGE_SIZE, expectedTotal - items.length);
          if (
            !validateContext(page) ||
            page.page !== nextPage ||
            page.page_size !== EXPORT_PAGE_SIZE ||
            page.total_records !== expectedTotal ||
            page.total_pages !== totalPages ||
            page.items.length !== expectedRows
          )
            throw new Error(
              'Report data or pagination changed during export. No file was downloaded. Refresh the report and try again.',
            );
          for (const item of page.items) {
            const key = rowKey(item);
            if (keys.has(key))
              throw new Error(
                'Duplicate records detected during export. No file was downloaded. Refresh and try again.',
              );
            keys.add(key);
          }
          bytes += new TextEncoder().encode(JSON.stringify(page.items)).byteLength;
          if (bytes > MAX_EXPORT_BYTES)
            throw new Error(
              'Report exceeds the 16 MiB browser memory guard. No file was downloaded. A backend streaming export is needed.',
            );
          items.push(...page.items);
          nextPage++;
          return page;
        }),
      );
    }
  });
}

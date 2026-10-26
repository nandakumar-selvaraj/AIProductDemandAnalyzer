import { Injectable } from '@angular/core';
import { CsvCell, ReportTable } from './report.models';

export const MAX_EXPORT_BYTES = 16 * 1024 * 1024;

/** Numeric strings remain exact, including negative decimals. Expressions are always text. */
export function csvCell(value: CsvCell): string {
  let text = value === null ? 'N/A' : String(value);
  const numeric = /^-?\d+(?:\.\d+)?$/.test(text);
  // eslint-disable-next-line no-control-regex -- Formula prefixes can follow control characters in spreadsheet input.
  if ((!numeric && /^[\s\u0000-\u001f]*[=+\-@]/u.test(text)) || /^[\t\r\n]/.test(text))
    text = `'${text}`;
  return `"${text.replace(/"/g, '""')}"`;
}

/** Context is repeated in ordinary columns, so every exported row is self-describing. */
export function reportCsv(table: ReportTable, context: Readonly<Record<string, CsvCell>>): string {
  const keys = Object.keys(context);
  const prefix = Object.values(context);
  return (
    '\ufeff' +
    [[...keys, ...table.headers], ...table.rows.map((row) => [...prefix, ...row])]
      .map((row) => row.map(csvCell).join(','))
      .join('\r\n') +
    '\r\n'
  );
}

@Injectable({ providedIn: 'root' })
export class CsvDownloadService {
  download(filename: string, table: ReportTable, context: Readonly<Record<string, CsvCell>>): void {
    const csv = reportCsv(table, context);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    if (blob.size > MAX_EXPORT_BYTES)
      throw new Error(
        'CSV exceeds the 16 MiB browser limit. Use a smaller report; a backend streaming export is needed for larger reports.',
      );
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    try {
      anchor.href = url;
      anchor.download = filename;
      document.body.append(anchor);
      anchor.click();
    } finally {
      anchor.remove();
      // Allow the browser to start the download before releasing the object URL.
      setTimeout(() => URL.revokeObjectURL(url), 0);
    }
  }
}

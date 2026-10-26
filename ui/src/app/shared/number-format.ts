import { formatNumber } from '@angular/common';

/** Display only: keep API values untouched for calculations and CSV exports. */
export function twoDecimals(value: string | number | null, missing = 'N/A'): string {
  if (value === null || String(value).trim() === '' || !Number.isFinite(Number(value)))
    return missing;
  return formatNumber(Number(value), 'en-US', '1.2-2');
}

import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { apiErrorInterceptor } from '../../core/api-error.interceptor';
import { CatalogPage } from '../../core/models/analytics.models';
import { ProductsPage } from './products.page';

function catalog(page = 1, name = 'Apples'): CatalogPage {
  return {
    page,
    page_size: 10,
    total_records: 21,
    total_pages: 3,
    items: [{ id: page, item_code: `ITEM_${page}`, name }],
  };
}

describe('ProductsPage', () => {
  let fixture: ComponentFixture<ProductsPage>;
  let root: HTMLElement;
  let http: HttpTestingController;

  function request(page = 1, search = '', pageSize = 10) {
    const pending = http.expectOne(
      (req) =>
        req.url === `${environment.apiBaseUrl}/products` &&
        req.params.get('page') === String(page) &&
        (req.params.get('search') ?? '') === search,
    );
    expect(pending.request.params.get('page_size')).toBe(String(pageSize));
    return pending;
  }

  async function enterSearch(value: string, submit = true): Promise<void> {
    const input = root.querySelector<HTMLInputElement>('input[type="search"]')!;
    input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    fixture.detectChanges();
    await fixture.whenStable();
    if (submit) {
      root
        .querySelector('form')!
        .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      fixture.detectChanges();
    }
  }

  function click(label: string): void {
    const button = Array.from(root.querySelectorAll('button')).find(
      (node) => node.textContent?.trim() === label,
    );
    expect(button).toBeDefined();
    button!.click();
    fixture.detectChanges();
  }

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [ProductsPage],
      providers: [
        provideHttpClient(withInterceptors([apiErrorInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(ProductsPage);
    root = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
    await fixture.whenStable();
  });
  afterEach(() => {
    fixture.destroy();
    http.verify();
  });

  it('shows loading while allowing a newer search to replace the request', () => {
    expect(root.querySelector('[role="status"]')?.textContent).toContain('Loading products');
    expect(root.querySelector('.panel')?.getAttribute('aria-busy')).toBe('true');
    expect(root.querySelector<HTMLButtonElement>('button[type="submit"]')?.disabled).toBe(false);
    expect(root.querySelector('table')).toBeNull();
    request().flush(catalog());
  });

  it('renders a successful catalog and pagination boundaries', () => {
    request().flush(catalog());
    fixture.detectChanges();
    expect(root.querySelector('table')?.textContent).toContain('Apples');
    expect(root.querySelector('.count-pill')?.textContent).toContain('21 products');
    expect(root.querySelector('.pagination-row')?.textContent).toContain('Page 1 of 3');
    const controls = root.querySelectorAll<HTMLButtonElement>('.pagination-row button');
    expect(controls[0].disabled).toBe(true);
    expect(controls[1].disabled).toBe(false);
    expect(root.querySelector('.panel')?.getAttribute('aria-busy')).toBe('false');
  });

  it('shows an empty catalog without pagination or an error', () => {
    request().flush({ ...catalog(), total_records: 0, total_pages: 0, items: [] });
    fixture.detectChanges();
    expect(root.querySelector('.empty-state')?.textContent).toContain('No products found');
    expect(root.querySelector('.empty-state')?.textContent).toContain('catalog data is available');
    expect(root.querySelector('table')).toBeNull();
    expect(root.querySelector('.pagination-row')).toBeNull();
    expect(root.querySelector('[role="alert"]')).toBeNull();
  });

  it('normalizes an error, hides results, and recovers through retry', () => {
    request().flush({ detail: 'Catalog maintenance' }, { status: 503, statusText: 'Unavailable' });
    fixture.detectChanges();
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Catalog maintenance');
    expect(root.querySelector('.loading-state')).toBeNull();
    expect(root.querySelector('.empty-state')).toBeNull();
    expect(root.querySelector('table')).toBeNull();
    click('Try again');
    expect(root.querySelector('.loading-state')).not.toBeNull();
    request().flush(catalog());
    fixture.detectChanges();
    expect(root.querySelector('table')?.textContent).toContain('Apples');
    expect(root.querySelector('[role="alert"]')).toBeNull();
  });

  it('removes stale rows, counts, and controls after a previously successful request fails', async () => {
    request().flush(catalog());
    fixture.detectChanges();
    await enterSearch('Bananas');
    expect(root.querySelector('table')).toBeNull();
    request(1, 'Bananas').flush(null, { status: 500, statusText: 'Error' });
    fixture.detectChanges();
    expect(root.querySelector('[role="alert"]')).not.toBeNull();
    expect(root.textContent).not.toContain('Apples');
    expect(root.querySelector('.count-pill')).toBeNull();
    expect(root.querySelector('.pagination-row')).toBeNull();
  });

  it('submits a trimmed search from page one and keeps it when paging', async () => {
    request().flush(catalog());
    fixture.detectChanges();
    click('Next');
    request(2).flush(catalog(2));
    fixture.detectChanges();
    await enterSearch('  tea & coffee  ');
    request(1, 'tea & coffee').flush(catalog(1, 'Tea'));
    fixture.detectChanges();
    await enterSearch('unsubmitted draft', false);
    click('Next');
    request(2, 'tea & coffee').flush(catalog(2, 'More tea'));
    fixture.detectChanges();
    expect(root.querySelector('table')?.textContent).toContain('More tea');
    expect(root.querySelector('.pagination-row')?.textContent).toContain('Page 2 of 3');
    click('Previous');
    request(1, 'tea & coffee').flush(catalog(1, 'Tea'));
  });

  it('disables Next at the last page', () => {
    request().flush({ ...catalog(1), total_pages: 1, total_records: 1 });
    fixture.detectChanges();
    const controls = root.querySelectorAll<HTMLButtonElement>('.pagination-row button');
    expect(controls[0].disabled).toBe(true);
    expect(controls[1].disabled).toBe(true);
    click('Next');
    http.expectNone((req) => req.url.endsWith('/products'));
  });

  it('cancels an older search so its late response cannot overwrite newer results', async () => {
    const initial = request();
    await enterSearch('old');
    const old = request(1, 'old');
    expect(initial.cancelled).toBe(true);
    await enterSearch('new');
    const latest = request(1, 'new');
    expect(old.cancelled).toBe(true);
    expect(latest.cancelled).toBe(false);
    expect(root.querySelector('.loading-state')).not.toBeNull();
    latest.flush(catalog(1, 'Newest result'));
    expect(() => old.flush(catalog(1, 'Outdated result'))).toThrow(/cancelled/i);
    fixture.detectChanges();
    expect(root.querySelector('table')?.textContent).toContain('Newest result');
    expect(root.textContent).not.toContain('Outdated result');
  });

  it('cancels pending pagination when a new search is submitted', async () => {
    request().flush(catalog());
    fixture.detectChanges();
    click('Next');
    const pageTwo = request(2);
    await enterSearch('latest');
    expect(pageTwo.cancelled).toBe(true);
    request(1, 'latest').flush(catalog(1, 'Latest'));
    fixture.detectChanges();
    expect(root.querySelector('.pagination-row')?.textContent).toContain('Page 1 of 3');
  });

  it('retries the failed submitted query even if the draft input changed', async () => {
    request().flush(catalog());
    fixture.detectChanges();
    await enterSearch('tea');
    request(1, 'tea').flush(null, { status: 503, statusText: 'Unavailable' });
    fixture.detectChanges();
    await enterSearch('draft', false);
    click('Try again');
    request(1, 'tea').flush(catalog(1, 'Tea'));
  });

  it('explains empty search results and supports clearing the search', async () => {
    request().flush(catalog());
    fixture.detectChanges();
    await enterSearch('missing');
    request(1, 'missing').flush({ ...catalog(), total_records: 0, total_pages: 0, items: [] });
    fixture.detectChanges();
    expect(root.querySelector('.empty-state')?.textContent).toContain(
      'Try a different search term.',
    );
    await enterSearch('');
    request().flush(catalog());
    fixture.detectChanges();
    expect(root.querySelector('table')).not.toBeNull();
  });

  it('resets to page one and cancels the old request when page size changes', () => {
    request().flush(catalog());
    fixture.detectChanges();
    click('Next');
    const older = request(2);
    const select = root.querySelector<HTMLSelectElement>('#products-page-size')!;
    expect(Array.from(select.options, (option) => option.textContent?.trim())).toEqual([
      '10',
      '25',
      '50',
    ]);
    select.selectedIndex = 1;
    select.dispatchEvent(new Event('change', { bubbles: true }));
    fixture.detectChanges();
    expect(older.cancelled).toBe(true);
    const medium = request(1, '', 25);
    select.selectedIndex = 2;
    select.dispatchEvent(new Event('change', { bubbles: true }));
    fixture.detectChanges();
    expect(medium.cancelled).toBe(true);
    request(1, '', 50).flush({ ...catalog(), page_size: 50 });
    fixture.detectChanges();
    click('Next');
    request(2, '', 50).flush({ ...catalog(2), page_size: 50 });
  });

  it('cancels the active request on component destruction', () => {
    const pending = request();
    fixture.destroy();
    expect(pending.cancelled).toBe(true);
  });
});

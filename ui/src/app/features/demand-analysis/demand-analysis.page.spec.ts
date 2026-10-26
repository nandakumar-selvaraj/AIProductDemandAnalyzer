import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { apiErrorInterceptor } from '../../core/api-error.interceptor';
import {
  CatalogPage,
  ProductAnalyticsResponse,
  SalesSummary,
  StorePage,
} from '../../core/models/analytics.models';
import { DemandAnalysisPage } from './demand-analysis.page';

const products: CatalogPage = {
  page: 1,
  page_size: 50,
  total_records: 2,
  total_pages: 1,
  items: [
    { id: 11, item_code: 'ITEM_A', name: 'Apples' },
    { id: 12, item_code: 'ITEM_B', name: 'Bananas' },
  ],
};
const stores: StorePage = {
  page: 1,
  page_size: 50,
  total_records: 1,
  total_pages: 1,
  items: [{ id: 21, store_code: 'NORTH', name: 'North' }],
};
const overview: SalesSummary = {
  start_date: '2020-01-01',
  end_date: '2024-12-31',
  total_sales: 1_000_000,
  product_count: 100,
  store_count: 10,
  daily_sales: [{ sale_date: '2020-01-01', total_sales: 100 }],
};
const analysis: ProductAnalyticsResponse = {
  product_id: 11,
  store_id: null,
  start_date: '2024-01-01',
  end_date: '2024-01-07',
  total_units_sold: 30,
  observed_dates: 3,
  daily_sales: [
    { period: '2024-01-01', units_sold: 10 },
    { period: '2024-01-03', units_sold: 0 },
    { period: '2024-01-07', units_sold: 20 },
  ],
  monthly_sales: [{ period: '2024-01-01', units_sold: 30 }],
};

describe('DemandAnalysisPage', () => {
  let fixture: ComponentFixture<DemandAnalysisPage>;
  let root: HTMLElement;
  let http: HttpTestingController;

  function catalogRequest(kind: 'products' | 'stores', page = 1, search = '') {
    const request = http.expectOne(
      (req) =>
        req.url === `${environment.apiBaseUrl}/${kind}` &&
        req.params.get('page') === String(page) &&
        (req.params.get('search') ?? '') === search,
    );
    expect(request.request.params.get('page_size')).toBe('50');
    return request;
  }
  function analysisRequest(id = 11) {
    return http.expectOne(
      (req) => req.url === `${environment.apiBaseUrl}/products/${id}/analytics`,
    );
  }
  async function loadCatalogs(productPage = products, storePage = stores): Promise<void> {
    catalogRequest('products').flush(productPage);
    catalogRequest('stores').flush(storePage);
    http.expectOne(`${environment.apiBaseUrl}/sales/summary`).flush(overview);
    fixture.detectChanges();
    await fixture.whenStable();
  }
  async function setInput(selector: string, value: string): Promise<void> {
    const input = root.querySelector<HTMLInputElement>(selector)!;
    input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    fixture.detectChanges();
    await fixture.whenStable();
  }
  async function select(selector: string, text: string): Promise<void> {
    const control = root.querySelector<HTMLSelectElement>(selector)!;
    const option = Array.from(control.options).find((option) => option.textContent?.includes(text));
    expect(option).toBeDefined();
    control.value = option!.value;
    control.dispatchEvent(new Event('change', { bubbles: true }));
    fixture.detectChanges();
    await fixture.whenStable();
  }
  function click(text: string): void {
    const button = Array.from(root.querySelectorAll('button')).find(
      (button) => button.textContent?.trim() === text,
    );
    expect(button).toBeDefined();
    button!.click();
    fixture.detectChanges();
  }
  function apply(): void {
    root
      .querySelector('form')!
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    fixture.detectChanges();
  }
  async function pickProduct(): Promise<void> {
    await select('#products-catalog-select', 'Apples');
  }

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [DemandAnalysisPage],
      providers: [
        provideHttpClient(withInterceptors([apiErrorInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(DemandAnalysisPage);
    root = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
    await fixture.whenStable();
  });
  afterEach(() => {
    fixture.destroy();
    http.verify();
  });

  it('loads both paginated catalogs and global context without issuing speculative analytics', async () => {
    expect(root.textContent).toContain('Loading products');
    expect(root.textContent).toContain('Loading stores');
    expect(root.querySelector<HTMLSelectElement>('#stores-catalog-select')?.disabled).toBe(true);
    await loadCatalogs();
    expect(
      root.querySelector<HTMLSelectElement>('#stores-catalog-select')?.selectedOptions[0]
        .textContent,
    ).toContain('All Stores');
    expect(root.textContent).toContain('Choose a product to begin');
    expect(root.textContent).toContain('Jan 1, 2020');
    http.expectNone((req) => req.url.endsWith('/analytics'));
  });

  it('supports an empty product catalog and no stores while preserving All Stores', async () => {
    await loadCatalogs(
      { ...products, items: [], total_records: 0, total_pages: 0 },
      { ...stores, items: [], total_records: 0, total_pages: 0 },
    );
    expect(root.textContent).toContain('No products available.');
    expect(root.textContent).toContain('No stores available.');
    expect(
      root.querySelector<HTMLSelectElement>('#stores-catalog-select')?.selectedOptions[0]
        .textContent,
    ).toContain('All Stores');
    apply();
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Select a product');
    http.expectNone((req) => req.url.endsWith('/analytics'));
  });

  it('searches catalogs, paginates matches, and retains a selected product across pages', async () => {
    await loadCatalogs({
      ...products,
      items: [products.items[0]],
      total_records: 51,
      total_pages: 2,
    });
    await pickProduct();
    root.querySelector<HTMLButtonElement>('[aria-label="Next product page"]')!.click();
    fixture.detectChanges();
    catalogRequest('products', 2).flush({
      ...products,
      page: 2,
      items: [products.items[1]],
      total_records: 51,
      total_pages: 2,
    });
    fixture.detectChanges();
    await fixture.whenStable();
    expect(
      root.querySelector<HTMLSelectElement>('#products-catalog-select')?.selectedOptions[0]
        .textContent,
    ).toContain('Apples');
    await setInput('#products-catalog-search', '  Ban  ');
    root.querySelector<HTMLButtonElement>('[aria-label="Search products"]')!.click();
    fixture.detectChanges();
    catalogRequest('products', 1, 'Ban').flush({
      ...products,
      items: [products.items[1]],
      total_records: 1,
    });
    fixture.detectChanges();
    await fixture.whenStable();
    await select('#products-catalog-select', 'Bananas');
    apply();
    analysisRequest(12).flush({ ...analysis, product_id: 12 });
    fixture.detectChanges();
    expect(root.querySelector('.applied-context')?.textContent).toContain('Bananas');
  });

  it('distinguishes a catalog search with no matches', async () => {
    await loadCatalogs();
    await setInput('#products-catalog-search', 'missing');
    root.querySelector<HTMLButtonElement>('[aria-label="Search products"]')!.click();
    fixture.detectChanges();
    catalogRequest('products', 1, 'missing').flush({
      ...products,
      items: [],
      total_records: 0,
      total_pages: 0,
    });
    fixture.detectChanges();
    expect(root.textContent).toContain('No products match this search.');
    expect(root.textContent).not.toContain('No products available.');
  });

  it('uses filters in the verified HTTP query and calculates averages only over observed dates', async () => {
    await loadCatalogs();
    await pickProduct();
    await select('#stores-catalog-select', 'North');
    await setInput('#analysis-start', '2024-01-01');
    await setInput('#analysis-end', '2024-01-07');
    apply();
    expect(root.querySelector('.loading-state')?.textContent).toContain('Apples');
    const request = analysisRequest();
    expect(request.request.params.get('store_id')).toBe('21');
    expect(request.request.params.get('start_date')).toBe('2024-01-01');
    expect(request.request.params.get('end_date')).toBe('2024-01-07');
    request.flush({ ...analysis, store_id: 21 });
    fixture.detectChanges();
    const metrics = Array.from(root.querySelectorAll('.metric > strong'), (node) =>
      node.textContent?.trim(),
    );
    expect(metrics.slice(0, 3)).toEqual(['30', '3', '10']);
    expect(root.querySelector('.applied-context')?.textContent).toContain('North');
    expect(root.textContent).toContain('not per calendar day');
    expect(root.querySelectorAll('.observations tbody tr')).toHaveLength(3);
    expect(root.querySelectorAll('app-historical-chart')).toHaveLength(2);
  });

  it.each([
    ['2024-02-02', '2024-02-01', 'must not be after'],
    ['2024-01-01', '2024-12-31', 'at most 365'],
  ])('rejects invalid date range %s / %s without an API request', async (start, end, message) => {
    await loadCatalogs();
    await pickProduct();
    await setInput('#analysis-start', start);
    await setInput('#analysis-end', end);
    apply();
    expect(root.querySelector('[role="alert"]')?.textContent).toContain(message);
    expect(root.querySelector('#analysis-start')?.getAttribute('aria-invalid')).toBe('true');
    http.expectNone((req) => req.url.endsWith('/analytics'));
  });

  it('supports partial date filters and omits All Stores from the query', async () => {
    await loadCatalogs();
    await pickProduct();
    await setInput('#analysis-start', '2024-01-01');
    apply();
    const request = analysisRequest();
    expect(request.request.params.keys()).toEqual(['start_date']);
    request.flush(analysis);
  });

  it('renders empty analytics without turning missing history into a zero-day average', async () => {
    await loadCatalogs();
    await pickProduct();
    apply();
    analysisRequest().flush({
      ...analysis,
      start_date: null,
      end_date: null,
      total_units_sold: 0,
      observed_dates: 0,
      daily_sales: [],
      monthly_sales: [],
    });
    fixture.detectChanges();
    expect(root.textContent).toContain('No sales for the selected filters');
    expect(root.querySelectorAll('.metric > strong')[2].textContent?.trim()).toBe('—');
    expect(root.querySelectorAll('svg')).toHaveLength(0);
    expect(root.querySelector('.observations')).toBeNull();
  });

  it('preserves a real zero observation as a zero average', async () => {
    await loadCatalogs();
    await pickProduct();
    apply();
    analysisRequest().flush({
      ...analysis,
      total_units_sold: 0,
      observed_dates: 1,
      daily_sales: [{ period: '2024-01-03', units_sold: 0 }],
      monthly_sales: [{ period: '2024-01-01', units_sold: 0 }],
    });
    fixture.detectChanges();
    expect(root.querySelectorAll('.metric > strong')[2].textContent?.trim()).toBe('0');
    expect(root.querySelectorAll('.observations tbody tr')).toHaveLength(1);
  });

  it('handles product-not-found and retries the applied filters after the draft changes', async () => {
    await loadCatalogs();
    await pickProduct();
    apply();
    analysisRequest().flush(
      { detail: { code: 'product_not_found', message: 'Product was not found' } },
      { status: 404, statusText: 'Not found' },
    );
    fixture.detectChanges();
    expect(root.querySelector('.analysis-results [role="alert"]')?.textContent).toContain(
      'choose another product',
    );
    await select('#stores-catalog-select', 'North');
    click('Retry analysis');
    const retried = analysisRequest();
    expect(retried.request.params.has('store_id')).toBe(false);
    retried.flush(analysis);
    fixture.detectChanges();
    expect(root.querySelector('.applied-context')?.textContent).toContain('All Stores');
    expect(root.querySelector('.changed-note')?.textContent).toContain('Filters have changed');
  });

  it('clears earlier analytics on backend failure and recovers with retry', async () => {
    await loadCatalogs();
    await pickProduct();
    apply();
    analysisRequest().flush(analysis);
    fixture.detectChanges();
    apply();
    expect(root.querySelector('.summary-grid')).toBeNull();
    analysisRequest().flush(
      { detail: 'Product analytics unavailable' },
      { status: 503, statusText: 'Unavailable' },
    );
    fixture.detectChanges();
    expect(root.querySelector('.analysis-results [role="alert"]')?.textContent).toContain(
      'Product analytics unavailable',
    );
    expect(root.querySelector('.summary-grid')).toBeNull();
    click('Retry analysis');
    analysisRequest().flush(analysis);
    fixture.detectChanges();
    expect(root.querySelector('.summary-grid')).not.toBeNull();
  });

  it('cancels obsolete analytics on rapid Apply actions', async () => {
    await loadCatalogs();
    await pickProduct();
    apply();
    const previous = analysisRequest();
    await select('#stores-catalog-select', 'North');
    apply();
    const latest = analysisRequest();
    expect(previous.cancelled).toBe(true);
    expect(latest.request.params.get('store_id')).toBe('21');
    latest.flush({ ...analysis, store_id: 21 });
    expect(() => previous.flush(analysis)).toThrow(/cancelled/i);
    fixture.detectChanges();
    expect(root.querySelector('.applied-context')?.textContent).toContain('North');
  });

  it('cancels outdated product and store searches independently', async () => {
    await loadCatalogs();
    await setInput('#products-catalog-search', 'old');
    root.querySelector<HTMLButtonElement>('[aria-label="Search products"]')!.click();
    fixture.detectChanges();
    const oldProduct = catalogRequest('products', 1, 'old');
    await setInput('#products-catalog-search', 'new');
    root.querySelector<HTMLButtonElement>('[aria-label="Search products"]')!.click();
    fixture.detectChanges();
    expect(oldProduct.cancelled).toBe(true);
    catalogRequest('products', 1, 'new').flush(products);
    await setInput('#stores-catalog-search', 'old');
    root.querySelector<HTMLButtonElement>('[aria-label="Search stores"]')!.click();
    fixture.detectChanges();
    const oldStore = catalogRequest('stores', 1, 'old');
    await setInput('#stores-catalog-search', 'North');
    root.querySelector<HTMLButtonElement>('[aria-label="Search stores"]')!.click();
    fixture.detectChanges();
    expect(oldStore.cancelled).toBe(true);
    catalogRequest('stores', 1, 'North').flush(stores);
  });

  it('resets selections, search, dates, validation, and pending analytics', async () => {
    await loadCatalogs();
    await pickProduct();
    await setInput('#analysis-start', '2024-01-01');
    apply();
    const pending = analysisRequest();
    await setInput('#products-catalog-search', 'draft');
    click('Reset Filters');
    expect(pending.cancelled).toBe(true);
    catalogRequest('products').flush(products);
    catalogRequest('stores').flush(stores);
    fixture.detectChanges();
    await fixture.whenStable();
    expect(root.querySelector<HTMLInputElement>('#products-catalog-search')?.value).toBe('');
    expect(root.querySelector<HTMLInputElement>('#analysis-start')?.value).toBe('');
    expect(
      root.querySelector<HTMLSelectElement>('#products-catalog-select')?.selectedOptions[0]
        .textContent,
    ).toContain('Select a product');
    expect(
      root.querySelector<HTMLSelectElement>('#stores-catalog-select')?.selectedOptions[0]
        .textContent,
    ).toContain('All Stores');
    expect(root.textContent).toContain('Choose a product to begin');
    expect(root.querySelector('.summary-grid')).toBeNull();
  });

  it('recovers catalog and overall-history errors independently', async () => {
    catalogRequest('products').flush(null, { status: 503, statusText: 'Unavailable' });
    catalogRequest('stores').flush(stores);
    http
      .expectOne(`${environment.apiBaseUrl}/sales/summary`)
      .flush(null, { status: 503, statusText: 'Unavailable' });
    fixture.detectChanges();
    expect(root.textContent).toContain('Product catalog unavailable');
    expect(root.textContent).toContain('You can still analyze a product');
    click('Retry products');
    catalogRequest('products').flush(products);
    fixture.detectChanges();
    await fixture.whenStable();
    await pickProduct();
    apply();
    analysisRequest().flush(analysis);
    click('Retry overall history');
    http.expectOne(`${environment.apiBaseUrl}/sales/summary`).flush(overview);
    fixture.detectChanges();
    expect(root.querySelector('.summary-grid')).not.toBeNull();
  });

  it('bounds daily table DOM rows and supports sorting and pagination for a full year', async () => {
    await loadCatalogs();
    await pickProduct();
    apply();
    const daily = Array.from({ length: 365 }, (_, index) => ({
      period: new Date(Date.UTC(2023, 0, index + 1)).toISOString().slice(0, 10),
      units_sold: 1,
    }));
    const totals = new Map<string, number>();
    for (const point of daily) {
      const month = point.period.slice(0, 7) + '-01';
      totals.set(month, (totals.get(month) ?? 0) + 1);
    }
    analysisRequest().flush({
      ...analysis,
      start_date: '2023-01-01',
      end_date: '2023-12-31',
      total_units_sold: 365,
      observed_dates: 365,
      daily_sales: daily,
      monthly_sales: Array.from(totals, ([period, units_sold]) => ({ period, units_sold })),
    });
    fixture.detectChanges();
    expect(root.querySelectorAll('.observations tbody tr')).toHaveLength(25);
    click('Next dates');
    expect(root.querySelector('.observations tbody tr')?.textContent).toContain('Jan 26, 2023');
    expect(root.querySelector('.table-pages')?.textContent).toContain('Page 2 of 15');
    await select('#observation-order', 'Newest first');
    expect(root.querySelector('.observations tbody tr')?.textContent).toContain('Dec 31, 2023');
    expect(root.querySelector('th[aria-sort]')?.getAttribute('aria-sort')).toBe('descending');
    expect(root.querySelector('.table-pages')?.textContent).toContain('Page 1 of 15');
  });

  it('provides labels, chart descriptions, and exact daily values for assistive technology', async () => {
    await loadCatalogs();
    await pickProduct();
    apply();
    analysisRequest().flush(analysis);
    fixture.detectChanges();
    expect(root.querySelector('label[for="products-catalog-select"]')).not.toBeNull();
    expect(root.querySelector('label[for="analysis-start"]')).not.toBeNull();
    expect(root.querySelector('svg')?.getAttribute('aria-describedby')).toBe(
      'daily-history-description',
    );
    expect(root.querySelector('.observations caption')?.textContent).toContain(
      'Exact daily totals',
    );
    expect(root.querySelectorAll('.observations tbody tr')).toHaveLength(3);
    expect(root.textContent).toContain('Missing periods are gaps');
  });

  it('cancels all initial requests on destruction', () => {
    const product = catalogRequest('products');
    const store = catalogRequest('stores');
    const history = http.expectOne(`${environment.apiBaseUrl}/sales/summary`);
    fixture.destroy();
    expect(product.cancelled).toBe(true);
    expect(store.cancelled).toBe(true);
    expect(history.cancelled).toBe(true);
  });

  it('cancels analytics on destruction', async () => {
    await loadCatalogs();
    await pickProduct();
    apply();
    const request = analysisRequest();
    fixture.destroy();
    expect(request.cancelled).toBe(true);
  });
});

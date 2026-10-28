import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { BehaviorSubject, catchError, map, of, startWith, switchMap } from 'rxjs';
import { AlertComponent, SpinnerComponent } from '@coreui/angular';
import { AnalyticsApiService } from '../../core/services/analytics-api.service';
import { ProductListItem } from '../../core/models/analytics.models';
@Component({
  selector: 'app-products-page',
  imports: [FormsModule, AlertComponent, SpinnerComponent],
  templateUrl: './products.page.html',
  styleUrl: './products.page.scss',
})
export class ProductsPage {
  private readonly api = inject(AnalyticsApiService);
  protected readonly products = signal<ProductListItem[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly search = signal('');
  protected readonly submittedSearch = signal('');
  protected readonly page = signal(1);
  protected readonly pageSize = signal(10);
  protected readonly pageSizes = [10, 25, 50];
  protected readonly totalPages = signal(0);
  protected readonly totalRecords = signal(0);
  private readonly query = new BehaviorSubject({ page: 1, pageSize: 10, search: '' });

  constructor() {
    this.query
      .pipe(
        switchMap((query) => {
          this.page.set(query.page);
          this.pageSize.set(query.pageSize);
          this.submittedSearch.set(query.search);
          return this.api.getProducts(query.page, query.pageSize, query.search).pipe(
            map((result) => ({ status: 'success', result }) as const),
            catchError((error: unknown) =>
              of({
                status: 'error',
                message:
                  error instanceof Error && error.message
                    ? error.message
                    : 'Product catalog could not be loaded.',
              } as const),
            ),
            startWith({ status: 'loading' } as const),
          );
        }),
        takeUntilDestroyed(),
      )
      .subscribe((state) => {
        this.loading.set(state.status === 'loading');
        this.error.set(state.status === 'error' ? state.message : null);
        this.products.set(state.status === 'success' ? state.result.items : []);
        this.totalRecords.set(state.status === 'success' ? state.result.total_records : 0);
        this.totalPages.set(state.status === 'success' ? state.result.total_pages : 0);
      });
  }

  protected loadProducts(): void {
    this.query.next({ ...this.query.value });
  }

  protected changePage(page: number): void {
    if (this.loading() || page < 1 || page > this.totalPages()) return;
    this.query.next({ ...this.query.value, page });
  }

  protected changePageSize(pageSize: number): void {
    if (!this.pageSizes.includes(pageSize) || pageSize === this.pageSize()) return;
    this.query.next({ ...this.query.value, page: 1, pageSize });
  }

  protected submitSearch(event: Event): void {
    event.preventDefault();
    this.query.next({ ...this.query.value, page: 1, search: this.search().trim() });
  }
}

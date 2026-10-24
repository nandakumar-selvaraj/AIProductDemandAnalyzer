import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { finalize } from 'rxjs';
import { AlertComponent, SpinnerComponent } from '@coreui/angular';
import { AnalyticsApiService } from '../../core/services/analytics-api.service';
import { ProductListItem } from '../../core/models/analytics.models';
@Component({ selector: 'app-products-page', imports: [FormsModule, AlertComponent, SpinnerComponent], templateUrl: './products.page.html', styleUrl: './products.page.scss' })
export class ProductsPage {
  private readonly api = inject(AnalyticsApiService);
  protected readonly products = signal<ProductListItem[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly search = signal('');
  protected readonly page = signal(1);
  protected readonly totalPages = signal(0);
  protected readonly totalRecords = signal(0);
  constructor() { this.loadProducts(); }
  protected loadProducts(): void {
    this.loading.set(true); this.error.set(null);
    this.api.getProducts(this.page(), 10, this.search()).pipe(finalize(() => this.loading.set(false))).subscribe({
      next: (result) => { this.products.set(result.items); this.totalPages.set(result.total_pages); this.totalRecords.set(result.total_records); },
      error: (error: Error) => this.error.set(error.message || 'Product catalog could not be loaded.'),
    });
  }
  protected changePage(page: number): void { if (page < 1 || page > this.totalPages()) return; this.page.set(page); this.loadProducts(); }
  protected submitSearch(event: Event): void { event.preventDefault(); this.page.set(1); this.loadProducts(); }
}
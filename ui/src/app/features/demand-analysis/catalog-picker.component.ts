import {
  Component,
  computed,
  DestroyRef,
  inject,
  input,
  model,
  OnInit,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { AlertComponent, SpinnerComponent } from '@coreui/angular';
import { BehaviorSubject, catchError, map, Observable, of, startWith, switchMap } from 'rxjs';
import { CatalogPage, StorePage } from '../../core/models/analytics.models';
import { AnalyticsApiService } from '../../core/services/analytics-api.service';
import { CatalogChoice } from './demand-analysis.models';

type CatalogState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'success'; items: CatalogChoice[]; totalPages: number; total: number };

@Component({
  selector: 'app-catalog-picker',
  imports: [FormsModule, AlertComponent, SpinnerComponent],
  templateUrl: './catalog-picker.component.html',
  styleUrl: './catalog-picker.component.scss',
})
export class CatalogPickerComponent implements OnInit {
  readonly kind = input.required<'products' | 'stores'>();
  readonly selection = model<CatalogChoice | null>(null);
  readonly invalid = input(false);
  private readonly api = inject(AnalyticsApiService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly query = new BehaviorSubject({ page: 1, search: '' });
  protected readonly search = signal('');
  protected readonly appliedSearch = signal('');
  protected readonly page = signal(1);
  protected readonly state = signal<CatalogState>({ status: 'loading' });
  protected readonly label = computed(() => (this.kind() === 'products' ? 'Product' : 'Store'));
  protected readonly controlId = computed(() => `${this.kind()}-catalog`);
  protected readonly result = computed(() => {
    const state = this.state();
    return state.status === 'success' ? state : null;
  });
  protected readonly pinnedSelection = computed(() => {
    const selected = this.selection();
    return selected && !this.result()?.items.some((item) => item.id === selected.id)
      ? selected
      : null;
  });

  ngOnInit(): void {
    this.query
      .pipe(
        switchMap((query) => {
          this.page.set(query.page);
          this.appliedSearch.set(query.search);
          const request: Observable<CatalogPage | StorePage> =
            this.kind() === 'products'
              ? this.api.getProducts(query.page, 50, query.search)
              : this.api.getStores(query.page, 50, query.search);
          return request.pipe(
            map((result): CatalogState => ({
              status: 'success',
              totalPages: result.total_pages,
              total: result.total_records,
              items: result.items.map((item) => ({
                id: item.id,
                name: item.name,
                code: 'item_code' in item ? item.item_code : item.store_code,
              })),
            })),
            catchError((error: unknown) =>
              of<CatalogState>({
                status: 'error',
                message: error instanceof Error ? error.message : 'Catalog could not be loaded.',
              }),
            ),
            startWith({ status: 'loading' } as const),
          );
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((state) => this.state.set(state));
  }

  protected searchCatalog(event?: Event): void {
    event?.preventDefault();
    this.query.next({ page: 1, search: this.search().trim() });
  }

  protected changePage(page: number): void {
    if (this.state().status === 'loading' || page < 1 || page > (this.result()?.totalPages ?? 0))
      return;
    this.query.next({ page, search: this.appliedSearch() });
  }

  protected select(id: number | null): void {
    const choice = this.result()?.items.find((item) => item.id === id) ?? this.pinnedSelection();
    this.selection.set(id === null ? null : (choice ?? null));
  }

  protected retry(): void {
    this.query.next({ ...this.query.value });
  }

  reset(): void {
    this.search.set('');
    this.selection.set(null);
    this.query.next({ page: 1, search: '' });
  }
}

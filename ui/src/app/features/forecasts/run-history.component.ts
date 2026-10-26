import { DatePipe } from '@angular/common';
import {
  Component,
  computed,
  ElementRef,
  inject,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { AlertComponent, SpinnerComponent } from '@coreui/angular';
import { BehaviorSubject, switchMap } from 'rxjs';
import { ForecastRunItem, PagedResult, RunStatusFilter } from '../../core/models/forecast.models';
import { ForecastApiService } from '../../core/services/forecast-api.service';
import { LoadState, requestState } from './forecast.helpers';

@Component({
  selector: 'app-run-history',
  imports: [DatePipe, FormsModule, AlertComponent, SpinnerComponent],
  templateUrl: './run-history.component.html',
  styleUrl: './forecast-panel.scss',
})
export class RunHistoryComponent {
  readonly selectedId = input<number | null>(null);
  readonly runSelected = output<ForecastRunItem>();
  private readonly api = inject(ForecastApiService);
  private readonly query = new BehaviorSubject<{ page: number; status: RunStatusFilter }>({
    page: 1,
    status: '',
  });
  private readonly heading = viewChild<ElementRef<HTMLElement>>('heading');
  protected readonly filter = signal<RunStatusFilter>('');
  protected readonly page = signal(1);
  protected readonly state = signal<LoadState<PagedResult<ForecastRunItem>>>({ status: 'loading' });
  protected readonly result = computed(() => {
    const state = this.state();
    return state.status === 'success' ? state.data : null;
  });
  constructor() {
    this.query
      .pipe(
        switchMap((query) => requestState(this.api.getRuns(query.page, query.status))),
        takeUntilDestroyed(),
      )
      .subscribe((state) => this.state.set(state));
  }
  protected setFilter(status: RunStatusFilter): void {
    this.filter.set(status);
    this.page.set(1);
    this.query.next({ page: 1, status });
  }
  protected changePage(page: number): void {
    if (this.state().status === 'loading' || page < 1 || page > (this.result()?.total_pages ?? 0))
      return;
    this.page.set(page);
    this.query.next({ page, status: this.filter() });
  }
  refresh(afterCreation = false): void {
    if (afterCreation) this.setFilter('');
    else this.query.next({ ...this.query.value });
  }
  focusHeading(): void {
    this.heading()?.nativeElement.focus();
  }
}

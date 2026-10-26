import { Component, computed, inject, model, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { AlertComponent, SpinnerComponent } from '@coreui/angular';
import { BehaviorSubject, switchMap } from 'rxjs';
import { ForecastRunItem, PagedResult } from '../../core/models/forecast.models';
import { ForecastApiService } from '../../core/services/forecast-api.service';
import { LoadState, requestState } from '../forecasts/forecast.helpers';

@Component({
  selector: 'app-report-run-picker',
  imports: [FormsModule, AlertComponent, SpinnerComponent],
  templateUrl: './run-picker.component.html',
  styleUrl: './reports.scss',
})
export class ReportRunPickerComponent {
  readonly selection = model<ForecastRunItem | null>(null);
  private readonly api = inject(ForecastApiService);
  private readonly requests = new BehaviorSubject(1);
  protected readonly state = signal<LoadState<PagedResult<ForecastRunItem>>>({ status: 'loading' });
  protected readonly result = computed(() => {
    const state = this.state();
    return state.status === 'success' ? state.data : null;
  });
  protected readonly pinned = computed(() => {
    const selection = this.selection();
    return selection && !this.result()?.items.some((run) => run.id === selection.id)
      ? selection
      : null;
  });
  constructor() {
    this.requests
      .pipe(
        switchMap((page) => requestState(this.api.getRuns(page, 'completed'))),
        takeUntilDestroyed(),
      )
      .subscribe((state) => this.state.set(state));
  }
  protected select(id: number | null): void {
    this.selection.set(
      id === null ? null : (this.result()?.items.find((run) => run.id === id) ?? this.pinned()),
    );
  }
  protected refresh(): void {
    this.requests.next(this.requests.value);
  }
  protected page(page: number): void {
    if (this.state().status !== 'loading' && page > 0 && page <= (this.result()?.total_pages ?? 0))
      this.requests.next(page);
  }
}

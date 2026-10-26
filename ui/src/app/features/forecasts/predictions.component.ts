import { Component, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { AlertComponent, SpinnerComponent } from '@coreui/angular';
import { startWith, Subject, switchMap } from 'rxjs';
import { PredictionPage } from '../../core/models/forecast.models';
import { ForecastApiService } from '../../core/services/forecast-api.service';
import { twoDecimals } from '../../shared/number-format';
import { LoadState, predictionBars, requestState } from './forecast.helpers';

@Component({
  selector: 'app-forecast-predictions',
  imports: [AlertComponent, SpinnerComponent],
  templateUrl: './predictions.component.html',
  styleUrl: './forecast-panel.scss',
})
export class PredictionsComponent {
  readonly runId = input.required<number>();
  protected readonly decimal = twoDecimals;
  private readonly api = inject(ForecastApiService);
  private readonly pages = new Subject<number>();
  protected readonly page = signal(1);
  protected readonly state = signal<LoadState<PredictionPage>>({ status: 'loading' });
  protected readonly result = computed(() => {
    const state = this.state();
    return state.status === 'success' && state.data.run_id === this.runId() ? state.data : null;
  });
  protected readonly bars = computed(() => predictionBars(this.result()?.items ?? []));
  constructor() {
    toObservable(this.runId)
      .pipe(
        switchMap((id) =>
          this.pages.pipe(
            startWith(1),
            switchMap((page) => {
              this.page.set(page);
              return requestState(this.api.getPredictions(id, page));
            }),
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((state) => this.state.set(state));
  }
  protected retry(): void {
    this.pages.next(this.page());
  }
  protected changePage(page: number): void {
    if (this.state().status === 'loading' || page < 1 || page > (this.result()?.total_pages ?? 0))
      return;
    this.pages.next(page);
  }
}

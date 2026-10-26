import { Component, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { AlertComponent, SpinnerComponent } from '@coreui/angular';
import { distinctUntilChanged, of, startWith, Subject, switchMap } from 'rxjs';
import {
  RecommendationLabel,
  RecommendationPage,
  RunContext,
} from '../../core/models/forecast.models';
import { ForecastApiService } from '../../core/services/forecast-api.service';
import { exactDecimal, LoadState, requestState } from './forecast.helpers';

@Component({
  selector: 'app-forecast-recommendations',
  imports: [AlertComponent, SpinnerComponent],
  templateUrl: './recommendations.component.html',
  styleUrl: './forecast-panel.scss',
})
export class RecommendationsComponent {
  readonly run = input.required<RunContext>();
  private readonly api = inject(ForecastApiService);
  private readonly pages = new Subject<number>();
  protected readonly page = signal(1);
  protected readonly exact = exactDecimal;
  protected readonly labels: Record<RecommendationLabel, string> = {
    increase: 'Increase',
    maintain: 'Maintain',
    reduce: 'Reduce',
    insufficient_data: 'Insufficient data',
  };
  protected readonly state = signal<LoadState<RecommendationPage>>({ status: 'idle' });
  protected readonly result = computed(() => {
    const state = this.state();
    return state.status === 'success' && state.data.forecast_run_id === this.run().id
      ? state.data
      : null;
  });
  constructor() {
    toObservable(this.run)
      .pipe(
        distinctUntilChanged(
          (previous, current) => previous.id === current.id && previous.status === current.status,
        ),
        switchMap((run) =>
          run.status === 'completed'
            ? this.pages.pipe(
                startWith(1),
                switchMap((page) => {
                  this.page.set(page);
                  return requestState(this.api.getRecommendations(run.id, page));
                }),
              )
            : of<LoadState<RecommendationPage>>({ status: 'idle' }),
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

import { Component, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { AlertComponent, SpinnerComponent } from '@coreui/angular';
import { distinctUntilChanged, exhaustMap, of, startWith, Subject, switchMap } from 'rxjs';
import { EvaluationResult, RunContext } from '../../core/models/forecast.models';
import { ForecastApiService } from '../../core/services/forecast-api.service';
import { AccuracyMetricsComponent } from './accuracy-metrics.component';
import { LoadState, requestState } from './forecast.helpers';

@Component({
  selector: 'app-forecast-evaluation',
  imports: [AlertComponent, SpinnerComponent, AccuracyMetricsComponent],
  templateUrl: './evaluation.component.html',
  styleUrl: './forecast-panel.scss',
})
export class EvaluationComponent {
  readonly run = input.required<RunContext>();
  private readonly api = inject(ForecastApiService);
  private readonly requests = new Subject<void>();
  protected readonly state = signal<LoadState<EvaluationResult>>({ status: 'idle' });
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
            ? this.requests.pipe(
                exhaustMap(() => requestState(this.api.evaluate(run.id))),
                startWith({ status: 'idle' } as const),
              )
            : of<LoadState<EvaluationResult>>({ status: 'idle' }),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((state) => this.state.set(state));
  }
  protected evaluate(): void {
    if (this.run().status === 'completed' && this.state().status !== 'loading')
      this.requests.next();
  }
}

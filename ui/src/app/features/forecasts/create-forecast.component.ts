import { Component, computed, inject, output, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { AlertComponent, SpinnerComponent } from '@coreui/angular';
import { exhaustMap, Subject } from 'rxjs';
import { ForecastCreated, ForecastRequest } from '../../core/models/forecast.models';
import { ForecastApiService } from '../../core/services/forecast-api.service';
import { createdContext, LoadState, requestState, validateForecast } from './forecast.helpers';
import { RunOverviewComponent } from './run-overview.component';

@Component({
  selector: 'app-create-forecast',
  imports: [FormsModule, AlertComponent, SpinnerComponent, RunOverviewComponent],
  templateUrl: './create-forecast.component.html',
  styleUrl: './forecast-panel.scss',
})
export class CreateForecastComponent {
  readonly created = output<ForecastCreated>();
  private readonly api = inject(ForecastApiService);
  private readonly submissions = new Subject<ForecastRequest>();
  protected readonly horizon = signal<number | null>(30);
  protected readonly cutoff = signal('');
  protected readonly errors = signal<string[]>([]);
  protected readonly state = signal<LoadState<ForecastCreated>>({ status: 'idle' });
  protected readonly pending = computed(() => this.state().status === 'loading');
  protected readonly context = computed(() => {
    const state = this.state();
    return state.status === 'success' ? createdContext(state.data) : null;
  });

  constructor() {
    this.submissions
      .pipe(
        exhaustMap((request) => requestState(this.api.createForecast(request))),
        takeUntilDestroyed(),
      )
      .subscribe((state) => {
        this.state.set(state);
        if (state.status === 'success') this.created.emit(state.data);
      });
  }
  protected submit(): void {
    if (this.pending()) return;
    const horizon = this.horizon();
    this.errors.set(validateForecast(horizon, this.cutoff()));
    if (this.errors().length || horizon === null) return;
    this.submissions.next({ horizon_days: horizon, start_date: this.cutoff() || null });
  }
}

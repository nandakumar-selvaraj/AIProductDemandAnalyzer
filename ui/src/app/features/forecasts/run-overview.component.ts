import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, input } from '@angular/core';
import { RunContext } from '../../core/models/forecast.models';
import { recordedCount } from './forecast.helpers';

@Component({
  selector: 'app-run-overview',
  imports: [DatePipe, DecimalPipe],
  templateUrl: './run-overview.component.html',
  styleUrl: './forecast-panel.scss',
})
export class RunOverviewComponent {
  readonly run = input.required<RunContext>();
  protected readonly count = recordedCount;
}

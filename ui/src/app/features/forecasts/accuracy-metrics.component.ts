import { DecimalPipe } from '@angular/common';
import { Component, input } from '@angular/core';
import { AccuracyMetrics } from '../../core/models/forecast.models';
import { exactDecimal } from './forecast.helpers';

@Component({
  selector: 'app-accuracy-metrics',
  imports: [DecimalPipe],
  templateUrl: './accuracy-metrics.component.html',
  styleUrl: './forecast-panel.scss',
})
export class AccuracyMetricsComponent {
  readonly metrics = input.required<AccuracyMetrics>();
  protected readonly exact = exactDecimal;
}

import { Component, input } from '@angular/core';
import { displayCell } from './report-formatters';
import { ReportTable } from './report.models';

@Component({
  selector: 'app-report-table',
  template: ` <div
    class="table-wrap"
    tabindex="0"
    role="region"
    [attr.aria-label]="caption() + ', scroll horizontally if needed'"
  >
    <table class="table">
      <caption>
        {{
          caption()
        }}
      </caption>
      <thead>
        <tr>
          @for (header of table().headers; track header) {
            <th scope="col">{{ header.replaceAll('_', ' ') }}</th>
          }
        </tr>
      </thead>
      <tbody>
        @for (row of table().rows; track $index) {
          <tr>
            @for (cell of row; track $index) {
              <td>
                @if (
                  cell === 'increase' ||
                  cell === 'maintain' ||
                  cell === 'reduce' ||
                  cell === 'insufficient_data'
                ) {
                  <span [class]="'status-chip ' + cell">{{ display(cell) }}</span>
                } @else {
                  {{ display(cell, table().headers[$index]) }}
                }
              </td>
            }
          </tr>
        }
      </tbody>
    </table>
  </div>`,
  styleUrl: './reports.scss',
})
export class ReportTableComponent {
  readonly table = input.required<ReportTable>();
  readonly caption = input.required<string>();
  protected readonly display = displayCell;
}

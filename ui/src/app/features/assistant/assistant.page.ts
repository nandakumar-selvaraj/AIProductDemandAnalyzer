import {
  afterNextRender,
  Component,
  computed,
  ElementRef,
  inject,
  Injector,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { AlertComponent, SpinnerComponent } from '@coreui/angular';
import { BehaviorSubject, of, Subject, switchMap } from 'rxjs';
import {
  AssistantContext,
  AssistantRequest,
  AssistantResponse,
  ChatMessage,
} from '../../core/models/assistant.models';
import { ForecastRunItem, PagedResult } from '../../core/models/forecast.models';
import { AssistantApiService } from '../../core/services/assistant-api.service';
import { ForecastApiService } from '../../core/services/forecast-api.service';
import { validateFilters } from '../demand-analysis/demand-analysis.helpers';
import { LoadState, requestState } from '../forecasts/forecast.helpers';
import { DemoService } from '../../core/services/demo.service';
import { PublicAssistantComponent } from './public-assistant.component';
import { ChatMessageComponent } from './chat-message.component';

@Component({
  selector: 'app-assistant-page',
  imports: [FormsModule, AlertComponent, SpinnerComponent, ChatMessageComponent, PublicAssistantComponent],
  templateUrl: './assistant.page.html',
  styleUrl: './assistant.page.scss',
})
export class AssistantPage {
  protected readonly demo = inject(DemoService);
  private readonly injector = inject(Injector);
  private readonly composer = viewChild<ElementRef<HTMLTextAreaElement>>('composer');
  private readonly transcript = viewChild<ElementRef<HTMLElement>>('transcript');
  private followBottom = true;
  private readonly api = inject(AssistantApiService);
  private readonly forecastApi = inject(ForecastApiService);
  private readonly requests = new Subject<AssistantRequest | null>();
  private readonly runQueries = new BehaviorSubject(1);
  private session = crypto.randomUUID();
  private conversationId: string | null = null;
  private lastRequest: AssistantRequest | null = null;
  private nextId = 0;
  protected readonly draft = signal('');
  protected readonly runId = signal<number | null>(null);
  protected readonly productId = signal<number | null>(null);
  protected readonly storeId = signal<number | null>(null);
  protected readonly startDate = signal('');
  protected readonly endDate = signal('');
  protected readonly messages = signal<ChatMessage[]>([]);
  protected readonly errors = signal<string[]>([]);
  protected readonly notice = signal('');
  protected readonly state = signal<LoadState<AssistantResponse>>({ status: 'idle' });
  protected readonly pending = computed(() => this.state().status === 'loading');
  protected readonly runState = signal<LoadState<PagedResult<ForecastRunItem>>>({
    status: 'loading',
  });
  protected readonly runs = computed(() => {
    const state = this.runState();
    return state.status === 'success' ? state.data : null;
  });
  protected readonly starters = [
    'Which products show increasing demand?',
    'What are the highest-demand products?',
    'Explain the latest forecast.',
    'How accurate are the forecasts?',
    'Which products show decreasing demand?',
    'How are demand recommendations calculated?',
  ];
  constructor() {
    if (this.demo.readOnly) return;
    this.requests
      .pipe(
        switchMap((request) =>
          request
            ? requestState(this.api.chat(request, this.session))
            : of<LoadState<AssistantResponse>>({ status: 'idle' }),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((state) => {
        this.state.set(state);
        if (state.status === 'success') {
          const response = state.data;
          this.conversationId = response.conversation_id;
          this.messages.update((rows) =>
            [
              ...rows,
              {
                id: ++this.nextId,
                role: 'assistant' as const,
                text: response.answer,
                timestamp: response.generated_at,
                response,
              },
            ].slice(-20),
          );
          this.runId.set(response.context.forecast_run_id);
          this.productId.set(response.context.product_id);
          this.storeId.set(response.context.store_id);
          this.startDate.set(response.context.start_date ?? '');
          this.endDate.set(response.context.end_date ?? '');
          this.afterUpdate(true);
        } else if (state.status === 'error') {
          this.afterUpdate(true);
        }
      });
    this.runQueries
      .pipe(
        switchMap((page) => requestState(this.forecastApi.getRuns(page, 'completed'))),
        takeUntilDestroyed(),
      )
      .subscribe((state) => this.runState.set(state));
  }
  protected starter(question: string): void {
    if (this.pending()) return;
    this.draft.set(question);
    this.send();
  }
  protected send(): void {
    if (this.pending()) return;
    const message = this.draft().trim();
    const errors: string[] = [];
    if (!message || message.length > 1000) errors.push('Enter a question of 1–1000 characters.');
    for (const [label, id] of [
      ['Product', this.productId()],
      ['Store', this.storeId()],
      ['Run', this.runId()],
    ] as const) {
      if (id !== null && (!Number.isInteger(id) || id < 1 || id > 2147483647))
        errors.push(`${label} ID must be a positive whole number.`);
    }
    errors.push(...validateFilters(1, this.startDate(), this.endDate()));
    this.errors.set(errors);
    if (errors.length) return;
    const context: AssistantContext = {
      forecast_run_id: this.runId(),
      product_id: this.productId(),
      store_id: this.storeId(),
      start_date: this.startDate() || null,
      end_date: this.endDate() || null,
    };
    this.lastRequest = { message, conversation_id: this.conversationId, context };
    this.messages.update((rows) =>
      [
        ...rows,
        {
          id: ++this.nextId,
          role: 'user' as const,
          text: message,
          timestamp: new Date().toISOString(),
        },
      ].slice(-20),
    );
    this.draft.set('');
    this.notice.set('');
    this.requests.next(this.lastRequest);
    this.followBottom = true;
    this.afterUpdate(true);
  }
  protected keydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      this.send();
    }
  }
  protected retry(): void {
    if (this.lastRequest && !this.pending()) {
      this.notice.set('');
      this.requests.next(this.lastRequest);
    }
  }
  protected cancel(): void {
    this.requests.next(null);
    this.notice.set(
      'Stopped waiting for this answer. The server may finish processing; retry uses the original question and context.',
    );
    this.afterUpdate(true);
  }
  protected newChat(): void {
    this.requests.next(null);
    this.session = crypto.randomUUID();
    this.conversationId = null;
    this.lastRequest = null;
    this.messages.set([]);
    this.draft.set('');
    this.errors.set([]);
    this.notice.set('New conversation started.');
    this.runId.set(null);
    this.productId.set(null);
    this.storeId.set(null);
    this.startDate.set('');
    this.endDate.set('');
    this.afterUpdate(true);
  }
  protected onScroll(): void {
    const node = this.transcript()?.nativeElement;
    if (node) this.followBottom = node.scrollHeight - node.scrollTop - node.clientHeight < 80;
  }
  private afterUpdate(focus = false): void {
    afterNextRender(
      () => {
        const node = this.transcript()?.nativeElement;
        if (node && this.followBottom) node.scrollTop = node.scrollHeight;
        if (focus) this.composer()?.nativeElement.focus({ preventScroll: true });
      },
      { injector: this.injector },
    );
  }
  protected runPage(page: number): void {
    if (page > 0 && page <= (this.runs()?.total_pages ?? 0) && !this.pending())
      this.runQueries.next(page);
  }
  protected retryRuns(): void {
    this.runQueries.next(this.runQueries.value);
  }
}

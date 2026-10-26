import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { apiErrorInterceptor } from '../../core/api-error.interceptor';
import { AssistantResponse } from '../../core/models/assistant.models';
import { AssistantPage } from './assistant.page';

const response: AssistantResponse = {
  answer: '[f1] Product #10: 30.246 persisted predicted units.',
  conversation_id: '1b0f6b93-8538-4613-a919-01c32839ea11',
  intent: 'forecast',
  context: { forecast_run_id: 7, product_id: 10, store_id: null, start_date: null, end_date: null },
  sources: [
    {
      id: 'f1',
      type: 'forecast',
      label: 'Persisted prediction aggregate',
      forecast_run_id: 7,
      product_id: 10,
      store_id: null,
      start_date: '2018-01-01',
      end_date: '2018-01-30',
    },
  ],
  warnings: ['Predictions are not guaranteed demand.'],
  generated_at: '2026-10-26T10:00:00Z',
  provider_used: true,
};
describe('AI Business Assistant', () => {
  let fixture: ComponentFixture<AssistantPage>;
  let root: HTMLElement;
  let http: HttpTestingController;
  const base = environment.apiBaseUrl;
  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([apiErrorInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(AssistantPage);
    root = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
    await fixture.whenStable();
  });
  afterEach(() => {
    fixture.destroy();
    http.verify();
  });
  function runs() {
    return http.expectOne((req) => req.url === `${base}/forecasts/runs`);
  }
  function loadRuns() {
    const request = runs();
    expect(request.request.params.get('status')).toBe('completed');
    request.flush({
      page: 1,
      page_size: 10,
      total_records: 1,
      total_pages: 1,
      items: [{ id: 7, model_name: 'baseline', training_cutoff: '2017-12-31' }],
    });
    fixture.detectChanges();
  }
  function button(label: string) {
    const node = Array.from(root.querySelectorAll<HTMLButtonElement>('button')).find(
      (node) => node.textContent?.trim() === label,
    );
    expect(node, label).toBeDefined();
    return node!;
  }
  function click(label: string) {
    button(label).click();
    fixture.detectChanges();
  }
  async function input(id: string, value: string) {
    const node = root.querySelector<HTMLInputElement>(`#${id}`)!;
    node.value = value;
    node.dispatchEvent(new Event('input', { bubbles: true }));
    fixture.detectChanges();
    await fixture.whenStable();
  }
  function chat() {
    return http.expectOne(`${base}/assistant/chat`);
  }
  it('shows empty guidance, labeled context and suggested questions without invented answers', () => {
    loadRuns();
    expect(root.textContent).toContain('Start with a business question');
    expect(root.querySelectorAll('.starters button')).toHaveLength(6);
    expect(root.querySelector('label[for="assistant-question"]')).not.toBeNull();
    expect(root.querySelector('[role="log"]')?.getAttribute('aria-live')).toBe('polite');
    expect(root.querySelectorAll('.message')).toHaveLength(0);
    expect(button('Send').disabled).toBe(true);
  });
  it('submits starter questions through the regular API flow', async () => {
    loadRuns();
    click('Explain the latest forecast.');
    const pending = chat();
    expect(pending.request.body.message).toBe('Explain the latest forecast.');
    expect(root.querySelectorAll('.message.user')).toHaveLength(1);
    pending.flush(response);
  });
  it('sends the configured API request, ownership header and selected run with duplicate protection', async () => {
    loadRuns();
    const select = root.querySelector<HTMLSelectElement>('#assistant-run')!;
    select.value = Array.from(select.options).find((item) =>
      item.textContent?.includes('#7'),
    )!.value;
    select.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    await fixture.whenStable();
    await input('assistant-question', 'Forecast for product 10');
    click('Send');
    click('Send');
    const request = chat();
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({
      message: 'Forecast for product 10',
      conversation_id: null,
      context: {
        forecast_run_id: 7,
        product_id: null,
        store_id: null,
        start_date: null,
        end_date: null,
      },
    });
    expect(request.request.headers.get('X-Assistant-Session')).toMatch(/^[0-9a-f-]{36}$/);
    expect(root.textContent).toContain('Reviewing verified business evidence');
    expect(root.querySelector('[role="log"]')?.getAttribute('aria-busy')).toBe('true');
    http.expectNone(`${base}/assistant/chat`);
    request.flush(response);
    fixture.detectChanges();
    expect(root.textContent).toContain('30.246');
    expect(root.textContent).toContain('Persisted prediction aggregate');
    expect(root.textContent).toContain('Product #10');
    expect(root.textContent).toContain('Predictions are not guaranteed');
  });
  it('retains resolved conversation and context on follow-ups', async () => {
    loadRuns();
    await input('assistant-question', 'Forecast product 10');
    click('Send');
    const first = chat();
    const owner = first.request.headers.get('X-Assistant-Session');
    first.flush(response);
    fixture.detectChanges();
    await input('assistant-question', 'What about store 2?');
    click('Send');
    const next = chat();
    expect(next.request.body.conversation_id).toBe(response.conversation_id);
    expect(next.request.body.context.product_id).toBe(10);
    expect(next.request.body.context.forecast_run_id).toBe(7);
    expect(next.request.headers.get('X-Assistant-Session')).toBe(owner);
    next.flush(response);
  });
  it('renders provider errors and retries the original snapshot without duplicating user messages', async () => {
    loadRuns();
    await input('assistant-question', 'Forecast product 10');
    click('Send');
    const first = chat();
    const body = first.request.body;
    first.flush(
      { error: { code: 'ai_timeout', message: 'The AI provider timed out.' } },
      { status: 504, statusText: 'Timeout' },
    );
    fixture.detectChanges();
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('AI provider timed out');
    await input('assistant-product', '20');
    click('Retry answer');
    const retry = chat();
    expect(retry.request.body).toEqual(body);
    retry.flush(response);
    fixture.detectChanges();
    expect(root.querySelectorAll('.message.user')).toHaveLength(1);
    expect(root.querySelectorAll('.message.assistant')).toHaveLength(1);
  });
  it('cancels a pending request and prevents its response from reaching the conversation', async () => {
    loadRuns();
    await input('assistant-question', 'Forecast');
    click('Send');
    const pending = chat();
    click('Cancel request');
    expect(pending.cancelled).toBe(true);
    expect(root.textContent).toContain('Stopped waiting');
    expect(root.querySelectorAll('.message.assistant')).toHaveLength(0);
  });
  it('New Chat cancels pending work, clears context/history and rotates ownership', async () => {
    loadRuns();
    await input('assistant-question', 'Forecast');
    click('Send');
    const old = chat();
    const owner = old.request.headers.get('X-Assistant-Session');
    click('New Chat');
    expect(old.cancelled).toBe(true);
    expect(root.querySelectorAll('.message')).toHaveLength(0);
    await input('assistant-question', 'How does forecasting work?');
    click('Send');
    const fresh = chat();
    expect(fresh.request.body.conversation_id).toBeNull();
    expect(fresh.request.body.context.forecast_run_id).toBeNull();
    expect(fresh.request.headers.get('X-Assistant-Session')).not.toBe(owner);
    fresh.flush(response);
  });
  it('supports Enter submission, Shift+Enter newline and IME composition', async () => {
    loadRuns();
    await input('assistant-question', 'Forecast');
    const textarea = root.querySelector('textarea')!;
    const newline = new KeyboardEvent('keydown', {
      key: 'Enter',
      shiftKey: true,
      bubbles: true,
      cancelable: true,
    });
    textarea.dispatchEvent(newline);
    expect(newline.defaultPrevented).toBe(false);
    http.expectNone(`${base}/assistant/chat`);
    textarea.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Enter', isComposing: true, bubbles: true }),
    );
    http.expectNone(`${base}/assistant/chat`);
    const enter = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true });
    textarea.dispatchEvent(enter);
    fixture.detectChanges();
    expect(enter.defaultPrevented).toBe(true);
    chat().flush(response);
  });
  it('validates IDs and date ranges without requesting AI', async () => {
    loadRuns();
    await input('assistant-question', 'Sales');
    await input('assistant-product', '0');
    click('Send');
    expect(root.textContent).toContain('positive whole number');
    http.expectNone(`${base}/assistant/chat`);
    await input('assistant-product', '1');
    await input('assistant-start', '2023-01-01');
    await input('assistant-end', '2024-01-01');
    click('Send');
    expect(root.textContent).toContain('at most 365');
    http.expectNone(`${base}/assistant/chat`);
  });
  it('retries run catalog errors without blocking general questions and cleans up on teardown', async () => {
    runs().flush({ detail: 'Runs unavailable' }, { status: 503, statusText: 'Unavailable' });
    fixture.detectChanges();
    expect(root.textContent).toContain('Runs unavailable');
    click('Retry run choices');
    const pendingRuns = runs();
    await input('assistant-question', 'How does forecasting work?');
    click('Send');
    const pendingChat = chat();
    fixture.destroy();
    expect(pendingRuns.cancelled).toBe(true);
    expect(pendingChat.cancelled).toBe(true);
  });
  it('renders untrusted model/data text as plain text without HTML execution', async () => {
    loadRuns();
    await input('assistant-question', '<script>unsafe</script>');
    click('Send');
    chat().flush({
      ...response,
      answer: '<img src=x onerror=alert(1)>',
      warnings: ['<script>evil</script>'],
    });
    fixture.detectChanges();
    expect(root.textContent).toContain('<img src=x');
    expect(root.querySelector('img')).toBeNull();
    expect(root.querySelector('script')).toBeNull();
  });
  it('announces missing completed runs without blocking historical questions', () => {
    runs().flush({ page: 1, page_size: 10, total_records: 0, total_pages: 0, items: [] });
    fixture.detectChanges();
    expect(root.textContent).toContain('No completed forecast run is available');
    expect(root.textContent).toContain('General and historical questions remain available');
  });
  it('keeps evidence from each run separate when run selection changes', async () => {
    loadRuns();
    await input('assistant-question', 'Forecast');
    click('Send');
    chat().flush(response);
    fixture.detectChanges();
    const select = root.querySelector<HTMLSelectElement>('#assistant-run')!;
    select.value = select.options[0].value;
    select.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    await fixture.whenStable();
    await input('assistant-question', 'Forecast run 8');
    click('Send');
    const next = chat();
    expect(next.request.body.context.forecast_run_id).toBeNull();
    next.flush({
      ...response,
      answer: 'Run 8 answer.',
      context: { ...response.context, forecast_run_id: 8 },
      sources: response.sources.map((source) => ({ ...source, forecast_run_id: 8 })),
    });
    fixture.detectChanges();
    const answers = root.querySelectorAll('.message.assistant');
    expect(answers[0].textContent).toContain('Run #7');
    expect(answers[1].textContent).toContain('Run #8');
  });
  it('returns focus to the input after response and New Chat', async () => {
    loadRuns();
    await input('assistant-question', 'Forecast');
    click('Send');
    chat().flush(response);
    fixture.detectChanges();
    await fixture.whenStable();
    click('New Chat');
    await fixture.whenStable();
    expect(document.activeElement?.id).toBe('assistant-question');
  });
  it('formats paragraphs, lists and bold safely and copies plain response text', async () => {
    loadRuns();
    const copied = vi.fn().mockResolvedValue(undefined);
    const original = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: copied },
    });
    try {
      await input('assistant-question', 'Explain forecast');
      click('Send');
      const answer = '**Forecast**\n- Verified evidence\n- <img src=x onerror=bad()> is text';
      chat().flush({ ...response, answer });
      fixture.detectChanges();
      expect(root.querySelector('.message-text strong')?.textContent).toBe('Forecast');
      expect(root.querySelectorAll('.message-text li')).toHaveLength(2);
      expect(root.querySelector('.message-text img')).toBeNull();
      click('Copy response');
      await fixture.whenStable();
      fixture.detectChanges();
      expect(copied).toHaveBeenCalledWith(answer);
      expect(root.textContent).toContain('Response copied');
    } finally {
      if (original) Object.defineProperty(navigator, 'clipboard', original);
      else Reflect.deleteProperty(navigator, 'clipboard');
    }
  });
});

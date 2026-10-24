import {
  HttpClient,
  HttpErrorResponse,
  HttpRequest,
  provideHttpClient,
  withInterceptors,
} from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
  TestRequest,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { throwError } from 'rxjs';
import { ApiRequestError, apiErrorInterceptor } from './api-error.interceptor';

interface ErrorCase {
  name: string;
  body: Parameters<TestRequest['flush']>[0];
  status: number;
  message: string;
  code: string;
}

const cases: ErrorCase[] = [
  {
    name: 'FastAPI string detail',
    body: { detail: 'Product not found' },
    status: 404,
    message: 'Product not found',
    code: 'request_failed',
  },
  {
    name: 'structured detail',
    body: { detail: { code: 'run_not_ready', message: 'Forecast is not ready' } },
    status: 409,
    message: 'Forecast is not ready',
    code: 'run_not_ready',
  },
  {
    name: 'multiple validation issues',
    body: {
      detail: [
        { loc: ['query', 'page'], msg: 'Must be greater than 0', input: 'private input' },
        { loc: ['body', 'items', 0, 'quantity'], msg: 'Field required' },
      ],
    },
    status: 422,
    message: 'query.page: Must be greater than 0; body.items.0.quantity: Field required',
    code: 'validation_error',
  },
  {
    name: 'existing custom envelope',
    body: { error: { code: 'database_error', message: 'Products unavailable' } },
    status: 503,
    message: 'Products unavailable',
    code: 'database_error',
  },
  {
    name: 'custom validation envelope',
    body: {
      error: {
        code: 'request_validation_error',
        message: 'Request validation failed',
        details: [{ loc: ['query', 'page'], msg: 'Invalid integer' }],
      },
    },
    status: 422,
    message: 'Request validation failed: query.page: Invalid integer',
    code: 'request_validation_error',
  },
  {
    name: 'plain message envelope',
    body: { message: 'Service warming up' },
    status: 503,
    message: 'Service warming up',
    code: 'request_failed',
  },
  {
    name: 'null response',
    body: null,
    status: 500,
    message: 'The request failed with status 500.',
    code: 'request_failed',
  },
  {
    name: 'HTML gateway response',
    body: '<html>Bad gateway</html>',
    status: 502,
    message: 'The request failed with status 502.',
    code: 'request_failed',
  },
  {
    name: 'unexpected array response',
    body: [1, 2],
    status: 500,
    message: 'The request failed with status 500.',
    code: 'request_failed',
  },
  {
    name: 'malformed message fields',
    body: { error: { message: 42, code: [] }, detail: [{ loc: ['body'], msg: {} }] },
    status: 422,
    message: 'The request failed with status 422.',
    code: 'validation_error',
  },
  {
    name: 'empty message',
    body: { detail: { message: '   ' } },
    status: 400,
    message: 'The request failed with status 400.',
    code: 'request_failed',
  },
];

describe('apiErrorInterceptor', () => {
  let client: HttpClient;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([apiErrorInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    client = TestBed.inject(HttpClient);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it.each(cases)('normalizes $name', ({ body, status, message, code }) => {
    let received: unknown;
    client.get('/test').subscribe({
      error: (error: unknown) => {
        received = error;
      },
    });
    http.expectOne('/test').flush(body, { status, statusText: 'Request failed' });
    expect(received).toBeInstanceOf(ApiRequestError);
    expect(received).toMatchObject({ message, status, code });
    expect((received as Error).message).not.toContain('private input');
  });

  it('normalizes a network failure without exposing the ProgressEvent', () => {
    let received: unknown;
    client.get('/test').subscribe({
      error: (error: unknown) => {
        received = error;
      },
    });
    http.expectOne('/test').error(new ProgressEvent('error'));
    expect(received).toBeInstanceOf(ApiRequestError);
    expect(received).toMatchObject({ status: 0, code: 'network_error' });
    expect((received as Error).message).toContain('The API could not be reached.');
  });

  it('leaves successful response bodies intact', () => {
    let result: unknown;
    client.get('/test').subscribe((body) => {
      result = body;
    });
    http.expectOne('/test').flush({ items: [1] });
    expect(result).toEqual({ items: [1] });
  });

  it('preserves non-HTTP errors from another interceptor', () => {
    const original = new Error('Unexpected application failure');
    let received: unknown;
    apiErrorInterceptor(new HttpRequest('GET', '/test'), () =>
      throwError(() => original),
    ).subscribe({
      error: (error: unknown) => {
        received = error;
      },
    });
    expect(received).toBe(original);
  });

  it('normalizes a JSON parsing failure even when the HTTP status was successful', () => {
    const failure = new HttpErrorResponse({
      status: 200,
      error: { error: new SyntaxError('Invalid JSON'), text: '<html>Unexpected page</html>' },
    });
    let received: unknown;
    apiErrorInterceptor(new HttpRequest('GET', '/test'), () => throwError(() => failure)).subscribe(
      {
        error: (error: unknown) => {
          received = error;
        },
      },
    );
    expect(received).toMatchObject({
      status: 200,
      code: 'invalid_response',
      message: 'The API returned an unreadable response. Please try again.',
    });
  });
});

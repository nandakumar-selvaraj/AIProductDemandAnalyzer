export interface AssistantContext {
  forecast_run_id: number | null;
  product_id: number | null;
  store_id: number | null;
  start_date: string | null;
  end_date: string | null;
  backtest_cutoff?: string | null;
  backtest_horizon_days?: number;
}
export interface AssistantRequest {
  message: string;
  conversation_id: string | null;
  context: AssistantContext;
}
export interface AssistantSource {
  id: string;
  type: 'historical' | 'forecast' | 'recommendation' | 'evaluation' | 'backtest' | 'application';
  label: string;
  forecast_run_id: number | null;
  product_id: number | null;
  store_id: number | null;
  start_date: string | null;
  end_date: string | null;
}
export interface AssistantResponse {
  answer: string;
  conversation_id: string;
  intent: string;
  context: AssistantContext;
  sources: AssistantSource[];
  warnings: string[];
  generated_at: string;
  provider_used: boolean;
}

export interface ChatMessage {
  id: number;
  role: 'user' | 'assistant';
  text: string;
  timestamp?: string;
  response?: AssistantResponse;
}

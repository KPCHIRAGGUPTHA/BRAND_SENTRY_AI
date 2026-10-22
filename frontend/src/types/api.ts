export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
}

export interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  lastChecked: string | null;
}

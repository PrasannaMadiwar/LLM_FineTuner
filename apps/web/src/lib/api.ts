import {
  DatasetAnalyzeRequest,
  DatasetAnalyzeResponse,
  DatasetInfoResponse,
  DatasetNormalizeRequest,
  DatasetNormalizeResponse,
  DatasetRowPreview,
  DatasetSearchResult,
  HealthResponse,
  ModelListResponse,
  ReadinessResponse,
  TemplateListResponse,
  TokenResponse,
  TrainingArtifactListResponse,
  TrainingCheckpointResponse,
  TrainingJob,
  TrainingJobCreateRequest,
  TrainingJobEventListResponse,
  TrainingJobListResponse,
  TrainingJobResponse,
  TrainingMetricListResponse,
  User,
} from './types';

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:18000/api/v1';

class ApiClient {
  private getAuthToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('token');
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getAuthToken();
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    if (
      options.body &&
      !(options.body instanceof FormData) &&
      !headers['Content-Type']
    ) {
      headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const errorData = await response.json();
        if (typeof errorData.detail === 'string') {
          errorMessage = errorData.detail;
        } else if (Array.isArray(errorData.detail)) {
          errorMessage = errorData.detail
            .map((err: any) => `${err.loc?.join('.')}: ${err.msg}`)
            .join(', ');
        } else if (errorData.detail?.message) {
          errorMessage = errorData.detail.message;
        }
      } catch {
        // Fallback to response status text
      }
      throw new Error(errorMessage);
    }

    if (response.status === 204) {
      return {} as T;
    }

    return response.json();
  }

  // --- Auth APIs ---
  async register(data: { email: string; password: string; full_name?: string }): Promise<User> {
    return this.request<User>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async login(email: string, password: string): Promise<TokenResponse> {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData,
    });

    if (!response.ok) {
      let errorMessage = 'Login failed. Please check your credentials.';
      try {
        const err = await response.json();
        if (err.detail) errorMessage = err.detail;
      } catch {}
      throw new Error(errorMessage);
    }

    const tokenData = (await response.json()) as TokenResponse;
    if (typeof window !== 'undefined') {
      localStorage.setItem('token', tokenData.access_token);
    }
    return tokenData;
  }

  async getMe(): Promise<User> {
    return this.request<User>('/auth/me');
  }

  logout(): void {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('token');
    }
  }

  // --- Dataset APIs ---
  async searchDatasets(query: string): Promise<DatasetSearchResult[]> {
    const res = await this.request<any>(
      `/datasets/search?query=${encodeURIComponent(query)}`
    );
    const items = res?.results || (Array.isArray(res) ? res : []);
    return items.map((item: any) => ({
      id: item.dataset_id || item.id || item.name,
      name: item.name || item.dataset_id,
      description: item.description,
      downloads: item.downloads,
      likes: item.likes,
      tags: item.tags || [item.source || 'Hugging Face'],
    }));
  }

  async getDatasetInfo(datasetId: string): Promise<DatasetInfoResponse> {
    return this.request<DatasetInfoResponse>(
      `/datasets/info/${encodeURIComponent(datasetId)}`
    );
  }

  async previewDataset(
    datasetId: string,
    split = 'train',
    limit = 5
  ): Promise<DatasetRowPreview[]> {
    return this.request<DatasetRowPreview[]>(
      `/datasets/preview/${encodeURIComponent(datasetId)}?split=${split}&limit=${limit}`
    );
  }

  async analyzeDataset(
    data: DatasetAnalyzeRequest
  ): Promise<DatasetAnalyzeResponse> {
    return this.request<DatasetAnalyzeResponse>('/datasets/analyze', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async normalizeDataset(
    data: any
  ): Promise<DatasetNormalizeResponse> {
    const promptField = data.field_mapping?.prompt_field || data.mapping?.user?.[0] || 'instruction';
    const responseField = data.field_mapping?.response_field || data.mapping?.assistant || 'output';
    const payload = {
      dataset_id: data.dataset_id,
      source: data.source || 'hugging_face',
      split: data.split || 'train',
      mapping: data.mapping || {
        user: [promptField],
        assistant: responseField,
      },
    };
    return this.request<DatasetNormalizeResponse>('/datasets/normalize', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // --- Training APIs ---
  async getModels(): Promise<ModelListResponse> {
    return this.request<ModelListResponse>('/training/models');
  }

  async getTemplates(): Promise<TemplateListResponse> {
    return this.request<TemplateListResponse>('/training/templates');
  }

  async getJobs(): Promise<TrainingJobListResponse> {
    return this.request<TrainingJobListResponse>('/training/jobs');
  }

  async getJob(jobId: string): Promise<TrainingJobResponse> {
    return this.request<TrainingJobResponse>(`/training/jobs/${jobId}`);
  }

  async createJob(
    data: TrainingJobCreateRequest
  ): Promise<TrainingJobResponse> {
    return this.request<TrainingJobResponse>('/training/jobs', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async queueJob(jobId: string): Promise<TrainingJobResponse> {
    return this.request<TrainingJobResponse>(
      `/training/jobs/${jobId}/queue`,
      { method: 'POST' }
    );
  }

  async cancelJob(jobId: string): Promise<TrainingJobResponse> {
    return this.request<TrainingJobResponse>(
      `/training/jobs/${jobId}/cancel`,
      { method: 'POST' }
    );
  }

  async resumeJob(
    jobId: string,
    checkpoint?: string
  ): Promise<TrainingJobResponse> {
    return this.request<TrainingJobResponse>(
      `/training/jobs/${jobId}/resume`,
      {
        method: 'POST',
        body: JSON.stringify({ resume_from_checkpoint: checkpoint }),
      }
    );
  }

  async getJobEvents(jobId: string): Promise<TrainingJobEventListResponse> {
    return this.request<TrainingJobEventListResponse>(
      `/training/jobs/${jobId}/events`
    );
  }

  async getJobMetrics(jobId: string): Promise<TrainingMetricListResponse> {
    return this.request<TrainingMetricListResponse>(
      `/training/jobs/${jobId}/metrics`
    );
  }

  async getLatestCheckpoint(
    jobId: string
  ): Promise<TrainingCheckpointResponse> {
    return this.request<TrainingCheckpointResponse>(
      `/training/jobs/${jobId}/checkpoints/latest`
    );
  }

  async getJobArtifacts(
    jobId: string
  ): Promise<TrainingArtifactListResponse> {
    return this.request<TrainingArtifactListResponse>(
      `/training/jobs/${jobId}/artifacts`
    );
  }

  // --- GPU APIs ---
  async getGpus(): Promise<any[]> {
    return this.request<any[]>('/gpu');
  }

  // --- Health APIs ---
  async getHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health');
  }

  async getReady(): Promise<ReadinessResponse> {
    return this.request<ReadinessResponse>('/ready');
  }
}

export const api = new ApiClient();

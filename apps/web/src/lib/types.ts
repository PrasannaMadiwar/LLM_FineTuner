export interface User {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  full_name?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface DatasetSearchResult {
  id: string;
  name: string;
  description?: string;
  downloads?: number;
  likes?: number;
  tags?: string[];
}

export interface DatasetInfoResponse {
  id: string;
  description?: string;
  citation?: string;
  homepage?: string;
  license?: string;
  features?: Record<string, any>;
  splits?: Record<string, { num_bytes: number; num_examples: number }>;
}

export interface DatasetRowPreview {
  [key: string]: any;
}

export interface DatasetAnalyzeRequest {
  dataset_id: string;
  rows?: Record<string, any>[];
}

export interface DatasetAnalyzeResponse {
  dataset_id: string;
  detected_schema?: Record<string, string>;
  suggested_prompt_field?: string;
  suggested_response_field?: string;
  quality_score?: number;
  summary?: string;
}

export interface DatasetNormalizeRequest {
  dataset_id: string;
  field_mapping: {
    prompt_field: string;
    response_field: string;
    system_field?: string;
  };
  output_filename?: string;
}

export interface DatasetNormalizeResponse {
  dataset_id: string;
  artifact_path?: string;
  normalized_artifact_path?: string;
  num_examples?: number;
  size_bytes?: number;
  validation_report?: any;
  normalized_rows?: any[];
}

export interface ModelDefinition {
  model_key: string;
  model_id: string;
  display_name: string;
  huggingface_repo: string;
  template: string;
  default_config: Record<string, any>;
  lora_supported: boolean;
  quantization: string;
  sequence_length: number;
  gpu_requirements: {
    recommended: string;
    minimum_vram_gb: number;
  };
}

export interface ModelListResponse {
  models: ModelDefinition[];
}

export interface TemplateListResponse {
  templates: string[];
}

export interface TrainingConfig {
  model_key: string;
  dataset_id: string;
  normalized_dataset_path: string;
  output_dir?: string;
  epochs?: number;
  learning_rate?: number;
  batch_size?: number;
  gradient_accumulation_steps?: number;
  lora_rank?: number;
  lora_alpha?: number;
  lora_dropout?: number;
  max_sequence_length?: number;
  load_in_4bit?: boolean;
  extra?: Record<string, any>;
}

export type TrainingJobStatus =
  | 'created'
  | 'queued'
  | 'preparing'
  | 'waiting_gpu'
  | 'gpu_ready'
  | 'uploading'
  | 'starting'
  | 'training'
  | 'checkpointing'
  | 'collecting_artifacts'
  | 'completed'
  | 'failed'
  | 'cancelled';

export interface TrainingJob {
  id: string;
  user_id: string;
  project_id?: string;
  status: TrainingJobStatus;
  model_key: string;
  model_id: string;
  template_name: string;
  training_config: TrainingConfig;
  dataset_id: string;
  normalized_dataset_path: string;
  gpu_instance_id?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
  queued_at?: string;
  started_at?: string;
  completed_at?: string;
}

export interface TrainingJobCreateRequest {
  project_id?: string;
  config: TrainingConfig;
}

export interface TrainingJobResponse {
  job: TrainingJob;
}

export interface TrainingJobListResponse {
  jobs: TrainingJob[];
}

export interface TrainingJobEvent {
  id: string;
  training_job_id: string;
  user_id: string;
  from_status?: TrainingJobStatus;
  to_status: TrainingJobStatus;
  message: string;
  metadata: Record<string, any>;
  created_at: string;
}

export interface TrainingJobEventListResponse {
  events: TrainingJobEvent[];
}

export interface TrainingMetric {
  id: string;
  training_job_id: string;
  timestamp: string;
  epoch?: number;
  global_step?: number;
  loss?: number;
  learning_rate?: number;
  tokens_per_second?: number;
  samples_per_second?: number;
  gpu_utilization?: number;
  gpu_memory?: Record<string, any>;
  cpu_usage?: number;
  ram_usage?: Record<string, any>;
  eta_seconds?: number;
}

export interface TrainingMetricListResponse {
  metrics: TrainingMetric[];
}

export interface TrainingCheckpoint {
  id: string;
  training_job_id: string;
  epoch?: number;
  global_step?: number;
  path: string;
  is_latest: boolean;
  metadata: Record<string, any>;
  created_at: string;
}

export interface TrainingCheckpointResponse {
  checkpoint: TrainingCheckpoint | null;
}

export interface TrainingArtifact {
  id: string;
  training_job_id: string;
  user_id: string;
  project_id?: string;
  artifact_type: string;
  path: string;
  filename: string;
  size_bytes: number;
  checksum?: string;
  metadata: Record<string, any>;
  created_at: string;
}

export interface TrainingArtifactListResponse {
  artifacts: TrainingArtifact[];
}

export interface HealthResponse {
  status: string;
}

export interface ReadinessResponse {
  database: string;
  redis: string;
}

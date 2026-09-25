export type UserRole = 'CITIZEN' | 'OFFICER' | 'ADMIN';

export type ComplaintPriority = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

export type ComplaintStatus =
  | 'SUBMITTED'
  | 'UNDER_REVIEW'
  | 'ASSIGNED'
  | 'IN_PROGRESS'
  | 'RESOLVED'
  | 'REJECTED'
  | 'REOPENED'
  | 'OVERDUE';

export type ComplaintSource = 'WEB_TEXT' | 'WEB_VOICE' | 'AUDIO_UPLOAD' | 'TELEPHONY_IVR';

export interface User {
  id: number;
  public_id: string;
  full_name: string;
  email: string;
  phone?: string;
  role: UserRole;
  department_id?: number;
  is_active: boolean;
  created_at: string;
}

export interface Department {
  id: number;
  code: string;
  name: string;
  description?: string;
  is_active: boolean;
  created_at: string;
}

export interface ComplaintHistory {
  id: number;
  complaint_id: number;
  previous_status?: string;
  new_status: string;
  note?: string;
  changed_by_name?: string;
  created_at: string;
}

export interface Complaint {
  id: number;
  complaint_number: string;
  citizen_id?: number;
  citizen_name?: string;
  department_id?: number;
  department_name?: string;
  assigned_officer_id?: number;
  assigned_officer_name?: string;
  title: string;
  description: string;
  language: string;
  category: string;
  location?: string;
  latitude?: string;
  longitude?: string;
  priority: ComplaintPriority;
  status: ComplaintStatus;
  source: ComplaintSource;
  ai_metadata?: Record<string, any>;
  citizen_confirmed: boolean;
  audio_file_path?: string;
  created_at: string;
  updated_at: string;
  resolved_at?: string;
  due_at?: string;
  history?: ComplaintHistory[];
  department?: Department;
}

export interface AnalysisResult {
  original_text: string;
  transcription?: string;
  detected_language: string;
  normalized_text: string;
  category: string;
  suggested_department: string;
  extracted_location?: string;
  latitude?: string;
  longitude?: string;
  priority: ComplaintPriority;
  summary: string;
  analysis_method: string;
  requires_review: boolean;
  warnings: string[];
  metadata?: Record<string, any>;
}

export interface CategoryStat {
  category: string;
  count: number;
}

export interface DepartmentStat {
  department_id: number;
  department_name: string;
  total: number;
  pending: number;
  in_progress: number;
  resolved: number;
}

export interface PriorityStat {
  priority: string;
  count: number;
}

export interface AdminStats {
  total_complaints: number;
  submitted: number;
  under_review: number;
  assigned: number;
  in_progress: number;
  resolved: number;
  rejected: number;
  reopened: number;
  overdue: number;
  emergency_critical: number;
  categories: CategoryStat[];
  departments: DepartmentStat[];
  priorities: PriorityStat[];
  recent_activity: Array<{
    id: number;
    complaint_id: number;
    complaint_number: string;
    new_status: string;
    note: string;
    changed_by: string;
    created_at: string;
  }>;
}

export interface NotificationItem {
  id: number;
  user_id: number;
  complaint_id?: number;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id: number;
  public_id: string;
  full_name: string;
  email: string;
  role: UserRole;
  department_id?: number;
}

export interface ActionSuggestion {
  label: string;
  action_type: 'SUBMIT_DRAFT' | 'TRACK_COMPLAINT' | 'CALL_HELPLINE' | 'QUICK_PROMPT';
  payload: Record<string, any>;
  icon?: string;
}

export interface ComplaintDraft {
  title: string;
  description: string;
  category: string;
  suggested_department: string;
  extracted_location?: string;
  latitude?: string;
  longitude?: string;
  priority: ComplaintPriority;
  summary: string;
}

export interface ComplaintCollectionState {
  session_id: string;
  stage: 'GREETING' | 'COLLECTING' | 'CONFIRMATION_PENDING' | 'REGISTERED' | string;
  language: string;
  fields: {
    problem_description?: string | null;
    exact_location?: string | null;
    street_road_name?: string | null;
    district_area?: string | null;
    landmark?: string | null;
    date_and_time?: string | null;
    frequency?: string | null;
    current_status?: string | null;
    additional_details?: string | null;
    citizen_details?: string | null;
    [key: string]: string | null | undefined;
  };
  current_field_prompted?: string | null;
  completed_fields_count: number;
  total_fields: number;
  completion_percentage: number;
  created_complaint_number?: string | null;
  created_complaint_id?: number | null;
}

export interface AssistantResponse {
  reply_text: string;
  spoken_text: string;
  detected_language: string;
  intent: string;
  draft_complaint?: ComplaintDraft;
  status_info?: Record<string, any>;
  collection_state?: ComplaintCollectionState;
  suggested_actions: ActionSuggestion[];
  session_id?: string;
  metadata?: Record<string, any>;
  transcription?: string;
  speech_status?: string;
  duration_seconds?: number;
}

export interface AssistantMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  spoken_text?: string;
  detected_language?: string;
  intent?: string;
  draft_complaint?: ComplaintDraft;
  status_info?: Record<string, any>;
  collection_state?: ComplaintCollectionState;
  suggested_actions?: ActionSuggestion[];
  timestamp: Date;
  isAudio?: boolean;
}


export interface SuggestionsResponse {
  sample_questions: Array<{ label: string; query: string }>;
  emergency_helplines: Array<{ service: string; number: string; desc: string }>;
  quick_categories: Array<{ name: string; icon: string; sample: string }>;
}

export interface IVRCallInitiateResponse {
  call_sid: string;
  caller_phone: string;
  toll_free_number: string;
  greeting_tamil: string;
  greeting_english: string;
  prompt_tamil: string;
  prompt_english: string;
  combined_spoken_prompt: string;
}

export interface AcousticMetrics {
  duration_seconds: number;
  rms_energy_db: number;
  peak_amplitude: number;
  speech_activity_ratio: number;
  estimated_snr_db: number;
  noise_profile: string;
  speech_tempo: string;
  file_size_bytes: number;
}

export interface SecondaryCategoryPrediction {
  category: string;
  confidence: number;
}

export interface AudioPredictionResponse {
  success: boolean;
  transcription: string;
  predicted_category: string;
  category_confidence: number;
  suggested_department: string;
  department_confidence: number;
  predicted_priority: string;
  urgency_score: number;
  distress_level: string;
  predicted_language: string;
  language_confidence: number;
  extracted_location?: string;
  latitude?: string;
  longitude?: string;
  summary: string;
  acoustic_metrics: AcousticMetrics;
  secondary_categories: SecondaryCategoryPrediction[];
  speech_engine_info?: Record<string, any>;
}

export interface IVRProcessSpeechResponse {
  call_sid: string;
  caller_phone: string;
  transcription: string;
  detected_language: string;
  category: string;
  suggested_department: string;
  department_id?: number;
  extracted_location?: string;
  latitude?: string;
  longitude?: string;
  priority: string;
  complaint_number: string;
  complaint_id: number;
  confirmation_spoken_tamil: string;
  confirmation_spoken_english: string;
  combined_spoken_confirmation: string;
  sms_text: string;
  status: string;
  audio_prediction?: Record<string, any>;
}

export interface IVRCallDialogueResponse {
  call_sid: string;
  dialogue_turn: number;
  ai_spoken_reply: string;
  ai_spoken_reply_tamil: string;
  ai_spoken_reply_english: string;
  detected_language: string;
  language_confidence?: number;
  latitude?: string;
  longitude?: string;
  osm_location_name?: string;
  intent: 'GATHER_MORE_INFO' | 'CONFIRMATION_PENDING' | 'READY_TO_REGISTER' | 'CONFIRMED' | 'GENERAL_HELP';
  extracted_category?: string;
  extracted_location?: string;
  suggested_department?: string;
  is_confirmation_pending?: boolean;
  is_completed: boolean;
  collection_state?: Record<string, any>;
  summary?: string;
  complaint_id?: number;
  complaint_number?: string;
  sms_sent: boolean;
}
export interface InboundSMSResponse {
  sms_sid: string;
  sender_phone: string;
  raw_message: string;
  detected_language: string;
  extracted_category: string;
  extracted_location?: string;
  assigned_department: string;
  complaint_id: number;
  complaint_number: string;
  reply_sms_tamil: string;
  reply_sms_english: string;
  reply_sms_dispatched: string;
  status: string;
}

export interface ManualSMSResponse {
  success: boolean;
  sms_sid: string;
  to_phone: string;
  message: string;
  mode: string;
  status: string;
}

export interface TelephonyLogItem {
  id: string;
  timestamp: string;
  event_type: string;
  direction: string;
  phone: string;
  status: string;
  details: Record<string, any>;
}

export interface TelephonyLogsResponse {
  total: number;
  logs: TelephonyLogItem[];
}

export interface ConversationalAnalysis {
  category: string;
  location: string;
  problem: string;
  duration?: string;
  affected_scope?: string;
  severity?: string;
  priority?: string;
  department?: string;
}

export interface IVRConversationalSessionResponse {
  session_id: string;
  transcription: string;
  original_transcription?: string;
  normalized_transcription?: string;
  language: string;
  detected_language?: string;
  analysis?: ConversationalAnalysis;
  response_text: string;
  ai_text?: string;
  ai_spoken?: string;
  audio_base64?: string | null;
  conversation_state:
    | 'AI_SPEAKING'
    | 'WAITING_FOR_CITIZEN'
    | 'CITIZEN_SPEAKING'
    | 'PROCESSING_AUDIO'
    | 'TRANSCRIBING'
    | 'DETECTING_LANGUAGE'
    | 'UNDERSTANDING'
    | 'GENERATING_RESPONSE'
    | 'CONFIRMED'
    | 'CANCELLED'
    | 'CALL_ENDED'
    | 'ERROR'
    | string;
  state?: string;
  should_continue: boolean;
  complaint_id?: number | null;
  complaint_number?: string | null;
  context?: Record<string, any>;
  confirmation_required?: boolean;
  conversation_complete?: boolean;
  speech_recognition_available?: boolean;
  error?: string | null;
}

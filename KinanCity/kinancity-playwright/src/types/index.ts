export type WorkflowStatus =
  | 'QUEUED'
  | 'NAVIGATING'
  | 'FILLING_CREDENTIALS'
  | 'CAPTCHA_PENDING'
  | 'MANUAL_VERIFICATION_REQUIRED'
  | 'SUBMITTING'
  | 'AWAITING_EMAIL_VERIFICATION'
  | 'ACTIVATING'
  | 'COMPLETED'
  | 'FAILED';

export interface AccountCredentials {
  username: string;
  password?: string;
  email: string;
}

export interface AccountState {
  username: string;
  email: string;
  status: WorkflowStatus;
  retries: number;
  maxRetries: number;
  lastError?: string;
  activationUrl?: string;
  createdAt: number;
  updatedAt: number;
  completedAt?: number;
}

export enum CaptchaType {
  RECAPTCHA_V2 = 'reCAPTCHA_v2',
  RECAPTCHA_V3 = 'reCAPTCHA_v3',
  HCAPTCHA = 'hCaptcha',
  TURNSTILE = 'Cloudflare_Turnstile',
  UNKNOWN = 'UNKNOWN',
  NONE = 'NONE',
}

export interface ChallengeDetectionResult {
  detected: boolean;
  type: CaptchaType;
  isActive: boolean;
  frameUrl?: string;
  siteKey?: string;
}

export interface VerificationMessage {
  id: string;
  sender: string;
  recipient: string;
  subject: string;
  timestamp: number;
  activationUrl?: string;
  verificationCode?: string;
  rawBody?: string;
}

export interface WorkflowResult {
  success: boolean;
  username: string;
  finalStatus: WorkflowStatus;
  durationMs: number;
  diagnosticScreenshot?: string;
  error?: string;
}

/**
 * TypeScript interfaces matching the 7-entity database schema from Level 4 Data Models
 * These interfaces ensure type safety and alignment with the Django backend
 */

// Base interface for all entities with common fields
export interface BaseEntity {
  id: string; // UUID
  is_active: boolean;
  created_at: string; // ISO date string
  updated_at: string; // ISO date string
  deleted_at?: string | null; // ISO date string for soft deletes
}

// Role entity - RBAC roles (Admin, Publisher, Developer, Reviewer)
export interface Role extends BaseEntity {
  name: 'Admin' | 'Publisher' | 'Developer' | 'Reviewer';
  description: string;
  permissions: Record<string, any>; // JSONB field for flexible permissions
}

// User entity - All system users with Auth0 integration
export interface User extends BaseEntity {
  auth0_id: string; // Auth0 subject identifier (unique)
  email: string; // Unique email address
  username: string;
  first_name: string;
  last_name: string;
  role_id: string; // Foreign key to Role
  role?: Role; // Populated role object
  profile_data: Record<string, any>; // JSONB for additional user metadata
  last_login?: string | null; // ISO date string
}

// Resource entity - Quranic content (text, audio, translations, tafsir)
export interface Resource extends BaseEntity {
  title: string;
  description: string;
  resource_type: 'text' | 'audio' | 'translation' | 'tafsir';
  language: string; // ISO language codes (ar, en, ur, etc.)
  version: string;
  checksum: string; // SHA-256 hash for content integrity verification
  publisher_id: string; // Foreign key to User with Publisher role
  publisher?: User; // Populated publisher object
  metadata: Record<string, any>; // JSONB for resource-specific properties
  published_at?: string | null; // ISO date string
}

// License entity - Legal terms and conditions governing resource usage
export interface License extends BaseEntity {
  resource_id: string; // Foreign key to Resource
  resource?: Resource; // Populated resource object
  license_type: 'open' | 'restricted' | 'commercial';
  terms: string; // Legal terms and conditions text
  geographic_restrictions: {
    allowed_countries?: string[]; // ISO country codes
    restricted_countries?: string[]; // ISO country codes
  };
  usage_restrictions: {
    rate_limits?: {
      requests_per_minute?: number;
      requests_per_hour?: number;
      requests_per_day?: number;
    };
    requires_attribution?: boolean;
    attribution_text?: string;
  };
  requires_approval: boolean; // Whether admin approval is needed
  effective_from: string; // ISO date string
  expires_at?: string | null; // ISO date string (null = never expires)
}

// Distribution entity - Specific delivery format/endpoint for accessing a resource
export interface Distribution extends BaseEntity {
  resource_id: string; // Foreign key to Resource
  resource?: Resource; // Populated resource object
  format_type: 'REST_JSON' | 'GraphQL' | 'ZIP' | 'API';
  endpoint_url: string; // API endpoint or download URL
  version: string;
  access_config: {
    api_keys?: string[];
    authentication_methods?: string[];
    rate_limits?: Record<string, number>;
  }; // JSONB for API keys, authentication methods, rate limits
  metadata: Record<string, any>; // JSONB for format-specific configuration
}

// AccessRequest entity - Developer requests for distribution access with approval workflow
export interface AccessRequest extends BaseEntity {
  requester_id: string; // Foreign key to User with Developer role
  requester?: User; // Populated requester object
  distribution_id: string; // Foreign key to Distribution
  distribution?: Distribution; // Populated distribution object
  status: 'pending' | 'under_review' | 'approved' | 'rejected' | 'expired' | 'revoked';
  priority: 'low' | 'normal' | 'high' | 'urgent';
  justification: string; // Developer's use case description
  admin_notes: string; // Admin review notes and feedback
  rejection_reason?: 'insufficient_justification' | 'license_violation' | 'incomplete_information' | 'policy_violation' | 'resource_unavailable' | 'other';
  approved_by?: string | null; // Foreign key to User with Admin role
  approver?: User; // Populated approver object
  notification_sent: boolean; // Whether notification email has been sent
  requested_at: string; // ISO date string (auto-generated)
  reviewed_at?: string | null; // ISO date string
  expires_at?: string | null; // ISO date string for time-limited access
}

// UsageEvent entity - Comprehensive logging for analytics, billing, and compliance
export interface UsageEvent extends BaseEntity {
  user_id: string; // Foreign key to User (developer making the request)
  user?: User; // Populated user object
  resource_id: string; // Foreign key to Resource being accessed
  resource?: Resource; // Populated resource object
  distribution_id: string; // Foreign key to Distribution used
  distribution?: Distribution; // Populated distribution object
  event_type: 'api_call' | 'download' | 'view';
  endpoint: string; // Specific API endpoint called
  request_size: number; // Size of request in bytes
  response_size: number; // Size of response in bytes
  ip_address: string;
  user_agent: string;
  metadata: Record<string, any>; // JSONB for additional tracking data
  occurred_at: string; // ISO date string
}

// API Response wrapper interfaces
export interface ApiResponse<T> {
  data: T;
  message?: string;
  status: 'success' | 'error';
}

export interface PaginatedResponse<T> {
  results: T[];
  count: number;
  next?: string | null;
  previous?: string | null;
  page_size: number;
  current_page: number;
  total_pages: number;
}

// Authentication interfaces
export interface AuthUser {
  user: User;
  access_token: string;
  refresh_token?: string;
  expires_at: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

// Islamic content specific interfaces
export interface QuranicVerse {
  surah: number;
  ayah: number;
  text_arabic: string;
  text_transliteration?: string;
  translation?: string;
  tafsir?: string;
  audio_url?: string;
  reciter?: string;
}

export interface IslamicContent {
  type: 'quran' | 'hadith' | 'dua' | 'tafsir';
  language: string;
  content: QuranicVerse | Record<string, any>;
  metadata: {
    source?: string;
    authenticity_level?: 'sahih' | 'hasan' | 'daif';
    scholar_verified?: boolean;
    verification_date?: string;
  };
}

// Search and filtering interfaces
export interface SearchFilters {
  resource_type?: Resource['resource_type'][];
  language?: string[];
  license_type?: License['license_type'][];
  status?: AccessRequest['status'][];
  date_from?: string;
  date_to?: string;
  publisher_id?: string;
}

export interface SearchResult<T> {
  items: T[];
  total: number;
  facets: Record<string, { value: string; count: number }[]>;
  query: string;
  filters: SearchFilters;
}

// Form interfaces for creating/updating entities
export interface CreateResourceForm {
  title: string;
  description: string;
  resource_type: Resource['resource_type'];
  language: string;
  version: string;
  metadata: Record<string, any>;
}

export interface CreateAccessRequestForm {
  distribution_id: string;
  justification: string;
  priority: AccessRequest['priority'];
}

export interface UpdateUserProfileForm {
  first_name: string;
  last_name: string;
  profile_data: Record<string, any>;
}

// Dashboard and analytics interfaces
export interface DashboardStats {
  total_resources: number;
  total_users: number;
  pending_requests: number;
  recent_activity: UsageEvent[];
  popular_resources: Resource[];
}

export interface AccessRequestDashboard {
  status_counts: Record<AccessRequest['status'], number>;
  priority_counts: Record<AccessRequest['priority'], number>;
  recent_requests: number;
  pending_notifications: number;
  total_requests: number;
}

// Error handling interfaces
export interface ApiError {
  message: string;
  code: string;
  details?: Record<string, any>;
  field_errors?: Record<string, string[]>;
}

// Utility type for partial updates
export type PartialUpdate<T> = Partial<Omit<T, 'id' | 'created_at' | 'updated_at'>>;

// All interfaces are already exported above

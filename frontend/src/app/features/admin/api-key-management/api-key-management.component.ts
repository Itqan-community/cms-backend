import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';

// NG-ZORRO imports
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzModalModule } from 'ng-zorro-antd/modal';
import { NzFormModule } from 'ng-zorro-antd/form';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzSwitchModule } from 'ng-zorro-antd/switch';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzMessageService } from 'ng-zorro-antd/message';
import { NzModalService } from 'ng-zorro-antd/modal';
import { NzTabsModule } from 'ng-zorro-antd/tabs';
import { NzStatisticModule } from 'ng-zorro-antd/statistic';
import { NzRowModule } from 'ng-zorro-antd/row';
import { NzColModule } from 'ng-zorro-antd/col';
import { NzBreadCrumbModule } from 'ng-zorro-antd/breadcrumb';
import { NzPopconfirmModule } from 'ng-zorro-antd/popconfirm';
import { NzInputNumberModule } from 'ng-zorro-antd/input-number';
import { NzDividerModule } from 'ng-zorro-antd/divider';
import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzProgressModule } from 'ng-zorro-antd/progress';
import { NzListModule } from 'ng-zorro-antd/list';
import { NzAlertModule } from 'ng-zorro-antd/alert';
import { NzCopyToClipboardModule } from 'ng-zorro-antd/copy-to-clipboard';

// Services
import { AuthService } from '../../../core/services/auth.service';
import { I18nService } from '../../../core/services/i18n.service';

// Environment
import { environment } from '../../../../environments/environment';

// Interfaces
interface APIKey {
  id: string;
  name: string;
  key_prefix: string;
  user: string;
  user_email: string;
  user_name: string;
  description: string;
  permissions: { [key: string]: string[] };
  allowed_ips: string[];
  rate_limit: number;
  total_requests: number;
  last_used_at: string;
  last_used_ip: string;
  expires_at: string;
  revoked_at: string;
  revoked_by: string;
  revoked_reason: string;
  is_expired: boolean;
  is_revoked: boolean;
  is_valid: boolean;
  days_until_expiry: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface APIKeyUsage {
  id: string;
  api_key: string;
  api_key_name: string;
  endpoint: string;
  method: string;
  status_code: number;
  ip_address: string;
  user_agent: string;
  request_data: any;
  response_time: number;
  created_at: string;
}

interface APIKeyStats {
  api_key_id: string;
  total_requests: number;
  error_requests: number;
  error_rate: number;
  rate_limit_violations: number;
  daily_usage: { date: string; requests: number }[];
  top_endpoints: { endpoint: string; requests: number }[];
  period_days: number;
}

interface RateLimitEvent {
  id: string;
  api_key: string;
  api_key_name: string;
  ip_address: string;
  endpoint: string;
  method: string;
  limit_type: string;
  current_count: number;
  limit_value: number;
  window_seconds: number;
  created_at: string;
}

interface GlobalStats {
  api_keys: {
    total: number;
    active: number;
    expired: number;
    revoked: number;
  };
  usage_last_30_days: {
    total_requests: number;
    error_requests: number;
    error_rate: number;
    rate_limit_events: number;
  };
  top_api_keys: { api_key__name: string; api_key__id: string; requests: number }[];
  daily_requests: { date: string; requests: number }[];
}

@Component({
  selector: 'app-api-key-management',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    NzCardModule,
    NzTableModule,
    NzButtonModule,
    NzModalModule,
    NzFormModule,
    NzInputModule,
    NzSelectModule,
    NzSwitchModule,
    NzTagModule,
    NzIconModule,
    NzSpinModule,
    NzEmptyModule,
    NzTabsModule,
    NzStatisticModule,
    NzRowModule,
    NzColModule,
    NzBreadCrumbModule,
    NzPopconfirmModule,
    NzInputNumberModule,
    NzDividerModule,
    NzDescriptionsModule,
    NzProgressModule,
    NzListModule,
    NzAlertModule,
    NzCopyToClipboardModule
  ],
  templateUrl: './api-key-management.component.html',
  styleUrl: './api-key-management.component.scss'
})
export class ApiKeyManagementComponent implements OnInit {
  // Injected services
  private fb = inject(FormBuilder);
  private http = inject(HttpClient);
  private router = inject(Router);
  private message = inject(NzMessageService);
  private modal = inject(NzModalService);
  private authService = inject(AuthService);
  private i18n = inject(I18nService);

  // Signals for reactive state
  loading = signal(false);
  apiKeys = signal<APIKey[]>([]);
  usageLogs = signal<APIKeyUsage[]>([]);
  rateLimitEvents = signal<RateLimitEvent[]>([]);
  globalStats = signal<GlobalStats | null>(null);
  selectedApiKey = signal<APIKey | null>(null);
  apiKeyStats = signal<APIKeyStats | null>(null);

  // Modal visibility
  apiKeyModalVisible = signal(false);
  statsModalVisible = signal(false);
  revokeModalVisible = signal(false);
  keyDisplayModalVisible = signal(false);

  // Forms
  apiKeyForm: FormGroup;
  revokeForm: FormGroup;

  // Current tab
  currentTab = signal(0);

  // Generated API key (only shown once)
  generatedApiKey = signal<string | null>(null);

  constructor() {
    // Initialize forms
    this.apiKeyForm = this.fb.group({
      name: ['', [Validators.required, Validators.maxLength(255)]],
      description: ['', [Validators.maxLength(1000)]],
      rate_limit: [1000, [Validators.required, Validators.min(1), Validators.max(10000)]],
      expires_in_days: [null, [Validators.min(1), Validators.max(365)]],
      allowed_ips: [[]],
      permissions: [{}]
    });

    this.revokeForm = this.fb.group({
      reason: ['', [Validators.required, Validators.maxLength(500)]]
    });
  }

  ngOnInit(): void {
    this.loadData();
  }

  private async loadData(): Promise<void> {
    this.loading.set(true);
    try {
      await Promise.all([
        this.loadApiKeys(),
        this.loadGlobalStats(),
        this.loadUsageLogs(),
        this.loadRateLimitEvents()
      ]);
    } catch (error) {
      console.error('Error loading API key management data:', error);
      this.message.error(this.i18n.t()('error.loading_data'));
    } finally {
      this.loading.set(false);
    }
  }

  private async loadApiKeys(): Promise<void> {
    const response = await this.http.get<APIKey[]>(`${environment.apiUrl}/api-keys/`).toPromise();
    this.apiKeys.set(response || []);
  }

  private async loadUsageLogs(): Promise<void> {
    const response = await this.http.get<APIKeyUsage[]>(`${environment.apiUrl}/api-keys-usage/`).toPromise();
    this.usageLogs.set(response || []);
  }

  private async loadRateLimitEvents(): Promise<void> {
    const response = await this.http.get<RateLimitEvent[]>(`${environment.apiUrl}/rate-limit-events/`).toPromise();
    this.rateLimitEvents.set(response || []);
  }

  private async loadGlobalStats(): Promise<void> {
    const response = await this.http.get<GlobalStats>(`${environment.apiUrl}/api-stats/global_stats/`).toPromise();
    this.globalStats.set(response || null);
  }

  // API Key management methods
  openApiKeyModal(apiKey?: APIKey): void {
    if (apiKey) {
      this.selectedApiKey.set(apiKey);
      this.apiKeyForm.patchValue({
        name: apiKey.name,
        description: apiKey.description,
        rate_limit: apiKey.rate_limit,
        allowed_ips: apiKey.allowed_ips,
        permissions: apiKey.permissions
      });
    } else {
      this.selectedApiKey.set(null);
      this.apiKeyForm.reset({
        rate_limit: 1000,
        allowed_ips: [],
        permissions: {}
      });
    }
    this.apiKeyModalVisible.set(true);
  }

  async saveApiKey(): Promise<void> {
    if (this.apiKeyForm.valid) {
      const formData = this.apiKeyForm.value;
      const selectedApiKey = this.selectedApiKey();

      try {
        if (selectedApiKey) {
          // Update existing API key
          await this.http.put(`${environment.apiUrl}/api-keys/${selectedApiKey.id}/`, formData).toPromise();
          this.message.success(this.i18n.t()('api_key.updated_successfully'));
        } else {
          // Create new API key
          const response = await this.http.post<APIKey & { full_key: string }>(`${environment.apiUrl}/api-keys/`, formData).toPromise();
          this.generatedApiKey.set(response!.full_key);
          this.message.success(this.i18n.t()('api_key.created_successfully'));
          
          // Show the generated key modal
          this.keyDisplayModalVisible.set(true);
        }
        
        this.apiKeyModalVisible.set(false);
        await this.loadApiKeys();
        await this.loadGlobalStats();
      } catch (error) {
        console.error('Error saving API key:', error);
        this.message.error(this.i18n.t()('error.saving_api_key'));
      }
    }
  }

  openRevokeModal(apiKey: APIKey): void {
    this.selectedApiKey.set(apiKey);
    this.revokeForm.reset();
    this.revokeModalVisible.set(true);
  }

  async revokeApiKey(): Promise<void> {
    if (this.revokeForm.valid && this.selectedApiKey()) {
      const reason = this.revokeForm.value.reason;
      const apiKey = this.selectedApiKey()!;

      try {
        await this.http.post(`${environment.apiUrl}/api-keys/${apiKey.id}/revoke/`, { reason }).toPromise();
        this.message.success(this.i18n.t()('api_key.revoked_successfully'));
        this.revokeModalVisible.set(false);
        await this.loadApiKeys();
        await this.loadGlobalStats();
      } catch (error) {
        console.error('Error revoking API key:', error);
        this.message.error(this.i18n.t()('error.revoking_api_key'));
      }
    }
  }

  async regenerateApiKey(apiKey: APIKey): Promise<void> {
    try {
      const response = await this.http.post<APIKey & { full_key: string }>(`${environment.apiUrl}/api-keys/${apiKey.id}/regenerate/`, {}).toPromise();
      this.generatedApiKey.set(response!.full_key);
      this.message.success(this.i18n.t()('api_key.regenerated_successfully'));
      
      // Show the new key modal
      this.keyDisplayModalVisible.set(true);
      
      await this.loadApiKeys();
    } catch (error) {
      console.error('Error regenerating API key:', error);
      this.message.error(this.i18n.t()('error.regenerating_api_key'));
    }
  }

  async openStatsModal(apiKey: APIKey): Promise<void> {
    this.selectedApiKey.set(apiKey);
    
    try {
      const stats = await this.http.get<APIKeyStats>(`${environment.apiUrl}/api-keys/${apiKey.id}/stats/`).toPromise();
      this.apiKeyStats.set(stats || null);
      this.statsModalVisible.set(true);
    } catch (error) {
      console.error('Error loading API key stats:', error);
      this.message.error(this.i18n.t()('error.loading_stats'));
    }
  }

  // Utility methods
  getApiKeyStatus(apiKey: APIKey): string {
    if (apiKey.is_revoked) return 'revoked';
    if (apiKey.is_expired) return 'expired';
    if (apiKey.is_valid) return 'active';
    return 'inactive';
  }

  getApiKeyStatusColor(status: string): string {
    const colors: { [key: string]: string } = {
      'active': 'green',
      'expired': 'orange',
      'revoked': 'red',
      'inactive': 'default'
    };
    return colors[status] || 'default';
  }

  getStatusCodeColor(statusCode: number): string {
    if (statusCode < 300) return 'green';
    if (statusCode < 400) return 'blue';
    if (statusCode < 500) return 'orange';
    return 'red';
  }

  formatBytes(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  formatDate(dateString: string): string {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString();
  }

  formatDateTime(dateString: string): string {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleString();
  }

  copyToClipboard(text: string): void {
    navigator.clipboard.writeText(text).then(() => {
      this.message.success(this.i18n.t()('common.copied_to_clipboard'));
    }).catch(() => {
      this.message.error(this.i18n.t()('error.copy_failed'));
    });
  }

  // Chart data for statistics
  getUsageChartData(): any[] {
    const stats = this.apiKeyStats();
    if (!stats || !stats.daily_usage) return [];
    
    return stats.daily_usage.map(item => ({
      date: item.date,
      requests: item.requests
    }));
  }

  // Cancel modal operations
  cancelApiKeyModal(): void {
    this.apiKeyModalVisible.set(false);
    this.selectedApiKey.set(null);
  }

  cancelStatsModal(): void {
    this.statsModalVisible.set(false);
    this.selectedApiKey.set(null);
    this.apiKeyStats.set(null);
  }

  cancelRevokeModal(): void {
    this.revokeModalVisible.set(false);
    this.selectedApiKey.set(null);
  }

  closeKeyDisplayModal(): void {
    this.keyDisplayModalVisible.set(false);
    this.generatedApiKey.set(null);
  }
}

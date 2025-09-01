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
import { NzCheckboxModule } from 'ng-zorro-antd/checkbox';
import { NzDividerModule } from 'ng-zorro-antd/divider';
import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

// Services
import { AuthService } from '../../../core/services/auth.service';
import { I18nService } from '../../../core/services/i18n.service';

// Environment
import { environment } from '../../../../environments/environment';

// Interfaces
interface Role {
  id: string;
  name: string;
  description: string;
  permissions: { [key: string]: string[] };
  user_count: number;
  permission_categories: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface User {
  id: string;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: string;
  role_name: string;
  role_permissions: { [key: string]: string[] };
  is_active: boolean;
  last_login: string;
  can_access_admin: boolean;
  created_at: string;
  updated_at: string;
}

interface PermissionMatrix {
  matrix: { [roleName: string]: { [resource: string]: string[] } };
  roles: string[];
  resources: string[];
}

interface UserStats {
  role_distribution: { [roleName: string]: number };
  total_users: number;
  active_users: number;
  inactive_users: number;
  roles_count: number;
}

@Component({
  selector: 'app-role-management',
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
    NzCheckboxModule,
    NzDividerModule,
    NzDescriptionsModule
  ],
  templateUrl: './role-management.component.html',
  styleUrl: './role-management.component.scss'
})
export class RoleManagementComponent implements OnInit {
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
  roles = signal<Role[]>([]);
  users = signal<User[]>([]);
  permissionMatrix = signal<PermissionMatrix | null>(null);
  userStats = signal<UserStats | null>(null);
  selectedRole = signal<Role | null>(null);
  selectedUser = signal<User | null>(null);

  // Modal visibility
  roleModalVisible = signal(false);
  userModalVisible = signal(false);
  permissionModalVisible = signal(false);
  userRoleModalVisible = signal(false);

  // Forms
  roleForm: FormGroup;
  userForm: FormGroup;
  userRoleForm: FormGroup;

  // Current tab
  currentTab = signal(0);

  // Permission categories and actions for the UI
  permissionCategories = [
    { key: 'users', label: 'User Management', icon: 'user' },
    { key: 'roles', label: 'Role Management', icon: 'team' },
    { key: 'resources', label: 'Content Resources', icon: 'book' },
    { key: 'licenses', label: 'License Management', icon: 'safety-certificate' },
    { key: 'distributions', label: 'Content Distribution', icon: 'cloud-download' },
    { key: 'access_requests', label: 'Access Requests', icon: 'key' },
    { key: 'usage_events', label: 'Usage Analytics', icon: 'bar-chart' },
    { key: 'system', label: 'System Administration', icon: 'setting' },
    { key: 'workflow', label: 'Workflow Management', icon: 'flow-chart' },
    { key: 'media', label: 'Media Library', icon: 'file-image' },
    { key: 'search', label: 'Search Configuration', icon: 'search' },
    { key: 'api', label: 'API Access', icon: 'api' }
  ];

  permissionActions = [
    { key: 'create', label: 'Create', color: 'green' },
    { key: 'read', label: 'Read', color: 'blue' },
    { key: 'update', label: 'Update', color: 'orange' },
    { key: 'delete', label: 'Delete', color: 'red' },
    { key: 'approve', label: 'Approve', color: 'cyan' },
    { key: 'reject', label: 'Reject', color: 'purple' },
    { key: 'review', label: 'Review', color: 'geekblue' },
    { key: 'publish', label: 'Publish', color: 'lime' },
    { key: 'manage', label: 'Manage', color: 'volcano' },
    { key: 'access', label: 'Access', color: 'gold' }
  ];

  constructor() {
    // Initialize forms
    this.roleForm = this.fb.group({
      name: ['', [Validators.required, Validators.maxLength(50)]],
      description: ['', [Validators.maxLength(500)]],
      permissions: [{}]
    });

    this.userForm = this.fb.group({
      username: ['', [Validators.required, Validators.maxLength(150)]],
      email: ['', [Validators.required, Validators.email]],
      first_name: ['', [Validators.maxLength(150)]],
      last_name: ['', [Validators.maxLength(150)]],
      role: ['', [Validators.required]],
      is_active: [true]
    });

    this.userRoleForm = this.fb.group({
      user_id: ['', [Validators.required]],
      role_id: ['', [Validators.required]],
      reason: ['']
    });
  }

  ngOnInit(): void {
    this.loadData();
  }

  private async loadData(): Promise<void> {
    this.loading.set(true);
    try {
      await Promise.all([
        this.loadRoles(),
        this.loadUsers(),
        this.loadPermissionMatrix(),
        this.loadUserStats()
      ]);
    } catch (error) {
      console.error('Error loading role management data:', error);
      this.message.error(this.i18n.t()('error.loading_data'));
    } finally {
      this.loading.set(false);
    }
  }

  private async loadRoles(): Promise<void> {
    const response = await this.http.get<Role[]>(`${environment.apiUrl}/roles/`).toPromise();
    this.roles.set(response || []);
  }

  private async loadUsers(): Promise<void> {
    const response = await this.http.get<User[]>(`${environment.apiUrl}/users/`).toPromise();
    this.users.set(response || []);
  }

  private async loadPermissionMatrix(): Promise<void> {
    const response = await this.http.get<PermissionMatrix>(`${environment.apiUrl}/roles/permission_matrix/`).toPromise();
    this.permissionMatrix.set(response || null);
  }

  private async loadUserStats(): Promise<void> {
    const response = await this.http.get<UserStats>(`${environment.apiUrl}/users/role_statistics/`).toPromise();
    this.userStats.set(response || null);
  }

  // Role management methods
  openRoleModal(role?: Role): void {
    if (role) {
      this.selectedRole.set(role);
      this.roleForm.patchValue({
        name: role.name,
        description: role.description,
        permissions: role.permissions
      });
    } else {
      this.selectedRole.set(null);
      this.roleForm.reset();
    }
    this.roleModalVisible.set(true);
  }

  async saveRole(): Promise<void> {
    if (this.roleForm.valid) {
      const formData = this.roleForm.value;
      const selectedRole = this.selectedRole();

      try {
        if (selectedRole) {
          // Update existing role
          await this.http.put(`${environment.apiUrl}/roles/${selectedRole.id}/`, formData).toPromise();
          this.message.success(this.i18n.t()('role.updated_successfully'));
        } else {
          // Create new role
          await this.http.post(`${environment.apiUrl}/roles/`, formData).toPromise();
          this.message.success(this.i18n.t()('role.created_successfully'));
        }
        
        this.roleModalVisible.set(false);
        await this.loadRoles();
        await this.loadPermissionMatrix();
      } catch (error) {
        console.error('Error saving role:', error);
        this.message.error(this.i18n.t()('error.saving_role'));
      }
    }
  }

  async deleteRole(role: Role): Promise<void> {
    if (role.user_count > 0) {
      this.message.warning(this.i18n.t()('role.cannot_delete_with_users'));
      return;
    }

    try {
      await this.http.delete(`${environment.apiUrl}/roles/${role.id}/`).toPromise();
      this.message.success(this.i18n.t()('role.deleted_successfully'));
      await this.loadRoles();
      await this.loadPermissionMatrix();
    } catch (error) {
      console.error('Error deleting role:', error);
      this.message.error(this.i18n.t()('error.deleting_role'));
    }
  }

  async resetRoleToDefault(role: Role): Promise<void> {
    try {
      await this.http.post(`${environment.apiUrl}/roles/${role.id}/reset_to_default/`, {}).toPromise();
      this.message.success(this.i18n.t()('role.reset_to_default_successfully'));
      await this.loadRoles();
      await this.loadPermissionMatrix();
    } catch (error) {
      console.error('Error resetting role:', error);
      this.message.error(this.i18n.t()('error.resetting_role'));
    }
  }

  // User management methods
  openUserModal(user?: User): void {
    if (user) {
      this.selectedUser.set(user);
      this.userForm.patchValue({
        username: user.username,
        email: user.email,
        first_name: user.first_name,
        last_name: user.last_name,
        role: user.role,
        is_active: user.is_active
      });
    } else {
      this.selectedUser.set(null);
      this.userForm.reset({ is_active: true });
    }
    this.userModalVisible.set(true);
  }

  async saveUser(): Promise<void> {
    if (this.userForm.valid) {
      const formData = this.userForm.value;
      const selectedUser = this.selectedUser();

      try {
        if (selectedUser) {
          // Update existing user
          await this.http.put(`${environment.apiUrl}/users/${selectedUser.id}/`, formData).toPromise();
          this.message.success(this.i18n.t()('user.updated_successfully'));
        } else {
          // Create new user
          await this.http.post(`${environment.apiUrl}/users/`, formData).toPromise();
          this.message.success(this.i18n.t()('user.created_successfully'));
        }
        
        this.userModalVisible.set(false);
        await this.loadUsers();
        await this.loadUserStats();
      } catch (error) {
        console.error('Error saving user:', error);
        this.message.error(this.i18n.t()('error.saving_user'));
      }
    }
  }

  // User role assignment
  openUserRoleModal(user: User): void {
    this.userRoleForm.patchValue({
      user_id: user.id,
      role_id: user.role,
      reason: ''
    });
    this.userRoleModalVisible.set(true);
  }

  async changeUserRole(): Promise<void> {
    if (this.userRoleForm.valid) {
      const formData = this.userRoleForm.value;

      try {
        await this.http.patch(`${environment.apiUrl}/users/${formData.user_id}/change_role/`, {
          role_id: formData.role_id,
          reason: formData.reason
        }).toPromise();

        this.message.success(this.i18n.t()('user.role_changed_successfully'));
        this.userRoleModalVisible.set(false);
        await this.loadUsers();
        await this.loadUserStats();
      } catch (error) {
        console.error('Error changing user role:', error);
        this.message.error(this.i18n.t()('error.changing_user_role'));
      }
    }
  }

  // Permission matrix methods
  openPermissionModal(role: Role): void {
    this.selectedRole.set(role);
    this.permissionModalVisible.set(true);
  }

  hasPermission(role: Role, category: string, action: string): boolean {
    const permissions = role.permissions || {};
    const categoryPermissions = permissions[category] || [];
    return categoryPermissions.includes(action);
  }

  togglePermission(role: Role, category: string, action: string): void {
    const permissions = { ...role.permissions };
    
    if (!permissions[category]) {
      permissions[category] = [];
    }

    const categoryPermissions = [...permissions[category]];
    const index = categoryPermissions.indexOf(action);

    if (index > -1) {
      categoryPermissions.splice(index, 1);
    } else {
      categoryPermissions.push(action);
    }

    permissions[category] = categoryPermissions;
    
    // Update the role permissions
    role.permissions = permissions;
  }

  async savePermissions(role: Role): Promise<void> {
    try {
      await this.http.patch(`${environment.apiUrl}/roles/${role.id}/update_permissions/`, {
        permissions: role.permissions
      }).toPromise();

      this.message.success(this.i18n.t()('permissions.updated_successfully'));
      this.permissionModalVisible.set(false);
      await this.loadRoles();
      await this.loadPermissionMatrix();
    } catch (error) {
      console.error('Error saving permissions:', error);
      this.message.error(this.i18n.t()('error.saving_permissions'));
    }
  }

  // Utility methods
  getRoleColor(roleName: string): string {
    const colors: { [key: string]: string } = {
      'Admin': 'red',
      'Publisher': 'green',
      'Developer': 'blue',
      'Reviewer': 'orange'
    };
    return colors[roleName] || 'default';
  }

  getPermissionActionColor(action: string): string {
    const actionColors: { [key: string]: string } = {
      'create': 'green',
      'read': 'blue',
      'update': 'orange',
      'delete': 'red',
      'approve': 'cyan',
      'reject': 'purple'
    };
    return actionColors[action] || 'default';
  }

  formatDate(dateString: string): string {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString();
  }

  formatDateTime(dateString: string): string {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleString();
  }

  // Cancel modal operations
  cancelRoleModal(): void {
    this.roleModalVisible.set(false);
    this.selectedRole.set(null);
  }

  cancelUserModal(): void {
    this.userModalVisible.set(false);
    this.selectedUser.set(null);
  }

  cancelPermissionModal(): void {
    this.permissionModalVisible.set(false);
    this.selectedRole.set(null);
  }

  cancelUserRoleModal(): void {
    this.userRoleModalVisible.set(false);
  }
}

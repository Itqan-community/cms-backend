import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient, HttpEventType } from '@angular/common/http';
import { NzLayoutModule } from 'ng-zorro-antd/layout';
import { NzBreadCrumbModule } from 'ng-zorro-antd/breadcrumb';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzGridModule } from 'ng-zorro-antd/grid';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzUploadModule, NzUploadFile, NzUploadChangeParam } from 'ng-zorro-antd/upload';
import { NzMessageModule, NzMessageService } from 'ng-zorro-antd/message';
import { NzModalModule, NzModalService } from 'ng-zorro-antd/modal';
import { NzTreeModule, NzTreeNodeOptions } from 'ng-zorro-antd/tree';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzTypographyModule } from 'ng-zorro-antd/typography';
import { NzToolTipModule } from 'ng-zorro-antd/tooltip';
import { NzDropDownModule } from 'ng-zorro-antd/dropdown';
import { NzMenuModule } from 'ng-zorro-antd/menu';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { FormsModule } from '@angular/forms';

import { environment } from '../../../../environments/environment';

/**
 * ADMIN-001: Media Library Component
 * 
 * Implements the complete media library interface with MinIO integration
 * following the ADMIN-001 wireframe design with NG-ZORRO components
 */

interface MediaFile {
  id: string;
  title: string;
  description: string;
  file_url: string;
  original_filename: string;
  file_size: number;
  human_readable_size: string;
  mime_type: string;
  media_type: string;
  width?: number;
  height?: number;
  duration?: string;
  checksum: string;
  folder?: string;
  folder_name?: string;
  tags: string[];
  uploaded_by_name: string;
  created_at: string;
  updated_at: string;
}

interface MediaFolder {
  id: string;
  name: string;
  description: string;
  parent?: string;
  full_path: string;
  file_count: number;
  children?: MediaFolder[];
  created_at: string;
}

interface UploadProgress {
  file: NzUploadFile;
  progress: number;
  status: 'uploading' | 'done' | 'error';
}

@Component({
  selector: 'app-media-library',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    NzLayoutModule,
    NzBreadCrumbModule,
    NzButtonModule,
    NzCardModule,
    NzGridModule,
    NzIconModule,
    NzUploadModule,
    NzMessageModule,
    NzModalModule,
    NzTreeModule,
    NzSpinModule,
    NzEmptyModule,
    NzTagModule,
    NzTypographyModule,
    NzToolTipModule,
    NzDropDownModule,
    NzMenuModule,
    NzInputModule,
    NzSelectModule
  ],
  template: `
    <nz-layout class="media-library">
      <!-- Header -->
      <nz-header class="media-header">
        <nz-breadcrumb>
          <nz-breadcrumb-item>
            <span nz-icon nzType="home"></span>
            Admin
          </nz-breadcrumb-item>
          <nz-breadcrumb-item>
            <span nz-icon nzType="picture"></span>
            Media Library
          </nz-breadcrumb-item>
          @if (currentFolder()) {
            <nz-breadcrumb-item>
              {{ currentFolder()?.name }}
            </nz-breadcrumb-item>
          }
        </nz-breadcrumb>

        <div class="header-actions">
          <button nz-button nzType="primary" (click)="showUploadModal()">
            <span nz-icon nzType="upload"></span>
            Upload Files
          </button>
          <button nz-button nzType="default" (click)="createFolder()">
            <span nz-icon nzType="folder-add"></span>
            New Folder
          </button>
          <button nz-button nzType="default" (click)="refreshLibrary()">
            <span nz-icon nzType="reload"></span>
            Refresh
          </button>
        </div>
      </nz-header>

      <nz-layout>
        <!-- Sidebar: Folder Tree -->
        <nz-sider nzWidth="280px" class="folder-sidebar">
          <div class="sidebar-header">
            <h3>Folders</h3>
          </div>
          
          <div class="folder-tree-container">
            @if (isLoadingFolders()) {
              <nz-spin nzSimple class="loading-spinner"></nz-spin>
            } @else {
              <nz-tree
                [nzData]="folderTreeData()"
                [nzBlockNode]="true"
                [nzExpandedKeys]="expandedKeys()"
                (nzClick)="onFolderSelect($event)"
                (nzExpandChange)="onExpandChange($event)">
              </nz-tree>
            }
          </div>
        </nz-sider>

        <!-- Main Content: File Grid -->
        <nz-content class="file-content">
          <!-- Filter Bar -->
          <div class="filter-bar">
            <div class="filter-row">
              <nz-input-group nzSearch nzSize="large" class="search-input">
                <input
                  type="text"
                  nz-input
                  placeholder="Search files..."
                  [(ngModel)]="searchQuery"
                  (ngModelChange)="onSearchChange($event)" />
              </nz-input-group>

              <nz-select
                nzPlaceHolder="Media Type"
                [(ngModel)]="selectedMediaType"
                (ngModelChange)="onFilterChange()"
                nzAllowClear
                class="filter-select">
                <nz-option nzValue="image" nzLabel="Images"></nz-option>
                <nz-option nzValue="audio" nzLabel="Audio"></nz-option>
                <nz-option nzValue="video" nzLabel="Videos"></nz-option>
                <nz-option nzValue="document" nzLabel="Documents"></nz-option>
                <nz-option nzValue="archive" nzLabel="Archives"></nz-option>
              </nz-select>

              <div class="view-toggle">
                <button
                  nz-button
                  [nzType]="viewMode() === 'grid' ? 'primary' : 'default'"
                  (click)="setViewMode('grid')">
                  <span nz-icon nzType="appstore"></span>
                </button>
                <button
                  nz-button
                  [nzType]="viewMode() === 'list' ? 'primary' : 'default'"
                  (click)="setViewMode('list')">
                  <span nz-icon nzType="bars"></span>
                </button>
              </div>
            </div>
          </div>

          <!-- File Display Area -->
          <div class="file-display">
            @if (isLoadingFiles()) {
              <div class="loading-container">
                <nz-spin nzSimple nzSize="large"></nz-spin>
                <p>Loading media files...</p>
              </div>
            } @else if (mediaFiles().length === 0) {
              <nz-empty
                nzNotFoundImage="simple"
                nzNotFoundContent="No files found">
                <div nz-empty-footer>
                  <button nz-button nzType="primary" (click)="showUploadModal()">
                    Upload First File
                  </button>
                </div>
              </nz-empty>
            } @else {
              <!-- Grid View -->
              @if (viewMode() === 'grid') {
                <div nz-row [nzGutter]="[16, 16]" class="file-grid">
                  @for (file of mediaFiles(); track file.id) {
                    <div nz-col [nzXs]="12" [nzSm]="8" [nzMd]="6" [nzLg]="4" [nzXl]="3">
                      <nz-card
                        class="file-card"
                        [nzCover]="fileCardCover"
                        [nzActions]="fileCardActions"
                        (click)="selectFile(file)">
                        <ng-template #fileCardCover>
                          <div class="file-preview">
                            @if (file.media_type === 'image') {
                              <img [src]="file.file_url" [alt]="file.title" />
                            } @else {
                              <div class="file-icon">
                                <span nz-icon [nzType]="getFileIcon(file.media_type)" nzTheme="outline"></span>
                              </div>
                            }
                          </div>
                        </ng-template>

                        <ng-template #fileCardActions>
                          <span nz-icon nzType="eye" nzTheme="outline" (click)="viewFile(file)" nz-tooltip nzTooltipTitle="View"></span>
                          <span nz-icon nzType="download" nzTheme="outline" (click)="downloadFile(file)" nz-tooltip nzTooltipTitle="Download"></span>
                          <span nz-icon nzType="edit" nzTheme="outline" (click)="editFile(file)" nz-tooltip nzTooltipTitle="Edit"></span>
                          <span nz-icon nzType="delete" nzTheme="outline" (click)="deleteFile(file)" nz-tooltip nzTooltipTitle="Delete"></span>
                        </ng-template>

                        <div class="file-info">
                          <h4 nz-typography nzEllipsis>{{ file.title }}</h4>
                          <p class="file-meta">
                            <span class="file-size">{{ file.human_readable_size }}</span>
                            <nz-tag [nzColor]="getMediaTypeColor(file.media_type)">
                              {{ file.media_type }}
                            </nz-tag>
                          </p>
                        </div>
                      </nz-card>
                    </div>
                  }
                </div>
              }

              <!-- List View -->
              @if (viewMode() === 'list') {
                <div class="file-list">
                  @for (file of mediaFiles(); track file.id) {
                    <nz-card class="file-list-item" [nzBodyStyle]="{ padding: '12px 16px' }">
                      <div class="list-item-content">
                        <div class="file-preview-small">
                          @if (file.media_type === 'image') {
                            <img [src]="file.file_url" [alt]="file.title" />
                          } @else {
                            <span nz-icon [nzType]="getFileIcon(file.media_type)" nzTheme="outline"></span>
                          }
                        </div>

                        <div class="file-details">
                          <h4>{{ file.title }}</h4>
                          <p class="file-filename">{{ file.original_filename }}</p>
                          <div class="file-meta">
                            <span>{{ file.human_readable_size }}</span>
                            <span>{{ file.created_at | date:'short' }}</span>
                            <nz-tag [nzColor]="getMediaTypeColor(file.media_type)">
                              {{ file.media_type }}
                            </nz-tag>
                          </div>
                        </div>

                        <div class="file-actions">
                          <button nz-button nzType="text" (click)="viewFile(file)">
                            <span nz-icon nzType="eye"></span>
                          </button>
                          <button nz-button nzType="text" (click)="downloadFile(file)">
                            <span nz-icon nzType="download"></span>
                          </button>
                          <button nz-button nzType="text" (click)="editFile(file)">
                            <span nz-icon nzType="edit"></span>
                          </button>
                          <button nz-button nzType="text" nzDanger (click)="deleteFile(file)">
                            <span nz-icon nzType="delete"></span>
                          </button>
                        </div>
                      </div>
                    </nz-card>
                  }
                </div>
              }
            }
          </div>
        </nz-content>
      </nz-layout>
    </nz-layout>

    <!-- Upload Modal -->
    <nz-modal
      [(nzVisible)]="isUploadModalVisible"
      nzTitle="Upload Files"
      [nzFooter]="null"
      [nzWidth]="600"
      (nzOnCancel)="closeUploadModal()">
      
      <div *nzModalContent>
        <nz-upload
          nzType="drag"
          [nzMultiple]="true"
          [nzAction]="uploadUrl"
          [nzHeaders]="uploadHeaders"
          [nzData]="uploadData"
          [nzBeforeUpload]="beforeUpload"
          (nzChange)="onUploadChange($event)"
          class="upload-area">
          <p class="ant-upload-drag-icon">
            <span nz-icon nzType="inbox" nzTheme="outline"></span>
          </p>
          <p class="ant-upload-text">Click or drag files to this area to upload</p>
          <p class="ant-upload-hint">
            Support for single or bulk upload. Strictly prohibited from uploading company data or other banned files.
          </p>
        </nz-upload>

        @if (uploadProgress().length > 0) {
          <div class="upload-progress">
            <h4>Upload Progress</h4>
            @for (progress of uploadProgress(); track progress.file.uid) {
              <div class="progress-item">
                <div class="progress-info">
                  <span>{{ progress.file.name }}</span>
                  <span>{{ progress.progress }}%</span>
                </div>
                <nz-progress [nzPercent]="progress.progress" [nzStatus]="progress.status === 'error' ? 'exception' : 'active'"></nz-progress>
              </div>
            }
          </div>
        }
      </div>
    </nz-modal>
  `,
  styleUrls: ['./media-library.component.scss']
})
export class MediaLibraryComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly message = inject(NzMessageService);
  private readonly modal = inject(NzModalService);

  // Reactive state
  mediaFiles = signal<MediaFile[]>([]);
  mediaFolders = signal<MediaFolder[]>([]);
  folderTreeData = signal<NzTreeNodeOptions[]>([]);
  currentFolder = signal<MediaFolder | null>(null);
  selectedFiles = signal<MediaFile[]>([]);
  expandedKeys = signal<string[]>([]);
  
  // Loading states
  isLoadingFiles = signal(false);
  isLoadingFolders = signal(false);
  
  // UI state
  viewMode = signal<'grid' | 'list'>('grid');
  isUploadModalVisible = false;
  uploadProgress = signal<UploadProgress[]>([]);
  
  // Filters
  searchQuery = '';
  selectedMediaType = '';
  
  // Upload configuration
  uploadUrl = `${environment.apiUrl}/media/files/`;
  uploadHeaders = {}; // Will be set with auth token
  uploadData = {};

  ngOnInit(): void {
    this.loadFolders();
    this.loadFiles();
    this.setupUploadHeaders();
  }

  private setupUploadHeaders(): void {
    // Get auth token from localStorage or service
    const token = localStorage.getItem('access_token');
    if (token) {
      this.uploadHeaders = {
        'Authorization': `Bearer ${token}`
      };
    }
  }

  loadFolders(): void {
    this.isLoadingFolders.set(true);
    this.http.get<MediaFolder[]>(`${environment.apiUrl}/media/folders/`)
      .subscribe({
        next: (folders) => {
          this.mediaFolders.set(folders);
          this.buildFolderTree(folders);
          this.isLoadingFolders.set(false);
        },
        error: (error) => {
          console.error('Error loading folders:', error);
          this.message.error('Failed to load folders');
          this.isLoadingFolders.set(false);
        }
      });
  }

  loadFiles(): void {
    this.isLoadingFiles.set(true);
    let url = `${environment.apiUrl}/media/files/`;
    const params = new URLSearchParams();
    
    if (this.currentFolder()) {
      params.append('folder', this.currentFolder()!.id);
    }
    
    if (this.searchQuery) {
      params.append('search', this.searchQuery);
    }
    
    if (this.selectedMediaType) {
      params.append('media_type', this.selectedMediaType);
    }
    
    if (params.toString()) {
      url += '?' + params.toString();
    }

    this.http.get<{results: MediaFile[]}>(url)
      .subscribe({
        next: (response) => {
          this.mediaFiles.set(response.results);
          this.isLoadingFiles.set(false);
        },
        error: (error) => {
          console.error('Error loading files:', error);
          this.message.error('Failed to load files');
          this.isLoadingFiles.set(false);
        }
      });
  }

  private buildFolderTree(folders: MediaFolder[]): void {
    const tree = this.buildTreeFromFolders(folders);
    this.folderTreeData.set(tree);
  }

  private buildTreeFromFolders(folders: MediaFolder[], parentId?: string): NzTreeNodeOptions[] {
    const tree: NzTreeNodeOptions[] = [];
    
    // Add root folder
    if (!parentId) {
      tree.push({
        title: 'All Files',
        key: 'root',
        icon: 'folder',
        children: []
      });
    }
    
    const children = folders.filter(f => f.parent === parentId);
    
    for (const folder of children) {
      const node: NzTreeNodeOptions = {
        title: folder.name,
        key: folder.id,
        icon: 'folder',
        children: this.buildTreeFromFolders(folders, folder.id)
      };
      
      if (parentId) {
        tree.push(node);
      } else {
        tree[0].children!.push(node);
      }
    }
    
    return tree;
  }

  onFolderSelect(event: any): void {
    if (event.node?.key === 'root') {
      this.currentFolder.set(null);
    } else {
      const folder = this.mediaFolders().find(f => f.id === event.node?.key);
      this.currentFolder.set(folder || null);
    }
    this.loadFiles();
  }

  onExpandChange(event: any): void {
    // Handle folder expansion
  }

  onSearchChange(query: string): void {
    // Debounce search
    setTimeout(() => {
      if (this.searchQuery === query) {
        this.loadFiles();
      }
    }, 300);
  }

  onFilterChange(): void {
    this.loadFiles();
  }

  setViewMode(mode: 'grid' | 'list'): void {
    this.viewMode.set(mode);
  }

  showUploadModal(): void {
    this.isUploadModalVisible = true;
  }

  closeUploadModal(): void {
    this.isUploadModalVisible = false;
    this.uploadProgress.set([]);
  }

  beforeUpload = (file: NzUploadFile): boolean => {
    // Validate file size (max 100MB)
    const maxSize = 100 * 1024 * 1024;
    if (file.size! > maxSize) {
      this.message.error('File size cannot exceed 100MB');
      return false;
    }
    return true;
  };

  onUploadChange(event: NzUploadChangeParam): void {
    const { file, fileList } = event;
    
    if (file.status === 'uploading') {
      const progress = file.percent || 0;
      this.updateUploadProgress(file, progress, 'uploading');
    } else if (file.status === 'done') {
      this.message.success(`${file.name} uploaded successfully`);
      this.updateUploadProgress(file, 100, 'done');
      this.loadFiles(); // Refresh file list
    } else if (file.status === 'error') {
      this.message.error(`${file.name} upload failed`);
      this.updateUploadProgress(file, 0, 'error');
    }
  }

  private updateUploadProgress(file: NzUploadFile, progress: number, status: 'uploading' | 'done' | 'error'): void {
    const currentProgress = this.uploadProgress();
    const existingIndex = currentProgress.findIndex(p => p.file.uid === file.uid);
    
    if (existingIndex >= 0) {
      currentProgress[existingIndex] = { file, progress, status };
    } else {
      currentProgress.push({ file, progress, status });
    }
    
    this.uploadProgress.set([...currentProgress]);
  }

  selectFile(file: MediaFile): void {
    // Handle file selection
  }

  viewFile(file: MediaFile): void {
    // Open file in modal or new window
    window.open(file.file_url, '_blank');
  }

  downloadFile(file: MediaFile): void {
    // Trigger file download
    const link = document.createElement('a');
    link.href = file.file_url;
    link.download = file.original_filename;
    link.click();
  }

  editFile(file: MediaFile): void {
    // Open edit modal
    this.message.info('File editing feature coming soon');
  }

  deleteFile(file: MediaFile): void {
    this.modal.confirm({
      nzTitle: 'Delete File',
      nzContent: `Are you sure you want to delete "${file.title}"?`,
      nzOkText: 'Delete',
      nzOkType: 'primary',
      nzOkDanger: true,
      nzOnOk: () => {
        this.http.delete(`${environment.apiUrl}/media/files/${file.id}/`)
          .subscribe({
            next: () => {
              this.message.success('File deleted successfully');
              this.loadFiles();
            },
            error: (error) => {
              console.error('Error deleting file:', error);
              this.message.error('Failed to delete file');
            }
          });
      }
    });
  }

  createFolder(): void {
    // Show create folder modal
    this.message.info('Create folder feature coming soon');
  }

  refreshLibrary(): void {
    this.loadFolders();
    this.loadFiles();
  }

  getFileIcon(mediaType: string): string {
    const iconMap: { [key: string]: string } = {
      'image': 'picture',
      'audio': 'audio',
      'video': 'video',
      'document': 'file-text',
      'archive': 'file-zip',
      'other': 'file'
    };
    return iconMap[mediaType] || 'file';
  }

  getMediaTypeColor(mediaType: string): string {
    const colorMap: { [key: string]: string } = {
      'image': 'green',
      'audio': 'blue',
      'video': 'purple',
      'document': 'orange',
      'archive': 'red',
      'other': 'default'
    };
    return colorMap[mediaType] || 'default';
  }
}

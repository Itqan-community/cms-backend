import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, ActivatedRoute } from '@angular/router';
import { FormBuilder, FormGroup, ReactiveFormsModule } from '@angular/forms';

// NG-ZORRO imports
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzGridModule } from 'ng-zorro-antd/grid';
import { NzPaginationModule } from 'ng-zorro-antd/pagination';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzBreadCrumbModule } from 'ng-zorro-antd/breadcrumb';
import { NzTypographyModule } from 'ng-zorro-antd/typography';
import { NzDividerModule } from 'ng-zorro-antd/divider';
import { NzAvatarModule } from 'ng-zorro-antd/avatar';
import { NzSkeletonModule } from 'ng-zorro-antd/skeleton';

// Services
import { ArticleService, Article, ArticleListResponse, ArticleFilters } from '../article.service';
import { SEOService } from '../../../../core/services/seo.service';
import { I18nService } from '../../../../core/services/i18n.service';

@Component({
  selector: 'app-article-list',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    NzCardModule,
    NzGridModule,
    NzPaginationModule,
    NzInputModule,
    NzSelectModule,
    NzButtonModule,
    NzIconModule,
    NzTagModule,
    NzSpinModule,
    NzEmptyModule,
    NzBreadCrumbModule,
    NzTypographyModule,
    NzDividerModule,
    NzAvatarModule,
    NzSkeletonModule
  ],
  templateUrl: './article-list.component.html',
  styleUrl: './article-list.component.scss'
})
export class ArticleListComponent implements OnInit {
  // Injected services
  private articleService = inject(ArticleService);
  private seoService = inject(SEOService);
  private i18n = inject(I18nService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private fb = inject(FormBuilder);

  // Signals for reactive state
  articles = signal<Article[]>([]);
  totalArticles = signal(0);
  loading = signal(false);
  currentPage = signal(1);
  pageSize = signal(12);
  categories = signal<string[]>([]);
  tags = signal<string[]>([]);
  featuredArticles = signal<Article[]>([]);

  // Search and filter form
  filterForm: FormGroup;

  // Current filters computed signal
  currentFilters = computed(() => {
    const formValue = this.filterForm?.value || {};
    return {
      search: formValue.search || '',
      category: formValue.category || '',
      language: formValue.language || '',
      resource_type: formValue.resource_type || '',
      ordering: formValue.ordering || '-published_at',
      page: this.currentPage(),
      page_size: this.pageSize()
    } as ArticleFilters;
  });

  // Available sort options
  sortOptions = [
    { label: 'Latest First', value: '-published_at' },
    { label: 'Oldest First', value: 'published_at' },
    { label: 'Title A-Z', value: 'title' },
    { label: 'Title Z-A', value: '-title' },
    { label: 'Most Popular', value: '-distribution_count' }
  ];

  // Language options
  languageOptions = [
    { label: 'All Languages', value: '' },
    { label: 'Arabic', value: 'ar' },
    { label: 'English', value: 'en' }
  ];

  // Resource type options
  resourceTypeOptions = [
    { label: 'All Types', value: '' },
    { label: 'Article', value: 'article' },
    { label: 'Audio', value: 'audio' },
    { label: 'Video', value: 'video' },
    { label: 'Document', value: 'document' }
  ];

  constructor() {
    // Initialize filter form
    this.filterForm = this.fb.group({
      search: [''],
      category: [''],
      language: [''],
      resource_type: [''],
      ordering: ['-published_at']
    });

    // Subscribe to form changes
    this.filterForm.valueChanges.subscribe(() => {
      this.currentPage.set(1); // Reset to first page on filter change
      this.loadArticles();
    });
  }

  ngOnInit(): void {
    // Set up SEO
    this.setupSEO();
    
    // Load initial data
    this.loadInitialData();
    
    // Handle route params
    this.handleRouteParams();
  }

  private setupSEO(): void {
    const seoData = this.seoService.generateArticleListSEO({}, this.i18n.getCurrentLanguage());
    this.seoService.updateSEO(seoData);
  }

  private async loadInitialData(): Promise<void> {
    try {
      // Load categories and tags in parallel
      const [categories, tags, featured] = await Promise.all([
        this.articleService.getCategories().toPromise(),
        this.articleService.getTags().toPromise(),
        this.articleService.getFeaturedArticles(3).toPromise()
      ]);

      this.categories.set(categories || []);
      this.tags.set(tags || []);
      this.featuredArticles.set(featured || []);

      // Load articles
      await this.loadArticles();
    } catch (error) {
      console.error('Error loading initial data:', error);
    }
  }

  private handleRouteParams(): void {
    this.route.queryParams.subscribe(params => {
      // Update form with query params
      this.filterForm.patchValue({
        search: params['search'] || '',
        category: params['category'] || '',
        language: params['language'] || '',
        resource_type: params['type'] || '',
        ordering: params['sort'] || '-published_at'
      });

      // Update page if specified
      if (params['page']) {
        this.currentPage.set(parseInt(params['page'], 10) || 1);
      }
    });
  }

  private async loadArticles(): Promise<void> {
    this.loading.set(true);
    
    try {
      const filters = this.currentFilters();
      const response = await this.articleService.getArticles(filters).toPromise();
      
      if (response) {
        this.articles.set(response.results || []);
        this.totalArticles.set(response.count || 0);
      }

      // Update URL with current filters
      this.updateUrlParams();
      
      // Update SEO based on current filters
      const seoData = this.seoService.generateArticleListSEO(filters, this.i18n.getCurrentLanguage());
      this.seoService.updateSEO(seoData);
      
    } catch (error) {
      console.error('Error loading articles:', error);
      this.articles.set([]);
      this.totalArticles.set(0);
    } finally {
      this.loading.set(false);
    }
  }

  private updateUrlParams(): void {
    const filters = this.currentFilters();
    const queryParams: any = {};

    if (filters.search) queryParams.search = filters.search;
    if (filters.category) queryParams.category = filters.category;
    if (filters.language) queryParams.language = filters.language;
    if (filters.resource_type) queryParams.type = filters.resource_type;
    if (filters.ordering !== '-published_at') queryParams.sort = filters.ordering;
    if (filters.page && filters.page > 1) queryParams.page = filters.page;

    this.router.navigate([], {
      relativeTo: this.route,
      queryParams,
      queryParamsHandling: 'merge'
    });
  }

  // Event handlers
  onPageChange(page: number): void {
    this.currentPage.set(page);
    this.loadArticles();
    
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  onPageSizeChange(size: number): void {
    this.pageSize.set(size);
    this.currentPage.set(1);
    this.loadArticles();
  }

  onSearch(): void {
    this.currentPage.set(1);
    this.loadArticles();
  }

  onClearFilters(): void {
    this.filterForm.reset({
      search: '',
      category: '',
      language: '',
      resource_type: '',
      ordering: '-published_at'
    });
    this.currentPage.set(1);
  }

  onCategoryClick(category: string): void {
    this.filterForm.patchValue({ category });
  }

  onTagClick(tag: string): void {
    this.filterForm.patchValue({ search: tag });
  }

  // Navigation
  navigateToArticle(article: Article): void {
    const url = this.articleService.getArticleUrl(article);
    this.router.navigate([url]);
  }

  // Utility methods
  getLocalizedTitle(article: Article): string {
    return this.articleService.getLocalizedTitle(article, this.i18n.getCurrentLanguage());
  }

  getLocalizedDescription(article: Article): string {
    return this.articleService.getLocalizedDescription(article, this.i18n.getCurrentLanguage());
  }

  formatExcerpt(article: Article): string {
    return this.articleService.formatExcerpt(article, 120);
  }

  formatDate(dateString: string): string {
    if (!dateString) return '';
    return new Date(dateString).toLocaleDateString(this.i18n.getCurrentLanguage());
  }

  getResourceTypeIcon(type: string): string {
    const icons: { [key: string]: string } = {
      'article': 'file-text',
      'audio': 'sound',
      'video': 'video-camera',
      'document': 'file-pdf'
    };
    return icons[type] || 'file';
  }

  getResourceTypeColor(type: string): string {
    const colors: { [key: string]: string } = {
      'article': 'blue',
      'audio': 'green',
      'video': 'red',
      'document': 'orange'
    };
    return colors[type] || 'default';
  }

  getLanguageFlag(language: string): string {
    const flags: { [key: string]: string } = {
      'ar': '🇸🇦',
      'en': '🇺🇸'
    };
    return flags[language] || '🌐';
  }

  trackByArticleId(index: number, article: Article): string {
    return article.id;
  }

  // Featured article methods
  getFirstFeaturedArticle(): Article | null {
    const featured = this.featuredArticles();
    return featured.length > 0 ? featured[0] : null;
  }

  getOtherFeaturedArticles(): Article[] {
    const featured = this.featuredArticles();
    return featured.slice(1);
  }
}

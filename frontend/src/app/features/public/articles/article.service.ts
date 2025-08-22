import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, BehaviorSubject } from 'rxjs';
import { map, catchError } from 'rxjs/operators';
import { environment } from '../../../../environments/environment';

// Article interfaces
export interface Article {
  id: string;
  title: string;
  title_en?: string;
  title_ar?: string;
  description: string;
  description_en?: string;
  description_ar?: string;
  resource_type: string;
  language: string;
  language_display: string;
  version: string;
  checksum: string;
  publisher: string;
  publisher_name: string;
  publisher_email: string;
  metadata: any;
  is_published: boolean;
  published_at: string;
  distribution_count: number;
  license_count: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  slug?: string;
  excerpt?: string;
  content?: string;
  featured_image?: string;
  tags?: string[];
  category?: string;
}

export interface ArticleListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Article[];
}

export interface ArticleFilters {
  search?: string;
  category?: string;
  tags?: string[];
  language?: string;
  resource_type?: string;
  publisher?: string;
  page?: number;
  page_size?: number;
  ordering?: string;
}

@Injectable({
  providedIn: 'root'
})
export class ArticleService {
  private http = inject(HttpClient);
  private baseUrl = `${environment.apiUrl}/resources`;

  // Loading state
  private loadingSubject = new BehaviorSubject<boolean>(false);
  public loading$ = this.loadingSubject.asObservable();

  // Current filters
  private filtersSubject = new BehaviorSubject<ArticleFilters>({});
  public filters$ = this.filtersSubject.asObservable();

  /**
   * Get list of published articles with pagination and filtering
   */
  getArticles(filters: ArticleFilters = {}): Observable<ArticleListResponse> {
    this.loadingSubject.next(true);
    
    let params = new HttpParams();
    
    // Add filters to params
    if (filters.search) {
      params = params.set('search', filters.search);
    }
    if (filters.category) {
      params = params.set('category', filters.category);
    }
    if (filters.language) {
      params = params.set('language', filters.language);
    }
    if (filters.resource_type) {
      params = params.set('resource_type', filters.resource_type);
    }
    if (filters.publisher) {
      params = params.set('publisher', filters.publisher);
    }
    if (filters.page) {
      params = params.set('page', filters.page.toString());
    }
    if (filters.page_size) {
      params = params.set('page_size', filters.page_size.toString());
    }
    if (filters.ordering) {
      params = params.set('ordering', filters.ordering);
    }
    if (filters.tags && filters.tags.length > 0) {
      filters.tags.forEach(tag => {
        params = params.append('tags', tag);
      });
    }

    // Only show published articles for public view
    params = params.set('is_published', 'true');
    params = params.set('is_active', 'true');

    return this.http.get<ArticleListResponse>(this.baseUrl + '/', { params }).pipe(
      map(response => {
        this.loadingSubject.next(false);
        this.filtersSubject.next(filters);
        return response;
      }),
      catchError(error => {
        this.loadingSubject.next(false);
        console.error('Error fetching articles:', error);
        throw error;
      })
    );
  }

  /**
   * Get a single article by ID
   */
  getArticle(id: string): Observable<Article> {
    this.loadingSubject.next(true);
    
    return this.http.get<Article>(`${this.baseUrl}/${id}/`).pipe(
      map(article => {
        this.loadingSubject.next(false);
        return article;
      }),
      catchError(error => {
        this.loadingSubject.next(false);
        console.error('Error fetching article:', error);
        throw error;
      })
    );
  }

  /**
   * Get article by slug (if available)
   */
  getArticleBySlug(slug: string): Observable<Article> {
    this.loadingSubject.next(true);
    
    const params = new HttpParams().set('slug', slug);
    
    return this.http.get<ArticleListResponse>(this.baseUrl + '/', { params }).pipe(
      map(response => {
        this.loadingSubject.next(false);
        if (response.results && response.results.length > 0) {
          return response.results[0];
        }
        throw new Error('Article not found');
      }),
      catchError(error => {
        this.loadingSubject.next(false);
        console.error('Error fetching article by slug:', error);
        throw error;
      })
    );
  }

  /**
   * Get featured articles
   */
  getFeaturedArticles(limit: number = 5): Observable<Article[]> {
    const params = new HttpParams()
      .set('is_published', 'true')
      .set('is_active', 'true')
      .set('page_size', limit.toString())
      .set('ordering', '-published_at');

    return this.http.get<ArticleListResponse>(this.baseUrl + '/', { params }).pipe(
      map(response => response.results || []),
      catchError(error => {
        console.error('Error fetching featured articles:', error);
        return [];
      })
    );
  }

  /**
   * Get related articles based on tags/category
   */
  getRelatedArticles(articleId: string, limit: number = 3): Observable<Article[]> {
    // First get the current article to find related ones
    return this.getArticle(articleId).pipe(
      map(article => {
        const params = new HttpParams()
          .set('is_published', 'true')
          .set('is_active', 'true')
          .set('page_size', (limit + 1).toString()) // +1 to exclude current article
          .set('ordering', '-published_at');

        // Add category filter if available
        let relatedParams = params;
        if (article.metadata?.category) {
          relatedParams = relatedParams.set('category', article.metadata.category);
        }

        return this.http.get<ArticleListResponse>(this.baseUrl + '/', { params: relatedParams }).pipe(
          map(response => {
            // Filter out the current article and limit results
            return (response.results || [])
              .filter(a => a.id !== articleId)
              .slice(0, limit);
          })
        );
      }),
      catchError(error => {
        console.error('Error fetching related articles:', error);
        return [];
      })
    );
  }

  /**
   * Get available categories
   */
  getCategories(): Observable<string[]> {
    // This would ideally be a separate endpoint, but we'll extract from articles for now
    return this.getArticles({ page_size: 1000 }).pipe(
      map(response => {
        const categories = new Set<string>();
        response.results.forEach(article => {
          if (article.metadata?.category) {
            categories.add(article.metadata.category);
          }
        });
        return Array.from(categories).sort();
      }),
      catchError(error => {
        console.error('Error fetching categories:', error);
        return [];
      })
    );
  }

  /**
   * Get available tags
   */
  getTags(): Observable<string[]> {
    // This would ideally be a separate endpoint, but we'll extract from articles for now
    return this.getArticles({ page_size: 1000 }).pipe(
      map(response => {
        const tags = new Set<string>();
        response.results.forEach(article => {
          if (article.metadata?.tags && Array.isArray(article.metadata.tags)) {
            article.metadata.tags.forEach((tag: string) => tags.add(tag));
          }
        });
        return Array.from(tags).sort();
      }),
      catchError(error => {
        console.error('Error fetching tags:', error);
        return [];
      })
    );
  }

  /**
   * Search articles
   */
  searchArticles(query: string, filters: Omit<ArticleFilters, 'search'> = {}): Observable<ArticleListResponse> {
    return this.getArticles({ ...filters, search: query });
  }

  /**
   * Get current loading state
   */
  isLoading(): boolean {
    return this.loadingSubject.value;
  }

  /**
   * Get current filters
   */
  getCurrentFilters(): ArticleFilters {
    return this.filtersSubject.value;
  }

  /**
   * Update current filters
   */
  updateFilters(filters: ArticleFilters): void {
    this.filtersSubject.next(filters);
  }

  /**
   * Clear all filters
   */
  clearFilters(): void {
    this.filtersSubject.next({});
  }

  /**
   * Generate article slug from title
   */
  generateSlug(title: string): string {
    return title
      .toLowerCase()
      .trim()
      .replace(/[^\w\s-]/g, '') // Remove special characters
      .replace(/[\s_-]+/g, '-') // Replace spaces and underscores with hyphens
      .replace(/^-+|-+$/g, ''); // Remove leading/trailing hyphens
  }

  /**
   * Get article URL
   */
  getArticleUrl(article: Article): string {
    const slug = article.slug || this.generateSlug(article.title);
    return `/articles/${slug}`;
  }

  /**
   * Format article excerpt
   */
  formatExcerpt(article: Article, maxLength: number = 150): string {
    const description = article.description || '';
    if (description.length <= maxLength) {
      return description;
    }
    return description.substring(0, maxLength).trim() + '...';
  }

  /**
   * Get localized title
   */
  getLocalizedTitle(article: Article, locale: string = 'en'): string {
    if (locale === 'ar' && article.title_ar) {
      return article.title_ar;
    }
    if (locale === 'en' && article.title_en) {
      return article.title_en;
    }
    return article.title;
  }

  /**
   * Get localized description
   */
  getLocalizedDescription(article: Article, locale: string = 'en'): string {
    if (locale === 'ar' && article.description_ar) {
      return article.description_ar;
    }
    if (locale === 'en' && article.description_en) {
      return article.description_en;
    }
    return article.description;
  }
}

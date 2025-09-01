import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, BehaviorSubject } from 'rxjs';
import { map, catchError } from 'rxjs/operators';
import { environment } from '../../../environments/environment';

export interface SearchResult {
  id: string;
  title: string;
  description: string;
  resource_type: string;
  language: string;
  publisher_name: string;
  published_at: string;
  metadata: any;
  _formatted?: any; // MeiliSearch formatted results
  _rankingScore?: number;
}

export interface SearchResponse {
  hits: SearchResult[];
  query: string;
  processingTimeMs: number;
  limit: number;
  offset: number;
  estimatedTotalHits: number;
  facetDistribution?: any;
}

export interface SearchFilters {
  query?: string;
  resource_type?: string[];
  language?: string[];
  category?: string[];
  publisher?: string[];
  date_range?: {
    start?: string;
    end?: string;
  };
  limit?: number;
  offset?: number;
  sort?: string[];
  facets?: string[];
}

@Injectable({
  providedIn: 'root'
})
export class SearchService {
  private http = inject(HttpClient);
  private baseUrl = `${environment.apiUrl}/search`;

  // Search state
  private loadingSubject = new BehaviorSubject<boolean>(false);
  public loading$ = this.loadingSubject.asObservable();

  private currentQuerySubject = new BehaviorSubject<string>('');
  public currentQuery$ = this.currentQuerySubject.asObservable();

  /**
   * Perform search with MeiliSearch
   */
  search(filters: SearchFilters = {}): Observable<SearchResponse> {
    this.loadingSubject.next(true);
    
    const searchData = {
      q: filters.query || '',
      limit: filters.limit || 20,
      offset: filters.offset || 0,
      attributesToRetrieve: ['*'],
      attributesToHighlight: ['title', 'description'],
      highlightPreTag: '<mark>',
      highlightPostTag: '</mark>',
      attributesToCrop: ['description'],
      cropLength: 150,
      cropMarker: '...',
      showMatchesPosition: true,
      facets: filters.facets || ['resource_type', 'language', 'category', 'publisher_name'],
      sort: filters.sort || [],
      filter: this.buildFilters(filters)
    };

    return this.http.post<SearchResponse>(`${this.baseUrl}/`, searchData).pipe(
      map(response => {
        this.loadingSubject.next(false);
        this.currentQuerySubject.next(filters.query || '');
        return response;
      }),
      catchError(error => {
        this.loadingSubject.next(false);
        console.error('Search error:', error);
        throw error;
      })
    );
  }

  /**
   * Get search suggestions/autocomplete
   */
  getSuggestions(query: string, limit: number = 5): Observable<string[]> {
    if (!query || query.length < 2) {
      return new Observable(observer => {
        observer.next([]);
        observer.complete();
      });
    }

    const params = new HttpParams()
      .set('q', query)
      .set('limit', limit.toString())
      .set('attributesToRetrieve', 'title')
      .set('attributesToHighlight', 'title');

    return this.http.get<SearchResponse>(`${this.baseUrl}/suggestions/`, { params }).pipe(
      map(response => {
        return response.hits.map(hit => hit.title).slice(0, limit);
      }),
      catchError(error => {
        console.error('Suggestions error:', error);
        return [];
      })
    );
  }

  /**
   * Get popular search terms
   */
  getPopularSearches(): Observable<string[]> {
    return this.http.get<string[]>(`${this.baseUrl}/popular/`).pipe(
      catchError(error => {
        console.error('Popular searches error:', error);
        return [];
      })
    );
  }

  /**
   * Get search facets for filtering
   */
  getFacets(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/facets/`).pipe(
      catchError(error => {
        console.error('Facets error:', error);
        return {};
      })
    );
  }

  /**
   * Get related searches
   */
  getRelatedSearches(query: string): Observable<string[]> {
    const params = new HttpParams().set('q', query);
    
    return this.http.get<string[]>(`${this.baseUrl}/related/`, { params }).pipe(
      catchError(error => {
        console.error('Related searches error:', error);
        return [];
      })
    );
  }

  /**
   * Build MeiliSearch filter string from filters object
   */
  private buildFilters(filters: SearchFilters): string[] {
    const filterStrings: string[] = [];

    if (filters.resource_type && filters.resource_type.length > 0) {
      const types = filters.resource_type.map(type => `"${type}"`).join(' OR ');
      filterStrings.push(`resource_type IN [${types}]`);
    }

    if (filters.language && filters.language.length > 0) {
      const languages = filters.language.map(lang => `"${lang}"`).join(' OR ');
      filterStrings.push(`language IN [${languages}]`);
    }

    if (filters.category && filters.category.length > 0) {
      const categories = filters.category.map(cat => `"${cat}"`).join(' OR ');
      filterStrings.push(`metadata.category IN [${categories}]`);
    }

    if (filters.publisher && filters.publisher.length > 0) {
      const publishers = filters.publisher.map(pub => `"${pub}"`).join(' OR ');
      filterStrings.push(`publisher_name IN [${publishers}]`);
    }

    if (filters.date_range) {
      if (filters.date_range.start) {
        filterStrings.push(`published_at >= ${Math.floor(new Date(filters.date_range.start).getTime() / 1000)}`);
      }
      if (filters.date_range.end) {
        filterStrings.push(`published_at <= ${Math.floor(new Date(filters.date_range.end).getTime() / 1000)}`);
      }
    }

    // Always filter for published and active content
    filterStrings.push('is_published = true');
    filterStrings.push('is_active = true');

    return filterStrings;
  }

  /**
   * Format search results for display
   */
  formatSearchResult(result: SearchResult): SearchResult {
    return {
      ...result,
      title: result._formatted?.title || result.title,
      description: result._formatted?.description || result.description,
    };
  }

  /**
   * Get current loading state
   */
  isLoading(): boolean {
    return this.loadingSubject.value;
  }

  /**
   * Get current query
   */
  getCurrentQuery(): string {
    return this.currentQuerySubject.value;
  }

  /**
   * Clear search state
   */
  clearSearch(): void {
    this.currentQuerySubject.next('');
  }

  /**
   * Track search analytics
   */
  trackSearch(query: string, resultsCount: number): void {
    const analyticsData = {
      query,
      results_count: resultsCount,
      timestamp: new Date().toISOString()
    };

    // Send analytics data (fire and forget)
    this.http.post(`${this.baseUrl}/analytics/`, analyticsData).subscribe({
      next: () => console.log('Search tracked'),
      error: (error) => console.error('Search tracking error:', error)
    });
  }
}

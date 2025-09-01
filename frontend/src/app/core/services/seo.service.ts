import { Injectable, inject } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';
import { Router } from '@angular/router';
import { environment } from '../../../environments/environment';

export interface SEOData {
  title?: string;
  description?: string;
  keywords?: string[];
  image?: string;
  url?: string;
  type?: string;
  locale?: string;
  siteName?: string;
  author?: string;
  publishedTime?: string;
  modifiedTime?: string;
  section?: string;
  tags?: string[];
  twitterCard?: string;
  twitterSite?: string;
  twitterCreator?: string;
}

@Injectable({
  providedIn: 'root'
})
export class SEOService {
  private titleService = inject(Title);
  private metaService = inject(Meta);
  private router = inject(Router);

  private defaultSEO: SEOData = {
    title: 'Itqan CMS - Islamic Content Management System',
    description: 'Discover and access verified Quranic content, translations, and Islamic resources through our specialized content management platform.',
    keywords: ['Islamic', 'Quran', 'Islamic Content', 'CMS', 'Arabic', 'Islamic Resources'],
    image: `${environment.production ? 'https://cms.itqan.dev' : 'http://localhost:4200'}/assets/images/og-default.jpg`,
    type: 'website',
    locale: 'en_US',
    siteName: 'Itqan CMS',
    twitterCard: 'summary_large_image',
    twitterSite: '@ItqanCMS',
  };

  /**
   * Update page SEO metadata
   */
  updateSEO(seoData: Partial<SEOData>): void {
    const data = { ...this.defaultSEO, ...seoData };
    
    // Update title
    if (data.title) {
      this.titleService.setTitle(data.title);
    }

    // Update meta description
    if (data.description) {
      this.metaService.updateTag({ name: 'description', content: data.description });
    }

    // Update keywords
    if (data.keywords && data.keywords.length > 0) {
      this.metaService.updateTag({ name: 'keywords', content: data.keywords.join(', ') });
    }

    // Update canonical URL
    const url = data.url || this.getCurrentUrl();
    this.metaService.updateTag({ rel: 'canonical', href: url });

    // Open Graph tags
    this.metaService.updateTag({ property: 'og:title', content: data.title || this.defaultSEO.title! });
    this.metaService.updateTag({ property: 'og:description', content: data.description || this.defaultSEO.description! });
    this.metaService.updateTag({ property: 'og:image', content: data.image || this.defaultSEO.image! });
    this.metaService.updateTag({ property: 'og:url', content: url });
    this.metaService.updateTag({ property: 'og:type', content: data.type || this.defaultSEO.type! });
    this.metaService.updateTag({ property: 'og:locale', content: data.locale || this.defaultSEO.locale! });
    this.metaService.updateTag({ property: 'og:site_name', content: data.siteName || this.defaultSEO.siteName! });

    // Article-specific Open Graph tags
    if (data.type === 'article') {
      if (data.author) {
        this.metaService.updateTag({ property: 'article:author', content: data.author });
      }
      if (data.publishedTime) {
        this.metaService.updateTag({ property: 'article:published_time', content: data.publishedTime });
      }
      if (data.modifiedTime) {
        this.metaService.updateTag({ property: 'article:modified_time', content: data.modifiedTime });
      }
      if (data.section) {
        this.metaService.updateTag({ property: 'article:section', content: data.section });
      }
      if (data.tags && data.tags.length > 0) {
        // Remove existing article:tag tags
        this.metaService.removeTag('property="article:tag"');
        // Add new tags
        data.tags.forEach(tag => {
          this.metaService.addTag({ property: 'article:tag', content: tag });
        });
      }
    }

    // Twitter Card tags
    this.metaService.updateTag({ name: 'twitter:card', content: data.twitterCard || this.defaultSEO.twitterCard! });
    this.metaService.updateTag({ name: 'twitter:site', content: data.twitterSite || this.defaultSEO.twitterSite! });
    this.metaService.updateTag({ name: 'twitter:title', content: data.title || this.defaultSEO.title! });
    this.metaService.updateTag({ name: 'twitter:description', content: data.description || this.defaultSEO.description! });
    this.metaService.updateTag({ name: 'twitter:image', content: data.image || this.defaultSEO.image! });
    
    if (data.twitterCreator) {
      this.metaService.updateTag({ name: 'twitter:creator', content: data.twitterCreator });
    }

    // Additional meta tags for better SEO
    this.metaService.updateTag({ name: 'robots', content: 'index, follow' });
    this.metaService.updateTag({ name: 'author', content: data.author || 'Itqan CMS' });
    
    // Viewport and mobile optimization
    this.metaService.updateTag({ name: 'viewport', content: 'width=device-width, initial-scale=1.0' });
    this.metaService.updateTag({ name: 'format-detection', content: 'telephone=no' });
  }

  /**
   * Set default SEO for the application
   */
  setDefaultSEO(): void {
    this.updateSEO(this.defaultSEO);
  }

  /**
   * Generate SEO data for article pages
   */
  generateArticleSEO(article: any, locale: string = 'en'): SEOData {
    const title = this.getLocalizedField(article, 'title', locale);
    const description = this.getLocalizedField(article, 'description', locale);
    const slug = this.generateSlug(title);
    
    return {
      title: `${title} | Itqan CMS`,
      description: this.truncateText(description, 160),
      keywords: this.extractKeywords(article),
      image: article.metadata?.featured_image || this.defaultSEO.image,
      url: `${this.getBaseUrl()}/articles/${slug}`,
      type: 'article',
      locale: locale === 'ar' ? 'ar_SA' : 'en_US',
      author: article.publisher_name || 'Itqan CMS',
      publishedTime: article.published_at,
      modifiedTime: article.updated_at,
      section: article.metadata?.category || 'Islamic Content',
      tags: article.metadata?.tags || [],
    };
  }

  /**
   * Generate SEO data for article listing pages
   */
  generateArticleListSEO(filters: any = {}, locale: string = 'en'): SEOData {
    let title = 'Islamic Articles and Resources | Itqan CMS';
    let description = 'Explore our comprehensive collection of verified Islamic articles, Quranic content, and scholarly resources.';

    if (filters.category) {
      title = `${filters.category} Articles | Itqan CMS`;
      description = `Discover articles and resources in the ${filters.category} category from verified Islamic scholars and publishers.`;
    }

    if (filters.search) {
      title = `Search Results for "${filters.search}" | Itqan CMS`;
      description = `Find Islamic articles and resources related to "${filters.search}" in our verified content library.`;
    }

    return {
      title,
      description,
      keywords: ['Islamic Articles', 'Quran', 'Islamic Resources', 'Islamic Content', 'Arabic'],
      url: `${this.getBaseUrl()}/articles`,
      type: 'website',
      locale: locale === 'ar' ? 'ar_SA' : 'en_US',
    };
  }

  /**
   * Generate structured data (JSON-LD) for articles
   */
  generateArticleStructuredData(article: any, locale: string = 'en'): any {
    const title = this.getLocalizedField(article, 'title', locale);
    const description = this.getLocalizedField(article, 'description', locale);
    const slug = this.generateSlug(title);
    
    return {
      '@context': 'https://schema.org',
      '@type': 'Article',
      'headline': title,
      'description': description,
      'image': article.metadata?.featured_image || this.defaultSEO.image,
      'author': {
        '@type': 'Person',
        'name': article.publisher_name || 'Itqan CMS'
      },
      'publisher': {
        '@type': 'Organization',
        'name': 'Itqan CMS',
        'logo': {
          '@type': 'ImageObject',
          'url': `${this.getBaseUrl()}/assets/images/logo.png`
        }
      },
      'datePublished': article.published_at,
      'dateModified': article.updated_at,
      'mainEntityOfPage': {
        '@type': 'WebPage',
        '@id': `${this.getBaseUrl()}/articles/${slug}`
      },
      'keywords': (article.metadata?.tags || []).join(', '),
      'articleSection': article.metadata?.category || 'Islamic Content',
      'inLanguage': locale,
      'isAccessibleForFree': true,
      'about': {
        '@type': 'Thing',
        'name': 'Islamic Content'
      }
    };
  }

  /**
   * Add structured data to page
   */
  addStructuredData(data: any): void {
    // Remove existing structured data
    const existingScript = document.querySelector('script[type="application/ld+json"]');
    if (existingScript) {
      existingScript.remove();
    }

    // Add new structured data
    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.text = JSON.stringify(data);
    document.head.appendChild(script);
  }

  /**
   * Get current URL
   */
  private getCurrentUrl(): string {
    return `${this.getBaseUrl()}${this.router.url}`;
  }

  /**
   * Get base URL
   */
  private getBaseUrl(): string {
    return environment.production ? 'https://cms.itqan.dev' : 'http://localhost:4200';
  }

  /**
   * Get localized field value
   */
  private getLocalizedField(article: any, field: string, locale: string): string {
    const localizedField = `${field}_${locale}`;
    return article[localizedField] || article[field] || '';
  }

  /**
   * Extract keywords from article
   */
  private extractKeywords(article: any): string[] {
    const keywords = [...this.defaultSEO.keywords!];
    
    if (article.metadata?.tags) {
      keywords.push(...article.metadata.tags);
    }
    
    if (article.metadata?.category) {
      keywords.push(article.metadata.category);
    }
    
    if (article.language) {
      keywords.push(article.language);
    }
    
    return [...new Set(keywords)]; // Remove duplicates
  }

  /**
   * Truncate text to specified length
   */
  private truncateText(text: string, maxLength: number): string {
    if (!text || text.length <= maxLength) {
      return text;
    }
    return text.substring(0, maxLength).trim() + '...';
  }

  /**
   * Generate slug from title
   */
  private generateSlug(title: string): string {
    return title
      .toLowerCase()
      .trim()
      .replace(/[^\w\s-]/g, '')
      .replace(/[\s_-]+/g, '-')
      .replace(/^-+|-+$/g, '');
  }

  /**
   * Remove all SEO tags (useful for cleanup)
   */
  clearSEO(): void {
    // Clear Open Graph tags
    this.metaService.removeTag('property^="og:"');
    
    // Clear Twitter tags
    this.metaService.removeTag('name^="twitter:"');
    
    // Clear Article tags
    this.metaService.removeTag('property^="article:"');
    
    // Clear structured data
    const structuredData = document.querySelector('script[type="application/ld+json"]');
    if (structuredData) {
      structuredData.remove();
    }
  }

  /**
   * Update page language
   */
  updateLanguage(locale: string): void {
    document.documentElement.lang = locale;
    document.documentElement.dir = locale === 'ar' ? 'rtl' : 'ltr';
    
    // Update Open Graph locale
    this.metaService.updateTag({ 
      property: 'og:locale', 
      content: locale === 'ar' ? 'ar_SA' : 'en_US' 
    });
  }
}

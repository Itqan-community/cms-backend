"use client";

import { useState, useEffect } from 'react';
import { useAuth } from '@/components/providers/auth0-integrated-provider';
import { AssetCard } from './asset-card';
import { FiltersSidebar } from './filters-sidebar';
import { SearchBar } from './search-bar';
import { Pagination } from './pagination';
import type { Dictionary, Locale } from '@/lib/i18n/types';
import { logical, layoutPatterns, typography } from '@/lib/styles/logical';
import { cn } from '@/lib/utils';
import { Loader2, Filter } from 'lucide-react';
import { Button } from '@/components/ui/button';

// Mock data types based on API contract
interface AssetViewModel {
  id: string;
  title: string;
  description: string;
  thumbnail_url?: string;
  publisher: {
    id: string;
    name: string;
    avatar_url?: string;
    verified?: boolean;
  };
  category: string;
  tags: string[];
  format: string;
  language: string;
  license: {
    type: string;
    name: string;
    url: string;
  };
  stats: {
    downloads: number;
    size_mb: number;
    version: string;
  };
  created_at: string;
  updated_at: string;
  access_required: boolean;
  has_access: boolean;
}

interface FilterOption {
  value: string;
  label: string;
  count: number;
}

interface FiltersState {
  categories: string[];
  formats: string[];
  languages: string[];
  licenses: string[];
}

interface PaginationInfo {
  page: number;
  per_page: number;
  total: number;
  pages: number;
  has_next: boolean;
  has_prev: boolean;
}

interface DashboardContentProps {
  dict: Dictionary;
  locale: Locale;
}

// Mock data for demonstration
const mockAssets: AssetViewModel[] = [
  {
    id: "asset-1",
    title: "Complete Quran Text - Uthmani Script",
    description: "Full Quranic text in Uthmani script with verse indexing and metadata for developers",
    thumbnail_url: undefined,
    publisher: {
      id: "pub-1",
      name: "Quran Foundation",
      verified: true
    },
    category: "quran",
    tags: ["quran", "uthmani", "arabic", "text"],
    format: "json",
    language: "ar",
    license: {
      type: "cc0",
      name: "CC0 - Public Domain",
      url: "https://creativecommons.org/publicdomain/zero/1.0/"
    },
    stats: {
      downloads: 1250,
      size_mb: 2.5,
      version: "1.0.0"
    },
    created_at: "2024-01-15T10:30:00Z",
    updated_at: "2024-01-20T14:20:00Z",
    access_required: false,
    has_access: true
  },
  {
    id: "asset-2",
    title: "Sahih Bukhari Hadith Collection",
    description: "Complete collection of authentic hadiths from Sahih Bukhari with Arabic text and English translations",
    thumbnail_url: undefined,
    publisher: {
      id: "pub-2",
      name: "Islamic Heritage Foundation",
      verified: true
    },
    category: "hadith",
    tags: ["hadith", "bukhari", "arabic", "english"],
    format: "xml",
    language: "ar",
    license: {
      type: "cc-by",
      name: "CC BY - Attribution",
      url: "https://creativecommons.org/licenses/by/4.0/"
    },
    stats: {
      downloads: 890,
      size_mb: 15.2,
      version: "2.1.0"
    },
    created_at: "2024-01-10T08:00:00Z",
    updated_at: "2024-01-22T16:45:00Z",
    access_required: false,
    has_access: true
  }
];

const mockFilters = {
  categories: [
    { value: "quran", label: "Quran", count: 45 },
    { value: "hadith", label: "Hadith", count: 32 },
    { value: "tafsir", label: "Tafsir", count: 18 },
    { value: "fiqh", label: "Fiqh", count: 12 }
  ],
  formats: [
    { value: "json", label: "JSON", count: 67 },
    { value: "xml", label: "XML", count: 34 },
    { value: "csv", label: "CSV", count: 23 },
    { value: "audio", label: "Audio", count: 15 }
  ],
  languages: [
    { value: "ar", label: "Arabic", count: 89 },
    { value: "en", label: "English", count: 67 },
    { value: "ur", label: "Urdu", count: 23 }
  ],
  licenses: [
    { value: "cc0", label: "CC0", count: 78 },
    { value: "cc-by", label: "CC BY", count: 45 },
    { value: "cc-by-sa", label: "CC BY-SA", count: 23 }
  ]
};

export function DashboardContent({ dict, locale }: DashboardContentProps) {
  const { user } = useAuth();
  const [assets, setAssets] = useState<AssetViewModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filters, setFilters] = useState<FiltersState>({
    categories: [],
    formats: [],
    languages: [],
    licenses: []
  });
  const [pagination, setPagination] = useState<PaginationInfo>({
    page: 1,
    per_page: 20,
    total: 156,
    pages: 8,
    has_next: true,
    has_prev: false
  });
  const [showMobileFilters, setShowMobileFilters] = useState(false);

  // Simulate API call
  useEffect(() => {
    const fetchAssets = async () => {
      setLoading(true);
      // Simulate API delay
      await new Promise(resolve => setTimeout(resolve, 1000));
      setAssets(mockAssets);
      setLoading(false);
    };

    fetchAssets();
  }, [searchQuery, filters, pagination.page]);

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    setPagination(prev => ({ ...prev, page: 1 }));
  };

  const handleFiltersChange = (newFilters: FiltersState) => {
    setFilters(newFilters);
    setPagination(prev => ({ ...prev, page: 1 }));
  };

  const handlePageChange = (page: number) => {
    setPagination(prev => ({ ...prev, page }));
  };

  const handleDownload = async (assetId: string) => {
    // Implement download logic
    console.log('Downloading asset:', assetId);
  };

  const handleViewDetails = (assetId: string) => {
    // Navigate to asset details page
    console.log('Viewing details for asset:', assetId);
  };

  const handleRequestAccess = (assetId: string) => {
    // Show access request modal
    console.log('Requesting access for asset:', assetId);
  };

  if (!user) {
    return null;
  }

  return (
    <div className={cn("min-h-screen bg-background")}>
      <div className="container mx-auto py-6 space-y-6">
        {/* Header */}
        <div className={cn("space-y-2", logical.paddingInline('4'))}>
          <h1 className={cn(typography.heading, "text-3xl font-bold text-foreground")}>
            {dict.dashboard.title}
          </h1>
          <p className="text-muted-foreground">
            {locale === 'ar' 
              ? `أهلاً وسهلاً، ${user.firstName} ${user.lastName}` 
              : `Welcome, ${user.firstName} ${user.lastName}`
            }
          </p>
        </div>

        {/* Search Bar */}
        <div className={cn(logical.paddingInline('4'))}>
          <SearchBar
            dict={dict}
            locale={locale}
            value={searchQuery}
            onChange={setSearchQuery}
            onSearch={handleSearch}
          />
        </div>

        {/* Main Content */}
        <div className={cn(
          "grid grid-cols-1 lg:grid-cols-4 gap-6",
          logical.paddingInline('4')
        )}>
          {/* Filters Sidebar - Desktop */}
          <div className="hidden lg:block">
            <FiltersSidebar
              dict={dict}
              locale={locale}
              filters={filters}
              availableFilters={mockFilters}
              onFiltersChange={handleFiltersChange}
            />
          </div>

          {/* Mobile Filters Toggle */}
          <div className="lg:hidden">
            <Button
              variant="outline"
              onClick={() => setShowMobileFilters(!showMobileFilters)}
              className="w-full mb-4"
            >
              <Filter className="size-4 me-2" />
              {dict.dashboard.filters}
            </Button>
            
            {showMobileFilters && (
              <div className="mb-6">
                <FiltersSidebar
                  dict={dict}
                  locale={locale}
                  filters={filters}
                  availableFilters={mockFilters}
                  onFiltersChange={handleFiltersChange}
                />
              </div>
            )}
          </div>

          {/* Assets Grid */}
          <div className="lg:col-span-3 space-y-6">
            {/* Results header */}
            <div className={cn(layoutPatterns.spaceBetween, "items-center")}>
              <h2 className={cn(typography.heading, "text-xl font-semibold")}>
                {dict.dashboard.assets.title}
              </h2>
              <p className="text-sm text-muted-foreground">
                {pagination.total.toLocaleString(locale === 'ar' ? 'ar-SA' : 'en-US')} {dict.dashboard.results}
              </p>
            </div>

            {/* Loading state */}
            {loading && (
              <div className="flex items-center justify-center py-12">
                <div className="flex items-center gap-3">
                  <Loader2 className="size-6 animate-spin text-primary" />
                  <span className="text-muted-foreground">{dict.dashboard.loading}</span>
                </div>
              </div>
            )}

            {/* Assets grid */}
            {!loading && assets.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {assets.map((asset) => (
                  <AssetCard
                    key={asset.id}
                    asset={asset}
                    dict={dict}
                    locale={locale}
                    onDownload={handleDownload}
                    onViewDetails={handleViewDetails}
                    onRequestAccess={handleRequestAccess}
                  />
                ))}
              </div>
            )}

            {/* No results */}
            {!loading && assets.length === 0 && (
              <div className="text-center py-12">
                <p className="text-muted-foreground text-lg mb-2">
                  {dict.dashboard.noResults}
                </p>
                <p className="text-muted-foreground text-sm">
                  {locale === 'ar' 
                    ? 'جرب تغيير مصطلحات البحث أو المرشحات'
                    : 'Try adjusting your search terms or filters'
                  }
                </p>
              </div>
            )}

            {/* Pagination */}
            {!loading && assets.length > 0 && (
              <Pagination
                dict={dict}
                locale={locale}
                pagination={pagination}
                onPageChange={handlePageChange}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

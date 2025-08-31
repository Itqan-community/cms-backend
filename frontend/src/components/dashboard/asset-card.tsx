"use client";

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import type { Dictionary, Locale } from '@/lib/i18n/types';
import { logical, spacing, typography } from '@/lib/styles/logical';
import { cn } from '@/lib/utils';
import { Download, Eye, Calendar, User, FileText, Globe, Shield } from 'lucide-react';

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

interface AssetCardProps {
  asset: AssetViewModel;
  dict: Dictionary;
  locale: Locale;
  onDownload?: (assetId: string) => Promise<void>;
  onViewDetails?: (assetId: string) => void;
  onRequestAccess?: (assetId: string) => void;
  className?: string;
}

export function AssetCard({ 
  asset, 
  dict, 
  locale, 
  onDownload, 
  onViewDetails, 
  onRequestAccess,
  className 
}: AssetCardProps) {
  const formatFileSize = (sizeInMB: number): string => {
    if (sizeInMB < 1) {
      return `${Math.round(sizeInMB * 1024)} KB`;
    }
    return `${sizeInMB.toFixed(1)} MB`;
  };

  const formatDownloadCount = (count: number): string => {
    if (count >= 1000) {
      return `${(count / 1000).toFixed(1)}K`;
    }
    return count.toString();
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleDateString(locale === 'ar' ? 'ar-SA' : 'en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  const getCategoryLabel = (category: string): string => {
    const categoryKey = category as keyof typeof dict.categories;
    return dict.categories?.[categoryKey] || category;
  };

  const getFormatLabel = (format: string): string => {
    const formatKey = format as keyof typeof dict.formats;
    return dict.formats?.[formatKey] || format.toUpperCase();
  };

  const getLicenseLabel = (licenseType: string): string => {
    const licenseKey = licenseType as keyof typeof dict.licenses;
    return dict.licenses?.[licenseKey] || asset.license.name;
  };

  const handleDownload = async () => {
    if (onDownload) {
      await onDownload(asset.id);
    }
  };

  const handleViewDetails = () => {
    if (onViewDetails) {
      onViewDetails(asset.id);
    }
  };

  const handleRequestAccess = () => {
    if (onRequestAccess) {
      onRequestAccess(asset.id);
    }
  };

  return (
    <Card className={cn(
      "group hover:shadow-lg transition-all duration-200 border-border/50 hover:border-border",
      "bg-card hover:bg-card/80",
      className
    )}>
      <CardHeader className={cn("space-y-3 py-4", logical.paddingInline('4'))}>
        {/* Asset thumbnail and basic info */}
        <div className={cn("flex items-start", spacing.gapMd)}>
          {/* Thumbnail */}
          <div className="size-16 rounded-lg bg-muted flex items-center justify-center flex-shrink-0 overflow-hidden">
            {asset.thumbnail_url ? (
              <img 
                src={asset.thumbnail_url} 
                alt={asset.title}
                className="size-full object-cover"
              />
            ) : (
              <FileText className="size-8 text-muted-foreground" />
            )}
          </div>

          {/* Title and description */}
          <div className="flex-1 min-w-0">
            <h3 className={cn(
              typography.heading,
              "text-lg font-semibold text-foreground line-clamp-2 group-hover:text-primary transition-colors"
            )}>
              {asset.title}
            </h3>
            <p className={cn(
              typography.paragraph,
              "text-sm text-muted-foreground line-clamp-2 mt-1"
            )}>
              {asset.description}
            </p>
          </div>
        </div>

        {/* Publisher info */}
        <div className={cn("flex items-start", spacing.gapSm, "text-sm text-muted-foreground")}>
          <User className="size-4 flex-shrink-0" />
          <span className="font-medium text-foreground">{asset.publisher.name}</span>
          {asset.publisher.verified && (
            <Shield className="size-4 text-primary" />
          )}
        </div>
      </CardHeader>

      <CardContent className={cn("space-y-4 pb-4", logical.paddingInline('4'))}>
        {/* Metadata tags */}
        <div className="flex flex-wrap gap-2">
          {/* Category */}
          <span className="inline-flex items-center px-2 py-1 rounded-md bg-primary/10 text-primary text-xs font-medium">
            {getCategoryLabel(asset.category)}
          </span>
          
          {/* Format */}
          <span className="inline-flex items-center px-2 py-1 rounded-md bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs font-medium">
            {getFormatLabel(asset.format)}
          </span>
          
          {/* Language */}
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 text-xs font-medium">
            <Globe className="size-3" />
            {asset.language.toUpperCase()}
          </span>
        </div>

        {/* Stats */}
        <div className={cn(
          "grid grid-cols-3 gap-4 text-xs text-muted-foreground py-2 border-t border-border/50"
        )}>
          <div className={cn("flex items-center", spacing.gapXs)}>
            <Download className="size-3" />
            <span>{formatDownloadCount(asset.stats.downloads)}</span>
          </div>
          <div className={cn("flex items-center", spacing.gapXs)}>
            <FileText className="size-3" />
            <span>{formatFileSize(asset.stats.size_mb)}</span>
          </div>
          <div className={cn("flex items-center", spacing.gapXs)}>
            <Calendar className="size-3" />
            <span>{formatDate(asset.created_at)}</span>
          </div>
        </div>

        {/* License info */}
        <div className={cn(
          "flex items-center justify-between text-xs py-2 border-t border-border/50"
        )}>
          <span className="text-muted-foreground">
            {dict.dashboard.assets.license}: {getLicenseLabel(asset.license.type)}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleViewDetails}
            className="h-auto p-1 text-xs text-primary hover:text-primary/80"
          >
            <Eye className="size-3 me-1" />
            {dict.dashboard.assets.viewDetails}
          </Button>
        </div>

        {/* Action buttons */}
        <div className={cn("flex gap-2 pt-2")}>
          {asset.has_access ? (
            <Button
              onClick={handleDownload}
              size="sm"
              className="flex-1"
            >
              <Download className="size-4 me-2" />
              {dict.dashboard.assets.download}
            </Button>
          ) : (
            <Button
              onClick={handleRequestAccess}
              variant="outline"
              size="sm"
              className="flex-1"
            >
              {dict.dashboard.assets.requestAccess}
            </Button>
          )}
          
          <Button
            onClick={handleViewDetails}
            variant="outline"
            size="sm"
          >
            <Eye className="size-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

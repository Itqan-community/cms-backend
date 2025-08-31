"use client";

import { Button } from '@/components/ui/button';
import type { Dictionary, Locale } from '@/lib/i18n/types';
import { logical, layoutPatterns, spacing, typography } from '@/lib/styles/logical';
import { cn } from '@/lib/utils';
import { ChevronLeft, ChevronRight, MoreHorizontal } from 'lucide-react';

interface PaginationInfo {
  page: number;
  per_page: number;
  total: number;
  pages: number;
  has_next: boolean;
  has_prev: boolean;
}

interface PaginationProps {
  dict: Dictionary;
  locale: Locale;
  pagination: PaginationInfo;
  onPageChange: (page: number) => void;
  className?: string;
}

export function Pagination({
  dict,
  locale,
  pagination,
  onPageChange,
  className
}: PaginationProps) {
  const { page, per_page, total, pages, has_next, has_prev } = pagination;

  // Calculate the range of items being shown
  const startItem = (page - 1) * per_page + 1;
  const endItem = Math.min(page * per_page, total);

  // Generate page numbers to show
  const getVisiblePages = (): (number | 'ellipsis')[] => {
    const visiblePages: (number | 'ellipsis')[] = [];
    const maxVisiblePages = 7;
    
    if (pages <= maxVisiblePages) {
      // Show all pages if total pages is small
      for (let i = 1; i <= pages; i++) {
        visiblePages.push(i);
      }
    } else {
      // Always show first page
      visiblePages.push(1);
      
      if (page <= 4) {
        // Near the beginning
        for (let i = 2; i <= 5; i++) {
          visiblePages.push(i);
        }
        visiblePages.push('ellipsis');
        visiblePages.push(pages);
      } else if (page >= pages - 3) {
        // Near the end
        visiblePages.push('ellipsis');
        for (let i = pages - 4; i <= pages; i++) {
          visiblePages.push(i);
        }
      } else {
        // In the middle
        visiblePages.push('ellipsis');
        for (let i = page - 1; i <= page + 1; i++) {
          visiblePages.push(i);
        }
        visiblePages.push('ellipsis');
        visiblePages.push(pages);
      }
    }
    
    return visiblePages;
  };

  const visiblePages = getVisiblePages();

  if (pages <= 1) {
    return null;
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Results summary */}
      <div className={cn(
        "text-sm text-muted-foreground text-center",
        typography.paragraph
      )}>
        {dict.dashboard.pagination.showing} {startItem.toLocaleString(locale === 'ar' ? 'ar-SA' : 'en-US')} {dict.dashboard.pagination.to} {endItem.toLocaleString(locale === 'ar' ? 'ar-SA' : 'en-US')} {dict.dashboard.pagination.of} {total.toLocaleString(locale === 'ar' ? 'ar-SA' : 'en-US')} {dict.dashboard.pagination.total}
      </div>

      {/* Pagination controls */}
      <div className={cn(
        "flex items-center justify-center",
        spacing.gapSm
      )}>
        {/* Previous button */}
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(page - 1)}
          disabled={!has_prev}
          className="flex items-center gap-1"
        >
          <ChevronLeft className="size-4" />
          <span className="hidden sm:inline">
            {dict.dashboard.pagination.previous}
          </span>
        </Button>

        {/* Page numbers */}
        <div className={cn("flex items-center", spacing.gapXs)}>
          {visiblePages.map((pageNum, index) => {
            if (pageNum === 'ellipsis') {
              return (
                <div
                  key={`ellipsis-${index}`}
                  className="flex items-center justify-center size-9"
                >
                  <MoreHorizontal className="size-4 text-muted-foreground" />
                </div>
              );
            }

            const isCurrentPage = pageNum === page;

            return (
              <Button
                key={pageNum}
                variant={isCurrentPage ? "default" : "outline"}
                size="sm"
                onClick={() => onPageChange(pageNum)}
                className={cn(
                  "size-9 p-0",
                  isCurrentPage && "bg-primary text-primary-foreground"
                )}
              >
                {pageNum.toLocaleString(locale === 'ar' ? 'ar-SA' : 'en-US')}
              </Button>
            );
          })}
        </div>

        {/* Next button */}
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(page + 1)}
          disabled={!has_next}
          className="flex items-center gap-1"
        >
          <span className="hidden sm:inline">
            {dict.dashboard.pagination.next}
          </span>
          <ChevronRight className="size-4" />
        </Button>
      </div>

      {/* Mobile-friendly page info */}
      <div className={cn(
        "sm:hidden text-center text-sm text-muted-foreground",
        typography.paragraph
      )}>
        {dict.dashboard.pagination.page} {page.toLocaleString(locale === 'ar' ? 'ar-SA' : 'en-US')} {dict.dashboard.pagination.of} {pages.toLocaleString(locale === 'ar' ? 'ar-SA' : 'en-US')}
      </div>
    </div>
  );
}

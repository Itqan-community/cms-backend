"use client";

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { Dictionary, Locale } from '@/lib/i18n/types';
import { logical, layoutPatterns, spacing, typography } from '@/lib/styles/logical';
import { cn } from '@/lib/utils';
import { X, ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';

interface FilterOption {
  value: string;
  label: string;
  count: number;
}

interface FilterSection {
  key: string;
  title: string;
  options: FilterOption[];
  multiSelect?: boolean;
}

interface FiltersState {
  categories: string[];
  formats: string[];
  languages: string[];
  licenses: string[];
}

interface FiltersSidebarProps {
  dict: Dictionary;
  locale: Locale;
  filters: FiltersState;
  availableFilters: {
    categories: FilterOption[];
    formats: FilterOption[];
    languages: FilterOption[];
    licenses: FilterOption[];
  };
  onFiltersChange: (filters: FiltersState) => void;
  className?: string;
}

export function FiltersSidebar({
  dict,
  locale,
  filters,
  availableFilters,
  onFiltersChange,
  className
}: FiltersSidebarProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(['categories', 'formats', 'languages', 'licenses'])
  );

  const toggleSection = (sectionKey: string) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(sectionKey)) {
      newExpanded.delete(sectionKey);
    } else {
      newExpanded.add(sectionKey);
    }
    setExpandedSections(newExpanded);
  };

  const handleFilterChange = (
    filterType: keyof FiltersState,
    value: string,
    checked: boolean
  ) => {
    const currentValues = filters[filterType];
    let newValues: string[];

    if (checked) {
      newValues = [...currentValues, value];
    } else {
      newValues = currentValues.filter(v => v !== value);
    }

    onFiltersChange({
      ...filters,
      [filterType]: newValues
    });
  };

  const clearAllFilters = () => {
    onFiltersChange({
      categories: [],
      formats: [],
      languages: [],
      licenses: []
    });
  };

  const hasActiveFilters = Object.values(filters).some(arr => arr.length > 0);

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
    return dict.licenses?.[licenseKey] || licenseType;
  };

  const filterSections: FilterSection[] = [
    {
      key: 'categories',
      title: dict.dashboard.categories,
      options: availableFilters.categories.map(cat => ({
        ...cat,
        label: getCategoryLabel(cat.value)
      })),
      multiSelect: true
    },
    {
      key: 'formats',
      title: dict.dashboard.formats,
      options: availableFilters.formats.map(format => ({
        ...format,
        label: getFormatLabel(format.value)
      })),
      multiSelect: true
    },
    {
      key: 'languages',
      title: dict.dashboard.languages,
      options: availableFilters.languages.map(lang => ({
        ...lang,
        label: lang.value.toUpperCase()
      })),
      multiSelect: true
    },
    {
      key: 'licenses',
      title: dict.dashboard.licenses,
      options: availableFilters.licenses.map(license => ({
        ...license,
        label: getLicenseLabel(license.value)
      })),
      multiSelect: true
    }
  ];

  return (
    <div className={cn("space-y-4", className)}>
      {/* Header with clear filters */}
      <Card>
        <CardHeader className={cn("py-4", logical.paddingInline('4'))}>
          <div className={cn(layoutPatterns.spaceBetween)}>
            <CardTitle className={cn(typography.heading, "text-lg")}>
              {dict.dashboard.filters}
            </CardTitle>
            {hasActiveFilters && (
              <Button
                variant="ghost"
                size="sm"
                onClick={clearAllFilters}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                <X className="size-3 me-1" />
                {dict.dashboard.clearFilters}
              </Button>
            )}
          </div>
        </CardHeader>
      </Card>

      {/* Filter sections */}
      {filterSections.map((section) => (
        <Card key={section.key}>
          <CardHeader 
            className={cn(
              "cursor-pointer hover:bg-muted/50 transition-colors py-3",
              logical.paddingInline('4')
            )}
            onClick={() => toggleSection(section.key)}
          >
            <div className={cn(layoutPatterns.spaceBetween)}>
              <CardTitle className={cn(typography.heading, "text-sm font-medium")}>
                {section.title}
              </CardTitle>
              {expandedSections.has(section.key) ? (
                <ChevronUp className="size-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="size-4 text-muted-foreground" />
              )}
            </div>
          </CardHeader>

          {expandedSections.has(section.key) && (
            <CardContent className={cn(
              "space-y-2 pb-4",
              logical.paddingInline('4')
            )}>
              {section.options.map((option) => {
                const isChecked = filters[section.key as keyof FiltersState].includes(option.value);
                
                return (
                  <label
                    key={option.value}
                    className={cn(
                      "flex items-center gap-3 cursor-pointer hover:bg-muted/30 rounded-md p-2 transition-colors"
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={(e) => handleFilterChange(
                        section.key as keyof FiltersState,
                        option.value,
                        e.target.checked
                      )}
                      className="size-4 rounded border-border text-primary focus:ring-primary focus:ring-offset-0"
                    />
                    <div className="flex-1 min-w-0">
                      <div className={cn(layoutPatterns.spaceBetween, "items-center")}>
                        <span className="text-sm text-foreground truncate">
                          {option.label}
                        </span>
                        <span className="text-xs text-muted-foreground flex-shrink-0 ms-2">
                          ({option.count})
                        </span>
                      </div>
                    </div>
                  </label>
                );
              })}

              {section.options.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-4">
                  {dict.dashboard.noResults}
                </p>
              )}
            </CardContent>
          )}
        </Card>
      ))}
    </div>
  );
}

"use client";

import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import type { Dictionary, Locale } from '@/lib/i18n/types';
import { logical, layoutPatterns, spacing } from '@/lib/styles/logical';
import { cn } from '@/lib/utils';
import { Search, X } from 'lucide-react';
import { useState, useEffect } from 'react';

interface SearchBarProps {
  dict: Dictionary;
  locale: Locale;
  value: string;
  onChange: (value: string) => void;
  onSearch: (query: string) => void;
  placeholder?: string;
  className?: string;
}

export function SearchBar({
  dict,
  locale,
  value,
  onChange,
  onSearch,
  placeholder,
  className
}: SearchBarProps) {
  const [localValue, setLocalValue] = useState(value);

  useEffect(() => {
    setLocalValue(value);
  }, [value]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    setLocalValue(newValue);
    onChange(newValue);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch(localValue);
  };

  const handleClear = () => {
    setLocalValue('');
    onChange('');
    onSearch('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      onSearch(localValue);
    }
  };

  return (
    <form onSubmit={handleSubmit} className={cn("relative", className)}>
      <div className={cn(
        "relative flex items-center",
        spacing.gapSm
      )}>
        {/* Search input */}
        <div className="relative flex-1">
          <div className="absolute inset-y-0 start-0 flex items-center pointer-events-none ps-3">
            <Search className="size-4 text-muted-foreground" />
          </div>
          
          <Input
            type="text"
            value={localValue}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder={placeholder || dict.dashboard.searchPlaceholder}
            className={cn(
              "w-full bg-background border-border ps-10",
              localValue && "pe-10"
            )}
          />

          {/* Clear button */}
          {localValue && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleClear}
              className="absolute inset-y-0 end-0 h-auto p-0 hover:bg-transparent size-8 flex items-center justify-center pe-1"
            >
              <X className="size-4 text-muted-foreground hover:text-foreground" />
            </Button>
          )}
        </div>

        {/* Search button */}
        <Button
          type="submit"
          size="sm"
          className="flex-shrink-0"
        >
          <Search className="size-4 me-2" />
          {dict.dashboard.search}
        </Button>
      </div>
    </form>
  );
}

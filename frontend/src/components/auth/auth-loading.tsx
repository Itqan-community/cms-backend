"use client";

import { logical } from '@/lib/styles/logical';
import { cn } from '@/lib/utils';

interface AuthLoadingProps {
  message?: string;
}

export function AuthLoading({ message = "Loading..." }: AuthLoadingProps) {
  return (
    <div className={cn(
      "min-h-screen bg-background flex items-center justify-center",
      logical.paddingInline('4')
    )}>
      <div className="text-center space-y-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
        <p className="text-muted-foreground text-sm">{message}</p>
      </div>
    </div>
  );
}

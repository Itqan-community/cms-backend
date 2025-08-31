"use client";

import { useRouter, usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Languages } from "lucide-react";
import { getOppositeLocale, localeNames } from "@/lib/i18n/utils";
import type { Locale } from "@/lib/i18n/types";
import { cn } from "@/lib/utils";

interface LanguageSwitcherProps {
  currentLocale: Locale;
}

export function LanguageSwitcher({ currentLocale }: LanguageSwitcherProps) {
  const router = useRouter();
  const pathname = usePathname();

  const switchLanguage = (newLocale: Locale) => {
    // Remove current locale from pathname
    const pathWithoutLocale = pathname.replace(`/${currentLocale}`, '') || '/';
    const newPath = `/${newLocale}${pathWithoutLocale}`;
    router.push(newPath);
  };

  const getLanguageLabel = (locale: Locale) => {
    return localeNames[locale];
  };

  const otherLocale = getOppositeLocale(currentLocale);

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() => switchLanguage(otherLocale)}
      className={cn("gap-2")}
      aria-label={`Switch to ${getLanguageLabel(otherLocale)}`}
    >
      <Languages className="h-4 w-4" />
      <span className="text-sm">
        {getLanguageLabel(otherLocale)}
      </span>
    </Button>
  );
}

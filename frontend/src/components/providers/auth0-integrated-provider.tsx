"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth0 } from '@auth0/auth0-react';
import type { Locale } from '@/lib/i18n/types';
import { AuthLoading } from '@/components/auth/auth-loading';
import { env } from '@/lib/env';

interface User {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  provider: string;
  profileCompleted: boolean;
  auth0Id: string;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  requiresProfileCompletion: boolean;
  loginWithRedirect: (options?: { connection?: string; screen_hint?: 'login' | 'signup' }) => void;
  logout: () => void;
  updateUser: (user: User) => void;
  completeProfile: (profileData: Record<string, unknown>) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
  locale: Locale;
}

export function Auth0IntegratedProvider({ children, locale }: AuthProviderProps) {
  const {
    user: auth0User,
    isAuthenticated: auth0IsAuthenticated,
    isLoading: auth0IsLoading,
    loginWithRedirect: auth0LoginWithRedirect,
    logout: auth0Logout,
    getAccessTokenSilently,
  } = useAuth0();

  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [requiresProfileCompletion, setRequiresProfileCompletion] = useState(false);

  // Initialize user state from localStorage on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      try {
        const storedUser = localStorage.getItem('itqan_user');
        const profileCompleted = localStorage.getItem('itqan_profile_completed');
        
        if (storedUser) {
          const parsedUser = JSON.parse(storedUser);
          setUser(parsedUser);
          setRequiresProfileCompletion(profileCompleted !== '1' && !parsedUser.profileCompleted);
        }
      } catch (error) {
        console.error('Error loading user from localStorage:', error);
      }
    }
  }, []);
  
  const router = useRouter();
  const pathname = usePathname();

  // Helper function to update user state and persist to localStorage
  const persistUserState = (userData: User | null) => {
    setUser(userData);
    if (typeof window !== 'undefined') {
      if (userData) {
        localStorage.setItem('itqan_user', JSON.stringify(userData));
      } else {
        localStorage.removeItem('itqan_user');
        localStorage.removeItem('itqan_profile_completed');
      }
    }
  };

  // Sync Auth0 user with our backend
  useEffect(() => {
    const syncUser = async () => {
      if (auth0IsLoading) return;
      
      setIsLoading(true);
      
      try {
        if (auth0IsAuthenticated && auth0User) {
          // Build email and names with fallback to /userinfo if the connection doesn't expose them by default
          let resolvedEmail: string | undefined = auth0User.email || undefined;
          let resolvedGivenName: string | undefined = auth0User.given_name || undefined;
          let resolvedFamilyName: string | undefined = auth0User.family_name || undefined;
          if (!resolvedEmail || !resolvedGivenName || !resolvedFamilyName) {
            try {
              const token = await getAccessTokenSilently({
                authorizationParams: {
                  scope: 'openid profile email',
                },
              });
              const uiRes = await fetch(`https://${env.NEXT_PUBLIC_AUTH0_DOMAIN}/userinfo`, {
                headers: { Authorization: `Bearer ${token}` },
              });
              if (uiRes.ok) {
                const ui = await uiRes.json();
                resolvedEmail = resolvedEmail || ui.email;
                resolvedGivenName = resolvedGivenName || ui.given_name;
                resolvedFamilyName = resolvedFamilyName || ui.family_name;
                // If provider only returns full name, split it
                if ((!resolvedGivenName || !resolvedFamilyName) && ui.name) {
                  const parts = String(ui.name).trim().split(/\s+/);
                  if (!resolvedGivenName && parts[0]) resolvedGivenName = parts[0];
                  if (!resolvedFamilyName && parts.length > 1) resolvedFamilyName = parts.slice(1).join(' ');
                }
                // As a last resort, use nickname as first name
                if (!resolvedGivenName && ui.nickname) {
                  resolvedGivenName = ui.nickname;
                }
              }
            } catch (e) {
              console.warn('Could not resolve profile from /userinfo:', e);
            }
          }

          // Resolve name fallbacks for providers that don't expose given/family name
          const rawName = auth0User.name || '';
          const nickname = (auth0User as any).nickname as string | undefined;
          const derivedFirst = resolvedGivenName || auth0User.given_name || (rawName ? rawName.split(' ')[0] : (nickname || ''));
          const derivedLast = resolvedFamilyName || auth0User.family_name || (rawName && rawName.includes(' ') ? rawName.split(' ').slice(1).join(' ') : '');

          // Create user data from Auth0 user
          let userData: User = {
            id: auth0User.sub!,
            email: resolvedEmail || '',
            firstName: derivedFirst || '',
            lastName: derivedLast || '',
            provider: 'auth0',
            profileCompleted: false,
            auth0Id: auth0User.sub!,
          };
          
          // Check persisted flag to avoid redirecting again on page refresh
          try {
            const persisted = typeof window !== 'undefined' 
              ? window.localStorage.getItem('itqan_profile_completed')
              : null;
            if (persisted === '1') {
              userData.profileCompleted = true;
            }
          } catch {}

          // Try to fetch authoritative profile state from backend
          try {
            const token = await getAccessTokenSilently({
              authorizationParams: {
                audience: env.NEXT_PUBLIC_AUTH0_AUDIENCE,
                scope: 'openid profile email'
              },
            });

            const meResponse = await fetch(`${env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'}/api/v1/auth/me/`, {
              method: 'GET',
              headers: {
                'Authorization': `Bearer ${token}`,
              },
            });

            if (meResponse.ok) {
              const me = await meResponse.json();
              userData = {
                id: me.id,
                email: me.email || userData.email,
                firstName: me.first_name || userData.firstName,
                lastName: me.last_name || userData.lastName,
                provider: 'auth0',
                profileCompleted: !!me.profile_completed,
                auth0Id: auth0User.sub!,
              };

              persistUserState(userData);
              setRequiresProfileCompletion(!userData.profileCompleted);

              // Persist completion flag for future sessions
              if (typeof window !== 'undefined') {
                if (userData.profileCompleted) {
                  window.localStorage.setItem('itqan_profile_completed', '1');
                } else {
                  window.localStorage.removeItem('itqan_profile_completed');
                }
              }
            } else {
              // Fallback to local userData if backend not reachable
              persistUserState(userData);
              setRequiresProfileCompletion(!userData.profileCompleted);
            }
          } catch (e) {
            // Any token/me request issue: fallback gracefully
            persistUserState(userData);
            setRequiresProfileCompletion(!userData.profileCompleted);
          }
        } else {
          persistUserState(null);
          setRequiresProfileCompletion(false);
        }
      } catch (error) {
        console.error('Error syncing user:', error);
        persistUserState(null);
      } finally {
        setIsLoading(false);
      }
    };

    syncUser();
  }, [auth0IsAuthenticated, auth0User, auth0IsLoading, getAccessTokenSilently]);

  // Handle route protection
  useEffect(() => {
    // Wait for both Auth0 and our internal loading to complete
    if (isLoading || auth0IsLoading) return;

    const isAuthRoute = pathname.includes('/auth/');
    const isHomePage = pathname === `/${locale}` || pathname === `/${locale}/`;
    const isCallbackRoute = pathname.includes('/auth/callback');
    
    // Don't redirect during callback processing if Auth0 is still loading
    if (isCallbackRoute && auth0IsLoading) return;
    
    // If user is authenticated
    if (auth0IsAuthenticated && user) {
      // Special handling for callback route - redirect once authentication is complete
      if (isCallbackRoute) {
        if (requiresProfileCompletion) {
          router.replace(`/${locale}/auth/complete-profile`);
        } else {
          router.replace(`/${locale}/dashboard`);
        }
        return;
      }
      
      // If user needs to complete profile
      if (requiresProfileCompletion && !pathname.includes('/auth/complete-profile')) {
        router.replace(`/${locale}/auth/complete-profile`);
        return;
      }
      
      // If profile is completed and user is on auth pages, redirect to dashboard
      if (!requiresProfileCompletion && isAuthRoute) {
        router.replace(`/${locale}/dashboard`);
        return;
      }
    }
    
    // Only redirect to login if we're sure the user is not authenticated
    // and Auth0 has finished loading (to avoid redirecting during token refresh)
    if (!auth0IsAuthenticated && !auth0IsLoading && !isAuthRoute && !isHomePage) {
      router.replace(`/${locale}/auth/login`);
      return;
    }
  }, [auth0IsAuthenticated, user, requiresProfileCompletion, pathname, locale, router, isLoading, auth0IsLoading]);

  const loginWithRedirect = (options?: { connection?: string; screen_hint?: 'login' | 'signup' }) => {
    auth0LoginWithRedirect({
      authorizationParams: {
        redirect_uri: `${env.NEXT_PUBLIC_APP_URL}/${locale}/auth/callback`,
        audience: env.NEXT_PUBLIC_AUTH0_AUDIENCE,
        scope: 'openid profile email offline_access',
        connection: options?.connection,
        screen_hint: options?.screen_hint,
      },
    });
  };

  const logout = () => {
    // Clear local user state and flags first
    persistUserState(null);
    setRequiresProfileCompletion(false);
    
    auth0Logout({
      logoutParams: {
        returnTo: `${env.NEXT_PUBLIC_APP_URL}/${locale}`,
      },
    });
  };

  const updateUser = (userData: User) => {
    setUser(userData);
    setRequiresProfileCompletion(!userData.profileCompleted);
  };

  const completeProfile = async (profileData: Record<string, unknown>) => {
    try {
      // For now, simulate profile completion without backend call
      // TODO: Re-enable backend integration after fixing JWT token issues
      console.log('Profile data to be saved:', profileData);
      
      // Update user with completed profile
      const token = await getAccessTokenSilently({
        authorizationParams: {
          audience: env.NEXT_PUBLIC_AUTH0_AUDIENCE || undefined,
          scope: 'openid profile email'
        }
      });
      
      console.log('Auth0 token obtained:', token ? 'Token received' : 'No token');
      console.log('Audience used:', env.NEXT_PUBLIC_AUTH0_AUDIENCE);
      console.log('Backend URL:', env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000');
      
      const response = await fetch(`${env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'}/api/v1/auth/complete-profile/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          auth0_id: auth0User?.sub,
          // Prefer Auth0 email if available; otherwise use fallback provided by the form
          email: auth0User?.email || (profileData as any).email,
          first_name: profileData.firstName,
          last_name: profileData.lastName,
          job_title: profileData.jobTitle,
          phone_number: profileData.phoneNumber,
          business_model: profileData.businessModel,
          team_size: profileData.teamSize,
          about_yourself: profileData.aboutYourself,
        }),
      });

      if (response.ok) {
        const backendUser = await response.json();
        const userData: User = {
          id: backendUser.id,
          email: backendUser.email,
          firstName: backendUser.first_name,
          lastName: backendUser.last_name,
          provider: 'auth0',
          profileCompleted: true,
          auth0Id: auth0User?.sub!,
        };
        persistUserState(userData);
        setRequiresProfileCompletion(false);
        
        // Set profile completion flag
        if (typeof window !== 'undefined') {
          localStorage.setItem('itqan_profile_completed', '1');
        }
        
        router.replace(`/${locale}/dashboard`);
      } else {
        const errorText = await response.text();
        console.error('Backend error response:', response.status, errorText);
        let errorData;
        try {
          errorData = JSON.parse(errorText);
        } catch {
          errorData = { error: errorText };
        }
        throw new Error(errorData.error || `Failed to complete profile: ${response.status}`);
      }
    } catch (error) {
      console.error('Error completing profile:', error);
      throw error;
    }
  };

  const value = {
    user,
    isAuthenticated: auth0IsAuthenticated,
    isLoading: isLoading || auth0IsLoading,
    requiresProfileCompletion,
    loginWithRedirect,
    logout,
    updateUser,
    completeProfile,
  };

  // Show loading screen while checking authentication
  if (isLoading || auth0IsLoading) {
    return <AuthLoading message={locale === 'ar' ? 'جاري التحميل...' : 'Loading...'} />;
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an Auth0IntegratedProvider');
  }
  return context;
}

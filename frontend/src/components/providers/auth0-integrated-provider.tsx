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
  loginWithRedirect: () => void;
  logout: () => void;
  updateUser: (user: User) => void;
  completeProfile: (profileData: any) => Promise<void>;
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
  
  const router = useRouter();
  const pathname = usePathname();

  // Sync Auth0 user with our backend
  useEffect(() => {
    const syncUser = async () => {
      if (auth0IsLoading) return;
      
      setIsLoading(true);
      
      try {
        if (auth0IsAuthenticated && auth0User) {
          // Get access token for API calls
          const token = await getAccessTokenSilently();
          
          // Check if user exists in our backend
          const response = await fetch(`${env.NEXT_PUBLIC_BACKEND_URL}/api/v1/auth/me`, {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          });

          if (response.ok) {
            // User exists in backend
            const backendUser = await response.json();
            const userData: User = {
              id: backendUser.id,
              email: backendUser.email,
              firstName: backendUser.first_name,
              lastName: backendUser.last_name,
              provider: 'auth0',
              profileCompleted: backendUser.profile_completed || false,
              auth0Id: auth0User.sub!,
            };
            setUser(userData);
            setRequiresProfileCompletion(!userData.profileCompleted);
          } else if (response.status === 404) {
            // User doesn't exist in backend, needs profile completion
            const userData: User = {
              id: '', // Will be set after profile completion
              email: auth0User.email!,
              firstName: auth0User.given_name || '',
              lastName: auth0User.family_name || '',
              provider: 'auth0',
              profileCompleted: false,
              auth0Id: auth0User.sub!,
            };
            setUser(userData);
            setRequiresProfileCompletion(true);
          } else {
            console.error('Failed to sync user with backend');
            setUser(null);
          }
        } else {
          setUser(null);
          setRequiresProfileCompletion(false);
        }
      } catch (error) {
        console.error('Error syncing user:', error);
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };

    syncUser();
  }, [auth0IsAuthenticated, auth0User, auth0IsLoading, getAccessTokenSilently]);

  // Handle route protection
  useEffect(() => {
    if (isLoading || auth0IsLoading) return;

    const isAuthRoute = pathname.includes('/auth/');
    const isHomePage = pathname === `/${locale}` || pathname === `/${locale}/`;
    
    // If user is authenticated
    if (auth0IsAuthenticated && user) {
      // If user needs to complete profile
      if (requiresProfileCompletion && !pathname.includes('/auth/complete-profile')) {
        router.replace(`/${locale}/auth/complete-profile`);
        return;
      }
      
      // If profile is completed and user is on auth pages, redirect to dashboard/home
      if (!requiresProfileCompletion && isAuthRoute) {
        router.replace(`/${locale}/dashboard`);
        return;
      }
    }
    
    // If user is not authenticated and trying to access protected routes
    if (!auth0IsAuthenticated && !isAuthRoute && !isHomePage) {
      router.replace(`/${locale}/auth/login`);
      return;
    }
  }, [auth0IsAuthenticated, user, requiresProfileCompletion, pathname, locale, router, isLoading, auth0IsLoading]);

  const loginWithRedirect = () => {
    auth0LoginWithRedirect({
      authorizationParams: {
        redirect_uri: `${env.NEXT_PUBLIC_APP_URL}/${locale}/auth/callback`,
      },
    });
  };

  const logout = () => {
    auth0Logout({
      logoutParams: {
        returnTo: `${env.NEXT_PUBLIC_APP_URL}/${locale}`,
      },
    });
    setUser(null);
    setRequiresProfileCompletion(false);
  };

  const updateUser = (userData: User) => {
    setUser(userData);
    setRequiresProfileCompletion(!userData.profileCompleted);
  };

  const completeProfile = async (profileData: any) => {
    try {
      const token = await getAccessTokenSilently();
      
      const response = await fetch(`${env.NEXT_PUBLIC_BACKEND_URL}/api/v1/auth/complete-profile`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          auth0_id: auth0User?.sub,
          email: auth0User?.email,
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
        setUser(userData);
        setRequiresProfileCompletion(false);
        router.replace(`/${locale}/dashboard`);
      } else {
        throw new Error('Failed to complete profile');
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

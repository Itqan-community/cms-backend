'use client';

import { useUser } from '@auth0/nextjs-auth0/client';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

export default function RegisterPage() {
  const { user, isLoading } = useUser();
  const router = useRouter();
  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    phone: '',
    title: '',
    email: '',
    password: ''
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!isLoading && user) {
      // User is already logged in, redirect to dashboard
      router.push('/dashboard');
    }
  }, [user, isLoading, router]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError('');

    try {
      // For now, redirect to Auth0 Universal Login with email pre-filled
      // In a full implementation, we'd use Auth0's database connection signup
      const params = new URLSearchParams({
        screen_hint: 'signup',
        login_hint: formData.email
      });
      
      window.location.href = `/api/auth/login?${params.toString()}`;
    } catch (err) {
      setError('Registration failed. Please try again.');
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '100vh' }}>
        <div className="spinner-border text-itqan-primary" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
      </div>
    );
  }

  if (user) {
    return null; // Will redirect in useEffect
  }

  return (
    <div className="min-vh-100 bg-light d-flex align-items-center justify-content-center">
      <div className="container">
        <div className="row justify-content-center">
          <div className="col-md-6 col-lg-5">
            <div className="text-center mb-4">
              <h2 className="text-itqan-primary fw-bold mb-2">Itqan CMS</h2>
            </div>
            
            <div className="card border-0 shadow-sm">
              <div className="card-header bg-white text-center">
                <h4 className="mb-0">Create Account</h4>
              </div>
              <div className="card-body p-4">
                {error && (
                  <div className="alert alert-danger" role="alert">
                    {error}
                  </div>
                )}

                <form onSubmit={handleSubmit}>
                  <div className="mb-3">
                    <label htmlFor="firstName" className="form-label">First Name</label>
                    <input
                      type="text"
                      className="form-control"
                      id="firstName"
                      name="firstName"
                      placeholder="Ahmed"
                      value={formData.firstName}
                      onChange={handleInputChange}
                      required
                    />
                  </div>

                  <div className="mb-3">
                    <label htmlFor="lastName" className="form-label">Last Name</label>
                    <input
                      type="text"
                      className="form-control"
                      id="lastName"
                      name="lastName"
                      placeholder="AlRajhy"
                      value={formData.lastName}
                      onChange={handleInputChange}
                      required
                    />
                  </div>

                  <div className="mb-3">
                    <label htmlFor="phone" className="form-label">Phone Number</label>
                    <input
                      type="tel"
                      className="form-control"
                      id="phone"
                      name="phone"
                      placeholder="009650000000"
                      value={formData.phone}
                      onChange={handleInputChange}
                      required
                    />
                  </div>

                  <div className="mb-3">
                    <label htmlFor="title" className="form-label">Title</label>
                    <input
                      type="text"
                      className="form-control"
                      id="title"
                      name="title"
                      placeholder="Software Engineer"
                      value={formData.title}
                      onChange={handleInputChange}
                      required
                    />
                  </div>

                  <div className="mb-3">
                    <label htmlFor="email" className="form-label">Email Address</label>
                    <input
                      type="email"
                      className="form-control"
                      id="email"
                      name="email"
                      placeholder="you@example.com"
                      value={formData.email}
                      onChange={handleInputChange}
                      required
                    />
                  </div>

                  <div className="mb-3">
                    <label htmlFor="password" className="form-label">Password</label>
                    <input
                      type="password"
                      className="form-control"
                      id="password"
                      name="password"
                      placeholder="********"
                      value={formData.password}
                      onChange={handleInputChange}
                      required
                      minLength={8}
                    />
                  </div>

                  <button 
                    type="submit" 
                    className="btn btn-itqan-primary w-100"
                    disabled={isSubmitting}
                  >
                    {isSubmitting ? (
                      <>
                        <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                        Creating Account...
                      </>
                    ) : (
                      'Sign Up'
                    )}
                  </button>

                  <div className="text-center mt-3">
                    <small className="text-muted">
                      Already have an account?{' '}
                      <a href="/api/auth/login" className="text-itqan-primary text-decoration-none">
                        Log In
                      </a>
                    </small>
                  </div>
                </form>

                <hr className="my-4" />
                
                <div className="text-center">
                  <p className="text-muted mb-3"><small>Or continue with:</small></p>
                  <div className="d-grid gap-2">
                    <a
                      href="/api/auth/login?connection=github"
                      className="btn btn-dark d-flex align-items-center justify-content-center"
                    >
                      <svg className="me-2" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                        <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.012 8.012 0 0 0 16 8c0-4.42-3.58-8-8-8z"/>
                      </svg>
                      GitHub
                    </a>
                    <a
                      href="/api/auth/login?connection=google-oauth2"
                      className="btn btn-outline-danger d-flex align-items-center justify-content-center"
                    >
                      <svg className="me-2" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                        <path d="M15.545 6.558a9.42 9.42 0 0 1 .139 1.626c0 2.434-.87 4.492-2.384 5.885h.002C11.978 15.292 10.158 16 8 16A8 8 0 1 1 8 0a7.689 7.689 0 0 1 5.352 2.082l-2.284 2.284A4.347 4.347 0 0 0 8 3.166c-2.087 0-3.86 1.408-4.492 3.304a4.792 4.792 0 0 0 0 3.063h.003c.635 1.893 2.405 3.301 4.492 3.301 1.078 0 2.004-.276 2.722-.764h-.003a3.702 3.702 0 0 0 1.599-2.431H8v-3.08h7.545z"/>
                      </svg>
                      Google
                    </a>
                  </div>
                </div>
              </div>
            </div>

            <div className="text-center mt-3">
              <small className="text-muted">
                By creating an account, you agree to our{' '}
                <a href="/terms" className="text-itqan-primary text-decoration-none">Terms of Service</a>
                {' '}and{' '}
                <a href="/privacy" className="text-itqan-primary text-decoration-none">Privacy Policy</a>
              </small>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

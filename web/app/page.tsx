import Link from 'next/link';

export default function HomePage() {
  return (
    <div className="min-vh-100 bg-light">
      {/* Navigation */}
      <nav className="navbar navbar-expand-lg navbar-light bg-white shadow-sm">
        <div className="container">
          <a className="navbar-brand text-itqan-primary fw-bold fs-3" href="/">
            Itqan CMS
          </a>
          <div className="navbar-nav ms-auto">
            <Link href="/register" className="btn btn-itqan-primary me-2">
              Sign Up
            </Link>
            <Link href="/api/auth/login" className="btn btn-outline-secondary">
              Sign In
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <div className="container mt-5">
        <div className="row justify-content-center text-center">
          <div className="col-lg-8">
            <h1 className="display-4 fw-bold text-itqan-dark mb-4">
              Quranic Content Management System
            </h1>
            <p className="lead text-muted mb-4">
              A headless CMS designed to aggregate and distribute verified Quranic content 
              with proper licensing workflows for scholars and developers.
            </p>
            <div className="d-flex gap-3 justify-content-center">
              <Link href="/register" className="btn btn-itqan-primary btn-lg">
                Get Started
              </Link>
              <Link href="/api/docs" className="btn btn-outline-secondary btn-lg">
                API Documentation
              </Link>
            </div>
          </div>
        </div>

        {/* Features */}
        <div className="row mt-5 pt-5">
          <div className="col-md-4 text-center mb-4">
            <div className="card h-100 border-0 shadow-sm">
              <div className="card-body">
                <div className="text-itqan-primary mb-3">
                  <svg width="48" height="48" fill="currentColor" viewBox="0 0 16 16">
                    <path d="M8 4.754a3.246 3.246 0 1 0 0 6.492 3.246 3.246 0 0 0 0-6.492zM5.754 8a2.246 2.246 0 1 1 4.492 0 2.246 2.246 0 0 1-4.492 0z"/>
                    <path d="M9.796 1.343c-.527-1.79-3.065-1.79-3.592 0l-.094.319a.873.873 0 0 1-1.255.52l-.292-.16c-1.64-.892-3.433.902-2.54 2.541l.159.292a.873.873 0 0 1-.52 1.255l-.319.094c-1.79.527-1.79 3.065 0 3.592l.319.094a.873.873 0 0 1 .52 1.255l-.16.292c-.892 1.64.901 3.434 2.541 2.54l.292-.159a.873.873 0 0 1 1.255.52l.094.319c.527 1.79 3.065 1.79 3.592 0l.094-.319a.873.873 0 0 1 1.255-.52l.292.16c1.64.893 3.434-.902 2.54-2.541l-.159-.292a.873.873 0 0 1 .52-1.255l.319-.094c1.79-.527 1.79-3.065 0-3.592l-.319-.094a.873.873 0 0 1-.52-1.255l.16-.292c.893-1.64-.902-3.433-2.541-2.54l-.292.159a.873.873 0 0 1-1.255-.52l-.094-.319zm-2.633.283c.246-.835 1.428-.835 1.674 0l.094.319a1.873 1.873 0 0 0 2.693 1.115l.291-.16c.764-.415 1.6.42 1.184 1.185l-.159.292a1.873 1.873 0 0 0 1.116 2.692l.318.094c.835.246.835 1.428 0 1.674l-.319.094a1.873 1.873 0 0 0-1.115 2.693l.16.291c.415.764-.42 1.6-1.185 1.184l-.291-.159a1.873 1.873 0 0 0-2.693 1.116l-.094.318c-.246.835-1.428.835-1.674 0l-.094-.319a1.873 1.873 0 0 0-2.692-1.115l-.292.16c-.764.415-1.6-.42-1.184-1.185l.159-.291A1.873 1.873 0 0 0 1.945 8.93l-.319-.094c-.835-.246-.835-1.428 0-1.674l.319-.094A1.873 1.873 0 0 0 3.06 4.377l-.16-.292c-.415-.764.42-1.6 1.185-1.184l.292.159a1.873 1.873 0 0 0 2.692-1.115l.094-.319z"/>
                  </svg>
                </div>
                <h5>Content Management</h5>
                <p className="text-muted">
                  Manage Quranic content with proper versioning, review workflows, and multi-language support.
                </p>
              </div>
            </div>
          </div>
          <div className="col-md-4 text-center mb-4">
            <div className="card h-100 border-0 shadow-sm">
              <div className="card-body">
                <div className="text-itqan-primary mb-3">
                  <svg width="48" height="48" fill="currentColor" viewBox="0 0 16 16">
                    <path d="M6 .5a.5.5 0 0 1 .5-.5h3a.5.5 0 0 1 .5.5v1H6v-1zM11 2.5v-1A1.5 1.5 0 0 0 9.5 0h-3A1.5 1.5 0 0 0 5 1.5v1H2.506a.58.58 0 0 0-.01 0H1.5a.5.5 0 0 0 0 1h.538l.853 10.66A2 2 0 0 0 4.885 16h6.23a2 2 0 0 0 1.994-1.84l.853-10.66h.538a.5.5 0 0 0 0-1h-.995a.59.59 0 0 0-.01 0H11zm1.958 1-.846 10.58a1 1 0 0 1-.997.92h-6.23a1 1 0 0 1-.997-.92L3.042 3.5h9.916zm-7.487 1a.5.5 0 0 1 .528.47l.5 8.5a.5.5 0 0 1-.998.06L5 5.03a.5.5 0 0 1 .47-.53Zm5.058 0a.5.5 0 0 1 .47.53l-.5 8.5a.5.5 0 1 1-.998-.06l.5-8.5a.5.5 0 0 1 .528-.47ZM8 4.5a.5.5 0 0 1 .5.5v8.5a.5.5 0 0 1-1 0V5a.5.5 0 0 1 .5-.5Z"/>
                  </svg>
                </div>
                <h5>API Access</h5>
                <p className="text-muted">
                  RESTful and GraphQL APIs with authentication, rate limiting, and comprehensive documentation.
                </p>
              </div>
            </div>
          </div>
          <div className="col-md-4 text-center mb-4">
            <div className="card h-100 border-0 shadow-sm">
              <div className="card-body">
                <div className="text-itqan-primary mb-3">
                  <svg width="48" height="48" fill="currentColor" viewBox="0 0 16 16">
                    <path d="M0 4a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V4Zm2-1a1 1 0 0 0-1 1v.217l7 4.2 7-4.2V4a1 1 0 0 0-1-1H2Zm13 2.383-4.708 2.825L15 11.105V5.383Zm-.034 6.876-5.64-3.471L8 9.583l-1.326-.795-5.64 3.47A1 1 0 0 0 2 13h12a1 1 0 0 0 .966-.741ZM1 11.105l4.708-2.897L1 5.383v5.722Z"/>
                  </svg>
                </div>
                <h5>Licensing & Compliance</h5>
                <p className="text-muted">
                  Built-in licensing workflows ensure proper attribution and compliance for Quranic content usage.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

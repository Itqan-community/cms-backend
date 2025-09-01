# Itqan CMS - Quranic Content Management System

A modern, headless CMS designed to aggregate, license, and distribute verified Quranic content (text, audio, translations, tafsir) to developers and publishers through controlled APIs with proper licensing workflows.

## 🏗️ Architecture

- **Frontend**: Angular 19 (CSR) with NG-ZORRO UI components
- **Backend**: Django 4.2 LTS + Wagtail CMS + Django REST Framework
- **Database**: PostgreSQL 16 with UUID primary keys
- **Search**: MeiliSearch v1.6 for full-text search
- **Cache/Queue**: Redis for caching and Celery task queue
- **Storage**: MinIO (dev) / Alibaba OSS (prod)
- **Auth**: Auth0 (SPA SDK on Angular, OIDC/JWKS on Django)

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 20+ (for local Angular development)
- Python 3.11+ (for local Django development)

### 1. Clone & Setup

```bash
git clone https://github.com/Itqan-community/cms.git
cd cms
cp env.example .env
# Edit .env with your configuration
```

### 2. Start with Docker

```bash
# Start all services
docker-compose -f deployment/docker/docker-compose.yml up -d

# Check service status
docker-compose -f deployment/docker/docker-compose.yml ps

# View logs
docker-compose -f deployment/docker/docker-compose.yml logs -f backend
```

### 3. Access the Application

- **Angular Frontend**: http://localhost:4200
- **Django API**: http://localhost:8000/api/v1/
- **Wagtail Admin**: http://localhost:8000/cms/
- **Django Admin**: http://localhost:8000/django-admin/
- **MeiliSearch**: http://localhost:7700
- **MinIO Console**: http://localhost:9001

## 🔧 Development Setup

### Backend (Django)

```bash
cd backend

# Install dependencies
pip install -r requirements/development.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

### Frontend (Angular)

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run start
```

### Background Tasks (Celery)

```bash
cd backend

# Start Celery worker
celery -A config worker --loglevel=info

# Start Celery beat (for scheduled tasks)
celery -A config beat --loglevel=info
```

## 📁 Project Structure

```
cms/
├── frontend/                 # Angular 19 application
│   ├── src/app/
│   │   ├── core/            # Core services (Auth, HTTP)
│   │   ├── features/        # Feature modules
│   │   │   ├── auth/        # Authentication
│   │   │   ├── dashboard/   # User dashboard
│   │   │   ├── admin/       # Admin panels
│   │   │   ├── public/      # Public content
│   │   │   ├── search/      # Search interface
│   │   │   └── licensing/   # License workflows
│   │   ├── layouts/         # Layout components
│   │   └── shared/          # Shared components
│   
├── backend/                  # Django + Wagtail backend
│   ├── apps/
│   │   ├── accounts/        # User management
│   │   ├── content/         # Quranic content
│   │   ├── licensing/       # License management
│   │   ├── analytics/       # Usage analytics
│   │   ├── core/            # Core utilities
│   │   └── api/             # REST API endpoints
│   └── config/              # Django configuration
│   
├── deployment/              # Infrastructure & deployment
│   ├── docker/              # Docker configurations
│   ├── k8s/                 # Kubernetes manifests
│   └── terraform/           # Infrastructure as Code
│   
├── shared/                  # Shared types and utilities
├── docs/                    # Documentation
└── ai-memory-bank/          # Task management
```

## 🔐 Authentication Flow

1. **Frontend**: User logs in via Auth0 SPA SDK
2. **Auth0**: Returns access token to Angular app
3. **Backend**: Validates Auth0 token via OIDC/JWKS
4. **Backend**: Issues internal JWT for API access
5. **API**: All endpoints protected by JWT + role-based permissions

## 📊 Core Data Models

- **User**: Account representing developers, publishers, admins, reviewers
- **Role**: RBAC role (Admin, Publisher, Developer, Reviewer)
- **Resource**: Any Qur'anic asset (text corpus, audio set, tafsir, translation)
- **License**: Legal terms attached to a Resource
- **Distribution**: Deliverable package/API endpoint for a Resource
- **AccessRequest**: Developer's request to use a Distribution under a License
- **UsageEvent**: Logged event for analytics and rate limiting

## 🛠️ Available Commands

### Docker Commands

```bash
# Start all services
docker-compose -f deployment/docker/docker-compose.yml up -d

# Stop all services
docker-compose -f deployment/docker/docker-compose.yml down

# Rebuild and restart
docker-compose -f deployment/docker/docker-compose.yml up --build

# View service logs
docker-compose -f deployment/docker/docker-compose.yml logs -f [service-name]

# Execute commands in containers
docker-compose -f deployment/docker/docker-compose.yml exec backend python manage.py shell
docker-compose -f deployment/docker/docker-compose.yml exec postgres psql -U itqan_user -d itqan_cms
```

### Django Commands

```bash
# Database operations
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic

# Run tests
python manage.py test

# Django shell
python manage.py shell

# Check deployment
python manage.py check --deploy
```

### Angular Commands

```bash
# Development server
npm run start

# Build for production
npm run build

# Run tests
npm run test

# Run e2e tests
npm run e2e

# Lint code
npm run lint
```

## 🧪 Testing

### Backend Testing

```bash
cd backend
python manage.py test
```

### Frontend Testing

```bash
cd frontend
npm run test
npm run e2e
```

## 📈 Monitoring & Observability

- **Application Logs**: Structured logging with Django + Angular
- **Error Tracking**: Sentry integration (production)
- **Performance**: Django Debug Toolbar (development)
- **Health Checks**: Built-in Docker health checks

## 🔒 Security

- **Authentication**: Auth0 with JWT tokens
- **Authorization**: Role-based access control (RBAC)
- **CORS**: Configured for secure cross-origin requests
- **HTTPS**: SSL/TLS termination at load balancer
- **Secrets**: Environment variables, never committed

## 🚚 Deployment

### Development
- **Environment**: Docker Compose
- **Database**: PostgreSQL container
- **Storage**: MinIO container

### Production (Phase 1 - DigitalOcean)
- **Platform**: DigitalOcean Kubernetes (DOKS)
- **Database**: DigitalOcean Managed PostgreSQL
- **Storage**: DigitalOcean Spaces
- **Load Balancer**: DigitalOcean Load Balancer

### Production (Phase 2 - Alibaba Cloud)
- **Platform**: Alibaba Cloud Container Service (ACK)
- **Database**: ApsaraDB for PostgreSQL
- **Storage**: Object Storage Service (OSS)
- **CDN**: Alibaba Cloud CDN

## 📚 Documentation

- [API Documentation](docs/api/openapi-spec.yaml) - OpenAPI 3.0 specification
- [Architecture Diagrams](docs/diagrams/) - C4 model diagrams
- [Task Management](ai-memory-bank/) - Development tasks and progress
- [Database Schema](docs/diagrams/high-level-db-components-relationship.png) - ER diagram

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/Itqan-community/cms/issues)
- **Documentation**: [Project Docs](docs/)
- **Community**: [Itqan Community](https://itqan.com)

---

**Built with ❤️ by the Itqan Community**

## 🚀 Test Deployment - Mon Sep  1 18:09:26 SAST 2025

Testing the improved CI/CD pipeline with git pull functionality.

🌟 Testing PRODUCTION auto-deployment - Mon Sep  1 21:54:26 SAST 2025
✅ SSH key updated - testing deployment

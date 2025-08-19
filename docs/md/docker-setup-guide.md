# Itqan CMS - Docker Development Setup

This document explains how to run the Itqan CMS stack locally using Docker Compose, and how to deploy it on any cloud provider for testing.

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose installed
- At least 4GB RAM available for containers
- Node.js 20+ (for local development outside containers)

### 1. Clone and Setup

```bash
git clone <repository-url> itqan-cms
cd itqan-cms

# Copy environment file and adjust as needed
cp env.dev.example .env.dev

# Generate Strapi secrets
# You can use online generators or:
node -e "console.log(require('crypto').randomBytes(64).toString('hex'))"
```

### 2. Build and Start Services

```bash
# Build all images and start services
docker compose up --build

# Or run in background
docker compose up -d --build
```

### 3. Access Services

- **Strapi Admin**: http://localhost:1337/admin
- **Next.js Public Site**: http://localhost:3000
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)
- **Meilisearch**: http://localhost:7700
- **PostgreSQL**: localhost:5432

### 4. First-Time Setup

1. **Create Strapi Admin User**:
   - Visit http://localhost:1337/admin
   - Complete the admin user registration

2. **Configure Auth0**:
   - Update `.env.dev` with your Auth0 tenant details
   - Restart containers: `docker compose restart`

3. **Configure MinIO Bucket**:
   - Visit http://localhost:9001
   - Create bucket: `itqan-uploads`
   - Set access policy to public-read

## 🛠 Development Workflow

### Container Structure

| Service | Purpose | Port | Volume Mount |
|---------|---------|------|------------- |
| `strapi` | Headless CMS API | 1337 | `./cms` → `/srv/app` |
| `web` | Next.js frontend | 3000 | `./web` → `/app` |
| `postgres` | Database | 5432 | Volume: `postgres_data` |
| `minio` | Object storage | 9000/9001 | Volume: `minio_data` |
| `meilisearch` | Search engine | 7700 | Volume: `meilisearch_data` |

### Hot Reload Development

Both Strapi and Next.js containers use volume mounts and run in development mode:

```bash
# Watch logs from all services
docker compose logs -f

# Watch specific service
docker compose logs -f strapi

# Restart specific service
docker compose restart strapi

# Rebuild after package.json changes
docker compose up --build strapi
```

### Database Management

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U cms_user -d itqan_cms

# Backup database
docker compose exec postgres pg_dump -U cms_user itqan_cms > backup.sql

# Restore database
docker compose exec -T postgres psql -U cms_user itqan_cms < backup.sql
```

## ☁️ Cloud Deployment (DigitalOcean Example)

### Deploy on DigitalOcean Droplet

1. **Create Droplet**:
   ```bash
   # 4GB RAM, Docker pre-installed
   doctl compute droplet create itqan-cms \
     --size s-2vcpu-4gb \
     --image docker-20-04 \
     --region nyc1
   ```

2. **Setup on Droplet**:
   ```bash
   # SSH into droplet
   ssh root@<droplet-ip>

   # Clone repository
   git clone <repository-url> itqan-cms
   cd itqan-cms

   # Setup environment
   cp env.dev.example .env.dev
   nano .env.dev  # Update with production values

   # Start services
   docker compose up -d --build
   ```

3. **Configure Firewall**:
   ```bash
   # Allow HTTP traffic
   ufw allow 80
   ufw allow 443
   ufw allow 1337  # Strapi API
   ufw allow 3000  # Next.js
   ```

### Production Considerations

For production deployment, consider:

- Use proper SSL certificates (Let's Encrypt)
- External managed databases (DigitalOcean Managed PostgreSQL)
- Object storage service (DigitalOcean Spaces)
- Load balancer for multiple instances
- Backup strategy
- Monitoring and logging

## 🔧 Troubleshooting

### Common Issues

1. **Port Conflicts**:
   ```bash
   # Check what's using ports
   lsof -i :1337
   lsof -i :3000
   
   # Update docker-compose.yaml port mappings if needed
   ```

2. **Permission Issues**:
   ```bash
   # Fix volume permissions
   sudo chown -R $(id -u):$(id -g) ./cms ./web
   ```

3. **Memory Issues**:
   ```bash
   # Check Docker resource usage
   docker stats
   
   # Increase Docker Desktop memory limit to 4GB+
   ```

4. **Database Connection**:
   ```bash
   # Verify PostgreSQL is ready
   docker compose exec postgres pg_isready -U cms_user
   
   # Reset database if needed
   docker compose down -v
   docker compose up postgres -d
   ```

### Debugging Services

```bash
# Enter container shell
docker compose exec strapi sh
docker compose exec web sh

# View container environment
docker compose exec strapi env

# Check container health
docker compose ps
```

## 📊 Service URLs & Credentials

### Development URLs
- Strapi Admin: http://localhost:1337/admin
- Strapi API: http://localhost:1337/api
- Next.js App: http://localhost:3000
- MinIO Console: http://localhost:9001
- Meilisearch Dashboard: http://localhost:7700

### Default Credentials
- **PostgreSQL**: `cms_user` / `dev_password_123`
- **MinIO**: `minioadmin` / `minioadmin`
- **Meilisearch**: Master Key: `dev-master-key-123`

## 🔄 Next Steps

Once the application is fully developed and tested:

1. Create production Dockerfiles (multi-stage builds)
2. Set up Kubernetes manifests for ACK (Alibaba Cloud)
3. Configure Terraform for infrastructure provisioning
4. Implement CI/CD pipeline with GitHub Actions
5. Set up monitoring and alerting

---

For questions or issues, please check the main project documentation or create an issue in the repository.

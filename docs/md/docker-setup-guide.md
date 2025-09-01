# 6 – Docker Development Stack

**Date:** 2024-12-15  
**Author:** Itqan CMS Team  

## Overview
Complete Docker Compose development environment setup for the Itqan CMS stack including Strapi v5, Next.js 14, PostgreSQL, MinIO, and Meilisearch. This implementation provides a fully containerized development environment with hot reload capabilities and cloud deployment instructions.

## Objectives
- Set up complete Docker Compose development stack
- Configure all required services (Strapi, Next.js, PostgreSQL, MinIO, Meilisearch)
- Enable hot reload development workflow
- Provide cloud deployment instructions
- Document troubleshooting procedures

### Container Architecture
- **Strapi Container**: Headless CMS API on port 1337 with volume mount to `./cms`
- **Next.js Container**: Frontend application on port 3000 with volume mount to `./web`
- **PostgreSQL Container**: Database service on port 5432 with persistent volume
- **MinIO Container**: S3-compatible object storage on ports 9000/9001
- **Meilisearch Container**: Search engine on port 7700 with persistent index storage

### Environment Configuration
- Environment variables managed through `env.dev.example` template
- Docker Compose configuration supports development hot reload
- Volume mounts enable real-time code changes without container rebuilds
- Service dependencies properly configured for startup order

### Key Setup Commands
```bash
# Initial setup
git clone <repository-url> itqan-cms && cd itqan-cms
cp env.dev.example .env.dev
node -e "console.log(require('crypto').randomBytes(64).toString('hex'))"

# Service startup
docker compose up --build  # Build and start all services
docker compose up -d --build  # Background mode

# Service access
# Strapi Admin: http://localhost:1337/admin
# Next.js App: http://localhost:3000
# MinIO Console: http://localhost:9001 (minioadmin/minioadmin)
# PostgreSQL: localhost:5432
```

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

## Acceptance Criteria Verification
- [x] Docker Compose stack with all services configured
- [x] Hot reload development environment functional
- [x] Volume mounts enable real-time code changes
- [x] All service ports accessible and documented
- [x] Cloud deployment instructions provided
- [x] Troubleshooting procedures documented

## Next Steps
1. Create production Dockerfiles (multi-stage builds)
2. Set up Kubernetes manifests for ACK (Alibaba Cloud)
3. Configure Terraform for infrastructure provisioning
4. Implement CI/CD pipeline with GitHub Actions
5. Set up monitoring and alerting

## References
- Service URLs: Strapi (1337), Next.js (3000), MinIO (9000/9001), Meilisearch (7700)
- Default credentials: PostgreSQL (cms_user/dev_password_123), MinIO (minioadmin/minioadmin)
- Related task JSON: `ai-memory-bank/tasks/6.json`

# CanopyIQ Deployment Guide

## Railway Deployment (Recommended - ~$5/month)

Railway is perfect for FastAPI apps with built-in PostgreSQL and zero-config deployments.

### 1. Setup Railway Account
1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub (connects to your repo automatically)
3. Create new project → Deploy from GitHub repo
4. Select `amacisaac222/sandbox_canopy`

### 2. Configure Environment Variables
In Railway dashboard → Variables tab, add:

```bash
# Required
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db  # Railway auto-provides this
SESSION_SECRET=your-super-secure-production-secret-change-this-now
BASE_URL=https://canopyiq.ai
ADMIN_EMAIL=admin@canopyiq.ai
DEFAULT_COMPANY_DOMAIN=canopyiq.ai

# Optional (for enterprise features)
OIDC_ISSUER=https://your-domain.okta.com
OIDC_CLIENT_ID=your-client-id
OIDC_CLIENT_SECRET=your-client-secret
OIDC_REDIRECT_URL=https://canopyiq.ai/auth/oidc/callback
```

### 3. Add PostgreSQL Database
1. In Railway project → Add service → Database → PostgreSQL
2. Railway automatically sets DATABASE_URL environment variable
3. Database migrations run automatically on deploy

### 4. Configure Custom Domain
1. Railway Settings → Domains → Add custom domain
2. Add: `canopyiq.ai` and `www.canopyiq.ai`
3. Update your DNS records at your domain registrar:
   ```
   A     @        76.76.19.123  (Railway will provide exact IP)
   CNAME www      your-app.up.railway.app
   ```
4. SSL certificates are automatically provisioned

### 5. Deploy
- Push to GitHub main branch
- Railway auto-deploys on every push
- Monitor logs in Railway dashboard

## Alternative: Render (Free tier available)

### Free Option:
1. [render.com](https://render.com) → Web Service from GitHub
2. Select repository: `amacisaac222/sandbox_canopy`
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `cd canopyiq_site && python -m uvicorn app:app --host 0.0.0.0 --port $PORT`
5. Add PostgreSQL database (free tier: 90 days, then $7/month)

### Custom Domain on Render:
1. Render Settings → Custom Domains → Add `canopyiq.ai`
2. Update DNS: CNAME `www` → `your-app.onrender.com`

## Cost Comparison:
- **Railway**: $5/month (app) + $5/month (PostgreSQL) = $10/month
- **Render**: Free (sleeps after 15min) or $7/month + $7/month (DB) = $14/month
- **Heroku**: $7/month + $9/month (PostgreSQL) = $16/month

## Production Checklist:
- [ ] Set strong SESSION_SECRET (use: `python -c "import secrets; print(secrets.token_hex(32))"`)
- [ ] Configure ADMIN_EMAIL for first admin user
- [ ] Add custom domain and SSL
- [ ] Set up monitoring/alerts
- [ ] Configure OIDC for enterprise customers (optional)
- [ ] Set up backups for PostgreSQL

## Monitoring:
- Railway provides built-in metrics and logs
- Add health check endpoint: GET `/health`
- Monitor costs in Railway dashboard

## Database Migrations:
- Migrations run automatically via `init_db()` in startup
- For production, consider using Alembic migrations
- Database backups available in Railway dashboard
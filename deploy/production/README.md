# NovelScripter Production Deployment

This deployment is intended for a small server and runs only the active demo path:

- FastAPI backend
- Next.js standalone frontend
- SQLite project snapshot persistence

It intentionally does not start PostgreSQL, Redis, MinIO, Celery, or local model services.

## Deploy

```bash
cd /opt/novelscripter/deploy/production
docker compose build
docker compose up -d
```

## Reverse Proxy

Add this site to the existing Caddy instance:

```caddy
novel.ggbond686.online {
  encode zstd gzip

  handle /api/* {
    reverse_proxy novelscripter-api:8000
  }

  handle {
    reverse_proxy novelscripter-web:3000
  }
}
```

Validate before reloading Caddy:

```bash
docker exec shengtu-image2-caddy-1 caddy validate --config /etc/caddy/Caddyfile
docker exec shengtu-image2-caddy-1 caddy reload --config /etc/caddy/Caddyfile
```

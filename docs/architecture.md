# 🏛️ Mimari Dokumantasyon

## Sistem Genel Bakis

```
┌─────────────────┐      ┌──────────────────┐      ┌────────────────┐
│                 │      │                  │      │                │
│   Next.js 14    │─────▶│    FastAPI       │─────▶│  PostgreSQL 16 │
│   (Frontend)    │ HTTP │    (Backend)     │ SQL  │   (Database)   │
│   Port: 3000    │      │   Port: 8000     │      │   Port: 5433   │
│                 │      │                  │      │                │
└─────────────────┘      └──────────────────┘      └────────────────┘
        │                         │
        │                         │
        ▼                         ▼
┌─────────────────┐      ┌──────────────────┐
│  Shadcn UI      │      │  AI Parser       │
│  TailwindCSS    │      │  (OpenAI/Claude) │
│  Recharts       │      │  Report Gen      │
└─────────────────┘      └──────────────────┘
```

## Katmanli Mimari (Backend)

```
┌─────────────────────────────────────────┐
│ API Layer (app/api/v1/endpoints/)       │ ← HTTP endpoint'ler
├─────────────────────────────────────────┤
│ Schema Layer (app/schemas/)             │ ← Pydantic validation
├─────────────────────────────────────────┤
│ Service Layer (app/services/)           │ ← Is mantigi
├─────────────────────────────────────────┤
│ Model Layer (app/models/)               │ ← SQLAlchemy ORM
├─────────────────────────────────────────┤
│ Database (PostgreSQL)                   │ ← Persistence
└─────────────────────────────────────────┘
```

## Frontend Mimarisi

- **Route Groups:** `(auth)` ve `(dashboard)` ile farkli layout'lar
- **Server Components** default olarak kullanilacak (performans)
- **Client Components** sadece interaktivite gerektiginde (`"use client"`)
- **State Management:** Yerel state icin `useState`, global icin **Zustand** (Day 4+)
- **Data Fetching:** Server Actions + React Query (Day 5+)
- **Forms:** React Hook Form + Zod validation

## Guvenlik Katmanlari (Planlanan)

1. **Authentication:** JWT (access + refresh token rotation)
2. **Authorization:** Role-Based Access Control (Admin, Project Manager, Engineer, Viewer)
3. **Rate Limiting:** slowapi (FastAPI)
4. **Input Validation:** Pydantic (backend) + Zod (frontend)
5. **CORS:** Sadece whitelisted origin'ler
6. **HTTPS:** Production'da mandatory (Nginx reverse proxy)

## Olceklenebilirlik Stratejisi

- **Stateless backend** — yatay olceklenebilir
- **Redis** (Day 10+) — session + caching + WebSocket pub/sub
- **Celery/RQ** (Day 11+) — async job queue (rapor uretimi, AI parser)
- **Object Storage** (S3/MinIO) — dokuman upload'lari icin

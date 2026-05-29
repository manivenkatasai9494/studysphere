# StudySphere AI — Deployment Guide (Render)

## 1. Supabase Setup

1. Create a project at [supabase.com](https://supabase.com)
2. Run `database/schema.sql` in **SQL Editor**
3. Enable Email auth under **Authentication → Providers**
4. Copy from **Settings → API**:
   - Project URL → `SUPABASE_URL`
   - `anon` key → `SUPABASE_ANON_KEY`
   - `service_role` key → `SUPABASE_SERVICE_ROLE_KEY`

## 2. Pinecone Setup

1. Create account at [pinecone.io](https://pinecone.io)
2. Create index:
   - Name: `studysphere`
   - Dimensions: **384**
   - Metric: **cosine**
3. Copy API key → `PINECONE_API_KEY`

## 3. Groq Setup

1. Get API key from [console.groq.com](https://console.groq.com)
2. Set `GROQ_API_KEY`

## 4. Hugging Face Setup

1. Create token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. Set `HF_TOKEN`
3. Model used: `sentence-transformers/all-MiniLM-L6-v2`

## 5. Redis (Upstash)

1. Create database at [upstash.com](https://upstash.com)
2. Copy Redis URL → `REDIS_URL`

## 6. Deploy on Render

### Option A: Blueprint (render.yaml)

1. Push repo to GitHub
2. Render Dashboard → **New → Blueprint**
3. Connect repo — `render.yaml` auto-configures the service
4. Add environment variables (sync: false keys)

### Option B: Manual Web Service

| Setting | Value |
|---------|-------|
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Root Directory | `.` |

### Environment Variables

```
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
GROQ_API_KEY=
PINECONE_API_KEY=
PINECONE_INDEX=studysphere
HF_TOKEN=
REDIS_URL=
JWT_SECRET=<random-64-char-string>
ENVIRONMENT=production
CORS_ORIGINS=*
```

## 7. Post-Deploy Checklist

- [ ] Visit `https://your-app.onrender.com/api/health` → `{"status":"ok"}`
- [ ] Register a test user
- [ ] Upload a PDF in RAG Notes
- [ ] Send a tutor message
- [ ] Confirm data persists after logout/login

## 8. Custom Domain (Optional)

Render → Service → Settings → Custom Domains

Update Supabase **Authentication → URL Configuration** with your production URL.

## 9. Troubleshooting

| Issue | Fix |
|-------|-----|
| 401 on API calls | Check JWT / Supabase keys |
| RAG returns no context | Verify Pinecone index dimension (384) and HF_TOKEN |
| LLM errors | Verify GROQ_API_KEY and model availability |
| Redis errors | App works without Redis; caching/rate-limit disabled |
| Static files 404 | Ensure `frontend/` is in repo root |

## 10. Scaling

- Upgrade Render plan for more concurrent users
- Use Supabase connection pooling for high traffic
- Pinecone serverless scales automatically
- Groq has rate limits — monitor usage dashboard

# API Authentication and Access Control

## Current V2 status

Authentication is **not implemented in this V2 starter**. The API currently accepts requests without an API key or user token. Treat it as a local development or restricted test deployment only.

## Required production design

Before connecting customer systems or exposing the API publicly, implement:

1. Tenant registry with a unique tenant ID for each business.
2. API credentials issued per tenant and stored as securely hashed secrets.
3. Authentication middleware for every `/api/*` route.
4. Tenant authorization so a tenant can only access its own datasets, model, predictions and training history.
5. Key rotation, revocation, request logging and rate limits.
6. HTTPS and secrets stored in deployment environment variables or a secret manager.

Recommended request header after authentication is implemented:

```http
Authorization: Bearer YOUR_TENANT_API_TOKEN
```

This header is a future design recommendation, not a working V1 feature. Do not assume sending it currently authenticates a request.

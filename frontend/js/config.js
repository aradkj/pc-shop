/**
 * The ONLY place that knows where the API lives.
 *
 * - Local development and `docker compose up`: the API is published on port 8000.
 * - Behind a reverse proxy that serves the site and the API from one origin, use "/api/v1".
 *
 * (When the API is on another origin, add the site's origin to CORS_ORIGINS in .env.)
 */
export const API_BASE_URL = "http://localhost:8000/api/v1";

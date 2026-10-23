# ThoraxAI Deployment

This project is prepared for a Render free web service with Neon free PostgreSQL. It is an educational demonstration, not a clinically validated diagnostic service. Do not upload identifiable patient information; use synthetic or fully de-identified images only.

## Current Status

Deployment configuration is ready, but no public URL is available yet. Creating and testing the hosted service requires access to a GitHub repository, Render, and Neon accounts. Do not mark the acceptance criteria below complete until the deployed website has actually been tested.

## Free-Tier Limits Checked 2026-10-16

- [Render free services](https://render.com/docs/free): web services sleep after 15 minutes without traffic and commonly take about one minute to wake. The service filesystem is ephemeral, the free service has 512 MB RAM and 750 instance-hours per workspace per month, and free Render Postgres databases expire after 30 days. This deployment therefore uses Neon for persistent database storage, not Render Postgres or local disk.
- [Neon pricing](https://neon.com/pricing): its Free plan is listed as permanent with no credit card required, 100 compute-hours per project per month, 1 GB database storage per project, automatic scale-to-zero after five minutes, and 5 GB included public network transfer. Free-tier limits and terms can change; check them again before deployment.
- Uploaded originals and processed images are stored as database blobs. The app accepts files up to 16 MB, so image retention can consume the 1 GB database allowance quickly. Monitor database use and do not treat the free plan as an archival service.
- Render's free instance-hour and included-usage limits apply. If included usage is exhausted, services can be suspended when no payment method is on file. No paid service is required by this configuration, and no service should be upgraded without explicit approval.

## Deploy

1. Back up the local project and database. Keep the backup outside the public repository.
2. Push the project to a private or public GitHub repository. Confirm that `.env`, database files, and credentials are not tracked.
3. Create a Neon project on its Free plan. Copy its PostgreSQL connection string; prefer the pooled connection string if offered. Keep its password private.
4. In Render, create a Blueprint from the GitHub repository and select `render.yaml`. Confirm the web service uses the Free plan. The blueprint configures Gunicorn, `$PORT`, `0.0.0.0`, `/healthz`, production mode, a generated `FLASK_SECRET_KEY`, and disables public demo login.
5. In the Render service environment, set `DATABASE_URL` to the Neon connection string. Do not commit the connection string. Keep `APP_ENV=production`, `ENABLE_DEMO_ACCESS=false`, and the generated secret. Do not use SQLite for the hosted service.
6. Deploy and wait for `/healthz` to report `{"status":"ok"}`. On first startup, SQLAlchemy `db.create_all()` creates the existing `Users`, `Analyses`, and `ChatMessages` tables. It does not migrate an existing database schema or copy local SQLite data.
7. Open the Render HTTPS URL in a separate device or network. Test the checks below, including database and image persistence after a service restart. Record the exact URL and date in this file only after successful testing.

## Data and Schema Notes

The current models preserve SQLAlchemy table names and foreign keys. A new Neon database is initialized on startup. For an existing production database, use a reviewed schema migration; `create_all()` is not a migration tool. To preserve existing local accounts and history, export and deliberately migrate the local SQLite data before switching users to the hosted service. Never overwrite the only local database copy.

Uploaded image bytes are stored in `Analyses.original_image_bytes` and `Analyses.processed_image_bytes`. Image routes require an authenticated owner, and deleting an analysis deletes its database row and dependent chat messages. The uploads directory is only temporary processing storage on Render. Built-in public examples are generated synthetic samples.

## Acceptance Record

Status: **Not deployed; hosted acceptance is unverified.**

- Public HTTPS URL and access from another device: pending
- Registration, password login, and protected sessions: pending hosted test
- Image validation, preprocessing, report, and report-grounded chat: pending hosted test
- Saved histories, conversations, and image retrieval after restart: pending hosted test
- Cross-user access and deletion isolation: pending hosted test
- Medical-safety and synthetic-demo presentation: application copy exists; deployed review pending

Local test suite currently has pre-existing mismatches between two assertion labels and the dashboard template, plus SQLite teardown errors on Windows. See the deployment change summary for the checks that could and could not be verified locally.
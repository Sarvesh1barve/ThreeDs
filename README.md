# Three D's Exhibition Store

A real, mobile-first exhibition storefront and order desk for a small 3D-printing studio. The public design preserves the supplied `reference/three_ds_personal_studio_prototype.html`: its “Little things. Big feelings.” hero, lamp toggle, original SVG product illustrations, filters, quick views, cart motion, printer scroll scene, nameplate personalizer, editorial tone, and responsive behavior.

The live ordering path is FastAPI + SQLAlchemy + SQLite in WAL mode. GitHub Pages is the static catalogue; authenticated checkout, admin, and private uploads always move to the first-party FastAPI/ngrok origin.

## What works

- Anonymous browse, filters, quick view, lamp interaction, personalizer, cart quantity/removal, and local cart persistence.
- Six reference concepts and six seeded categories, fetched from the database. Seed prices are explicitly draft and checkout-disabled until an admin verifies them.
- Customer registration/login by Indian mobile number and Argon2id password. Mobile numbers are **not OTP/SMS verified**.
- Hashed opaque server-side sessions, customer 30-day rolling lifetime with 90-day absolute maximum, 12-hour admin sessions, logout/all-session revocation support, CSRF tokens, exact Origin checks, and rate/lockout controls.
- Server-authoritative INR paise pricing, stock check, immutable order-line snapshots, transactional persistence, idempotency keys, and owner-only order/PDF access.
- Checkout for pickup/delivery with NEW / UNPAID state. No card capture and no fictional payment success.
- Protected admin catalogue, categories, price verification, photo/logo normalization, site theme/settings, search/status updates, manual POS/custom lines, audited price overrides, receipts, and order audit events.
- Custom-print requests with material/finish/colour/quantity and optional validated STL, OBJ, 3MF, STEP or STP files. Model bytes are private SQLite BLOBs; only authenticated admins can list or download them.
- Branded A4 order acknowledgement/proforma PDFs. They are never called tax invoices without legal/tax configuration.
- Manual `wa.me` click-to-chat drafts. Opening a link does **not** send a message and cannot choose which WhatsApp account is logged in.
- One-time, 10-minute, no-PII/no-price-authority guest-cart handoff for optional GitLab Pages → first-party backend checkout.

## Windows 11 quick start

Install Python 3.12 or newer, then in PowerShell:

```powershell
cd D:\ThreeDs
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Edit `.env` before public use. Generate a secret without printing it into source control:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put that value in `APP_SECRET`. Create the first administrator; there is no default credential and no public promotion endpoint:

```powershell
python scripts/bootstrap_admin.py
```

Start locally:

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips 127.0.0.1
```

Or run `powershell -ExecutionPolicy Bypass -File scripts/run.ps1`. Open `http://127.0.0.1:8000`, then `/admin`.

## Exhibition QR: one precise URL workflow

Mode A is the supported event path. Start FastAPI on `127.0.0.1:8000`, then in a second terminal:

```powershell
ngrok http 8000
```

Suppose ngrok shows `https://example.ngrok-free.app`. Stop the server, set these values in `.env`, and restart it:

```dotenv
BASE_URL=https://example.ngrok-free.app
ALLOWED_ORIGINS=https://example.ngrok-free.app
COOKIE_SECURE=true
TRUSTED_PROXY_HOSTS=127.0.0.1
```

Put **exactly `https://example.ngrok-free.app/`** on the exhibition QR. Storefront, API, login, checkout, PDFs, media, and `/admin` then share one first-party HTTPS origin. Uvicorn trusts forwarded headers only from local `127.0.0.1`, where the ngrok agent connects; do not broaden that list. Keep the PC, FastAPI process, internet connection, and tunnel running. Ngrok’s free interstitial may require a visitor click and its quota/domain can change, so test the QR from a second phone on mobile data before opening.

Never expose the SQLite file, Python debugger, `.env`, admin bootstrap, or development tooling through the tunnel.

## Required pre-opening checklist

1. Sign into `/admin` using the locally created admin.
2. In Catalogue, inspect each sample price. Check **Verified** and **Checkout** only for products the studio can actually sell; click Save.
3. Upload the genuine official logo in Brand settings. Until then, the honest stylized “Three D's” wordmark remains; no Instagram avatar is presented as verified.
4. Enter the studio WhatsApp number and pickup details.
5. Create a fresh customer from a phone, place one pickup order, download its PDF, update its status, and open (but do not accidentally send) the WhatsApp draft.
6. Scan the final ngrok QR on iOS/Android over mobile data.

Replace an illustration with a real photo from Catalogue → Photo → Save. The server checks decoded PNG/JPEG/WebP content, pixel count and size, strips metadata by normalization, and stores a random `.webp` filename outside Git.

## Tests

```powershell
python -m pytest -q
python -m compileall -q backend scripts tests
node --check frontend\assets\storefront.js
node --check frontend\assets\checkout.js
node --check frontend\assets\admin.js
```

Current local verification on Python 3.13.2: **11 passed**; the only emitted warning is a ReportLab dependency deprecation for Python 3.14. Browser smoke verification covered desktop/mobile storefront rendering, live catalogue/filter data, draft-price refusal, cart → checkout/auth navigation, and the mobile admin-login surface.

## Data, backup, and recovery

`DATA_DIR` contains the SQLite database and normalized product/logo uploads and is ignored by Git. The database also contains private custom-request model files, so backups must be protected as customer data. SQLite uses foreign keys, WAL mode, an 8-second busy timeout, short transactions, and a versioned bootstrap record. This is appropriate for a small exhibition, not high-concurrency commerce.

Stop writes briefly and run:

```powershell
powershell -File scripts/backup.ps1
```

To recover, stop FastAPI, preserve the damaged `data/` directory, copy a chosen backup’s `data` contents back to the configured `DATA_DIR`, then start and check `/api/health`. Test recovery before the event. For schema changes after v1, add an explicit forward migration before changing the recorded version; `create_all` is bootstrap, not a general migration engine.

## GitHub Pages

The repository is configured for GitHub origin `https://github.com/Sarvesh1barve/ThreeDs`. Push after reviewing:

```powershell
git add .
git commit -m "Build Three D's exhibition store"
git push -u origin main
```

`.github/workflows/pages.yml` publishes `frontend/`. Set the repository variable `BACKEND_PUBLIC_URL` to the HTTPS ngrok host. The Pages catalogue uses a deployment snapshot to avoid ngrok's cross-origin free-tier interstitial. Checkout transfers only product slugs and quantities in a top-level URL-safe handoff; the backend loads live products and recalculates every price. `/admin`, `/checkout`, and private custom-file submission use top-level navigation to the first-party backend origin, so authentication and uploads do not depend on third-party cookies or cross-origin form requests.

## Security posture and honest limitations

- CSP, nosniff, frame denial, referrer/permissions headers, HSTS on HTTPS, exact CORS origins, CSRF and Origin checks are enabled. ORM parameterization is used; admin/customer authorization is server enforced.
- Text from the database is rendered with DOM text APIs or escaped before HTML insertion. Uploaded SVG and executable content are rejected.
- The in-process rate limiter is suitable for one event process but resets on restart and is not distributed. Put a managed reverse proxy/WAF and shared limiter in front for broader production.
- SQLite has bounded write concurrency; move to managed PostgreSQL for sustained traffic or multiple workers. Run one Uvicorn worker with SQLite.
- There is no OTP, password reset provider, real payment gateway, tax/GST engine, shipping integration, automatic WhatsApp sender, malware scanner, or third-party security audit. Those features are unavailable rather than simulated.
- Admin re-authentication before every sensitive change and full financial revision/credit-note workflows are not included. Order totals remain immutable; status/payment changes are audited.
- Custom 3D model validation is structural, not antivirus scanning. Files are capped at 5 MB and admin downloads are forced as attachments, but define a deletion/retention policy and scan files in an isolated service before long-term public use.
- Before longer-term public use, commission professional security/privacy/legal review, add monitored backups and retention/deletion policies, and validate Indian tax/invoicing obligations.

No secrets, customer data, generated database, uploads, backups, or ngrok tokens belong in Git.

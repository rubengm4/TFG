# How to deploy to production (Internet) on a fresh VPS

This repository includes a production-ready Docker Compose stack (`docker-compose.prod.yml`) that runs:

- **Caddy** as the public reverse proxy (**HTTPS**, ports 80/443) and authenticated `/media/*` file serving
- **Django + Gunicorn** (`web`)
- **Celery** worker (`celery`)
- **MySQL** (`db`) — internal only
- **Redis** (`redis`) — internal only

This guide starts from “I don’t have a domain yet and I don’t have a VPS yet” and ends with a working `https://example.com` deployment.

## Requirements and recommendations

- **Domain**: any registrar (Porkbun/Namecheap/Cloudflare Registrar/etc.). DNS can be hosted anywhere.
- **VPS**: any provider (Hetzner Cloud, DigitalOcean, OVH, Linode, etc.).
  - **Recommendation**: Hetzner Cloud (good value) or any provider you already trust.
- **OS**: any modern Linux server OS.
  - **Recommendation**: Ubuntu **24.04 LTS**.
- **Sizing** (important for this repo): first boot can be heavy because the container entrypoint may build/install a Python venv for algorithm execution inside the **media volume**.
  - **Minimum**: 2 vCPU, 4 GB RAM
  - **Safer**: 2–4 vCPU, **8 GB RAM**, 40+ GB SSD (more if you store many uploads/outputs)

## What you will configure (high level)

- **DNS**: `A`/`AAAA` records for:
  - `example.com` (apex)
  - `www.example.com` (www)
- **Firewall** on VPS:
  - open **22**, **80**, **443**
  - do **not** open MySQL/Redis ports
- **Secrets** in `algovision/.env` (never commit):
  - `SECRET_KEY`, DB passwords, etc.
- **Deploy commands** (from repo root on VPS):
  - build: `docker compose ... build`
  - run: `docker compose ... up -d`
  - logs, restart, update, backups

---

## Step 0 — Choose your hostnames (apex + www)

Decide the exact public hostnames:

- `example.com`
- `www.example.com`

You’ll use these values in:

- `CADDY_DOMAIN` (Caddy host list)
- `ALLOWED_HOSTS` (Django)
- `CSRF_TRUSTED_ORIGINS` (Django, must include `https://`)

---

## Step 1 — Buy a domain (registrar-agnostic)

1. Pick any registrar and purchase your domain (example: `example.com`).
2. Ensure you can manage DNS records somewhere:
   - Either in the registrar’s DNS panel, **or**
   - By delegating DNS to a dedicated provider (commonly Cloudflare).

Notes:
- DNS hosting choice does **not** affect the Docker deployment; you just need to create the records in Step 4.
- If you use Cloudflare as DNS: consider starting in “DNS only” (grey cloud) mode until everything works, then decide whether you want proxying.

---

## Step 2 — Rent a VPS (provider-agnostic)

1. Create a VPS with:
   - Ubuntu 24.04 LTS (recommended)
   - Public IPv4 (required), IPv6 (optional but recommended)
2. Record:
   - `YOUR_SERVER_IPV4`
   - `YOUR_SERVER_IPV6` (if provided)
3. Choose SSH authentication:
   - **Recommended**: SSH key (no password SSH).

---

## Step 3 — First login + harden the VPS (new user, disable root)

### 3.1 Login as root (first time only)

Your provider will tell you how to connect (usually root + SSH key):

```bash
ssh root@YOUR_SERVER_IPV4
```

### 3.2 Update the server

On Ubuntu/Debian:

```bash
apt update
apt -y upgrade
apt -y install ca-certificates curl git ufw
```

If the kernel was updated, reboot:

```bash
reboot
```

Then reconnect as root:

```bash
ssh root@YOUR_SERVER_IPV4
```

### 3.3 Create a non-root deploy user

```bash
adduser deploy
usermod -aG sudo deploy
```

### 3.4 Configure SSH keys for `deploy`

From **your laptop**, copy your SSH public key:

```bash
ssh-copy-id deploy@YOUR_SERVER_IPV4
```

Verify you can login as `deploy`:

```bash
ssh deploy@YOUR_SERVER_IPV4
```

### 3.5 Disable root login and password SSH

On the VPS, edit SSH config:

```bash
sudoedit /etc/ssh/sshd_config
```

Set (or ensure) these values:

```text
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

Reload SSH:

```bash
sudo systemctl reload ssh
```

Important:
- Do **not** close your existing SSH session until you confirm a *second* session can still log in as `deploy`.

---

## Step 4 — Firewall: open only 22/80/443

Using UFW (Ubuntu/Debian):

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status verbose
```

Do **not** open MySQL or Redis ports. In production, they should remain internal to Docker.

Also check your **provider firewall / security group** (Hetzner Cloud Firewall, DigitalOcean Cloud Firewall, AWS Security Groups, etc.). You must allow inbound **80/tcp** and **443/tcp** there too, otherwise Let’s Encrypt certificate issuance will fail even if UFW is correct.

---

## Step 5 — DNS: point your domain to the VPS

In your DNS provider, create these records.

### 5.1 Apex: `example.com`

- `A` record:
  - Name/Host: `@` (or `example.com` depending on UI)
  - Value: `YOUR_SERVER_IPV4`
- Optional `AAAA` record (recommended if you have IPv6):
  - Name/Host: `@`
  - Value: `YOUR_SERVER_IPV6`

### 5.2 WWW: `www.example.com`

One of:
- `CNAME` record: `www` → `example.com`
- Or `A`/`AAAA` records directly to your server IP(s)

### 5.3 Wait for propagation

From your laptop:

```bash
dig +short A example.com
dig +short A www.example.com
dig +short AAAA example.com
dig +short AAAA www.example.com
```

You should see your VPS IPs returned.

---

## Step 6 — Install Docker + Compose (on the VPS)

Below are **copy-paste** commands for **Ubuntu 24.04** (recommended). If you’re using a different distro, install Docker Engine + the Compose plugin using Docker’s official docs:

- Docs: `https://docs.docker.com/engine/install/`

### 6.0 Ubuntu 24.04 exact install commands (Docker official repo)

Run on the VPS:

```bash
sudo apt update
sudo apt -y install ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo ${VERSION_CODENAME}) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Enable Docker at boot and start it now:

```bash
sudo systemctl enable --now docker
```

After installation, verify:

```bash
docker --version
docker compose version
```

### 6.1 Allow the `deploy` user to run Docker without sudo

```bash
sudo usermod -aG docker "$USER"
```

Log out and back in, then test:

```bash
docker ps
```

### 6.2 (Recommended) Enable Docker log rotation (prevents disk fill)

If you don’t already have it, create `/etc/docker/daemon.json` with log limits, e.g.:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

Then restart Docker:

```bash
sudo systemctl restart docker
```

---

## Step 7 — Clone the repo on the VPS (assumed public)

Choose a location on the VPS:

```bash
mkdir -p ~/apps
cd ~/apps
git clone <YOUR_REPO_URL> TFG
cd TFG
```

All commands below are run from this repo root directory.

---

## Step 8 — Create production secrets/config (`algovision/.env`)

This repo expects a `.env` file at `algovision/.env` (do **not** commit it).

```bash
cp algovision/.env.example algovision/.env
```

Edit it:

```bash
nano algovision/.env
```

Fill in at least these values.

### 8.1 Django core

Generate a strong secret key:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(64))'
```

Set:

- `SECRET_KEY=<paste generated value>`
- `DEBUG=False`
- `ALLOWED_HOSTS=example.com,www.example.com` (comma-separated, **no spaces**)
- `CSRF_TRUSTED_ORIGINS=https://example.com,https://www.example.com`
- `SECURE_PROXY_SSL=True` (TLS is terminated at Caddy; Django must trust `X-Forwarded-Proto`)
- `SECURE_HSTS_SECONDS=3600` (start low; raise after confirming everything is correct)
- `SECURE_HSTS_PRELOAD=False` (keep `False` until you're ready; when `True`, you should set `SECURE_HSTS_SECONDS=31536000` or higher)

### 8.2 Database (Django + MySQL container)

Choose strong passwords and keep root password different.

Set these consistently:

- `DATABASE_NAME=algovision`
- `DATABASE_USER=algovision`
- `DATABASE_PASSWORD=<strong password>`
- `DATABASE_HOST=db`
- `DATABASE_PORT=3306`

And MySQL variables:

- `MYSQL_DATABASE=algovision` (should match `DATABASE_NAME`)
- `MYSQL_USER=algovision` (should match `DATABASE_USER`)
- `MYSQL_PASSWORD=<same as DATABASE_PASSWORD>`
- `MYSQL_ROOT_PASSWORD=<different strong password>`

### 8.3 Redis / Celery

- `REDIS_URL=redis://redis:6379/0`

### 8.4 Caddy domain (public hostnames)

Set:

- `CADDY_DOMAIN=example.com, www.example.com`

Important:
- Multiple hostnames require **comma + space** (this is a Caddyfile parsing constraint).

### 8.5 Let’s Encrypt (ACME) email

You can deploy without explicitly setting an email, but it’s recommended so you receive expiry/security notices.

This repo’s `deploy/Caddyfile` notes an email setting; the most reliable approach is to add a global options block with your email:

```text
{
	email you@example.com
}
```

Place it at the top of `deploy/Caddyfile` (above the `{$CADDY_DOMAIN} { ... }` block).

After editing the Caddyfile, apply it by restarting the proxy container:

```bash
docker compose --env-file algovision/.env -f docker-compose.prod.yml restart proxy
docker compose --env-file algovision/.env -f docker-compose.prod.yml logs --tail=200 proxy
```

### 8.6 Optional: auto-create the first admin user

If you want an initial admin to be created automatically on first boot, set:

- `DJANGO_SUPERUSER_USERNAME=admin`
- `DJANGO_SUPERUSER_EMAIL=you@example.com`
- `DJANGO_SUPERUSER_PASSWORD=<strong password>`

---

## Step 9 — Build the production image(s) (SKIP TO HERE IF THE SERVER HAS BEEN CREATED ALREADY)

From repo root:

```bash
docker compose --env-file algovision/.env -f docker-compose.prod.yml build
```

This uses `Dockerfile` and includes a Tailwind CSS build (`npm run build-css`) during image build.

---

## Step 10 — Start the production stack

```bash
docker compose --env-file algovision/.env -f docker-compose.prod.yml up -d
```

Notes:
- The first boot may take longer than usual.
- Caddy will request HTTPS certificates from Let’s Encrypt. For that to work:
  - DNS must already point to this VPS
  - ports 80/443 must be reachable (firewall + provider security group)

---

## Step 11 — Verify (status + logs)

### 11.1 Container status

```bash
docker compose --env-file algovision/.env -f docker-compose.prod.yml ps
```

### 11.2 Quick “is it reachable” checks (from your laptop)

These help distinguish DNS/firewall issues from app issues.

```bash
curl -I http://example.com
curl -I https://example.com
curl -I https://www.example.com
```

Expected results:
- HTTP (`http://`) usually redirects to HTTPS (3xx).
- HTTPS should return `200` or `302` and a valid certificate.

### 11.2 Follow logs

All services:

```bash
docker compose --env-file algovision/.env -f docker-compose.prod.yml logs -f
```

Commonly useful:

```bash
docker compose --env-file algovision/.env -f docker-compose.prod.yml logs -f proxy
docker compose --env-file algovision/.env -f docker-compose.prod.yml logs -f web
docker compose --env-file algovision/.env -f docker-compose.prod.yml logs -f celery
docker compose --env-file algovision/.env -f docker-compose.prod.yml logs -f db
```

### 11.3 Browser smoke test

1. Open `https://example.com/`
2. Confirm:
   - HTTPS is active (valid cert)
   - pages and static assets load
   - login works
3. Upload a file and test a `/media/...` URL:
   - while logged in: should download (served by Caddy)
   - in a private window (logged out): should be blocked

---

## Step 12 — Algorithm management (upload algorithms, requirements, verify)

This section is about managing algorithms **inside the running web app** after the server is deployed.

### 12.1 Confirm you have an admin user

If you didn’t set `DJANGO_SUPERUSER_*` in `algovision/.env`, create one now:

```bash
docker compose --env-file algovision/.env -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

### 12.2 Upload an algorithm ZIP (via the UI)

High-level flow (matches the workflow described in `README.md`):

1. Log in as an administrator.
2. Enter the target project.
3. Open **Manage Algorithms**.
4. Click **Create new algorithm**.
5. Upload your `.zip` file.
6. Set the **entrypoint**:
   - It must be the path to the main script **relative to the extracted ZIP root** (examples: `main.py` or `src/main.py`).
7. Configure the algorithm options (input types, etc.) and save.

Operational notes:
- In production, uploaded algorithm archives and outputs live under the **named volume** `media_volume`. This is what makes uploads survive container rebuilds/restarts.
- Celery executes algorithms with its working directory set to the extracted folder under:
  - `MEDIA_ROOT/algorithms/pkg/<pk>/extract/`

### 12.3 Update “global requirements” for algorithms (if your app supports it)

This repo’s README describes a “global requirements” file that can be downloaded/uploaded from the UI.
If a newly uploaded algorithm fails due to missing Python packages, the intended workflow is:

1. Download the current requirements from the admin UI.
2. Test your algorithm in a clean venv and determine missing deps.
3. Update the requirements file and upload it back in the UI.

### 12.4 Verify uploaded algorithms exist on disk (preflight)

If you upload an algorithm but it “doesn’t appear”, fails to execute, or you suspect the DB and filesystem are out of sync, run:

```bash
docker compose --env-file algovision/.env -f docker-compose.prod.yml exec web python manage.py check_algorithm_media
docker compose --env-file algovision/.env -f docker-compose.prod.yml exec web python manage.py check_algorithm_media --zip-probe
```

These commands validate that each algorithm row has the expected archive file on disk, and can also probe ZIP headers.

### 12.5 Repair missing seed algorithm archives (after resetting `media_volume`)

If the DB contains seed algorithms but the media volume was cleared/recreated, restore the bundled seed archives:

```bash
docker compose --env-file algovision/.env -f docker-compose.prod.yml exec web python manage.py sync_missing_seed_archives --dry-run
docker compose --env-file algovision/.env -f docker-compose.prod.yml exec web python manage.py sync_missing_seed_archives
```

---

## Day-2 operations (build / deploy / reload / logs)

All commands are run from the **repo root** on the VPS.

### View logs

```bash
docker compose --env-file algovision/.env -f docker-compose.prod.yml logs --tail=200
docker compose --env-file algovision/.env -f docker-compose.prod.yml logs -f
```

### Restart (“reload”) services

```bash
docker compose --env-file algovision/.env -f docker-compose.prod.yml restart web
docker compose --env-file algovision/.env -f docker-compose.prod.yml restart proxy
docker compose --env-file algovision/.env -f docker-compose.prod.yml restart
```

### Recreate containers after env/config changes (no rebuild)

```bash
docker compose --env-file algovision/.env -f docker-compose.prod.yml up -d --force-recreate
```

### Update code and redeploy (rebuild + up)

```bash
git pull
docker compose --env-file algovision/.env -f docker-compose.prod.yml build
docker compose --env-file algovision/.env -f docker-compose.prod.yml up -d
```

### Rollback to a previous version (simple)

If a deploy breaks production, you can roll back by checking out the last known-good commit and redeploying:

```bash
git log --oneline --max-count=20
git checkout <KNOWN_GOOD_COMMIT_SHA>
docker compose --env-file algovision/.env -f docker-compose.prod.yml build
docker compose --env-file algovision/.env -f docker-compose.prod.yml up -d
```

To return to the latest `main` (or your branch) later:

```bash
git checkout main
git pull
docker compose --env-file algovision/.env -f docker-compose.prod.yml build
docker compose --env-file algovision/.env -f docker-compose.prod.yml up -d
```

### Run Django admin commands

```bash
docker compose --env-file algovision/.env -f docker-compose.prod.yml exec web python manage.py migrate
docker compose --env-file algovision/.env -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
docker compose --env-file algovision/.env -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

### Stop / start

```bash
docker compose --env-file algovision/.env -f docker-compose.prod.yml down --remove-orphans
docker compose --env-file algovision/.env -f docker-compose.prod.yml up -d
```

Warning:
- Do **not** run `down -v` unless you intend to delete **database/media/certs** volumes.

---

## Backups (minimum viable)

You must back up:

- **MySQL database** (`mysql_data` volume)
- **Media** (`media_volume`) — includes uploads, outputs, algorithm archives, and the algorithm venv (`media/envs/.algenv`)

### MySQL dump (example)

```bash
docker compose --env-file algovision/.env -f docker-compose.prod.yml exec db \
  mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" --all-databases > backup.sql
```

Also back up the `media_volume` contents on a schedule (provider snapshots, rsync to object storage, tar archives, etc.). Always test restores.

---

## Troubleshooting

### HTTPS certificates not issuing

Check:
- DNS points to the correct IPs (Step 5)
- ports 80/443 open in both VPS firewall and provider security rules
- `CADDY_DOMAIN` matches the DNS hostnames exactly

Then:

```bash
docker compose --env-file algovision/.env -f docker-compose.prod.yml logs --tail=300 proxy
```

### “First boot is slow”

This repo’s entrypoint may install heavy Python deps into the media volume. Give it time and watch logs:

```bash
docker compose --env-file algovision/.env -f docker-compose.prod.yml logs -f web
docker compose --env-file algovision/.env -f docker-compose.prod.yml logs -f celery
```

### Database credentials errors

Ensure `DATABASE_*` and `MYSQL_*` are consistent in `algovision/.env`, then recreate:

```bash
docker compose --env-file algovision/.env -f docker-compose.prod.yml up -d --force-recreate
```

### Algorithm upload / missing media issues (sanity checks)

If you see problems where algorithms are present in the DB but the expected ZIPs/files are missing in the media volume (or uploads fail unexpectedly), run the repo’s media preflight checks:

```bash
docker compose --env-file algovision/.env -f docker-compose.prod.yml exec web python manage.py check_algorithm_media
docker compose --env-file algovision/.env -f docker-compose.prod.yml exec web python manage.py check_algorithm_media --zip-probe
docker compose --env-file algovision/.env -f docker-compose.prod.yml exec web python manage.py check_algorithm_media --list-bundle
```

If the database still references seed algorithms but you cleared/replaced `media_volume`, you can repair missing seed archives from the bundled seeds:

```bash
docker compose --env-file algovision/.env -f docker-compose.prod.yml exec web python manage.py sync_missing_seed_archives --dry-run
docker compose --env-file algovision/.env -f docker-compose.prod.yml exec web python manage.py sync_missing_seed_archives
```


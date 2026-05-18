# LT428 — Banniskirk to Carnaig Site Visit Dashboard

A Django-based site survey dashboard for viewing, reporting and managing field survey data.

---

## Local Development (Windows)

```powershell
# Clone repo
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO

# Create and activate venv
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations and create superuser
python manage.py migrate
python manage.py createsuperuser

# Start dev server
python manage.py runserver
```

Visit `http://127.0.0.1:8000`

---

## Docker Deployment (Windows 11 VM)

### Prerequisites
- Docker Desktop installed on the VM
- Git installed on the VM

### First-time setup

**1. Clone the repo on the VM:**
```powershell
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

**2. Create your `.env` file:**
```powershell
copy .env.example .env
```
Edit `.env` and set:
- `DJANGO_SECRET_KEY` — generate a random string at https://djecrety.ir
- `DJANGO_ALLOWED_HOSTS` — add your VM's IP address
- `DJANGO_SUPERUSER_PASSWORD` — your admin password

**3. Build and start:**
```powershell
docker-compose up --build -d
```

**4. Visit the app:**
```
http://YOUR_VM_IP
```

**5. Admin dashboard:**
```
http://YOUR_VM_IP/admin
```
Log in with the superuser credentials from your `.env` file.

---

## Updating to a new version

```powershell
# On the VM
git pull
docker-compose up --build -d
```
Data volumes (`data/`, `media/`, `db.sqlite3`) are never touched during updates.

---

## Adding survey data

1. Go to `http://YOUR_VM_IP/admin`
2. Click **Map Generation Logs**
3. Click **Upload Route Data**
4. Upload your `.xlsx`, `.dxf` and photos
5. Click **Generate Maps** to create aerial images

---

## Generating maps via command line

```powershell
docker-compose exec web python manage.py generate_maps
docker-compose exec web python manage.py generate_maps --route PR402
docker-compose exec web python manage.py generate_maps --force
```

---

## Project structure

```
config/         Django project settings and URLs
survey/         Main app — views, models, admin, services
    services/   data_loader.py, map_renderer.py
    templates/  HTML templates
    management/ Management commands
data/           Survey xlsx and dxf files (Docker volume)
media/          Photos and map cache (Docker volume)
static/         CSS and JS
```

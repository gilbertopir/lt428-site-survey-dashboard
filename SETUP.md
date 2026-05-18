# Django Setup — Windows (Python 3.12, existing venv)

## 1. Activate venv and install dependencies

```powershell
cd D:\Python_Development\Site-DATA-Dashboard-VM_rev2
venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Project folder structure to create

```
Site-DATA-Dashboard-VM_rev2/
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── survey/
│   ├── __init__.py
│   ├── views.py
│   ├── urls.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── data_loader.py
│   └── templates/
│       └── survey/
│           ├── base.html         ← next step
│           ├── overview.html
│           ├── route_detail.html
│           ├── report.html       ← priority
│           └── summary.html
├── static/
│   └── css/
│       └── theme.css
├── media/
│   └── photos/
│       ├── features/             ← move photos here
│       └── passing_places/       ← move photos here
├── data/                         ← xlsx and dxf files (unchanged)
├── manage.py
└── requirements.txt
```

## 3. Create folder structure in PowerShell

```powershell
mkdir config
mkdir survey\services
mkdir survey\templates\survey
mkdir static\css
mkdir media\photos\features
mkdir media\photos\passing_places
mkdir data
```

## 4. Move your existing data files

- Copy your .xlsx and .dxf files into /data/
- Copy your photos into /media/photos/features/ and /media/photos/passing_places/

## 5. Verify Django is working

```powershell
python manage.py check
```

Should return: System check identified no issues.

## 6. Run dev server

```powershell
python manage.py runserver
```

Visit: http://127.0.0.1:8000/

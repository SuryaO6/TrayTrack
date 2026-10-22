# TrayTrack Backend

This folder contains the TrayTrack FastAPI backend. It uses MySQL for storage
and runs locally on `http://localhost:8000`.

## Railway deployment

Create a Railway service from this repository and set its root directory to
`backend`. Railway will use the included `Procfile` to start FastAPI.
Configure these variables in Railway's service settings:

```dotenv
DB_HOST=<Railway MySQL host>
DB_PORT=<Railway MySQL port>
DB_USER=<Railway MySQL user>
DB_PASSWORD=<Railway MySQL password>
DB_NAME=mess_monitor
GOOGLE_CLIENT_ID=<Google OAuth client ID>
FRONTEND_ORIGIN=https://<your-vercel-domain>
MESS_ADMIN_PASSWORD=<strong unique password>
ADMIN_TOKEN_SECRET=<strong unique secret>
SMTP_EMAIL=
SMTP_APP_PASSWORD=
```

Do not upload `.env` or place any production secrets in the repository.

## Requirements

- Python 3.10 or newer
- MySQL Server running on port `3306`
- A Google OAuth client ID for Google Sign-In

The backend creates its tables automatically when it starts. You only need to
create the database once.

## Windows setup

Open PowerShell in this folder:

```powershell
cd "C:\Users\Suryansh\Downloads\real traytrack\backend"
```

### 1. Create the database

Make sure the MySQL service is running. If MySQL was installed as a Windows
service, you can start it with:

```powershell
Start-Service MySQL
```

Create the database using the MySQL client:

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p -e "CREATE DATABASE IF NOT EXISTS mess_monitor;"
```

Enter your MySQL root password when prompted. If MySQL is installed in a
different location, use the path to that installation's `mysql.exe`.

### 2. Configure environment variables

Copy the example environment file:

```powershell
Copy-Item .env.example .env
```

Open `.env` and set the database values to match your MySQL installation:

```dotenv
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=mess_monitor
```

Also check these values:

```dotenv
GOOGLE_CLIENT_ID=your_google_client_id
FRONTEND_ORIGIN=http://localhost:5173
MESS_ADMIN_PASSWORD=choose-a-development-admin-password
ADMIN_TOKEN_SECRET=choose-a-long-random-secret
```

Do not commit `.env` or use the example development secrets in production.

### 3. Create a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, either run the commands below without
activating the environment, or allow scripts for your user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then activate it again:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

`python-multipart` is required because complaint submission accepts form data
and optional image uploads.

## Run the backend

From the `backend` folder, with the virtual environment activated:

```powershell
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API is now available at:

- API base URL: <http://localhost:8000>
- Interactive Swagger documentation: <http://localhost:8000/docs>
- ReDoc documentation: <http://localhost:8000/redoc>

Keep this PowerShell window open while using the frontend. Stop the server
with `Ctrl+C`.

For a normal run without automatic code reloading:

```powershell
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

## Verify that it is running

In a second PowerShell window:

```powershell
Invoke-WebRequest http://localhost:8000/docs
```

A successful response has status code `200`.

You can also open <http://localhost:8000/docs> in a browser.

## Run with the frontend

Start the backend first, then use a second terminal for the frontend:

```powershell
cd "C:\Users\Suryansh\Downloads\real traytrack\frontend"
npm install
npm run dev
```

The frontend normally runs at <http://localhost:5173>. This must match the
`FRONTEND_ORIGIN` value in `.env`.

## Deployment architecture

The React frontend can be deployed to Vercel. Set the Vercel project root to
`frontend`, use `npm run build` as the build command, and set the output
directory to `dist`. Add this Vercel environment variable:

```text
VITE_API_BASE_URL=https://your-public-backend.example.com
```

The backend should run on a persistent Python host such as Render, Railway, or
a VPS with a managed MySQL database. Do not point a deployed frontend at
`localhost`; that refers to each visitor's own computer.

Set the backend `FRONTEND_ORIGIN` environment variable to the exact Vercel
frontend URL, for example:

```text
FRONTEND_ORIGIN=https://your-traytrack.vercel.app
```

The backend currently uses local filesystem uploads and starts an hourly
background escalation thread. Those features need persistent storage and a
long-running process, so a normal Vercel serverless function is not suitable
for the backend without additional changes such as object storage and a
scheduled job.

## Adding colleges

No college dataset is required. On the first run, the backend creates a sample
college and two sample mess halls if the database is empty.

To add your real college:

1. Open the frontend and select **Admin Panel**.
2. Log in using the value of `MESS_ADMIN_PASSWORD` in `.env`.
3. Add the college name.
4. Enter the official email domain without the `@`. For example, for
   `student@ssipmt.com`, enter `ssipmt.com`.
5. Add at least one mess hall.
6. Select the new college on the complaint page.

### Bulk import many colleges

For many colleges, use the **Bulk import colleges** section in the Admin
Panel. Prepare a UTF-8 CSV with this header:

```csv
college_name,email_domain,mess_head_email,principal_email,fssai_contact_email,mess_hall_name
```

Example:

```csv
college_name,email_domain,mess_head_email,principal_email,fssai_contact_email,mess_hall_name
SSIPMT,ssipmt.com,messhead@ssipmt.com,principal@ssipmt.com,fssai@ssipmt.com,Main Mess
Indian Institute of Technology Delhi,iitd.ac.in,messhead@iitd.ac.in,principal@iitd.ac.in,fssai@iitd.ac.in,North Campus Mess
Indian Institute of Technology Delhi,iitd.ac.in,messhead@iitd.ac.in,principal@iitd.ac.in,fssai@iitd.ac.in,South Campus Mess
```

Use one row per mess hall. If a college has multiple mess halls, repeat the
college details on each row and change only `mess_hall_name`. Existing colleges
are updated by name, and existing mess halls are not duplicated. The import is
atomic: if a required value is invalid, no rows from that upload are saved.

Only upload verified institutional contact information. The application does
not automatically discover or validate college domains and contact addresses.

### Sync the Indian college directory

The project also includes a sync script for the public AICTE-based directory
at <https://indian-colleges-list.vercel.app/>. It stores college names, state,
district, address, institution type, and source ID in a separate
`college_directory` table:

```powershell
cd "C:\Users\Suryansh\Downloads\real traytrack\backend"
.\.venv\Scripts\Activate.ps1
python sync_college_directory.py
```

The script may take several minutes because it downloads each state snapshot.
It is safe to run again; records are updated by source ID instead of duplicated.

This directory is intentionally separate from active TrayTrack colleges. The
source does not reliably provide verified student email domains, Principal
emails, Mess Head emails, FSSAI contacts, or mess halls. Do not guess those
values. A college must still be added or verified through the Admin Panel
before students can submit complaints for it.

After syncing, use **Admin Panel → Find a college in the directory** to search
the imported records. Click **Use this college** to copy its name into the
active-college form, then manually enter and verify the official student email
domain, contact emails, and mess hall before clicking **Add college**.

## Common errors

### `Form data requires "python-multipart" to be installed`

Install dependencies again:

```powershell
python -m pip install -r requirements.txt
```

### `Can't connect to MySQL server`

Check that the MySQL service is running:

```powershell
Get-Service MySQL
Start-Service MySQL
```

Then verify `DB_HOST`, `DB_PORT`, `DB_USER`, and `DB_PASSWORD` in `.env`.

### `Unknown database 'mess_monitor'`

Create it manually:

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p -e "CREATE DATABASE IF NOT EXISTS mess_monitor;"
```

### `Your email doesn't match this college's registered domain`

Select a college whose authorized domain matches your signed-in email. The
domain is the text after `@`, such as `ssipmt.com`.

### Port `8000` is already in use

Find the process using the port:

```powershell
Get-NetTCPConnection -LocalPort 8000
```

Either stop that specific process or use another port:

```powershell
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

If you use another port, update the frontend API URL accordingly.

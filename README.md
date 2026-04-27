# 📦 Storage API

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Flask](https://img.shields.io/badge/Flask-API-lightgrey)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-blue)
![Ceph](https://img.shields.io/badge/Ceph-Storage-red)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)
![Tests](https://img.shields.io/badge/Tests-pytest-green)

Backend service for managing storage resources in the platform.

Storage API provides REST endpoints for account management, S3-compatible object storage, iSCSI resources, pool discovery, and service health checks. It acts as a storage control plane, persists metadata in PostgreSQL, applies RBAC rules, and integrates with Ceph-based storage infrastructure.

---

## ✨ Features

- 👤 Account management
- 🪣 S3 users, buckets, quotas, limits, and key regeneration
- 💽 iSCSI quotas, clusters, gateways, disks, clients, snapshots, and rollback
- 🧭 Storage pool discovery
- ❤️ Health check endpoint
- 🐘 PostgreSQL-backed metadata storage
- 🔄 Flask-Migrate database migrations
- ⚙️ YAML-based configuration with environment variable overrides
- ☁️ Ceph RGW, RBD, and iSCSI integration
- 🔐 RBAC support via `flask-rbac-icdc`
- 🌐 CORS support for API consumers

---

## 🛠 Tech Stack

| Area | Technology |
| --- | --- |
| 🐍 Language | Python 3.12 |
| 🌶 Framework | Flask |
| 🧩 ORM | SQLAlchemy, Flask-SQLAlchemy |
| 🐘 Database | PostgreSQL |
| 🔄 Migrations | Flask-Migrate |
| ☁️ Storage Integration | Ceph, RGW, RBD, iSCSI |
| 🪣 Object Storage Clients | `rgwadmin`, `boto3` |
| 🔑 Remote Access | `paramiko` |
| 🔐 Authorization | `flask-rbac-icdc` |
| 🚀 Server | Gunicorn |
| 🧪 Testing | pytest, pytest-cov |
| 🧹 Code Quality | Ruff, Pylint, pre-commit |
| 📦 Runtime | Docker / Podman |

---

## 📁 Project Structure

```text
.
├── app/
│   ├── controllers/   # Request handlers and business logic
│   ├── lib/           # External integrations and shared helpers
│   ├── models/        # SQLAlchemy models
│   ├── routers/       # Flask blueprints and API routes
│   ├── __init__.py    # Application factory
│   ├── consts.py      # Runtime configuration
│   └── database.py    # Database and migration setup
├── config/            # Environment-specific configuration
├── settings/          # Default application and RBAC settings
├── migrations/        # Alembic migrations
├── tests/             # Test suite
├── main.py            # Application entrypoint
├── entrypoint.sh      # Container startup script
├── Dockerfile         # Container build definition
└── run_tests.sh       # Integration test helper
```

---

## 🌐 API Overview

The service exposes versioned REST API endpoints under `/api/v2`.

| Area | Base Path |
| --- | --- |
| 👤 Accounts | `/api/v2/accounts` |
| 🪣 S3 | `/api/v2/s3` |
| 💽 iSCSI | `/api/v2/iscsi` |
| 🧭 Pools | `/api/v2/pools` |
| ❤️ Health | `/api/up` |

For the full API specification, including available operations, request/response schemas, and examples, refer to the OpenAPI documentation.

---

## 🚀 Running the Application

The application uses the Flask app factory pattern and exposes `main:flask_app` as the application entrypoint.

For local development:

```bash
export FLASK_APP=main:flask_app
flask run --host=0.0.0.0 --port=3000
```

Local server:

```text
http://0.0.0.0:3000
```

Health check:

```text
GET /api/up
```

---

## ⚙️ Configuration

Configuration is loaded from YAML files and can be overridden with environment variables.

### 📄 Configuration Files

```text
settings/config.yaml
config/config.yaml
settings/rbac.yaml
```

| File | Purpose |
| --- | --- |
| `settings/config.yaml` | Base application configuration shipped with the project. Defines the default config structure and values for logging, database, Ceph, SSH, storage pools, and pool limits. |
| `config/config.yaml` | Environment-specific override configuration. Used for real deployment values such as database credentials, Ceph hosts, access keys, SSH key paths, and group names. |
| `settings/rbac.yaml` | RBAC policy configuration. Defines available roles, permissions, and resource-level access filters for accounts, S3, iSCSI, and pools. |

### 🔃 Load Order

Configuration is loaded in the following order:

```text
1. settings/config.yaml
2. config/config.yaml
3. settings/rbac.yaml
```

For individual keys, environment variables have the highest priority and override YAML values.

### 🌱 Common Environment Variables

```bash
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_USERNAME=postgres
DATABASE_PASSWORD=postgres
DATABASE_NAME=storage_api

CEPH_HOST=localhost
CEPH_PORT=8000
CEPH_ACCESS_KEY=access_key
CEPH_SECRET_KEY=secret_key

LOG_LEVEL=DEBUG
```

Depending on the feature set, SSH and RBAC-related values may also be required.

---

## 💻 Local Development

### 📌 Requirements

- 🐍 Python 3.12
- 🐘 PostgreSQL
- ☁️ Access to Ceph environment
- 📦 `pip`

Some Ceph-related Python modules are provided by the operating system rather than installed from `requirements.txt`.

In particular, the application may require the following Ceph Python bindings:

- `rados` — Python bindings for Ceph RADOS
- `rbd` — Python bindings for Ceph RBD

Example installation on Fedora/RHEL-like systems:

```bash
sudo dnf install python3-rados python3-rbd
```

---

## ☁️ Ceph Preparation

Before the API can work correctly against a real storage environment, the Ceph side must also be prepared.

### 🪣 1. Prepare RGW Admin Access for S3 Operations

The S3 part of the API uses Ceph RGW administrative and user-level operations through:

- `rgwadmin`
- `boto3`
- `radosgw-admin` over SSH

To make that work, you need:

- Reachable RGW endpoint configured through `CEPH_HOST` and `CEPH_PORT`
- Valid RGW admin credentials in `CEPH_ACCESS_KEY` and `CEPH_SECRET_KEY`
- Object storage pools and placement targets that match the pool names expected by the application configuration

Without valid RGW admin credentials, features such as S3 user creation, quota changes, bucket inspection, and key regeneration will not work.

### 🔑 2. Prepare SSH Access to the Ceph Host

Some administrative actions are executed remotely over SSH, including `radosgw-admin` commands.

You need:

- Reachable SSH host in `CEPH_SSH_HOST`
- Correct SSH port in `CEPH_SSH_PORT`
- Valid SSH username in `CEPH_SSH_USER`
- Readable private key file in `CEPH_SSH_KEY`
- Remote host where `radosgw-admin` is installed and usable for the target Ceph cluster

If SSH access is missing or misconfigured, operations that depend on remote `radosgw-admin` execution will fail even if the RGW HTTP endpoint is reachable.

### 💽 3. Prepare Ceph Client Configuration for iSCSI/RBD Features

The iSCSI part of the application uses Ceph RBD bindings directly through `rados` and `rbd`.

For those features to work, the runtime environment usually needs:

- `/etc/ceph/ceph.conf`
- Credentials for the `client.storage` Ceph user
- `/etc/ceph/ceph.client.storage.keyring`
- Permission for that Ceph client to access the required RBD pools

In a typical Ceph host you may see files such as:

- `/etc/ceph/ceph.conf`
- `/etc/ceph/ceph.client.storage.keyring`
- `/etc/ceph/ceph.client.admin.keyring`

For this application, the important identity for direct RBD access is `client.storage`, because the code connects with:

```python
rados.Rados(conffile="/etc/ceph/ceph.conf", name="client.storage")
```

So the storage keyring must be present and readable in the runtime environment. The admin keyring may exist on the host as well, but it is not the primary credential this code path is using.

Without this client-side Ceph configuration, block-storage operations such as RBD image lookup, disk operations, and snapshot-related actions may fail.

### 🌐 4. Prepare iSCSI Gateway API Access

The application also talks to configured iSCSI gateways over HTTP API using gateway-specific credentials stored in the database.

This means you need:

- Reachable iSCSI gateway nodes
- Valid `api_user` and `api_password` values for each gateway
- Correct gateway IP addresses
- Network connectivity from the application to the gateway API port

### 🧭 5. Make Sure Configured Pools Really Exist

Pool names and limits are defined in `settings/config.yaml` and/or `config/config.yaml`.

Before using the API, verify that:

- The configured S3 pool names correspond to real RGW placement or storage targets
- The configured iSCSI pools correspond to real RBD pools in Ceph
- The application limits reflect what your environment actually allows

If the configured pool names do not exist in Ceph, user, bucket, disk, and quota operations may succeed in the database layer but fail when the service reaches the storage backend.

---

## 📦 Installation

```bash
python3.12 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

---

## 🔄 Database Migrations

Database migrations are usually applied through `entrypoint.sh`, which runs the required Flask-Migrate command before starting the application.

```bash
./entrypoint.sh
```

If you need to run migrations manually, use:

```bash
export FLASK_APP=main:flask_app
flask db upgrade --directory migrations
```

---

## 🌱 Seed Initial Data

Initial data seeding is not executed automatically by `entrypoint.sh`.

The container startup script currently applies database migrations only. If you need initial data such as default pool metadata, run seeding manually:

```bash
export FLASK_APP=main:flask_app
flask seed
```

---

## 🐳 Container Usage

Build the image:

```bash
docker build -t storage-api .
```

or:

```bash
podman build -t storage-api .
```

Run the container:

```bash
docker run --rm -p 8080:8080 --name storage-api storage-api
```

In container mode, database migrations are applied automatically before Gunicorn starts.

---

## ☁️ Deployment Notes

For containerized deployment, the service requires:

- 🐘 PostgreSQL connectivity
- ☁️ Ceph configuration and credentials
- 🔐 RBAC configuration
- 🔑 Optional SSH key material for Ceph/iSCSI operations
- ⚙️ Mounted YAML configuration files when needed

Common Ceph files:

```text
ceph.conf
ceph.client.storage.keyring
```

---

## 🧪 Testing

Run tests:

```bash
pytest
```

Run integration tests through the helper script:

```bash
export DATABASE_USERNAME="storage_username"
export DATABASE_PASSWORD="storage_password"
export DATABASE_NAME="storage_database"

touch report.xml
mkdir -p htmlcov

./run_tests.sh storage
```

---

## 🧹 Code Quality

Install Git hooks:

```bash
pip install pre-commit
pre-commit install
pre-commit install --hook-type pre-push
```

Run checks manually:

```bash
pre-commit run -a
ruff check .
ruff format .
pytest
```

---

## 📝 Notes

- 🌐 CORS is enabled for all routes.
- 🔐 RBAC policies are defined in `settings/rbac.yaml`.
- 🏭 The application factory is located in `app/__init__.py`.
- 💻 Local runtime uses Flask CLI with `main:flask_app`.
- 🚀 Container runtime uses Gunicorn with `main:flask_app`.

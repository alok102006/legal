# LegalOS Project Setup Guide

Welcome to **LegalOS**, a multi-workspace production-grade AI Legal & Compliance Operating System for Indian SMEs. This guide provides comprehensive, step-by-step instructions to set up the project locally on your machine.

---

## 🏗️ Architecture Overview

LegalOS consists of the following components:
1. **Backend**: A FastAPI application (`legalos/backend`) handling business logic, document ingestion, vector retrieval (Qdrant), database ORM (SQLAlchemy + Alembic), and LLM orchestration (Gemini API via `google-genai`).
2. **Frontend**: A React application (`legalos/frontend`) built using Vite, TypeScript, and Tailwind CSS.
3. **Database**: PostgreSQL (v15) for relational data persistence.
4. **Vector Database**: Qdrant for storing and retrieving high-dimensional embeddings (sentence-transformers MiniLM-L6-v2).

---

## 🛠️ Prerequisites

Before starting, ensure you have the following installed on your local machine:

- **Docker & Docker Compose**: (Highly Recommended) [Install Docker Desktop](https://www.docker.com/products/docker-desktop/)
- **Python**: v3.10 or higher (Needed for local backend setup) [Download Python](https://www.python.org/downloads/)
- **Poetry**: Python dependency manager [Install Poetry](https://python-poetry.org/docs/#installation)
- **Node.js**: v18.x or higher & **npm** (Needed for local frontend setup) [Download Node.js](https://nodejs.org/)

---

## 🔑 Environment Variables Setup

You need to create and configure the environment variables file for the project to run successfully.

1. Locate the root-level configuration files inside the [legalos](file:///c:/Users/Asus/Desktop/LegalOs/legalos/) folder:
   - Main env: [legalos/.env.example](file:///c:/Users/Asus/Desktop/LegalOs/legalos/.env.example)
   - Backend env: [legalos/backend/.env.example](file:///c:/Users/Asus/Desktop/LegalOs/legalos/backend/.env.example)
   - Frontend env: [legalos/frontend/.env.example](file:///c:/Users/Asus/Desktop/LegalOs/legalos/frontend/.env.example)

2. Copy the example files:
   ```bash
   # From root repository directory, navigate to legalos/
   cd legalos

   # Copy root env example
   cp .env.example .env

   # Copy backend env example
   cp backend/.env.example backend/.env

   # Copy frontend env example
   cp frontend/.env.example frontend/.env
   ```

3. **Configure API Keys**:
   Open [legalos/.env](file:///c:/Users/Asus/Desktop/LegalOs/legalos/.env) and [legalos/backend/.env](file:///c:/Users/Asus/Desktop/LegalOs/legalos/backend/.env) and populate the `GEMINI_API_KEY` with your actual Google Gemini API key:
   ```env
   GEMINI_API_KEY=your_actual_gemini_api_key_here
   ```

---

## 🐳 Option A: Quick Start with Docker (Recommended)

Docker Compose sets up all required services (Database, Qdrant Vector DB, Backend server, and Frontend dashboard) with a single command.

### 1. Build and Run Container Services
From the [legalos](file:///c:/Users/Asus/Desktop/LegalOs/legalos/) directory, run:
```bash
docker-compose up --build
```
This builds the frontend and backend, downloads PostgreSQL & Qdrant images, and starts the applications on the following ports:
- **Frontend Dashboard**: [http://localhost:5173](http://localhost:5173)
- **Backend Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **PostgreSQL**: `localhost:5435`
- **Qdrant Dashboard**: [http://localhost:6335/dashboard](http://localhost:6335/dashboard)

### 2. Apply Database Migrations
While the containers are running, apply migrations to set up the PostgreSQL database schema:
```bash
docker-compose exec backend alembic upgrade head
```

---

## 💻 Option B: Local/Hybrid Setup (For Active Development)

If you are writing code and want faster local hot-reloading/debugging, you can run databases in Docker but run the backend and frontend servers natively.

### Step 1: Spin up Databases in Docker
Run PostgreSQL and Qdrant in the background:
```bash
docker-compose up -d db qdrant
```

### Step 2: Backend Setup (FastAPI)

1. Open your terminal and navigate to the backend folder:
   ```bash
   cd legalos/backend
   ```
2. Verify Poetry is installed and install Python dependencies:
   ```bash
   poetry install
   ```
3. Run database migrations to initialize tables locally:
   ```bash
   poetry run alembic upgrade head
   ```
4. Start the FastAPI local development server:
   ```bash
   python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

   ```
   *Note: During startup, backend will automatically download the local embedding model `sentence-transformers/all-MiniLM-L6-v2` and cache it in `./model_cache`.*

### Step 3: Frontend Setup (Vite + React)

1. Open a new terminal and navigate to the frontend folder:
   ```bash
   cd legalos/frontend
   ```
2. Install npm dependencies:
   ```npm
   npm install
   ```
3. Start the Vite React local development server:
   ```bash
   npm run dev
   ```
4. Access the dashboard at [http://localhost:5173](http://localhost:5173).

---

## 🧪 Verification & Running Tests

To verify that the project is running correctly, you can run the test suite:

### Backend Tests
Ensure your dependencies are installed, then run `pytest` from the backend folder:
```bash
cd legalos/backend
poetry run pytest
```

### Check API Health
You can also call the healthcheck endpoint:
```bash
curl http://localhost:8000/health
```
**Expected Response:**
```json
{
  "status": "healthy",
  "timestamp": 1721731234.56,
  "provider": "gemini"
}
```

---

## 🛠️ Troubleshooting & Tips

### 1. `pymupdf` License Warning
This project uses **PyMuPDF** for PDF parsing. Please note that PyMuPDF is licensed under the **GNU AGPL (Affero General Public License)**. If you modify and distribute this system as a SaaS service, you are legally required to make the modified source code available.

### 2. Missing `GEMINI_API_KEY` Error
If the backend throws an initialization error, check that `GEMINI_API_KEY` is present in your environment or defined in the `.env` file within the [legalos/backend/](file:///c:/Users/Asus/Desktop/LegalOs/legalos/backend/) directory.

### 3. Port Conflicts
Ensure the following ports on your host machine are not being used by other services:
- `5173` (Frontend)
- `8000` (Backend FastAPI)
- `5435` (PostgreSQL DB)
- `6335` & `6336` (Qdrant Vector DB)

If ports are in use, you can customize the mappings inside [docker-compose.yml](file:///c:/Users/Asus/Desktop/LegalOs/legalos/docker-compose.yml).

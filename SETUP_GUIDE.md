# Setup Guide for HR CV Upload and Interview Link System

This guide will help you set up the new HR workflow features for uploading CVs, generating interview links, and managing candidate interviews.

---

## Option A: Run with Docker (recommended, no local installs)

You only need **Docker** and **Docker Compose** installed. PostgreSQL and Python run inside containers.

### 1. Create a `.env` file

In the project root (`AI-Interview-Simulator-Backend`), create a `.env` file. You can copy `.env.example` and then add your OpenAI key (and optional SMTP for emails):

```env
# Required for AI features
OPENAI_API_KEY=your_openai_api_key_here

# Optional: SMTP for sending interview emails
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USERNAME=your_email@gmail.com
# SMTP_PASSWORD=your_app_password
# SMTP_FROM_EMAIL=noreply@example.com

# Optional: app settings (defaults work with Docker)
# FRONTEND_URL=http://localhost:8080   (URL where the frontend runs; interview links point here)
# BASE_URL=http://localhost:8000
# DEFAULT_LINK_EXPIRY_DAYS=7
# MAX_CV_FILE_SIZE_MB=10
# AI_INTERVIEW_ALLOW_ORIGINS=*
```

Database URL is set automatically by Docker Compose; you don’t need to set `DATABASE_URL`.

Set `FRONTEND_URL` to your frontend origin (e.g. `http://localhost:8080`) so interview links open the app, not the API.

### 2. Start everything

From the backend project root (`AI-Interview-Simulator-Backend`):

```bash
docker compose up --build
```

- First run builds the backend image and starts PostgreSQL and the API.
- Migrations run automatically on startup.
- API: **http://localhost:8000**
- PostgreSQL is on `localhost:5432` (user `postgres`, password `postgres`, db `ai_interview_db`) if you need to connect from the host.

### 3. Stop

```bash
docker compose down
```

To remove the database volume as well: `docker compose down -v`.

---

## Option B: Local setup (Python + PostgreSQL on your machine)

### Prerequisites

1. **PostgreSQL Database**: You need a PostgreSQL database server running
2. **Python 3.10+**: Ensure Python 3.10 or higher is installed
3. **OpenAI API Key**: For AI-powered CV extraction and interview questions
4. **SMTP Email Account**: For sending interview invitation emails

## Step-by-Step Setup

### 1. Install Dependencies

```bash
uv pip install -e .[dev]
```

This will install all required packages including:
- SQLAlchemy for database ORM
- Alembic for database migrations
- PDF and DOCX parsing libraries
- Email libraries
- And all existing dependencies

### 2. Create PostgreSQL Database

```bash
# Using psql
psql -U postgres
CREATE DATABASE ai_interview_db;

# Or using createdb command
createdb ai_interview_db
```

### 3. Configure Environment Variables

Create a `.env` file in the project root (copy from `.env.example` if it exists):

```env
# OpenAI API Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Database Configuration
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost/ai_interview_db
DATABASE_ECHO=false

# SMTP Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM_EMAIL=noreply@example.com

# Application Configuration
BASE_URL=http://localhost:8000
DEFAULT_LINK_EXPIRY_DAYS=7
MAX_CV_FILE_SIZE_MB=10

# CORS Configuration
AI_INTERVIEW_ALLOW_ORIGINS=*
```

**Important Notes:**
- For Gmail, you'll need to use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password
- Update `BASE_URL` to your production URL when deploying
- Adjust `DEFAULT_LINK_EXPIRY_DAYS` as needed (default: 7 days)

### 4. Run Database Migrations

```bash
alembic upgrade head
```

This will create the following tables:
- `interview_links` - Stores generated interview links and CV data
- `interview_results` - Stores completed interview results

### 5. Create Uploads Directory

The application will automatically create the `uploads/cvs/` directory, but you can create it manually:

```bash
mkdir -p uploads/cvs
```

### 6. Start the API Server

```bash
uvicorn ai_interview_bot.api:app --reload
```

The API will be available at `http://localhost:8000`

## Testing the Setup

### Test HR Endpoint: Create Interview from CV

```bash
curl -X POST http://localhost:8000/hr/interviews/create \
  -F "hr_email=hr@example.com" \
  -F "candidate_email=candidate@example.com" \
  -F "candidate_name=John Doe" \
  -F "role=Software Engineer" \
  -F "level=mid" \
  -F "questions=5" \
  -F "expires_in_days=7" \
  -F "cv_file=@/path/to/resume.pdf"
```

Expected response:
```json
{
  "interview_id": "uuid-here",
  "token": "secure-token-here",
  "interview_link": "http://localhost:8000/interview/secure-token-here",
  "candidate_email": "candidate@example.com",
  "candidate_name": "John Doe",
  "role": "Software Engineer",
  "level": "mid",
  "expires_at": "2024-01-08T00:00:00",
  "status": "pending"
}
```

### Test Candidate Access: Use Interview Link

```bash
curl http://localhost:8000/interview/{token}
```

This will start the interview session and return the first question.

### Test HR Endpoint: Get Interview Results

```bash
curl "http://localhost:8000/hr/interviews/{interview_id}/results?hr_email=hr@example.com"
```

## API Endpoints Summary

### HR Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/hr/interviews/create` | Upload CV, create interview link, send email |
| GET | `/hr/interviews?hr_email={email}` | List all interviews by HR |
| GET | `/hr/interviews/{id}?hr_email={email}` | Get interview details |
| GET | `/hr/interviews/{id}/results?hr_email={email}` | Get interview results |

### Candidate Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/interview/{token}` | Access interview via secure link |
| POST | `/interviews/{session_id}/answer` | Submit answer to question |
| GET | `/interviews/{session_id}` | Get current interview state |

## Troubleshooting

### Database Connection Issues

- Verify PostgreSQL is running: `pg_isready`
- Check database credentials in `.env`
- Ensure database exists: `psql -l | grep ai_interview_db`

### Email Sending Issues

- For Gmail: Use App Password, not regular password
- Check SMTP settings match your email provider
- Verify firewall/network allows SMTP connections
- Check spam folder if emails aren't received

### CV Parsing Issues

- Ensure CV files are PDF or DOCX format
- Check file size is under `MAX_CV_FILE_SIZE_MB`
- Verify OpenAI API key is valid and has credits

### Migration Issues

- If migrations fail, check database connection
- Verify Alembic can find models: `alembic current`
- Manually run migration if needed: `alembic upgrade head`

## Next Steps

1. **Frontend Integration**: Build a frontend to consume these APIs
2. **Authentication**: Add authentication for HR users (currently open)
3. **Email Templates**: Customize email templates in `email_service.py`
4. **CV Extraction**: Fine-tune CV extraction prompts in `cv_parser.py`
5. **Monitoring**: Add logging and monitoring for production use

## Production Considerations

1. **Security**:
   - Add authentication/authorization for HR endpoints
   - Use HTTPS for all API calls
   - Secure file uploads (validate file types, scan for malware)
   - Rate limiting on endpoints

2. **Performance**:
   - Use connection pooling for database
   - Implement file storage (S3, etc.) instead of local filesystem
   - Add caching for frequently accessed data
   - Background job processing for email sending

3. **Scalability**:
   - Use message queue for email sending
   - Implement session persistence (Redis, database)
   - Add load balancing for API server
   - Database replication for high availability

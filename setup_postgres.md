# PostgreSQL with pgvector Setup Guide

## Prerequisites

1. **Install PostgreSQL** (version 12 or higher)
2. **Install pgvector extension**

### On Ubuntu/Debian:
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo apt install postgresql-14-pgvector  # Replace 14 with your PostgreSQL version
```

### On macOS (using Homebrew):
```bash
brew install postgresql
brew install pgvector
```

### On Windows:
1. Download and install PostgreSQL from https://www.postgresql.org/download/windows/
2. Install pgvector from https://github.com/pgvector/pgvector

## Database Setup

1. **Create database and user:**
```sql
-- Connect to PostgreSQL as superuser
sudo -u postgres psql

-- Create database
CREATE DATABASE rag_chatbot;

-- Create user
CREATE USER rag_user WITH PASSWORD 'your_password_here';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE rag_chatbot TO rag_user;

-- Connect to the new database
\c rag_chatbot

-- Enable pgvector extension
CREATE EXTENSION vector;

-- Grant usage on schema
GRANT USAGE ON SCHEMA public TO rag_user;
GRANT CREATE ON SCHEMA public TO rag_user;

-- Exit
\q
```

2. **Configure environment variables:**
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your database credentials
DB_NAME=rag_chatbot
DB_USER=rag_user
DB_PASSWORD=your_password_here
DB_HOST=localhost
DB_PORT=5432
```

## Django Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Run migrations:**
```bash
python manage.py makemigrations
python manage.py migrate
```

3. **Create superuser (optional):**
```bash
python manage.py createsuperuser
```

4. **Start the development server:**
```bash
python manage.py runserver
```

## Verify Installation

1. **Check pgvector is working:**
```sql
-- Connect to your database
psql -U rag_user -d rag_chatbot

-- Test vector operations
SELECT '[1,2,3]'::vector <-> '[4,5,6]'::vector;
```

2. **Test the API:**
```bash
# Health check
curl http://localhost:8000/api/health/

# Create a chat session
curl -X POST http://localhost:8000/api/chat/sessions/

# Ingest a GitHub repository
curl -X POST http://localhost:8000/api/ingest/github/ \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/your-username/your-repo.git"}'
```

## Production Considerations

1. **Use environment variables for sensitive data**
2. **Set up connection pooling with pgbouncer**
3. **Configure proper indexes for better performance**
4. **Set up regular backups**
5. **Monitor vector database performance**

## Troubleshooting

### Common Issues:

1. **pgvector extension not found:**
   - Make sure pgvector is installed for your PostgreSQL version
   - Verify the extension is available: `SELECT * FROM pg_available_extensions WHERE name = 'vector';`

2. **Permission denied:**
   - Ensure your database user has proper permissions
   - Grant necessary privileges on the database and schema

3. **Connection refused:**
   - Check if PostgreSQL is running: `sudo systemctl status postgresql`
   - Verify connection parameters in .env file

4. **Migration errors:**
   - Drop and recreate the database if needed (development only)
   - Check PostgreSQL logs for detailed error messages
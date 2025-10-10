#!/bin/bash
# entrypoint.sh

echo "Waiting for PostgreSQL..."
while ! pg_isready -h db -p 5432 -U postgres > /dev/null 2>&1; do
    sleep 1
done

echo "PostgreSQL is ready!"

# Run migrations
echo "Running migrations..."
python manage.py migrate

# Create pgvector extension
echo "Creating pgvector extension..."
PGPASSWORD=postgres psql -h db -U postgres -d fin_research_db -c "CREATE EXTENSION IF NOT EXISTS vector;" || true

# Create superuser if doesn't exist
echo "Creating superuser..."
python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Superuser created!')
else:
    print('Superuser already exists.')
END

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Seed documents if requested
if [ "$SEED_DOCUMENTS" = "true" ]; then
    echo "Seeding documents..."
    python manage.py seed_documents || true
fi

# Start server
echo "Starting Django server..."
exec "$@"
#!/bin/sh

# Replace environment variables in built files at runtime
echo "Injecting runtime environment variables..."

# Find all JavaScript files and replace placeholder with actual environment variable
find /usr/share/nginx/html -name "*.js" -exec sed -i "s|__REACT_APP_RECAPTCHA_SITE_KEY__|${REACT_APP_RECAPTCHA_SITE_KEY}|g" {} \;

echo "Environment variables injected successfully"

# Start nginx
exec "$@"
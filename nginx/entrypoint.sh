#!/bin/sh
set -e

if [ "$MIGRATE" = "true" ] || [ "$MIGRATE" = "True" ] || [ "$MIGRATE" = "1" ]; then
    echo "MIGRATE=True → routing to nextjs:3000"
    cp /etc/nginx/conf.d/nginx.conf.next /etc/nginx/conf.d/default.conf
else
    echo "MIGRATE not set → routing to frontend:5173"
    cp /etc/nginx/conf.d/nginx.conf.legacy /etc/nginx/conf.d/default.conf
fi

exec nginx -g "daemon off;"

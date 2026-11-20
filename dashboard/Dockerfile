# Assets (Vite)
FROM node:22-alpine AS assets
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Dependências PHP
FROM composer:2 AS vendor
WORKDIR /app
COPY composer.json composer.lock ./
RUN composer install --no-dev --no-scripts --prefer-dist --no-interaction

# Runtime
FROM php:8.4-cli
RUN apt-get update && apt-get install -y --no-install-recommends libzip-dev \
 && docker-php-ext-install exif zip \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /var/www
COPY . .
COPY --from=vendor /app/vendor ./vendor
COPY --from=assets /app/public/build ./public/build
RUN php artisan package:discover --ansi \
    && chown -R www-data:www-data storage bootstrap/cache database
EXPOSE 8080
CMD ["sh", "-c", "touch database/database.sqlite && php artisan migrate --force && php artisan serve --host=0.0.0.0 --port=8080"]

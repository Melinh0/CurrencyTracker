# ============================================
# CurrencyTracker Frontend - Multi-stage Dockerfile
# ============================================

# --------------------------------------------
# Build Stage
# --------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# --------------------------------------------
# Production Stage - Nginx
# --------------------------------------------
FROM nginx:alpine AS production

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost/ || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]

# --------------------------------------------
# Development Stage
# --------------------------------------------
FROM node:20-alpine AS dev

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy source
COPY . .

# Expose Vite dev server port
EXPOSE 3000

# Start dev server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
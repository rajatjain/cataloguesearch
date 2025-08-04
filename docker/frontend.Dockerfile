# --- Stage 1: Build the React application ---
FROM node:18-alpine as builder

WORKDIR /app

# The build context is the project root, so we specify the path to frontend/
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# --- Stage 2: Serve the application with Nginx ---
FROM nginx:1.25-alpine

# Copy the built static files from the builder stage
COPY --from=builder /app/build /usr/share/nginx/html

# Copy the Nginx configuration file
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
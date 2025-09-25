FROM node:18-slim AS builder

# Set environment variables to help with optional dependencies
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV CYPRESS_INSTALL_BINARY=0

WORKDIR /app

# Configure npm for better reliability
RUN npm config set registry https://registry.npmmirror.com/ && \
    npm config set fetch-retry-mintimeout 20000 && \
    npm config set fetch-retry-maxtimeout 120000 && \
    npm config set fetch-retries 3 && \
    npm config set audit-level moderate && \
    npm cache clean --force

# Copy package files
COPY package.json package-lock.json ./

# Install all dependencies including devDependencies (needed for TypeScript and build tools)
RUN rm -rf node_modules && \
    npm ci --include=dev --include=optional --legacy-peer-deps --verbose || \
    (echo "First install attempt failed, retrying with npm install..." && \
     rm -rf node_modules package-lock.json && \
     npm install --legacy-peer-deps --verbose)

# Verify critical build tools are installed
RUN npx tsc --version && \
    npx vite --version && \
    echo "Build tools verified successfully"

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Run stage
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
COPY default.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

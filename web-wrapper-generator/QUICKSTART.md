# Quick Start Guide

This guide will help you get started with the Web Wrapper Generator for Lovable Apps.

## Prerequisites

- **Go 1.21+** installed on your system
- **Node.js and npm** (optional, but recommended for real installer generation)

## Quick Setup

1. Navigate to the web-wrapper-generator directory:
   ```bash
   cd web-wrapper-generator
   ```

2. Build the application:
   ```bash
   go build -o web-wrapper-generator
   ```

3. Run the server:
   ```bash
   ./web-wrapper-generator
   ```

   The server will start on port 8080 by default. You can change the port:
   ```bash
   PORT=3000 ./web-wrapper-generator
   ```

4. Open your browser and go to:
   ```
   http://localhost:8080
   ```

## Using the Application

1. **Enter your Lovable app URL** in the input field (e.g., `https://your-app.lovable.app`)
2. **Click "Generate Wrapper"** to start the process
3. **Wait for the generation** to complete (you'll see status updates)
4. **Download installers** for your desired platforms:
   - Windows (.exe)
   - macOS (.dmg)
   - Linux (.AppImage)

## API Usage

If you prefer to use the API directly:

### Generate a wrapper
```bash
curl -X POST http://localhost:8080/api/generate \
  -H "Content-Type: application/json" \
  -d '{"url":"https://your-app.lovable.app"}' \
  | jq .
```

Response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Check status
```bash
curl http://localhost:8080/api/status/{job_id} | jq .
```

### Download installer
```bash
curl -O http://localhost:8080/api/download/{job_id}/windows
curl -O http://localhost:8080/api/download/{job_id}/macos
curl -O http://localhost:8080/api/download/{job_id}/linux
```

## How It Works

The generator:
1. Creates an Electron project configured to load your Lovable app URL
2. Attempts to build native installers using electron-builder
3. If building fails (e.g., missing dependencies), creates placeholder files
4. Makes installers available for download

## Production Deployment

For production use:

1. **Build the binary**:
   ```bash
   CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o web-wrapper-generator
   ```

2. **Install Node.js/npm** on your server for full functionality

3. **Run with appropriate permissions**:
   ```bash
   PORT=8080 ./web-wrapper-generator
   ```

4. **Consider adding**:
   - Reverse proxy (nginx, Caddy)
   - HTTPS/TLS certificate
   - Authentication
   - Rate limiting
   - Monitoring

## Troubleshooting

**Q: I only get placeholder files, not real installers**
- **A**: Make sure Node.js and npm are installed on your system

**Q: Port 8080 is already in use**
- **A**: Use a different port: `PORT=9090 ./web-wrapper-generator`

**Q: Windows builds fail on Linux**
- **A**: Cross-platform building requires additional tools (wine, etc.). Consider using Docker or building on the target platform

**Q: macOS builds fail**
- **A**: Building macOS installers typically requires running on a Mac or using specialized CI/CD services

## Examples

### Example 1: Basic Usage
```bash
# Start server
./web-wrapper-generator

# In another terminal, generate wrapper
curl -X POST http://localhost:8080/api/generate \
  -H "Content-Type: application/json" \
  -d '{"url":"https://myapp.lovable.app"}'
```

### Example 2: Production Setup with nginx
```nginx
server {
    listen 80;
    server_name wrappers.example.com;

    location / {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

### Example 3: Docker Deployment
```dockerfile
FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY . .
RUN go build -o web-wrapper-generator

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/web-wrapper-generator .
RUN npm install -g electron-builder
EXPOSE 8080
CMD ["./web-wrapper-generator"]
```

## Next Steps

- Read the full [README.md](README.md) for detailed information
- Explore the source code in [main.go](main.go)
- Consider adding authentication for production use
- Implement webhook notifications for completed builds
- Add custom branding options for generated apps

## Support

For issues or questions:
- Check the main repository README
- Review the logs (server outputs detailed build information)
- Ensure all prerequisites are installed

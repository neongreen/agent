# Web Wrapper Generator for Lovable Apps

A Go web application that generates native app wrappers for Lovable applications. This tool creates Electron-based wrappers and builds installers for Windows, macOS, and Linux platforms.

## Features

- 🌐 Web-based interface for easy app wrapper generation
- 🎯 Generates Electron-based native wrappers
- 📦 Builds installers for multiple platforms:
  - Windows (NSIS installer)
  - macOS (DMG installer)
  - Linux (AppImage)
- 🔄 Real-time status updates during generation
- 📥 Direct download links for generated installers
- 🚀 Async job processing for handling multiple requests

## Architecture

The application consists of:

1. **Go Backend Server**: Handles HTTP requests, manages job queue, and orchestrates the build process
2. **Web Frontend**: Simple HTML/CSS/JavaScript interface for submitting URLs and downloading installers
3. **Electron Wrapper Generator**: Creates Electron applications that wrap the target Lovable app
4. **Installer Builder**: Uses electron-builder to create platform-specific installers

## Prerequisites

- **Go 1.21+** (for running the server)
- **Node.js and npm** (optional, for building actual installers)
  - If npm is not available, the server will create placeholder installers for demonstration

## Installation

1. Navigate to the web-wrapper-generator directory:
   ```bash
   cd web-wrapper-generator
   ```

2. Install Go dependencies:
   ```bash
   go mod download
   ```

3. Build the application:
   ```bash
   go build -o web-wrapper-generator
   ```

## Usage

### Starting the Server

```bash
./web-wrapper-generator
```

By default, the server starts on port 8080. You can change this by setting the `PORT` environment variable:

```bash
PORT=3000 ./web-wrapper-generator
```

### Using the Web Interface

1. Open your browser and navigate to `http://localhost:8080`
2. Enter the URL of your Lovable app (e.g., `https://your-app.lovable.app`)
3. Click "Generate Wrapper"
4. Wait for the generation process to complete
5. Download the installers for your desired platforms

### API Endpoints

#### POST /api/generate
Generate a new app wrapper.

**Request Body:**
```json
{
  "url": "https://your-lovable-app.lovable.app"
}
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### GET /api/status/{job_id}
Check the status of a generation job.

**Response:**
```json
{
  "ID": "550e8400-e29b-41d4-a716-446655440000",
  "URL": "https://your-lovable-app.lovable.app",
  "Status": "completed",
  "CreatedAt": "2024-01-01T12:00:00Z",
  "CompletedAt": "2024-01-01T12:05:00Z",
  "Error": "",
  "OutputDir": "./builds/550e8400-e29b-41d4-a716-446655440000"
}
```

**Status values:**
- `queued`: Job is waiting to be processed
- `generating`: Job is currently being processed
- `completed`: Job completed successfully
- `failed`: Job failed (check Error field for details)

#### GET /api/download/{job_id}/{platform}
Download the generated installer for a specific platform.

**Platforms:**
- `windows`: Downloads the Windows installer (.exe)
- `macos`: Downloads the macOS installer (.dmg)
- `linux`: Downloads the Linux installer (.AppImage)

## How It Works

1. **Request Submission**: User submits a Lovable app URL through the web interface
2. **Job Creation**: Server creates a unique job ID and queues the generation task
3. **Wrapper Generation**: 
   - Creates an Electron project with package.json and main.js
   - Configures the app to load the specified URL
4. **Installer Building**:
   - If npm is available: Installs dependencies and builds real installers using electron-builder
   - If npm is not available: Creates placeholder installer files for demonstration
5. **Download**: Generated installers are made available for download

## Project Structure

```
web-wrapper-generator/
├── main.go           # Main server implementation
├── go.mod            # Go module dependencies
├── go.sum            # Go module checksums
├── README.md         # This file
└── builds/           # Generated builds (created at runtime)
    └── {job-id}/     # Individual job directories
        ├── package.json
        ├── main.js
        └── installer-{platform}.{ext}
```

## Building for Production

For production deployment:

1. Build the Go binary:
   ```bash
   CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o web-wrapper-generator
   ```

2. Ensure Node.js and npm are installed on the production server for full functionality

3. Set appropriate environment variables:
   ```bash
   export PORT=8080
   ```

4. Run the server:
   ```bash
   ./web-wrapper-generator
   ```

## Limitations and Future Improvements

**Current Limitations:**
- Requires npm/node for real installer generation (falls back to dummy files otherwise)
- Cross-platform building may require running on respective platforms
- No authentication or rate limiting
- Limited customization options for the generated apps

**Potential Improvements:**
- Add authentication and user management
- Support custom app icons and names
- Add progress bars for long-running builds
- Implement build caching for faster subsequent builds
- Add support for more customization options (window size, app name, etc.)
- Implement proper cross-platform building using docker containers
- Add webhook notifications when builds complete
- Support for automatic updates in generated apps

## Security Considerations

⚠️ **Warning**: This application executes shell commands and downloads external resources. In a production environment, you should:

- Implement proper input validation and sanitization
- Add authentication and authorization
- Rate limit requests to prevent abuse
- Run the build process in isolated containers
- Validate and sanitize URLs before processing
- Implement proper logging and monitoring

## License

This project follows the same license as the parent repository (MIT License).

## Troubleshooting

**Issue**: Installers are placeholder files
- **Solution**: Ensure Node.js and npm are installed on the system

**Issue**: Build fails with permission errors
- **Solution**: Ensure the `builds/` directory has proper write permissions

**Issue**: Port already in use
- **Solution**: Change the port using the `PORT` environment variable

**Issue**: Electron build fails
- **Solution**: Check that you have sufficient disk space and that npm can access the internet

## Contributing

Contributions are welcome! Please ensure your code follows the existing style and includes appropriate tests.

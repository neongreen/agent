# Multi-stage build for the Web Wrapper Generator

# Stage 1: Build the Go binary
FROM golang:1.21-alpine AS builder

WORKDIR /app

# Copy go mod files
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY main.go ./

# Build the binary
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o web-wrapper-generator .

# Stage 2: Create the runtime image with Node.js
FROM node:20-alpine

# Install necessary tools for electron-builder
RUN apk add --no-cache \
    git \
    python3 \
    make \
    g++ \
    cairo-dev \
    jpeg-dev \
    pango-dev \
    giflib-dev

WORKDIR /app

# Copy the binary from builder stage
COPY --from=builder /app/web-wrapper-generator .

# Create directories for builds
RUN mkdir -p ./builds ./templates

# Expose port
EXPOSE 8080

# Set environment variables
ENV PORT=8080

# Run the application
CMD ["./web-wrapper-generator"]

# LoopProxy

English | [中文](README.md)

<a name="README_EN.md"></a>

## LoopProxy

LoopProxy is a lightweight, high-performance HTTP proxy service that supports chained proxy forwarding, suitable for request routing in complex network environments.

### Features

- **Chain Proxying**: Support for multi-level proxy chains, flexible request path configuration
- **Timeout Control**: Customizable request timeout to prevent long-term blocking
- **Security Authentication**: Optional hash authentication mechanism to ensure service security
- **Cross-Origin Support**: Built-in CORS middleware supporting cross-origin requests
- **HTTP/2 Support**: Based on httpx client with HTTP/2 protocol support
- **Health Checking**: Provides a `/health` endpoint for service status monitoring

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MAX_PROXY_DEPTH` | Maximum proxy chain depth | 5 |
| `REQUEST_TIMEOUT_MS` | Request timeout (milliseconds) | 8000 |
| `HashAuth` | Hash authentication value | None |

### Request Headers

Use the following special request headers to control proxy behavior:

- `x-proxy-chain`: Base64 encoded JSON array containing target URLs in the proxy chain
- `x-loop-count`: Current proxy depth counter
- `x-target-url`: Final destination URL
- `HashAuth`: Allows access when matched with the value configured in environment variables

### Installation and Deployment

#### Dependencies

- Python 3.8+
- FastAPI
- Uvicorn
- httpx

#### Installation Steps

```bash
# Clone repository
git clone https://github.com/yourusername/looproxy.git
cd looproxy

# Install dependencies
pip install -r requirements.txt

# Start service
python main.py
```

The service runs by default at `http://localhost:8000`.

#### Docker Deployment

```bash
# Build image
docker build -t looproxy .

# Run container
docker run -p 8000:8000 -e HashAuth=your_secret_hash looproxy
```

### Usage Examples

#### Basic Proxy Request

```bash
curl -X GET "http://localhost:8000/any-path" \
  -H "x-target-url: https://example.com/target-api" \
  -H "HashAuth: your_secret_hash"
```

#### Chained Proxy Request

```bash
# Create proxy chain JSON array
PROXY_CHAIN='["https://proxy1.example.com", "https://proxy2.example.com"]'

# Base64 encode
ENCODED_CHAIN=$(echo -n $PROXY_CHAIN | base64)

# Send request
curl -X POST "http://localhost:8000/path" \
  -H "x-proxy-chain: $ENCODED_CHAIN" \
  -H "x-target-url: https://final-target.example.com/api" \
  -H "HashAuth: your_secret_hash" \
  -d '{"key": "value"}'
```

### Contribution Guidelines

Issue reports and pull requests are welcome. Please ensure you follow these steps:

1. Fork this repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Create a pull request

### License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### Performance Optimization

LoopProxy implements several performance optimization measures:

- Uses `uvloop` and `httptools` (non-Windows environments)
- HTTP/2 support reduces connection overhead
- Connection pool management optimization (max keepalive connections: 50, max connections: 100)
- Request timeout control to prevent resource depletion

Enjoy using LoopProxy!

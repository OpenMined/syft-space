# Rate Limit Policy Type

The Rate Limit policy type allows you to control the number of requests that can be made to an endpoint within a specific time window.

## Configuration Schema

The rate limit policy accepts the following configuration:

```python
{
    "limit": str,              # Rate limit in format "N/unit" (e.g., "50/m", "1000/h", "100/s")
    "scope": str,              # Scope of the rate limit (currently supports "per_user")
    "applied_to": list[str]    # List of user emails or ["*"] for all users
}
```

### Limit Format

The `limit` field uses a user-friendly format: `"N/unit"` where:
- `N` is a positive integer representing the number of requests allowed
- `unit` is one of:
  - `s` - seconds
  - `m` - minutes
  - `h` - hours

**Examples:**
- `"50/m"` - 50 requests per minute
- `"1000/h"` - 1000 requests per hour
- `"100/s"` - 100 requests per second

### Scope

Currently supports:
- `"per_user"` - Rate limit is applied per user (tracked by email)

### Applied To

Controls which users the rate limit applies to:
- `["*"]` - Apply to all users (default)
- `["user1@example.com", "user2@example.com"]` - Apply only to specific users

## Usage Examples

### Example 1: Basic Rate Limit for All Users

Limit all users to 100 requests per minute:

```json
{
    "name": "API Rate Limit",
    "policy_type": "rate_limit",
    "configuration": {
        "limit": "100/m",
        "scope": "per_user",
        "applied_to": ["*"]
    },
    "endpoint_id": "<endpoint-uuid>"
}
```

**Output Description:**
- Limit: 100 requests per 1 minute(s)
- Scope: per user
- Applies to: All users

### Example 2: Specific Users Only

Limit only specific users to 50 requests per hour:

```json
{
    "name": "Limited User Rate Limit",
    "policy_type": "rate_limit",
    "configuration": {
        "limit": "50/h",
        "scope": "per_user",
        "applied_to": ["user1@example.com", "user2@example.com"]
    },
    "endpoint_id": "<endpoint-uuid>"
}
```

**Output Description:**
- Limit: 50 requests per 1 hour(s)
- Scope: per user
- Applies to: user1@example.com, user2@example.com

### Example 3: High-Frequency Limit

Allow 1000 requests per second (for high-throughput endpoints):

```json
{
    "name": "High Throughput Limit",
    "policy_type": "rate_limit",
    "configuration": {
        "limit": "1000/s",
        "scope": "per_user",
        "applied_to": ["*"]
    },
    "endpoint_id": "<endpoint-uuid>"
}
```

**Output Description:**
- Limit: 1000 requests per 1 second(s)
- Scope: per user
- Applies to: All users

## API Usage

### Create a Rate Limit Policy

```bash
curl -X POST "http://localhost:8000/api/policies" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Rate limit 100/min",
    "policy_type": "rate_limit",
    "configuration": {
        "limit": "100/m",
        "scope": "per_user",
        "applied_to": ["*"]
    },
    "endpoint_id": "123e4567-e89b-12d3-a456-426614174000"
  }'
```

### Get Policy Type Information

```bash
curl "http://localhost:8000/api/policies/types/rate_limit"
```

Response:
```json
{
    "name": "Rate Limit",
    "description": "Limit the number of requests that can be made within a time window. Supports per-user rate limiting and selective application to specific users.",
    "config_schema": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "string",
                "description": "Rate limit in format \"N/unit\" where unit is s(econds), m(inutes), or h(ours)",
                "examples": ["50/m", "1000/h", "100/s"]
            },
            "scope": {
                "type": "string",
                "enum": ["per_user"],
                "default": "per_user",
                "description": "Scope of the rate limit"
            },
            "applied_to": {
                "type": "array",
                "items": {"type": "string"},
                "default": ["*"],
                "description": "List of user emails or '*' for all users"
            }
        },
        "required": ["limit"]
    },
    "icon": "⏱️",
    "enabled": true
}
```

## Behavior

### Rate Limit Enforcement

When a rate limit policy is attached to an endpoint:

1. **Pre-Hook Execution**: Before the endpoint processes a request, the policy checks:
   - If the user matches the `applied_to` filter
   - How many requests the user has made within the time window
   - If the limit has been exceeded

2. **Success Response**: If the limit is not exceeded:
   - The request proceeds normally
   - Request metadata includes rate limit status:
     ```python
     {
         "rate_limit": {
             "limit": "100/m",
             "requests_in_window": 42,
             "max_requests": 100,
             "window_seconds": 60
         }
     }
     ```

3. **Rate Limit Exceeded**: If the limit is exceeded:
   - The request is blocked with an exception
   - Error message: `"Rate limit exceeded: {limit}. Current requests in window: {count}"`
   - Example: `"Rate limit exceeded: 100 requests per 1 minute(s). Current requests in window: 100"`

### Time Window Tracking

- Requests are tracked in a sliding time window
- Old requests outside the window are automatically cleaned up
- Each user's requests are tracked separately (for `per_user` scope)

## Validation

The policy validates configuration on creation:

### Valid Configurations

✅ `"limit": "50/m"` - 50 per minute
✅ `"limit": "1000/h"` - 1000 per hour
✅ `"limit": "100/s"` - 100 per second
✅ `"limit": "1/s"` - 1 per second

### Invalid Configurations

❌ `"limit": "50/minute"` - Invalid unit (must be s, m, or h)
❌ `"limit": "50"` - Missing unit
❌ `"limit": "0/m"` - Count must be positive
❌ `"limit": "-10/h"` - Count must be positive
❌ `"limit": "abc/m"` - Count must be a number

## Implementation Notes

### In-Memory Storage

The current implementation uses in-memory storage for request tracking:
- **Pros**: Fast, simple, no external dependencies
- **Cons**: Not persistent across server restarts, not suitable for multi-instance deployments

**Future Enhancement**: For production use with multiple server instances, consider:
- Redis for distributed rate limiting
- Database-backed storage for persistence
- Token bucket or leaky bucket algorithms

### Thread Safety

The current implementation uses a simple dictionary for tracking. For high-concurrency scenarios, consider adding proper locking mechanisms.

## Testing

### Manual Testing

You can test the rate limit policy by:

1. Creating an endpoint
2. Attaching a rate limit policy (e.g., `"limit": "5/m"`)
3. Making repeated requests to the endpoint
4. Observing the rate limit being enforced after 5 requests

### Example Test Script

```python
import requests
import time

endpoint_url = "http://localhost:8000/api/endpoints/<endpoint-id>/run"
headers = {"Authorization": "Bearer <token>"}

# Make 6 requests (assuming limit is 5/m)
for i in range(6):
    response = requests.post(endpoint_url, headers=headers, json={"input": "test"})
    print(f"Request {i+1}: {response.status_code}")
    if response.status_code != 200:
        print(f"Error: {response.json()}")
    time.sleep(1)
```

Expected output:
```
Request 1: 200
Request 2: 200
Request 3: 200
Request 4: 200
Request 5: 200
Request 6: 400  # Rate limit exceeded
Error: {"detail": "Rate limit exceeded: 5 requests per 1 minute(s). Current requests in window: 5"}
```

## Future Enhancements

Potential improvements for the rate limit policy:

1. **Global Scope**: Rate limiting across all users combined
2. **Endpoint Scope**: Rate limiting per endpoint regardless of user
3. **Custom Time Windows**: Support for custom time periods (e.g., "100/15m" for 15 minutes)
4. **Redis Backend**: Distributed rate limiting for multi-instance deployments
5. **Rate Limit Headers**: Include rate limit information in response headers (X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset)
6. **Burst Allowance**: Allow temporary bursts above the limit
7. **Different Algorithms**: Token bucket, leaky bucket, or sliding log algorithms

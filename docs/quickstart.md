# Quick Start Guide

Get your knowledge queryable in three steps: add your data, create an endpoint, and publish it to the network.

## Prerequisites

- Syft Space installed and running ([Desktop App](installation/desktop-app.md) or [Docker](installation/docker.md))
- If running locally: a [developer token](installation/desktop-app.md#developer-token-required-for-non-vm-environments) for publishing

## Step 1: Add Your Data

Create a dataset from your documents, files, or folders.

### Via Web Interface

1. Navigate to **Datasets** in the sidebar
2. Click **"Add Dataset"**
3. **Name your dataset** (e.g., "Company Policies", "Research Papers")
4. **Select files or folders** using the file explorer
   - Click files/folders to add them
   - Selected items appear in the list below
5. (Optional) Add a **summary** and **tags** to help categorize it
6. Click **"Create Dataset"**

Your files will begin processing automatically. You can monitor progress on the Datasets page.

### Via API

```bash
curl -X POST http://localhost:8080/api/v1/datasets/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-docs",
    "dtype": "weaviate_local",
    "configuration": {
      "httpPort": 8081,
      "grpcPort": 50051,
      "collectionName": "Documents",
      "ingestionPath": "/path/to/your/documents"
    },
    "summary": "My document collection"
  }'
```

See the [Datasets guide](components/datasets.md) for more details.

## Step 2: Create an Endpoint

Combine your dataset with an AI model to create a queryable endpoint.

### Via Web Interface

1. Navigate to **Endpoints** in the sidebar
2. Click **"New Endpoint"**
3. **Basic Information:**
   - **Name**: e.g., "Document Q&A Assistant"
   - **Slug**: URL-friendly identifier (auto-generated from name)
   - **Summary**: Brief description of what your endpoint does
4. **Select Components:**
   - **Dataset**: Choose the dataset you created in Step 1
   - **Model**: Select an AI model (or create one if needed)
5. **Configure Response:**
   - **Response Type**: Choose "Both" to return both AI summary and source context
   - **Similarity Threshold**: 0.7 (default) - how closely documents must match
   - **Limit**: 5 (default) - max documents to retrieve
6. Click **"Create Endpoint"**

### Via API

```bash
curl -X POST http://localhost:8080/api/v1/endpoints/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Document QA Assistant",
    "slug": "doc-qa",
    "dataset_id": "your-dataset-id",
    "model_id": "your-model-id",
    "response_type": "both",
    "similarity_threshold": 0.7,
    "limit": 5,
    "summary": "AI assistant for document questions"
  }'
```

### Test Your Endpoint

Query it locally to make sure it works:

```bash
curl -X POST http://localhost:8080/api/v1/endpoints/doc-qa/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{
    "messages": [
      {"role": "user", "content": "What are the main topics in my documents?"}
    ]
  }'
```

See the [Endpoints guide](components/endpoints.md) for detailed configuration options.

## Step 3: Publish to SyftHub

Make your endpoint discoverable and queryable by others on the network.

### Before Publishing

1. **Create an Access Policy** (recommended):
   - Go to **Policies** → **Add Policy**
   - Choose **Access Control** type
   - Restrict to your email initially: `your-email@example.com`
   - This lets you test before opening to others

2. **Add Rate Limits** (recommended):
   - Create a **Rate Limit** policy
   - Set limits (e.g., 60 requests/minute)
   - Attach it to your endpoint

### Publish

1. Open your endpoint
2. Click **"Publish"** button
3. Choose visibility:
   - **Organization**: Only your organization
   - **Public**: Anyone on SyftHub
4. **Attach your access policy** (if you created one)
5. Add **category** and **tags** for discoverability
6. Click **"Publish"**

Your endpoint is now live on [SyftHub](https://syfthub.openmined.org)!

### After Publishing

- **Monitor usage**: Check analytics in your endpoint dashboard
- **Adjust access**: Update your access policy anytime to expand or restrict access
- **Update content**: Changes to your dataset automatically reflect in queries

### Query Published Endpoints

Discover and query other Spaces at [syfthub.openmined.org](https://syfthub.openmined.org)

## Next Steps

- [Components Overview](components/overview.md) — Deep dive into datasets, models, endpoints, and policies
- [API Reference](api.md) — Integrate programmatically
- [Policies Guide](components/policies.md) — Fine-tune access control and rate limiting

## Troubleshooting

**Endpoint not responding?**
- Check that your dataset finished processing
- Verify your model is healthy (Models → check status)
- Review endpoint logs

**Can't publish?**
- Ensure you have a developer token configured (if running locally)
- Check that your endpoint has at least a dataset or model attached
- Verify your Space is reachable (Settings → Network)

**Need help?**
- See the [Development Guide](development.md) for technical details
- Check component-specific guides for advanced configuration

---
tags: [NSAI]
title: User Flows
created: '2025-10-30T15:16:55.079Z'
modified: '2025-10-31T16:46:09.069Z'
---

# User Flows


## Endpoints


### 1. Create Endpoint

POST `/api/v1/endpoints/`

Request
```json

{
  "name": "Name of the endpoint",
  "slug": "Unique Endpoint name",
  "summary" : "Brief summary",
  "description": "Markdown based description",
  "tags": ["MIT", "Books"],
  "dataset_id": <uuid4>, # id of the linked dataset,
  "model_id": <uuid4>, # id of the linked model,
  "policies": [<uuid4>], # List of linked policies,
  "response_type": "raw/summary/both",
  "visibility": ["*"], # public to all, otherwise list of emails or domain regexes
  "published": "true/false"
}
```

**On Success**
Response 200 OK
```json

{
  "msg": "Endpoint <name> successfully published",
  "err": null,

}
```

**Failure**
Response 400

```json
{
  "msg": "Bad Request params."
  "err": "error from trace."
}
```

Response 409
```json
{
  "msg": "Endpoint name is not unique."
  "err" "Duplicate Endpoint slug"
}
```

### 2. Query an Endpoint

User sends a query to an Endpoint

POST `/api/v1/endpoints/<endpoint_slug>/query`

Request Payload

```json

{
    "user_email": "user@example.com",
    "messages str | List[dict[str, str]]": [
       {"role": "user", "content": "What is area of the capital of France?"},
{"role": "assistant", "content": "The capital of France is Paris."}
{"role": "system", "content": "You are a helpful assistant."},
    ],
    "similarity_threshold": 0.8,
    "limit": 5,
    "include_metadata": True,
    "max_tokens": 100,
    "temperature": 0.7,
    "stop_sequences": ["\n"],
    "stream": False,
    "stop": ".end",
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0,
    "logprobs": True,
    "top_logprobs": 5,
    "extras": {
        "reference_options": {},
        "summarize_options": {},
    }
}
```

**On Success**

Response 200 OK (Both summary and references)

```json

{
    "summary": {
        # OpenAI compatible chat completion response
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "model": "gpt-4",
        "message": {
            "role": "assistant",
            "content": "This is a generated response.",
            "tokens": 42
        },
        "finish_reason": "stop",
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 42,
            "total_tokens": 52
        },
        "logprobs": {
            "token_logprobs": {
                "This": -0.1,
                "is": -0.2,
                "a": -0.3,
                "generated": -0.4,
                "response.": -0.5
            }
        },
        "cost": 0.0025,
        "provider_info": {"api_version": "v1", "response_time_ms": 150},
    },
    "references": {
        "documents": [
        {
            "document_id": "doc1",
            "content": "This is a reference document.",
            "metadata": {"author": "Alice", "date": "2023-10-01"},
            "similarity_score": 0.95
        },
        {
            "document_id": "doc2",
            "content": "This is another reference document.",
            "metadata": {"author": "Bob", "date": "2023-10-02"},
            "similarity_score": 0.89
        },
        ],
        "provider_info": {"search_engine": "ElasticSearch", "response_time_ms": 200},
        "cost": 0.0010,
    },
}

```

**Failures**

Response 404

```json
{
  "msg" : "Endpoint not found"
  "err": "Endpoint does not exists for given slug",
}
```

Response 400

```json
{
  "msg": "Bad Request",
  "err": "Err stack trace",
}
```
Response 403

```json
{
  "msg": "Permission Denied",
  "err": "User denied permission for request user",
}
```
Response 401

```json
{
  "msg": "Unauthorized user",
  "err": "Endpoint needs authentication for access",
}
```


## Data Sources


### 1. List Data Source Types

GET `/api/v1/datasets/types/`

Response 200 OK
```json

[
  {
    "name": "string",
    "config_schema": {
      "additionalProp1": {}
    },
    "description": "string",
    "icon": "string",
    "enabled": true
  }
]
```


### 2. Get Data Source Type

GET `/api/v1/datasets/types/{name}`

Response: 200 OK

```json
{
  "name": "Name of dataset type",
  "description": "description",
  "config_schema" : {
      "additionalProp1": {},
      ...
    }, # Config schema that needs to be filled in
}
```


### 3. Add new Data Source

POST `/api/v1/datasets/`

Request Payload
```json
{
  "name": "Name of Data source",
  "type": "name of dataset type",
  "configuration": {....},  # Filled up configuration,
  "tags": ["Weaviate", "legal", ...],
}
```

Response 200OK
```json
{
  "name" : "Dataset name",
  "dataset_id" : "<uuid>",
}
```

Response 400
```json
{
  "msg": "Bad configuration",
  "err": "Error stack trace",
}
```

### 4. View Data Source

GET `/api/v1/datasets/{dataset_name}`

Response 200 OK
```json

{
  "name": "Name of dataset",
  "tags": ["Weaviate", "legal", ...],
  "status": "Running/Stopped/Pending",
  "type: "Weaviate",
  "connected_endpoints" : [
    {"name": "endpoint name 1"},
    {"name": "endpoint name 2"},
    ...
  ],
  "connected_ep_cnt": 2,
  "configuration": {....},
  "analytics": {....}, # Figure out this later
  "created_at": "January 15, 2024", # User friendly format
}
```


### 5. List Datasets

GET `/api/v1/datasets/`

Response 200 OK

```json
{
  "datasets": [
    {
      "name": "dataset1",
      "type": "weaviate",
      "status": "running",
      "endpoint_count": 2,
      "tags": "legal, documents, analysis",
      "summary": "Vector database for legal document analysis and retrieval"
    },
    ...
  ]
}
```

### 6. Delete Dataset

DELETE `/api/v1/datasets/{dataset_name}`

Response 200 OK
```json

{
  "msg": "Successfully deleted {dataset_name}"
}
```

Response 404
```json
{
  "msg": "Dataset doesn't exist",
  "err": "Error trace..",
}
```

### 7. Get Dataset Provisioner Status

GET `/api/v1/datasets/{dataset_name}/provisioner/status`

Response 200 OK
```json
{
  "name": "dataset1",
  "type": "weaviate",
  "provisioner_running": true,
  "provisioner_status": "healthy",
  "provisioner_state": {
    "container_name": "weaviate-dataset1",
    "http_port": 8080,
    "grpc_port": 50051
  }
}
```

Note: For datasets without provisioners (e.g., remote datasets), all provisioner fields will be `null` or `false`.

Response 404
```json
{
  "msg": "Dataset doesn't exist",
  "err": "Error trace..",
}
```

### 8. Ingest Data into Dataset

POST `/api/v1/datasets/{dataset_name}/ingest`

Request Payload
```json
{
  "documents": [
    {
      "document_id": "doc1",
      "content": "This is the document content",
      "metadata": {
        "author": "Alice",
        "date": "2024-01-15"
      }
    }
  ]
}
```

Response 200 OK
```json
{
  "message": "Successfully ingested data into dataset 'dataset1'",
  "documents_ingested": 1
}
```


## Model Sources


### 1. List Model Source Types

GET `/api/v1/models/types/`

Response 200 OK
```json

[
  {
    "name": "string",
    "config_schema": {
      "additionalProp1": {}
    },
    "description": "string",
    "icon": "string",
    "enabled": true
  }
]
```


### 2. Get Model Source Type

GET `/api/v1/models/types/{name}`

Response: 200 OK

```json
{
  "name": "Name of model type",
  "description": "description",
  "config_schema" : {
      "additionalProp1": {},
      ...
    }, # Config schema that needs to be filled in
}
```


### 3. Add new Model Source

POST `/api/v1/models/`

Request Payload
```json
{
  "name": "Name of model source",
  "type": "name of model type",
  "configuration": {....},  # Filled up configuration,
  "tags": ["vllm", "tiny-ollama", "finance" ...],
}
```

Response 200OK
```json
{
  "name" : "Model name",
  "model_id" : "<uuid>",
}
```

Response 400
```json
{
  "msg": "Bad configuration",
  "err": "Error stack trace",
}
```

### 4. View Data Source

GET `/api/v1/models/{model_name}`

Response 200 OK
```json

{
  "name": "Name of model",
  "tags": ["vllm", "legal", ...],
  "status": "Running/Stopped/Pending",
  "type: "vLLM",
  "connected_endpoints" : [
    {"name": "endpoint name 1"},
    {"name": "endpoint name 2"},
    ...
  ],
  "connected_ep_cnt": 2,
  "configuration": {....},
  "analytics": {....}, # Figure out this later
  "created_at": "January 15, 2024", # User friendly format
}
```


### 5. List Models

GET `/api/v1/models/`

Response 200 OK

```json
{
  "datasets": [
    {
      "name": "model1",
      "type": "vllm",
      "status": "running",
      "endpoint_count": 2,
      "tags": "legal, documents, analysis",
      "summary": "Local code generation and programming assistance"
    },
    ...
  ]
}
```

### 6. Delete Model

DELETE `/api/v1/models/{model_name}`

Response 200 OK
```json

{
  "msg": "Successfully deleted {model_name}"
}
```

Response 404
```json
{
  "msg": "Model doesn't exist",
  "err": "Error trace..",
}
```


## Schemas


### Dataset Type

We will by default provide a list of Dataset types that users can select from to create a Dataset.
Dataset Type here basically represent different types of Vector databases and their configurations.

A BaseDatasetType looks like the following:

```python

class BaseDatasetType(Protocol):
    """Base dataset type interface."""

    NAME: str

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @classmethod
    def name(cls):
        """Get the name of the dataset type."""
        return cls.NAME

    @classmethod
    def type(cls):
        """Get the type of the dataset type."""
        return cls.NAME.lower()

    @classmethod
    def description(cls):
        return cls.__doc__

    @classmethod
    def icon(cls) -> str:
        return "🕸️"

    @classmethod
    def configuration_schema() -> Dict[str, Any]:
        """Return a dictionary of config values required by this dataset type.
        This will be displayed in the frontend/sdk as configurable values
        when creating a service.
        """
        raise NotImplementedError("Configuration schema not implemented")

    def search(
        self, ctx: Context, query: str, params: Optional[SearchParameters] = None
    ) -> List[Dict[str, Any]]:
        """Search the dataset for the given query."""
        raise NotImplementedError("Search not implemented")

    def ingest(self, ctx: Context, data: List[Dict[str, Any]]) -> None:
        """Ingest the data into the dataset."""
        raise NotImplementedError("Ingest not implemented")

    def healthcheck(self) -> HealthcheckResponse:
        """Healthcheck the dataset.

        This will be called to check if the dataset is healthy.
        """
        raise NotImplementedError("Healthcheck not implemented")

    @classmethod
    def enabled(cls) -> bool:
        return True
```

Any Concrete dataset type will implement this base interface.
e.g. We can implement a WeaviateDatasetType class that will define what configuration it expects to initiailize the weaviate client. It can also define search method where it can pass the text query to it client and call and query the Weaviate DB, retrieve the results back and return the results.

Similarly, it also implement the ingest, methods, that can help add new documents to the Weaviate Database.


### Dataset Type Provisioner

Some dataset types require infrastructure provisioning (e.g., Docker containers, subprocesses). For these cases, we provide a `BaseDatasetTypeProvisioner` interface:

```python
class BaseDatasetTypeProvisioner(Protocol):
    """Base dataset type provisioner interface.

    Provisioners handle lifecycle management of dataset infrastructure.
    All methods are classmethods - provisioners are stateless.
    State is passed as parameters and stored in Dataset entity.
    """

    NAME: str

    @classmethod
    def name(cls) -> str:
        """Get the name of the provisioner."""
        ...

    @classmethod
    def start(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """Start/provision the resource.

        Args:
            config: Configuration for the resource

        Returns:
            State dictionary with persistent identifiers needed to
            re-discover and manage the resource after restart.

            Examples:
            - Docker: {"container_name": "...", "container_id": "...", "port": 8080}
            - Subprocess: {"port": 8080, "pid_file": "/path/to.pid"}
            - Systemd: {"unit_name": "service-name.service"}
        """
        ...

    @classmethod
    def stop(cls, state: Dict[str, Any]) -> None:
        """Stop the provisioned resource.

        Args:
            state: State dictionary returned from start()
        """
        ...

    @classmethod
    def is_running(cls, state: Dict[str, Any]) -> bool:
        """Check if resource is currently running.

        Uses state to re-discover the resource (important after restart).

        Args:
            state: State dictionary returned from start()

        Returns:
            True if resource is running, False otherwise
        """
        ...

    @classmethod
    def status(cls, state: Dict[str, Any]) -> str:
        """Get detailed status of the resource.

        Args:
            state: State dictionary returned from start()

        Returns:
            Status string: "running", "stopped", "starting", "error", etc.
        """
        ...
```

**Key Design Principles:**
- All methods are **classmethods** - provisioners are stateless
- State is returned from `start()` and stored in the `Dataset.provisioner_state` field
- State contains persistent identifiers (container names, PIDs, etc.) for re-discovery after restarts
- Multiple datasets of the same type can have separate provisioned resources

**Example:** `WeaviateProvisioner` starts a Docker container with a unique name per dataset and returns the container details as state.


### Dataset Type Registry

We also have defined a DatasetRegistry class, that will keep definition of all these registries.

```
class DatasetTypeRegistry:
    """Registry class for dataset types and provisioners."""

    _dataset_types: Dict[str, Type[BaseDatasetType]] = {}
    _provisioners: Dict[str, Type[BaseDatasetTypeProvisioner]] = {}

    def get_dataset_type(self, name: str) -> Type[BaseDatasetType]:
        """Get dataset type class by name."""
        try:
            return self._dataset_types[name]
        except KeyError:
            raise KeyError(f"No dataset type for name '{name}'")

    def get_provisioner(self, name: str) -> Optional[Type[BaseDatasetTypeProvisioner]]:
        """Get dataset type provisioner class by name.

        Returns:
            Provisioner class or None if not registered
        """
        return self._provisioners.get(name)

    def list_dataset_types(self) -> List[str]:
        """List all registered dataset type names."""
        return sorted(self._dataset_types.keys())

    def list_provisioners(self) -> List[str]:
        """List all registered dataset type provisioner names."""
        return sorted(self._provisioners.keys())

    def is_dataset_type_registered(self, name: str) -> bool:
        """Check if a dataset type is registered."""
        return name in self._dataset_types

    def is_provisioner_registered(self, name: str) -> bool:
        """Check if a provisioner is registered."""
        return name in self._provisioners

    def register_dataset_type(self, cls: Type[BaseDatasetType]) -> None:
        """Register a dataset type."""
        key = getattr(cls, "NAME", None)
        if not key:
            raise ValueError(f"{cls.__name__} missing NAME")
        if key in self._dataset_types:
            raise ValueError(f"Dataset type already registered for name '{key}'")
        self._dataset_types[key] = cls

    def register_provisioner(self, cls: Type[BaseDatasetTypeProvisioner]) -> None:
        key = getattr(cls, "NAME", None)
        if not key:
            raise ValueError(f"{cls.__name__} missing NAME")
        if key in self._provisioners:
            raise ValueError(
                f"Dataset type provisioner already registered for name '{key}'"
            )
        self._provisioners[key] = cls
```

`DatasetTypeRegistry.register_dataset_type(WeaviateDatasetType)` can help us track all the registered dataset types.


Later, we can also provide the option for users to define their own custom dataset types by implementing the BaseDatasetType class.


By default, we aim to provide DatasetTypes for Weaviate, Qdrant, ChromaDb.


### Datasets

Datasets are objects that store configuration information about different type of dataset types.

```
Dataset:
  id: uuid4 (unique)
  name: string (Unique)
  type: DatasetType
  configuration: Object # Filled in configuration
  summary: string
  tags: string # comma seperated strings
  created_at: datetime
  updated_at: datetime
  provisioner_state: Object | null # State for re-discovering provisioned resources
```

The `provisioner_state` field stores persistent identifiers for provisioned resources (e.g., Docker container names, PIDs, ports) to allow re-discovery after server restarts. For datasets without provisioners (e.g., remote datasets), this field is `null`.

Dataset Creation Flow:
 - Select the Dataset type
 - Name the dataset
 - Fill the configuration provided by the dataset type
 - Add summary
 - Add tags
 - Save and Create
 - If provisioner exists, it will automatically start the infrastructure


### Model Type

We will by default provide a list of Model types that users can select from to create a Model.
Model Type here basically represent different types of LLM providers and their configurations.

A BaseModelType looks like the following:

```python

class BaseModelType(Protocol):
    """Base model type interface."""

    NAME: str

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @classmethod
    def name(cls):
        """Get the name of the model type."""
        return cls.NAME

    @classmethod
    def type(cls):
        """Get the type of the model type."""
        return cls.NAME.lower()

    @classmethod
    def description(cls):
        return cls.__doc__

    @classmethod
    def icon(cls) -> str:
        return "🕸️"

    @classmethod
    def configuration_schema() -> Dict[str, Any]:
        """Return a dictionary of config values required by this model type.
        This will be displayed in the frontend/sdk as configurable values
        when creating a service.
        """
        raise NotImplementedError("Configuration schema not implemented")

    def chat(
        self, ctx: Context, messages: List[ChatMessage], params: Optional[ChatParameters] = None
    ) -> List[Dict[str, Any]]:
        """Chat with the model for the given messages."""
        raise NotImplementedError("Chat not implemented")

    def healthcheck(self) -> HealthcheckResponse:
        """Healthcheck the model.

        This will be called to check if the model is healthy.
        """
        raise NotImplementedError("Healthcheck not implemented")

    @classmethod
    def enabled(cls) -> bool:
        return True
```

Any Concrete model type will implement this base interface.
e.g. We can implement a VLLMModelType class that will define what configuration it expects to initiailize the vllm client. It can also define search method where it can pass the text query to it client and call and query the Weaviate DB, retrieve the results back and return the results.


We also have defined a ModelRegistry class, that will keep definition of all these registries.

```
class ModelTypeRegistry:
    """Registry class for model types and provisioners."""

    _model_types: Dict[str, Type[BaseModelType]] = {}
    _provisioners: Dict[str, Type[BaseModelTypeProvisioner]] = {}

    def get_model_type(self, name: str) -> Type[BaseModelType]:
        """Get model type class by name."""
        try:
            return self._model_types[name]
        except KeyError:
            raise KeyError(f"No model type for name '{name}'")

    def get_provisioner(self, name: str) -> Optional[Type[BaseModelTypeProvisioner]]:
        """Get model type provisioner class by name.

        Returns:
            Provisioner class or None if not registered
        """
        return self._provisioners.get(name)

    def list_model_types(self) -> List[str]:
        """List all registered model type names."""
        return sorted(self._model_types.keys())

    def list_provisioners(self) -> List[str]:
        """List all registered model type provisioner names."""
        return sorted(self._provisioners.keys())

    def is_model_type_registered(self, name: str) -> bool:
        """Check if a model type is registered."""
        return name in self._model_types

    def is_provisioner_registered(self, name: str) -> bool:
        """Check if a provisioner is registered."""
        return name in self._provisioners

    def register_model_type(self, cls: Type[BaseModelType]) -> None:
        """Register a model type."""
        key = getattr(cls, "NAME", None)
        if not key:
            raise ValueError(f"{cls.__name__} missing NAME")
        if key in self._model_types:
            raise ValueError(f"Model type already registered for name '{key}'")
        self._model_types[key] = cls

    def register_provisioner(self, cls: Type[BaseModelTypeProvisioner]) -> None:
        key = getattr(cls, "NAME", None)
        if not key:
            raise ValueError(f"{cls.__name__} missing NAME")
        if key in self._provisioners:
            raise ValueError(
                f"Model type provisioner already registered for name '{key}'"
            )
        self._provisioners[key] = cls
```

`ModelTypeRegistry.register_model_type(WeaviateModelType)` can help us track all the registered model types.


Later, we can also provide the option for users to define their own custom model types by implementing the BaseModelType class.


By default, we aim to provide ModelTypes for vLLMs, OpenAI, Anthropic, Ollama.


### Models

Models are objects that store configuration information about different type of model types.

```
Model:
  id: uuid4 (unique)
  name: string (Unique)
  type: ModelType
  configuration: Object # Filled in configuration
  summary: string
  tags: string # comma seperated strings
  created_at: datetime
  updated_at: datetime
  provisioner_state: Object | null # State for re-discovering provisioned resources
```

The `provisioner_state` field works the same as for Datasets - it stores persistent identifiers for provisioned resources (e.g., process IDs, container names, ports).

Model Creation Flow:
 - Select the Model type
 - Name the model
 - Fill the configuration provided by the model type
 - Add summary
 - Add tags
 - Save and Create
 - If provisioner exists, it will automatically start the infrastructure


### Endpoints

Endpoints will allow query over the created Datasets and Models. Each Endpoint can either be connected to a Dataset or Model or both.

- Connecting to a Dataset only, means, the end user only get raw responses from the datasets (i.e. the Vector databases).
- Connecting to a Model only, means, the end user only get a text based response from the model connected to the endpoint. The Model here can be a private model that is trained on private data.
- Lastly, connecting to both, means, the query is passed to dataset first to find relevant sources, and then passed to Model along with the query. The model can uses its knowlegdge to generate a text based response. The end user receives both raw results + text based response.

Endpoints will allow a RAG kind of a flow to the end user.

Admin can create endpoints as follows:
- name of the endpoint
- unique slug of the endpoint
- dataset id/name to
- model id/name
- summary of the endpoint
- description of the endpoint in markdown
- type of output i.e. whether if only to provide search results or model results or both.
- list of policies attached i.e. e.g. rate limiting, user access policy, etc.
- publish the endpoint


```
EpRespType(Enum):
  RAW = "raw"
  SUMMARY = "summary"
  BOTH = "both"
```

```
Endpoint:
  name: str
  slug: str # Unique
  description: str
  dataset: Dataset
  model: Model
  response_type: EpRespType
  policies: List[Policy]
  published: bool
  tags: list[str]
```


### Policy Type

A Policy Type are pre and post hooks are applied to the incoming requests and outgoing response for a given endpoint.

We have created a BasePolicyType interface, that one can define to create concrete implementations.


```python
class BasePolicyContext(BaseModel):
  endpoint_slug: str
  sender_email: EmailStr
  request: dict[str, Any]
  response: dict[str, Any] = None


class BasePolicyType:
  NAME: str

  def __init__(self, config: dict):
    self.config = config


  @classmethod
  def schema(cls) -> dict:
    raise NotImplementedError("Schema not implemented")

  @classmethod
  def name(cls) -> str:
    return cls.NAME

  @classmethod
  def description(cls) -> str:
    return cls.__doc__

  def pre_hook(self, context: BasePolicyContext) -> Type[BasePolicyContext]:
    raise NotImplementedError("Pre hook not defined")

  def post_hook(self, context: BasePolicyContext) -> Type[BasePolicyContext]:
    raise NotImplementedError("Pre hook not defined")
```

Policy Type defines a config schema i.e. defines the inputs fields it accepts. This config is passed to pre and post hooks methods defined.

e.g. A RateLimitPolicyType can have a schema like {"rate": "str"}, with pre hook defined.

We can create a RateLimitPolicyType instance with rate of "5/m", or "10/s", etc.

Similar to DatasetType and ModelType we can also have a registry that can keep track of all policy types.

### Policy

A Policy is an instance that saves the configuration of a concrete PolicyType.

i.e. e.g we can have a policy that allows 50 requests per min, and 20 requests per second.

Policy1 = RateLimitPolicyType(config={"rate": "50/m"})
Policy2 = RateLimitPolicyType(config={"rate": "50/m"})

Therefore a policy class can be defined as follows:

```
Policy:
 id: Unique id of the policy
 name: Name of the policy
 type: BasePolicyType i.e. name of the Policy Type Class
 config: Dict that holds the filled schema for given policy type
 endpoint_id: Id of the attached Endpoint
```

User Flow for Policy Creation:
- User lists the concrete policy types
- Selects one of the policy types
- Selected policy type provides a form to fill in the schema provided by the policy type
- Add a name for the policy
- Provides endpoint id
- Saves the policy for the given endpoint


## Architecture Notes

### Provisioner vs Healthcheck

The system separates infrastructure management from service health monitoring:

**Provisioner Status** (`get_dataset_provisioner_status()`)
- Checks if infrastructure is provisioned and running (Docker containers, processes, etc.)
- Uses `provisioner_state` to re-discover resources after restart
- Returns infrastructure-level status: "running", "stopped", "starting", "error"
- For datasets/models without provisioners (e.g., remote services), returns `null`/`false`

**Service Healthcheck** (`dataset_type.healthcheck()`)
- Checks if the dataset/model service is actually healthy and responding
- Works for all dataset/model types (local provisioned or remote)
- Returns application-level health status
- Called via the dataset type's `healthcheck()` method

This separation allows:
- Datasets like Weaviate to have both: provisioner manages Docker container, healthcheck pings the API
- Remote datasets (e.g., Pinecone) to only use healthcheck without provisioners
- Clear responsibility boundaries between infrastructure and application layers

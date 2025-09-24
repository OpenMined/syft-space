from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field


class Message(BaseModel):
    """Message in a conversation"""
    role: str = Field(..., description="Role of the message sender")
    content: str = Field(..., description="Content of the message")


class Extras(BaseModel):
    """Additional options for the service request"""
    reference_options: Dict[str, Any] = Field(default_factory=dict)
    summarize_options: Dict[str, Any] = Field(default_factory=dict)


class ServiceRequest(BaseModel):
    """Request schema for the service component"""
    user_email: str = Field(..., description="Email of the user making the request")
    messages: Union[str, List[Message]] = Field(..., description="Messages or conversation string")
    similarity_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="Similarity threshold for matching")
    limit: int = Field(default=5, ge=1, description="Maximum number of results to return")
    include_metadata: bool = Field(default=True, description="Whether to include metadata in response")
    max_tokens: int = Field(default=100, ge=1, description="Maximum tokens to generate")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature for generation")
    stop_sequences: List[str] = Field(default_factory=lambda: ["\n"], description="Stop sequences")
    stream: bool = Field(default=False, description="Whether to stream the response")
    stop: str = Field(default=".end", description="Stop string")
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0, description="Presence penalty")
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0, description="Frequency penalty")
    logprobs: bool = Field(default=True, description="Whether to include log probabilities")
    top_logprobs: int = Field(default=5, ge=1, description="Number of top log probabilities")
    extras: Extras = Field(default_factory=Extras, description="Additional options")


class MessageResponse(BaseModel):
    """Message in the response"""
    role: str = Field(..., description="Role of the message sender")
    content: str = Field(..., description="Content of the message")
    tokens: int = Field(..., description="Number of tokens in the message")


class Usage(BaseModel):
    """Token usage information"""
    prompt_tokens: int = Field(..., description="Number of tokens in the prompt")
    completion_tokens: int = Field(..., description="Number of tokens in the completion")
    total_tokens: int = Field(..., description="Total number of tokens used")


class LogProbs(BaseModel):
    """Log probabilities for tokens"""
    token_logprobs: Dict[str, float] = Field(..., description="Log probabilities for each token")


class ProviderInfo(BaseModel):
    """Provider-specific information"""
    api_version: Optional[str] = Field(default=None, description="API version used")
    response_time_ms: Optional[int] = Field(default=None, description="Response time in milliseconds")
    search_engine: Optional[str] = Field(default=None, description="Search engine used")


class Summary(BaseModel):
    """OpenAI compatible chat completion response"""
    id: str = Field(..., description="Unique identifier for the response")
    model: str = Field(..., description="Model used for generation")
    message: MessageResponse = Field(..., description="Generated message")
    finish_reason: str = Field(..., description="Reason for completion")
    usage: Usage = Field(..., description="Token usage information")
    logprobs: Optional[LogProbs] = Field(default=None, description="Log probabilities")
    cost: float = Field(..., description="Cost of the generation")
    provider_info: ProviderInfo = Field(..., description="Provider-specific information")


class Document(BaseModel):
    """Reference document"""
    document_id: str = Field(..., description="Unique identifier for the document")
    content: str = Field(..., description="Content of the document")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")
    similarity_score: float = Field(..., description="Similarity score for the document")


class References(BaseModel):
    """Reference documents and search information"""
    documents: List[Document] = Field(..., description="List of reference documents")
    provider_info: ProviderInfo = Field(..., description="Search provider information")
    cost: float = Field(..., description="Cost of the search")
    search_engine: Optional[str] = Field(default=None, description="Search engine used")


class ServiceResponse(BaseModel):
    """Response schema for the service component"""
    summary: Summary = Field(..., description="Generated response summary")
    references: References = Field(..., description="Reference documents and search results")

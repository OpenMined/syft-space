/**
 * Utility functions for mapping technical names to display names
 */

export const getDataSourceName = (type: string) => {
  const names: Record<string, string> = {
    filesystem: 'File System',
    weaviate: 'Legal Documents Store',
    qdrant: 'Customer Analytics Store',
    chroma: 'Research Database',
  }
  return names[type] || type
}

export const getModelName = (type: string) => {
  const names: Record<string, string> = {
    vllm: 'NLP Processing Engine',
    ollama: 'Code Assistant Model',
    huggingface: 'Text Embedding Service',
  }
  return names[type] || type
}

export const getTechnicalDataSourceName = (type: string) => {
  const names: Record<string, string> = {
    filesystem: 'File System',
    weaviate: 'Weaviate',
    qdrant: 'Qdrant',
    chroma: 'Chroma',
  }
  return names[type] || type
}

export const getTechnicalModelName = (type: string) => {
  const names: Record<string, string> = {
    vllm: 'vLLM',
    ollama: 'Ollama',
    huggingface: 'Hugging Face',
  }
  return names[type] || type
}

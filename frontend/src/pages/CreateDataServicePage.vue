<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Header -->
    <div class="bg-white border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-6 py-4">
        <div class="flex items-center justify-between">
          <Button 
            variant="ghost"
            @click="handleBack"
            class="flex items-center text-gray-600 hover:text-gray-900"
          >
            <ArrowLeft class="w-5 h-5 mr-2" />
            Back to Create Service
          </Button>
          
          <TooltipProvider>
            <Tooltip :delayDuration="0">
              <TooltipTrigger as-child>
                <span>
                  <Button 
                    @click="saveDraft"
                    :disabled="!canSaveDraft"
                    variant="outline"
                    class="flex items-center gap-2"
                  >
                    <Save class="w-4 h-4" />
                    Save Draft
                  </Button>
                </span>
              </TooltipTrigger>
              <TooltipContent v-if="!canSaveDraft">
                <p>Add service name and summary to enable</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </div>
    </div>

    <div class="max-w-5xl mx-auto px-6 py-12">
      <!-- Progress Steps -->
      <div class="mb-12">
        <div class="flex items-center justify-between mb-8">
          <!-- Step 1 -->
          <div class="flex items-center">
            <div 
              :class="[
                'w-10 h-10 rounded-full flex items-center justify-center font-medium transition-colors',
                currentSubStep >= 1 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500'
              ]"
            >
              {{ currentSubStep > 1 ? '✓' : '1' }}
            </div>
            <span 
              :class="[
                'ml-3 text-sm font-medium',
                currentSubStep >= 1 ? 'text-gray-900' : 'text-gray-500'
              ]"
            >
              Basic Info
            </span>
          </div>

          <div 
            :class="[
              'flex-1 h-1 mx-2 transition-colors',
              currentSubStep > 1 ? 'bg-blue-600' : 'bg-gray-200'
            ]"
          />

          <!-- Step 2 -->
          <div class="flex items-center">
            <div 
              :class="[
                'w-10 h-10 rounded-full flex items-center justify-center font-medium transition-colors',
                currentSubStep >= 2 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500'
              ]"
            >
              {{ currentSubStep > 2 ? '✓' : '2' }}
            </div>
            <span 
              :class="[
                'ml-3 text-sm font-medium',
                currentSubStep >= 2 ? 'text-gray-900' : 'text-gray-500'
              ]"
            >
              Data Source
            </span>
          </div>

          <div 
            :class="[
              'flex-1 h-1 mx-2 transition-colors',
              currentSubStep > 2 ? 'bg-blue-600' : 'bg-gray-200'
            ]"
          />

          <!-- Step 3 -->
          <div class="flex items-center">
            <div 
              :class="[
                'w-10 h-10 rounded-full flex items-center justify-center font-medium transition-colors',
                currentSubStep >= 3 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500'
              ]"
            >
              {{ currentSubStep > 3 ? '✓' : '3' }}
            </div>
            <span 
              :class="[
                'ml-3 text-sm font-medium',
                currentSubStep >= 3 ? 'text-gray-900' : 'text-gray-500'
              ]"
            >
              Output
            </span>
          </div>

          <div 
            :class="[
              'flex-1 h-1 mx-2 transition-colors',
              currentSubStep > 3 ? 'bg-blue-600' : 'bg-gray-200'
            ]"
          />

          <!-- Step 4: Policies -->
          <div class="flex items-center">
            <div 
              :class="[
                'w-10 h-10 rounded-full flex items-center justify-center font-medium transition-colors',
                currentSubStep >= 4 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500'
              ]"
            >
              {{ currentSubStep > 4 ? '✓' : '4' }}
            </div>
            <span 
              :class="[
                'ml-3 text-sm font-medium',
                currentSubStep >= 4 ? 'text-gray-900' : 'text-gray-500'
              ]"
            >
              Policies
            </span>
          </div>

          <div 
            :class="[
              'flex-1 h-1 mx-2 transition-colors',
              currentSubStep > 4 ? 'bg-blue-600' : 'bg-gray-200'
            ]"
          />

          <!-- Step 5: Review -->
          <div class="flex items-center">
            <div 
              :class="[
                'w-10 h-10 rounded-full flex items-center justify-center font-medium transition-colors',
                currentSubStep >= 5 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500'
              ]"
            >
              5
            </div>
            <span 
              :class="[
                'ml-3 text-sm font-medium',
                currentSubStep >= 5 ? 'text-gray-900' : 'text-gray-500'
              ]"
            >
              Review
            </span>
          </div>
        </div>

        <div class="text-center">
          <h1 class="text-4xl font-bold text-gray-900 mb-4">
            {{ stepTitles[currentSubStep - 1] }}
          </h1>
          <p class="text-lg text-gray-600">
            {{ stepDescriptions[currentSubStep - 1] }}
          </p>
        </div>
      </div>

      <div>
        <!-- Step 2.1: Basic Information -->
        <div v-if="currentSubStep === 1" class="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
          <div class="space-y-6">

            <!-- Service Name -->
            <div class="space-y-2">
              <Label for="service-name" class="text-sm font-medium text-gray-700">
                Service Name <span class="text-red-500">*</span>
              </Label>
              <Input
                id="service-name"
                v-model="formData.serviceName"
                placeholder="e.g., Legal Document Assistant"
                class="w-full"
              />
              <p class="text-sm text-gray-500">Choose a descriptive name for your service</p>
            </div>

            <!-- Summary -->
            <div class="space-y-2">
              <Label for="summary" class="text-sm font-medium text-gray-700">
                Summary <span class="text-red-500">*</span>
              </Label>
              <Input
                id="summary"
                v-model="formData.summary"
                placeholder="Brief description of what your service does"
                class="w-full"
              />
              <p class="text-sm text-gray-500">A short summary that will appear in service listings</p>
            </div>

            <!-- Description -->
            <div class="space-y-2">
              <Label for="description" class="text-sm font-medium text-gray-700">
                Description
              </Label>
              <Textarea
                id="description"
                v-model="formData.description"
                placeholder="Detailed description of your service (supports Markdown)"
                class="w-full min-h-[120px]"
              />
              <p class="text-sm text-gray-500">Provide a detailed description. Markdown formatting is supported.</p>
            </div>

            <!-- Tags -->
            <div class="space-y-2">
              <Label for="tags" class="text-sm font-medium text-gray-700">
                Tags
              </Label>
              <div class="space-y-2">
                <div class="flex gap-2">
                  <Input
                    id="tags"
                    v-model="tagInput"
                    @keydown.enter.prevent="addTag"
                    placeholder="Add tags to help users find your service"
                    class="flex-1"
                  />
                  <Button @click="addTag" variant="outline" size="sm">
                    <Plus class="h-4 w-4" />
                  </Button>
                </div>
                <div v-if="formData.tags.length > 0" class="flex flex-wrap gap-2 mt-2">
                  <Badge
                    v-for="(tag, index) in formData.tags"
                    :key="index"
                    variant="secondary"
                    class="px-3 py-1"
                  >
                    {{ tag }}
                    <button
                      @click="removeTag(index)"
                      class="ml-2 hover:text-gray-700"
                    >
                      <X class="h-3 w-3" />
                    </button>
                  </Badge>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Step 2.2: Data Source Selection -->
        <div v-if="currentSubStep === 2" class="space-y-8">
          <!-- Data Source Selection Cards -->
          <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <!-- File System Card -->
            <Card 
              class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-blue-300 hover:bg-gradient-to-br hover:from-blue-50 hover:to-indigo-50 border-2 bg-white"
              :class="selectedDataSourceType === 'filesystem' ? 'border-blue-500 bg-gradient-to-br from-blue-50 to-indigo-50' : 'border-gray-200'"
              @click="selectDataSourceType('filesystem')"
            >
              <CardContent class="p-6">
                <div class="flex flex-col items-center text-center">
                  <div class="w-14 h-14 rounded-full bg-blue-100 flex items-center justify-center mb-4">
                    <FileText class="w-7 h-7 text-blue-600" />
                  </div>
                  
                  <h3 class="text-lg font-bold text-gray-900 mb-2">Choose files from your system</h3>
                  
                  <p class="text-sm text-gray-600 mb-3">
                    Upload documents directly from your computer
                  </p>
                  
                  <p class="text-xs text-gray-500">
                    Supports PDF, TXT, CSV, DOCX, MD, HTML, RTF, ODT, LaTeX, EPUB, JSON, and more
                  </p>
                </div>
              </CardContent>
            </Card>

            <!-- Vector Database Card -->
            <Card 
              class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-purple-300 hover:bg-gradient-to-br hover:from-purple-50 hover:to-pink-50 border-2 bg-white"
              :class="selectedDataSourceType === 'vector' ? 'border-purple-500 bg-gradient-to-br from-purple-50 to-pink-50' : 'border-gray-200'"
              @click="selectDataSourceType('vector')"
            >
              <CardContent class="p-6">
                <div class="flex flex-col items-center text-center">
                  <div class="w-14 h-14 rounded-full bg-purple-100 flex items-center justify-center mb-4">
                    <Database class="w-7 h-7 text-purple-600" />
                  </div>
                  
                  <h3 class="text-lg font-bold text-gray-900 mb-2">Connect to a vector database</h3>
                  
                  <p class="text-sm text-gray-600 mb-3">
                    Advanced integration with vector stores
                  </p>
                  
                  <p class="text-xs text-gray-500">
                    Weaviate, Qdrant, Chroma, and more
                  </p>
                </div>
              </CardContent>
            </Card>

            <!-- Existing Data Source Card -->
            <Card 
              class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-green-300 hover:bg-gradient-to-br hover:from-green-50 hover:to-emerald-50 border-2 bg-white"
              :class="selectedDataSourceType === 'existing' ? 'border-green-500 bg-gradient-to-br from-green-50 to-emerald-50' : 'border-gray-200'"
              @click="selectDataSourceType('existing')"
            >
              <CardContent class="p-6">
                <div class="flex flex-col items-center text-center">
                  <div class="w-14 h-14 rounded-full bg-green-100 flex items-center justify-center mb-4">
                    <FolderOpen class="w-7 h-7 text-green-600" />
                  </div>
                  
                  <h3 class="text-lg font-bold text-gray-900 mb-2">Use an existing data source</h3>
                  
                  <p class="text-sm text-gray-600 mb-3">
                    Select from your configured sources
                  </p>
                  
                  <p class="text-xs text-gray-500">
                    {{ existingDataSourcesCount }} data source{{ existingDataSourcesCount !== 1 ? 's' : '' }} available
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>

          <!-- Content based on selection -->
          <div v-if="selectedDataSourceType">
            <!-- File System Browser -->
            <div v-if="selectedDataSourceType === 'filesystem'" class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <h3 class="text-lg font-medium text-gray-900 mb-4">Select Files</h3>
              <div class="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
                <FolderOpen class="mx-auto h-12 w-12 text-gray-400 mb-4" />
                <p class="text-gray-600 mb-2">Drop files here or click to browse</p>
                <p class="text-sm text-gray-500">File browser UI will be implemented here</p>
                <Button variant="outline" class="mt-4">
                  Browse Files
                </Button>
              </div>
            </div>

            <!-- Vector Database Configuration -->
            <div v-if="selectedDataSourceType === 'vector'" class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <div class="mb-6">
                <h3 class="text-lg font-medium text-gray-900 mb-2">Configure Vector Database</h3>
                <p class="text-sm text-gray-600">Select and configure your vector database connection</p>
              </div>
              
              <!-- Inline version of CreateDataSourceDialog content -->
              <div class="space-y-6">
                <!-- Vector DB Type Selection -->
                <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <div
                    v-for="db in vectorDatabases"
                    :key="db.id"
                    @click="db.isCustom ? openCustomSDKDocs() : selectedVectorDB = db.id"
                    :class="[
                      'flex flex-col items-center justify-center p-4 rounded-lg border cursor-pointer transition-all',
                      db.isCustom 
                        ? 'border-purple-200 bg-gradient-to-r from-purple-50 to-blue-50 hover:border-purple-300 hover:bg-gradient-to-r hover:from-purple-100 hover:to-blue-100'
                        : (selectedVectorDB === db.id ? 'border-purple-500 bg-purple-50' : 'border-gray-200 hover:bg-gray-50')
                    ]"
                  >
                    <div v-if="db.isCustom" class="p-2 bg-purple-100 rounded-md mb-2">
                      <Code class="h-6 w-6 text-purple-600" />
                    </div>
                    <IntegrationIcon
                      v-else
                      :name="db.id"
                      class="h-10 w-10 mb-2"
                      :class="selectedVectorDB === db.id ? 'text-purple-600' : 'text-gray-600'"
                    />
                    <span class="text-sm font-medium text-center" :class="[
                      db.isCustom 
                        ? 'text-purple-800'
                        : (selectedVectorDB === db.id ? 'text-purple-900' : 'text-gray-900')
                    ]">
                      {{ db.name }}
                    </span>
                    <span v-if="db.isCustom" class="text-xs text-purple-600 mt-1">Using SDK</span>
                  </div>
                </div>

                <!-- Configuration Form -->
                <div v-if="selectedVectorDB" class="mt-6 p-4 bg-gray-50 rounded-lg">
                  <p class="text-sm text-gray-600">Configuration form for {{ selectedVectorDB }} will be implemented here</p>
                </div>
              </div>
            </div>

            <!-- Existing Data Sources List -->
            <div v-if="selectedDataSourceType === 'existing'" class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <div class="space-y-4">
                <h3 class="text-lg font-medium text-gray-900 mb-4">Available Data Sources</h3>
                
                <RadioGroup v-model="formData.dataSource">
                  <div class="space-y-3">
                    <!-- Legal Documents Store -->
                    <div class="flex items-center space-x-3 p-4 border rounded-lg cursor-pointer hover:bg-gray-50"
                         :class="formData.dataSource === 'legal-docs' ? 'border-green-500 bg-green-50' : 'border-gray-200'"
                         @click="formData.dataSource = 'legal-docs'">
                      <RadioGroupItem value="legal-docs" id="legal-docs" />
                      <Label for="legal-docs" class="flex items-center gap-3 cursor-pointer flex-1">
                        <div class="p-2 bg-purple-100 rounded">
                          <IntegrationIcon name="weaviate" class="h-5 w-5" />
                        </div>
                        <div class="flex-1">
                          <div class="flex items-center gap-2">
                            <span class="font-medium">Legal Documents Store</span>
                            <Badge variant="secondary" class="text-xs">Weaviate</Badge>
                            <Badge variant="outline" class="bg-green-50 text-green-700 border-green-200 text-xs">
                              running
                            </Badge>
                          </div>
                          <p class="text-sm text-gray-600 mt-1">Vector database for legal document analysis</p>
                        </div>
                      </Label>
                    </div>

                    <!-- Customer Analytics Store -->
                    <div class="flex items-center space-x-3 p-4 border rounded-lg cursor-pointer hover:bg-gray-50"
                         :class="formData.dataSource === 'customer-analytics' ? 'border-green-500 bg-green-50' : 'border-gray-200'"
                         @click="formData.dataSource = 'customer-analytics'">
                      <RadioGroupItem value="customer-analytics" id="customer-analytics" />
                      <Label for="customer-analytics" class="flex items-center gap-3 cursor-pointer flex-1">
                        <div class="p-2 bg-blue-100 rounded">
                          <IntegrationIcon name="qdrant" class="h-5 w-5" />
                        </div>
                        <div class="flex-1">
                          <div class="flex items-center gap-2">
                            <span class="font-medium">Customer Analytics Store</span>
                            <Badge variant="secondary" class="text-xs">Qdrant</Badge>
                            <Badge variant="outline" class="bg-green-50 text-green-700 border-green-200 text-xs">
                              running
                            </Badge>
                          </div>
                          <p class="text-sm text-gray-600 mt-1">Customer behavior analysis and segmentation</p>
                        </div>
                      </Label>
                    </div>

                    <!-- Research Database -->
                    <div class="flex items-center space-x-3 p-4 border rounded-lg cursor-pointer hover:bg-gray-50"
                         :class="formData.dataSource === 'research-db' ? 'border-green-500 bg-green-50' : 'border-gray-200'"
                         @click="formData.dataSource = 'research-db'">
                      <RadioGroupItem value="research-db" id="research-db" />
                      <Label for="research-db" class="flex items-center gap-3 cursor-pointer flex-1">
                        <div class="p-2 bg-green-100 rounded">
                          <IntegrationIcon name="chroma" class="h-5 w-5" />
                        </div>
                        <div class="flex-1">
                          <div class="flex items-center gap-2">
                            <span class="font-medium">Research Database</span>
                            <Badge variant="secondary" class="text-xs">Chroma</Badge>
                            <Badge variant="outline" class="bg-gray-50 text-gray-600 border-gray-200 text-xs">
                              stopped
                            </Badge>
                          </div>
                          <p class="text-sm text-gray-600 mt-1">Research papers and scientific literature</p>
                        </div>
                      </Label>
                    </div>
                  </div>
                </RadioGroup>
              </div>
            </div>
          </div>
        </div>

        <!-- Step 2.3: Response Configuration -->
        <div v-if="currentSubStep === 3" class="space-y-8">
          <!-- Response Type Selection Cards -->
          <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <!-- Raw Document Chunks Card -->
            <Card 
              class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-blue-300 hover:bg-gradient-to-br hover:from-blue-50 hover:to-indigo-50 border-2 bg-white"
              :class="formData.responseType === 'raw' ? 'border-blue-500 bg-gradient-to-br from-blue-50 to-indigo-50' : 'border-gray-200'"
              @click="formData.responseType = 'raw'"
            >
              <CardContent class="p-8">
                <div class="flex flex-col items-center text-center">
                  <div class="w-16 h-16 rounded-full bg-blue-100 flex items-center justify-center mb-6">
                    <FileType class="w-8 h-8 text-blue-600" />
                  </div>
                  
                  <h3 class="text-2xl font-bold text-gray-900 mb-3">Raw Document Chunks</h3>
                  <p class="text-sm font-medium mb-4 text-blue-600">Direct document retrieval</p>

                  <p class="text-gray-600 mb-4 text-balance">
                    Return matching document chunks directly without any processing.
                  </p>
                  
                  <p class="text-sm text-gray-500 text-balance">
                    Perfect for when your users need the original source content exactly as it appears for providing references or citations.
                  </p>
                </div>
              </CardContent>
            </Card>

            <!-- AI-Generated Summary Card -->
            <Card 
              class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-purple-300 hover:bg-gradient-to-br hover:from-purple-50 hover:to-pink-50 border-2 bg-white"
              :class="formData.responseType === 'summary' ? 'border-purple-500 bg-gradient-to-br from-purple-50 to-pink-50' : 'border-gray-200'"
              @click="formData.responseType = 'summary'"
            >
              <CardContent class="p-8">
                <div class="flex flex-col items-center text-center">
                  <div class="w-16 h-16 rounded-full bg-purple-100 flex items-center justify-center mb-6">
                    <Sparkles class="w-8 h-8 text-purple-600" />
                  </div>
                  
                  <h3 class="text-2xl font-bold text-gray-900 mb-3">AI-Generated Summary</h3>
                  <p class="text-sm font-medium mb-4 text-purple-600">Smart content synthesis</p>

                  <p class="text-gray-600 mb-4 text-balance">
                    Use AI to summarize and synthesize information from matching documents.
                  </p>
                  
                  <p class="text-sm text-gray-500 text-balance">
                    Ideal for getting concise, intelligent responses from large document sets, and for preserving privacy of underlying documents.
                  </p>
                </div>
              </CardContent>
            </Card>

            <!-- Both Raw and Summary Card -->
            <Card 
              class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-green-300 hover:bg-gradient-to-br hover:from-green-50 hover:to-emerald-50 border-2 bg-white relative"
              :class="formData.responseType === 'both' ? 'border-green-500 bg-gradient-to-br from-green-50 to-emerald-50' : 'border-gray-200'"
              @click="formData.responseType = 'both'"
            >
              <!-- Recommended Badge -->
              <div class="absolute -top-3 -right-3 z-10">
                <Badge class="bg-green-600 text-white text-xs px-3 py-1 font-medium rounded-full shadow-lg">Recommended</Badge>
              </div>
              <CardContent class="p-8">
                <div class="flex flex-col items-center text-center">
                  <div class="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mb-6">
                    <GitMerge class="w-8 h-8 text-green-600" />
                  </div>
                  
                  <h3 class="text-2xl font-bold text-gray-900 mb-3">Both References & Summary</h3>
                  <p class="text-sm font-medium mb-4 text-green-600">Maximum flexibility for users</p>

                  <p class="text-gray-600 mb-4 text-balance">
                    Provide both the original document chunks and an AI-generated summary.
                  </p>
                  
                  <p class="text-sm text-gray-500 text-balance">
                    Best of both worlds - detailed source material plus intelligent insights.
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>

          <!-- Model Selection Section (shown when summary is selected) -->
          <div v-if="formData.responseType === 'summary' || formData.responseType === 'both'"
               class="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
            <div class="space-y-6">
              <div>
                <h2 class="text-xl font-semibold text-gray-900 mb-2">AI Model</h2>
                <p class="text-sm text-gray-600">Select an AI model to generate summaries</p>
              </div>

            <RadioGroup v-model="formData.aiModel">
              <div class="space-y-3">
                <!-- NLP Processing Engine -->
                <div class="flex items-center space-x-3 p-4 border rounded-lg cursor-pointer hover:bg-gray-50"
                     :class="formData.aiModel === 'nlp-engine' ? (formData.responseType === 'summary' ? 'border-purple-500 bg-purple-50' : 'border-green-500 bg-green-50') : 'border-gray-200'"
                     @click="formData.aiModel = 'nlp-engine'">
                  <RadioGroupItem value="nlp-engine" id="nlp-engine" />
                  <Label for="nlp-engine" class="flex items-center gap-3 cursor-pointer flex-1">
                    <div class="p-2 bg-purple-100 rounded">
                      <IntegrationIcon name="vllm" class="h-5 w-5" />
                    </div>
                    <div class="flex-1">
                      <div class="flex items-center gap-2">
                        <span class="font-medium">NLP Processing Engine</span>
                        <Badge variant="secondary" class="text-xs">vLLM</Badge>
                        <Badge variant="outline" class="bg-gray-50 text-gray-600 border-gray-200 text-xs">
                          stopped
                        </Badge>
                      </div>
                      <p class="text-sm text-gray-600 mt-1">Large language model for natural language processing</p>
                    </div>
                  </Label>
                </div>

                <!-- Code Assistant Model -->
                <div class="flex items-center space-x-3 p-4 border rounded-lg cursor-pointer hover:bg-gray-50"
                     :class="formData.aiModel === 'code-assistant' ? (formData.responseType === 'summary' ? 'border-purple-500 bg-purple-50' : 'border-green-500 bg-green-50') : 'border-gray-200'"
                     @click="formData.aiModel = 'code-assistant'">
                  <RadioGroupItem value="code-assistant" id="code-assistant" />
                  <Label for="code-assistant" class="flex items-center gap-3 cursor-pointer flex-1">
                    <div class="p-2 bg-orange-100 rounded">
                      <IntegrationIcon name="ollama" class="h-5 w-5" />
                    </div>
                    <div class="flex-1">
                      <div class="flex items-center gap-2">
                        <span class="font-medium">Code Assistant Model</span>
                        <Badge variant="secondary" class="text-xs">Ollama</Badge>
                        <Badge variant="outline" class="bg-green-50 text-green-700 border-green-200 text-xs">
                          running
                        </Badge>
                      </div>
                      <p class="text-sm text-gray-600 mt-1">Local code generation and programming assistance</p>
                    </div>
                  </Label>
                </div>

                <!-- Create New Model -->
                <div class="flex items-center space-x-3 p-4 border rounded-lg cursor-pointer hover:bg-gray-50"
                     :class="formData.aiModel === 'create-new-model' ? (formData.responseType === 'summary' ? 'border-purple-500 bg-purple-50' : 'border-green-500 bg-green-50') : 'border-gray-200'"
                     @click="formData.aiModel = 'create-new-model'">
                  <RadioGroupItem value="create-new-model" id="create-new-model" />
                  <Label for="create-new-model" class="flex items-center gap-3 cursor-pointer flex-1">
                    <div class="p-2 bg-gray-100 rounded">
                      <Plus class="h-5 w-5 text-gray-600" />
                    </div>
                    <div class="flex-1">
                      <span class="font-medium">Create New Model</span>
                      <p class="text-sm text-gray-600 mt-1">Set up a new AI model for your service</p>
                    </div>
                  </Label>
                </div>
              </div>
            </RadioGroup>
          </div>
        </div>
        </div>

        <!-- Step 4: Add Policies -->
        <div v-if="currentSubStep === 4" class="space-y-8">
          <!-- Search and Filters -->
          <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
            <div class="flex flex-col space-y-4">
              <!-- First Row: Search Bar -->
              <div class="flex-1">
                <div class="relative">
                  <Input
                    v-model="policySearch"
                    placeholder="Search policies..."
                    class="pl-10"
                  />
                  <svg class="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
              </div>

              <!-- Second Row: Filters and Actions -->
              <div class="flex items-center justify-between gap-4">
                <div class="flex items-center gap-4">
                  <!-- Filter by Type -->
                  <Select v-model="policyTypeFilter">
                    <SelectTrigger class="w-[180px]">
                      <div class="flex items-center">
                        <Filter class="w-4 h-4 mr-2 shrink-0" />
                        <SelectValue placeholder="All Types" />
                      </div>
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Types</SelectItem>
                      <SelectItem value="rate-limiter">Rate Limiter</SelectItem>
                      <SelectItem value="usage-tracking">Usage Tracking</SelectItem>
                      <SelectItem value="observability">Observability</SelectItem>
                      <SelectItem value="security">Security</SelectItem>
                    </SelectContent>
                  </Select>

                  <!-- Sort By -->
                  <Select v-model="policySortBy">
                    <SelectTrigger class="w-[240px]">
                      <div class="flex items-center">
                        <ArrowUpDown class="w-4 h-4 mr-2 shrink-0" />
                        <SelectValue placeholder="Most Frequently Used" />
                      </div>
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="most-used">Most Frequently Used</SelectItem>
                      <SelectItem value="recently-added">Most Recently Added</SelectItem>
                      <SelectItem value="name">Name (A-Z)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <!-- Select All/None Actions -->
                <div class="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    @click="selectAllPolicies"
                    class="text-xs"
                  >
                    <CheckSquare class="h-3 w-3 mr-1" />
                    Select All
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    @click="selectNoPolicies"
                    class="text-xs"
                  >
                    <Square class="h-3 w-3 mr-1" />
                    Select None
                  </Button>
                </div>
              </div>
            </div>
          </div>

          <!-- Available Policies -->
          <div class="space-y-4">
            <div
              v-for="policy in filteredAndSortedPolicies"
              :key="policy.id"
              class="bg-white border border-gray-200 rounded-lg p-6 cursor-pointer hover:bg-gray-50"
              :class="{
                'ring-2 ring-blue-500 ring-opacity-20': formData.policies[policy.id] && policy.color === 'blue',
                'ring-2 ring-green-500 ring-opacity-20': formData.policies[policy.id] && policy.color === 'green',
                'ring-2 ring-purple-500 ring-opacity-20': formData.policies[policy.id] && policy.color === 'purple',
                'ring-2 ring-red-500 ring-opacity-20': formData.policies[policy.id] && policy.color === 'red',
                'ring-2 ring-orange-500 ring-opacity-20': formData.policies[policy.id] && policy.color === 'orange'
              }"
              @click="formData.policies[policy.id] = !formData.policies[policy.id]"
            >
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-4">
                  <input 
                    type="checkbox" 
                    :id="policy.id" 
                    v-model="formData.policies[policy.id]"
                    :class="{
                      'h-4 w-4 border-gray-300 rounded focus:ring-blue-500 text-blue-600': policy.color === 'blue',
                      'h-4 w-4 border-gray-300 rounded focus:ring-green-500 text-green-600': policy.color === 'green',
                      'h-4 w-4 border-gray-300 rounded focus:ring-purple-500 text-purple-600': policy.color === 'purple',
                      'h-4 w-4 border-gray-300 rounded focus:ring-red-500 text-red-600': policy.color === 'red',
                      'h-4 w-4 border-gray-300 rounded focus:ring-orange-500 text-orange-600': policy.color === 'orange'
                    }"
                    @click.stop
                  />
                  <div :class="{
                    'p-3 rounded-lg bg-blue-100': policy.color === 'blue',
                    'p-3 rounded-lg bg-green-100': policy.color === 'green',
                    'p-3 rounded-lg bg-purple-100': policy.color === 'purple',
                    'p-3 rounded-lg bg-red-100': policy.color === 'red',
                    'p-3 rounded-lg bg-orange-100': policy.color === 'orange'
                  }">
                    <component :is="policy.icon" :class="{
                      'h-6 w-6 text-blue-600': policy.color === 'blue',
                      'h-6 w-6 text-green-600': policy.color === 'green',
                      'h-6 w-6 text-purple-600': policy.color === 'purple',
                      'h-6 w-6 text-red-600': policy.color === 'red',
                      'h-6 w-6 text-orange-600': policy.color === 'orange'
                    }" />
                  </div>
                  <div class="flex-1">
                    <div class="flex items-center gap-3 mb-2">
                      <h3 class="text-lg font-medium text-gray-900">{{ policy.name }}</h3>
                      <Badge variant="secondary" class="bg-gray-900 text-white text-xs px-2 py-1">{{ policy.badge }}</Badge>
                      <Badge variant="outline" class="bg-green-50 text-green-700 border-green-200 text-xs px-2 py-1">
                        <div class="w-2 h-2 bg-green-500 rounded-full mr-1"></div>
                        {{ policy.serviceCount }} services
                      </Badge>
                    </div>
                    <p class="text-gray-600 mb-3">
                      {{ policy.description }}
                    </p>
                    <div class="flex gap-2">
                      <Badge
                        v-for="config in policy.configs"
                        :key="config"
                        variant="outline"
                        class="text-xs px-2 py-1"
                      >
                        {{ config }}
                      </Badge>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- No Results -->
            <div v-if="filteredAndSortedPolicies.length === 0" class="text-center py-12">
              <div class="text-gray-400 mb-4">
                <svg class="h-12 w-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h3 class="text-lg font-medium text-gray-900 mb-2">No policies found</h3>
              <p class="text-gray-500">Try adjusting your search or filter criteria</p>
            </div>

            <!-- Add More Policies Button (Bottom) -->
            <div class="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-gray-400 transition-colors">
              <Button
                variant="outline"
                class="text-gray-600 hover:text-gray-900"
                @click="showCreatePolicyDialog = true"
              >
                <Plus class="h-4 w-4 mr-2" />
                Add More Policies
              </Button>
              <p class="text-sm text-gray-500 mt-2">Create custom policies for your specific needs</p>
            </div>
          </div>
        </div>

        <!-- Step 5: Review -->
        <div v-if="currentSubStep === 5" class="space-y-8">
          <!-- Service Summary -->
          <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
            <div class="space-y-6">
              <div>
                <h2 class="text-xl font-semibold text-gray-900 mb-2">Service Summary</h2>
                <p class="text-sm text-gray-600">Review your service configuration before deployment</p>
              </div>

              <!-- Basic Information -->
              <div class="border-l-4 border-blue-500 pl-4">
                <h3 class="font-medium text-gray-900 mb-2">Basic Information</h3>
                <div class="space-y-1 text-sm">
                  <p><span class="font-medium">Name:</span> {{ formData.serviceName || 'Not specified' }}</p>
                  <p><span class="font-medium">Summary:</span> {{ formData.summary || 'Not specified' }}</p>
                  <p v-if="formData.description"><span class="font-medium">Description:</span> {{ formData.description }}</p>
                  <div v-if="formData.tags.length > 0">
                    <span class="font-medium">Tags:</span>
                    <span class="ml-2">
                      <Badge v-for="tag in formData.tags" :key="tag" variant="outline" class="mr-1">{{ tag }}</Badge>
                    </span>
                  </div>
                </div>
              </div>

              <!-- Data Source -->
              <div class="border-l-4 border-purple-500 pl-4">
                <h3 class="font-medium text-gray-900 mb-2">Data Source</h3>
                <div class="text-sm space-y-2">
                  <div v-if="selectedDataSourceType === 'filesystem'">
                    <p><span class="font-medium">Type:</span> Files from your system</p>
                    <p><span class="font-medium">Files Selected:</span> {{ selectedFiles.length > 0 ? selectedFiles.length + ' files' : 'Ready to select files during deployment' }}</p>
                  </div>
                  <div v-else-if="selectedDataSourceType === 'vector'">
                    <p><span class="font-medium">Type:</span> Vector Database</p>
                    <p><span class="font-medium">Database:</span> {{ selectedVectorDB || 'Not selected' }}</p>
                    <p v-if="selectedVectorDB" class="text-gray-600">Configuration will be completed during deployment</p>
                  </div>
                  <div v-else-if="selectedDataSourceType === 'existing'">
                    <p><span class="font-medium">Type:</span> Existing Data Source</p>
                    <div v-if="formData.dataSource === 'legal-docs'">
                      <p><span class="font-medium">Source:</span> Legal Documents Store</p>
                      <p><span class="font-medium">Database:</span> Weaviate</p>
                      <p><span class="font-medium">Status:</span> <Badge variant="outline" class="bg-green-50 text-green-700 border-green-200 text-xs">Running</Badge></p>
                      <p class="text-gray-600">Vector database for legal document analysis</p>
                    </div>
                    <div v-else-if="formData.dataSource === 'customer-analytics'">
                      <p><span class="font-medium">Source:</span> Customer Analytics Store</p>
                      <p><span class="font-medium">Database:</span> Qdrant</p>
                      <p><span class="font-medium">Status:</span> <Badge variant="outline" class="bg-green-50 text-green-700 border-green-200 text-xs">Running</Badge></p>
                      <p class="text-gray-600">Customer behavior analysis and segmentation</p>
                    </div>
                    <div v-else-if="formData.dataSource === 'research-db'">
                      <p><span class="font-medium">Source:</span> Research Database</p>
                      <p><span class="font-medium">Database:</span> Chroma</p>
                      <p><span class="font-medium">Status:</span> <Badge variant="outline" class="bg-gray-50 text-gray-600 border-gray-200 text-xs">Stopped</Badge></p>
                      <p class="text-gray-600">Research papers and scientific literature</p>
                    </div>
                    <p v-if="!formData.dataSource">Not selected</p>
                  </div>
                  <p v-else>Not configured</p>
                </div>
              </div>

              <!-- Output Configuration -->
              <div class="border-l-4 border-green-500 pl-4">
                <h3 class="font-medium text-gray-900 mb-2">Output Configuration</h3>
                <div class="text-sm space-y-1">
                  <p v-if="formData.responseType === 'raw'"><span class="font-medium">Response Type:</span> Raw Document Chunks</p>
                  <p v-else-if="formData.responseType === 'summary'"><span class="font-medium">Response Type:</span> AI-Generated Summary</p>
                  <p v-else-if="formData.responseType === 'both'"><span class="font-medium">Response Type:</span> Both References & Summary</p>
                  <p v-else>Not configured</p>
                  
                  <div v-if="formData.aiModel && (formData.responseType === 'summary' || formData.responseType === 'both')">
                    <div v-if="formData.aiModel === 'nlp-engine'">
                      <p><span class="font-medium">AI Model:</span> NLP Processing Engine</p>
                      <p><span class="font-medium">Provider:</span> vLLM</p>
                    </div>
                    <div v-else-if="formData.aiModel === 'code-assistant'">
                      <p><span class="font-medium">AI Model:</span> Code Assistant Model</p>
                      <p><span class="font-medium">Provider:</span> Ollama</p>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Applied Policies -->
              <div class="border-l-4 border-orange-500 pl-4">
                <h3 class="font-medium text-gray-900 mb-2">Applied Policies</h3>
                <div class="text-sm space-y-2">
                  <div v-if="getAppliedPoliciesDetails().length > 0">
                    <div v-for="policy in getAppliedPoliciesDetails()" :key="policy.id" class="mb-4 last:mb-0">
                      <p><span class="font-medium">Policy:</span> {{ policy.name }}</p>
                      <p><span class="font-medium">Type:</span> {{ policy.type.replace('-', ' ') }}</p>
                      <div v-for="config in parseConfigKeyValues(policy.configs)" :key="config.key">
                        <p><span class="font-medium">{{ config.key }}:</span> {{ config.value }}</p>
                      </div>
                    </div>
                  </div>
                  <p v-else class="text-gray-500">No policies applied</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Navigation Buttons -->
        <div class="flex justify-between mt-8">
          <Button 
            v-if="currentSubStep > 1"
            @click="handlePrevious"
            variant="outline"
            class="px-8"
          >
            <ArrowLeft class="mr-2 h-4 w-4" />
            Previous
          </Button>
          <div v-else></div>
          
          <Button 
            @click="handleNext"
            :disabled="!isCurrentStepValid"
            class="bg-purple-600 hover:bg-purple-700 text-white px-8 ml-auto"
          >
            {{ currentSubStep === 5 ? 'Deploy Service' : 'Next' }}
            <ArrowRight class="ml-2 h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  </div>

  <!-- Create Data Source Dialog -->
  <CreateDataSourceDialog
    v-model:open="showCreateDataSourceDialog"
    @data-source-created="handleDataSourceCreated"
  />

  <!-- Create Model Dialog -->
  <CreateModelDialog
    v-model:open="showCreateModelDialog"
    @model-created="handleModelCreated"
  />

  <!-- Create Policy Dialog -->
  <CreatePolicyDialog
    v-model:open="showCreatePolicyDialog"
    @policy-created="handlePolicyCreated"
  />
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Database, Plus, X, ArrowRight, FileText, FolderOpen, Code, FileType, Sparkles, GitMerge, Save, Clock, Calculator, Activity, Shield, Users, CheckSquare, Square, Filter, ArrowUpDown } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import IntegrationIcon from '@/components/IntegrationIcons.vue'
import CreateDataSourceDialog from '@/components/CreateDataSourceDialog.vue'
import CreateModelDialog from '@/components/CreateModelDialog.vue'
import CreatePolicyDialog from '@/components/CreatePolicyDialog.vue'
import { AVAILABLE_POLICIES } from '@/data/policies'

const router = useRouter()

// Sub-step navigation
const currentSubStep = ref(1)

// Step titles and descriptions
const stepTitles = [
  'Basic Information',
  'Select Data Source',
  'Configure Output',
  'Apply Policies',
  'Review'
]

const stepDescriptions = [
  'Provide basic details about your service',
  'Choose where your data comes from',
  'Define how your service outputs information',
  'Select policies to govern your service\'s behavior and access',
  'Review and deploy your service'
]

// Form data
const formData = ref({
  serviceName: '',
  summary: '',
  description: '',
  tags: [] as string[],
  dataSource: '',
  responseType: 'raw',
  aiModel: '',
  policies: {}
})

// Data source selection
const selectedDataSourceType = ref<string | null>(null)
const selectedVectorDB = ref<string | null>(null)
const selectedFiles = ref<string[]>([])

// Tag input
const tagInput = ref('')

// Dialog states
const showCreateDataSourceDialog = ref(false)
const showCreateModelDialog = ref(false)
const showCreatePolicyDialog = ref(false)

// Policy search and filters
const policySearch = ref('')
const policyTypeFilter = ref('all')
const policySortBy = ref('most-used')


// Vector databases options (from CreateDataSourceDialog)
const vectorDatabases = [
  { id: 'weaviate', name: 'Weaviate' },
  { id: 'qdrant', name: 'Qdrant' },
  { id: 'chroma', name: 'Chroma' },
  { id: 'custom', name: 'Custom', isCustom: true }
]

// Count of existing data sources
const existingDataSourcesCount = computed(() => 3) // Based on the 3 sources in SettingsPage

// Filtered and sorted policies
const filteredAndSortedPolicies = computed(() => {
  let filtered = AVAILABLE_POLICIES.filter(policy => {
    // Filter by search
    const matchesSearch = policySearch.value === '' || 
      policy.name.toLowerCase().includes(policySearch.value.toLowerCase()) ||
      policy.description.toLowerCase().includes(policySearch.value.toLowerCase()) ||
      policy.badge.toLowerCase().includes(policySearch.value.toLowerCase())
    
    // Filter by type
    const matchesType = policyTypeFilter.value === 'all' || policy.type === policyTypeFilter.value
    
    return matchesSearch && matchesType
  })

  // Sort policies
  if (policySortBy.value === 'most-used') {
    filtered = filtered.sort((a, b) => b.usageCount - a.usageCount)
  } else if (policySortBy.value === 'recently-added') {
    filtered = filtered.sort((a, b) => b.dateAdded.getTime() - a.dateAdded.getTime())
  } else if (policySortBy.value === 'name') {
    filtered = filtered.sort((a, b) => a.name.localeCompare(b.name))
  }

  return filtered
})

// Watch for data source selection - removed since we no longer use radio button for create new

// Watch for AI model selection
watch(() => formData.value.aiModel, (newValue) => {
  if (newValue === 'create-new-model') {
    showCreateModelDialog.value = true
    formData.value.aiModel = '' // Reset selection
  }
})

// Step validation
const isStep1Valid = computed(() => {
  return formData.value.serviceName.trim() !== '' && 
         formData.value.summary.trim() !== ''
})

// Can save draft when we have name and summary
const canSaveDraft = computed(() => isStep1Valid.value)

const isStep2Valid = computed(() => {
  if (selectedDataSourceType.value === 'existing') {
    return formData.value.dataSource !== ''
  } else if (selectedDataSourceType.value === 'vector') {
    return selectedVectorDB.value !== null
  } else if (selectedDataSourceType.value === 'filesystem') {
    return selectedFiles.value.length > 0 || true // For now, allow proceeding without files selected
  }
  return false
})

const isStep3Valid = computed(() => {
  const hasResponseType = formData.value.responseType !== ''
  const needsModel = formData.value.responseType === 'summary' || formData.value.responseType === 'both'
  const hasModel = !needsModel || (formData.value.aiModel !== '' && formData.value.aiModel !== 'create-new-model')
  return hasResponseType && hasModel
})

const isStep4Valid = computed(() => {
  // Step 4 (policies) is always valid - policies are optional
  return true
})

const isStep5Valid = computed(() => {
  // Review step is always valid if we've reached it
  return true
})

const isCurrentStepValid = computed(() => {
  if (currentSubStep.value === 1) return isStep1Valid.value
  if (currentSubStep.value === 2) return isStep2Valid.value
  if (currentSubStep.value === 3) return isStep3Valid.value
  if (currentSubStep.value === 4) return isStep4Valid.value
  return isStep5Valid.value
})

// Add tag
const addTag = () => {
  const tag = tagInput.value.trim()
  if (tag && !formData.value.tags.includes(tag)) {
    formData.value.tags.push(tag)
    tagInput.value = ''
  }
}

// Remove tag
const removeTag = (index: number) => {
  formData.value.tags.splice(index, 1)
}

// Select data source type
const selectDataSourceType = (type: string) => {
  selectedDataSourceType.value = type
  // Reset selections when changing type
  if (type !== 'existing') {
    formData.value.dataSource = ''
  }
  if (type !== 'vector') {
    selectedVectorDB.value = null
  }
  if (type !== 'filesystem') {
    selectedFiles.value = []
  }
}

// Handle data source created
const handleDataSourceCreated = () => {
  // In a real app, this would update the data source list
  console.log('Data source created')
}

// Handle model created
const handleModelCreated = () => {
  // In a real app, this would update the model list
  console.log('Model created')
}

// Handle policy created
const handlePolicyCreated = () => {
  // In a real app, this would update the policy list
  console.log('Policy created')
}

// Get applied policies for review
const getAppliedPolicies = () => {
  const policies = []
  for (const [policyId, isSelected] of Object.entries(formData.value.policies)) {
    if (isSelected) {
      const policy = AVAILABLE_POLICIES.find(p => p.id === policyId)
      if (policy) {
        policies.push(policy.name)
      }
    }
  }
  return policies
}

// Get applied policies with full details for review
const getAppliedPoliciesDetails = () => {
  const policies = []
  for (const [policyId, isSelected] of Object.entries(formData.value.policies)) {
    if (isSelected) {
      const policy = AVAILABLE_POLICIES.find(p => p.id === policyId)
      if (policy) {
        policies.push(policy)
      }
    }
  }
  return policies
}

// Parse config strings into key-value pairs
const parseConfigKeyValues = (configs: string[]) => {
  return configs.map(config => {
    const colonIndex = config.indexOf(':')
    if (colonIndex > -1) {
      return {
        key: config.substring(0, colonIndex).trim(),
        value: config.substring(colonIndex + 1).trim()
      }
    }
    return {
      key: config,
      value: ''
    }
  })
}

// Select all visible policies
const selectAllPolicies = () => {
  filteredAndSortedPolicies.value.forEach(policy => {
    formData.value.policies[policy.id] = true
  })
}

// Select no policies
const selectNoPolicies = () => {
  formData.value.policies = {}
}

// Navigation handlers
const handleNext = () => {
  if (!isCurrentStepValid.value) return
  
  if (currentSubStep.value < 5) {
    currentSubStep.value++
  } else {
    // Deploy the service
    console.log('Deploying service with data:', formData.value)
    // router.push('/services')
  }
}

const handlePrevious = () => {
  if (currentSubStep.value > 1) {
    currentSubStep.value--
  }
}

const handleBack = () => {
  router.push('/create')
}

// Save draft function
const saveDraft = () => {
  if (!canSaveDraft.value) return
  
  console.log('Saving draft:', formData.value)
  // In a real app, this would save to local storage or backend
  // localStorage.setItem('dataServiceDraft', JSON.stringify(formData.value))
}

// Open custom SDK documentation
const openCustomSDKDocs = () => {
  window.open('https://docs.openmined.org/custom-data-sources', '_blank')
}
</script>
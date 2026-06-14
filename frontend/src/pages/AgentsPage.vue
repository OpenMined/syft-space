<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { Bot, Plus, Search, Link, Wrench, Plug, FolderOpen } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import CreateAgentDialog from '@/components/CreateAgentDialog.vue'
import { mockAgents, getOrchestratorLabel } from '@/stores/mockAgents'

const router = useRouter()
const searchQuery = ref('')
const showCreateDialog = ref(false)

const filteredAgents = computed(() => {
  const query = searchQuery.value.toLowerCase()
  if (!query) return mockAgents
  return mockAgents.filter(
    (agent) =>
      agent.name.toLowerCase().includes(query) ||
      agent.description.toLowerCase().includes(query) ||
      agent.tags.some((tag) => tag.toLowerCase().includes(query)),
  )
})

const navigateToDetail = (id: string) => router.push(`/agents/${id}`)
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
    <!-- Header -->
    <div class="mb-12">
      <h1 class="text-2xl font-semibold tracking-tight text-foreground mb-3">Your Agents</h1>
      <p class="body-lg text-muted-foreground md:max-w-[60%]">
        Local orchestrators — Claude or Codex — wired to the skills, MCPs and folders you grant
        them. Turn one into an API to put it to work.
      </p>
    </div>

    <!-- Actions Bar -->
    <div class="flex items-center justify-between mb-8">
      <div class="relative w-full max-w-sm">
        <Search
          class="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-muted-foreground"
        />
        <Input v-model="searchQuery" placeholder="Search agents..." class="pl-10 pr-4 py-2.5 w-full" />
      </div>
      <Button @click="showCreateDialog = true">
        <Plus class="h-4 w-4 mr-2" />
        Add
      </Button>
    </div>

    <!-- Empty State -->
    <div v-if="filteredAgents.length === 0" class="text-center py-8">
      <Bot class="h-10 w-10 text-muted-foreground mx-auto mb-4" />
      <h3 class="heading-3 text-foreground mb-2">No agents yet</h3>
      <p class="body-sm text-muted-foreground mb-4">Add your first agent to get started</p>
      <Button @click="showCreateDialog = true">
        <Plus class="h-4 w-4 mr-2" />
        Add Agent
      </Button>
    </div>

    <!-- Agents List -->
    <div v-else class="space-y-3">
      <div
        v-for="agent in filteredAgents"
        :key="agent.id"
        class="group rounded-lg border border-border/50 bg-card p-5 hover:shadow-sm hover:-translate-y-px transition-all cursor-pointer"
        @click="navigateToDetail(agent.id)"
      >
        <div class="flex items-start gap-4">
          <div class="p-3.5 rounded-xl bg-primary/10">
            <Bot class="h-6 w-6 text-foreground/60" />
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-3 mb-2 flex-wrap">
              <h3 class="heading-4 text-foreground">{{ agent.name }}</h3>
              <div
                :class="
                  agent.status === 'active'
                    ? 'w-2 h-2 rounded-full bg-green-500 shrink-0'
                    : 'w-2 h-2 rounded-full bg-muted-foreground/40 shrink-0'
                "
              />
              <Badge variant="outline" class="text-[11px] px-2 py-0.5">
                {{ getOrchestratorLabel(agent.orchestrator) }}
              </Badge>
              <Badge
                variant="outline"
                class="body-sm px-2.5 py-1 rounded-md"
                :class="
                  agent.endpointCount > 0
                    ? 'bg-primary/10 text-primary border border-primary/20'
                    : 'bg-muted text-muted-foreground border border-border'
                "
              >
                <Link class="w-3.5 h-3.5 mr-1.5" :class="agent.endpointCount > 0 ? '' : 'opacity-40'" />
                {{
                  agent.endpointCount === 0
                    ? 'No APIs'
                    : `${agent.endpointCount} API${agent.endpointCount !== 1 ? 's' : ''}`
                }}
              </Badge>
            </div>
            <p class="body-sm text-muted-foreground mb-3 line-clamp-2">{{ agent.description }}</p>

            <div class="flex flex-wrap gap-3 mb-3 text-xs text-muted-foreground">
              <span class="inline-flex items-center gap-1.5">
                <Wrench class="h-3.5 w-3.5" /> {{ agent.skills.length }} skills
              </span>
              <span class="inline-flex items-center gap-1.5">
                <Plug class="h-3.5 w-3.5" /> {{ agent.mcps.length }} MCPs
              </span>
              <span class="inline-flex items-center gap-1.5">
                <FolderOpen class="h-3.5 w-3.5" /> {{ agent.folders.length }} folders
              </span>
            </div>

            <div class="flex gap-1.5 flex-wrap">
              <Badge
                v-for="tag in agent.tags.slice(0, 3)"
                :key="tag"
                variant="secondary"
                class="text-[11px] px-2 py-0.5"
              >
                {{ tag }}
              </Badge>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <CreateAgentDialog v-model:open="showCreateDialog" />
</template>

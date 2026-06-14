<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Bot,
  ChevronRight,
  Plus,
  Wrench,
  Plug,
  FolderOpen,
  Globe,
  Slack,
  Phone,
  UserCheck,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import CreateApiFromAgentDialog from '@/components/CreateApiFromAgentDialog.vue'
import { getAgentById, getOrchestratorLabel } from '@/stores/mockAgents'
import { mockApis, getPlatformLabel, type Platform } from '@/stores/mockApis'

const route = useRoute()
const router = useRouter()

const agentId = computed(() => route.params.id as string)
const agent = computed(() => getAgentById(agentId.value))

const agentApis = computed(() =>
  mockApis.filter((api) => api.rootType === 'agent' && api.rootResourceId === agentId.value),
)

const showCreateApiDialog = ref(false)

const channelIcons: Record<Platform, typeof Globe> = {
  syfthub: Globe,
  slack: Slack,
  whatsapp: Phone,
}
</script>

<template>
  <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
    <!-- Breadcrumb -->
    <div class="flex items-center text-sm text-muted-foreground mb-8">
      <router-link to="/agents" class="flex items-center hover:text-foreground transition-colors">
        <Bot class="h-4 w-4 mr-2" />
        Agents
      </router-link>
      <ChevronRight class="h-4 w-4 mx-2" />
      <span class="text-foreground">{{ agent?.name }}</span>
    </div>

    <div v-if="!agent" class="text-center py-12">
      <p class="text-muted-foreground">Agent not found.</p>
    </div>

    <template v-else>
      <!-- Header -->
      <div class="flex items-start justify-between mb-10">
        <div class="flex items-start gap-4">
          <div class="p-3.5 rounded-xl bg-primary/10">
            <Bot class="h-7 w-7 text-foreground/60" />
          </div>
          <div>
            <div class="flex items-center gap-3 mb-2 flex-wrap">
              <h1 class="text-2xl font-semibold tracking-tight text-foreground">{{ agent.name }}</h1>
              <Badge variant="outline" class="text-[11px] px-2 py-0.5">
                {{ getOrchestratorLabel(agent.orchestrator) }}
              </Badge>
              <div
                :class="
                  agent.status === 'active'
                    ? 'w-2 h-2 rounded-full bg-green-500'
                    : 'w-2 h-2 rounded-full bg-muted-foreground/40'
                "
              />
            </div>
            <p class="body-sm text-muted-foreground max-w-2xl">{{ agent.description }}</p>
            <p class="text-xs text-muted-foreground mt-2">{{ agent.sessions }} active session(s)</p>
          </div>
        </div>
      </div>

      <!-- Imported access -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div class="bg-card border border-border rounded-xl p-6">
          <div class="flex items-center gap-2 mb-4">
            <Wrench class="h-4 w-4 text-muted-foreground" />
            <h3 class="heading-4">Skills</h3>
          </div>
          <div class="flex flex-wrap gap-2">
            <Badge v-for="skill in agent.skills" :key="skill" variant="secondary">{{ skill }}</Badge>
            <span v-if="agent.skills.length === 0" class="text-sm text-muted-foreground">None</span>
          </div>
        </div>
        <div class="bg-card border border-border rounded-xl p-6">
          <div class="flex items-center gap-2 mb-4">
            <Plug class="h-4 w-4 text-muted-foreground" />
            <h3 class="heading-4">MCPs</h3>
          </div>
          <div class="flex flex-wrap gap-2">
            <Badge v-for="mcp in agent.mcps" :key="mcp" variant="secondary">{{ mcp }}</Badge>
            <span v-if="agent.mcps.length === 0" class="text-sm text-muted-foreground">None</span>
          </div>
        </div>
        <div class="bg-card border border-border rounded-xl p-6">
          <div class="flex items-center gap-2 mb-4">
            <FolderOpen class="h-4 w-4 text-muted-foreground" />
            <h3 class="heading-4">Folders</h3>
          </div>
          <div class="space-y-1.5">
            <div
              v-for="folder in agent.folders"
              :key="folder"
              class="rounded-md border border-border/50 bg-muted/40 px-3 py-1.5 font-mono text-xs text-foreground/80 truncate"
            >
              {{ folder }}
            </div>
            <span v-if="agent.folders.length === 0" class="text-sm text-muted-foreground">None</span>
          </div>
        </div>
      </div>

      <!-- Connected APIs -->
      <div class="bg-card border border-border rounded-xl p-6">
        <div class="flex items-center justify-between mb-5">
          <h3 class="heading-3">Connected APIs</h3>
          <Button size="sm" @click="showCreateApiDialog = true">
            <Plus class="h-3.5 w-3.5 mr-2" />
            Create API
          </Button>
        </div>

        <div v-if="agentApis.length === 0" class="text-center py-8">
          <p class="body-sm text-muted-foreground">
            No APIs yet. Create one to expose this agent over channels.
          </p>
        </div>

        <div v-else class="space-y-3">
          <div
            v-for="api in agentApis"
            :key="api.id"
            class="rounded-lg border border-border/50 p-4 flex items-start justify-between gap-4"
          >
            <div class="min-w-0">
              <div class="flex items-center gap-2 mb-1.5 flex-wrap">
                <span class="font-medium text-foreground">{{ api.name }}</span>
                <Badge
                  v-if="api.hasHilPolicy"
                  variant="outline"
                  class="text-[11px] px-2 py-0.5 bg-purple-500/10 text-purple-600 border-purple-500/20"
                >
                  <UserCheck class="h-3 w-3 mr-1" /> HIL
                </Badge>
              </div>
              <p v-if="api.prompt" class="text-xs text-muted-foreground line-clamp-1 mb-2">
                {{ api.prompt }}
              </p>
              <div class="flex flex-wrap gap-2">
                <Badge
                  v-for="binding in api.channels.filter((c) => c.enabled)"
                  :key="binding.platform"
                  variant="secondary"
                  class="text-[11px] px-2 py-0.5"
                >
                  <component :is="channelIcons[binding.platform]" class="h-3 w-3 mr-1" />
                  {{ getPlatformLabel(binding.platform) }}
                  <span v-if="binding.isDefaultReply" class="ml-1 opacity-70">· default</span>
                </Badge>
              </div>
            </div>
            <Button variant="ghost" size="sm" @click="router.push('/endpoints')">View</Button>
          </div>
        </div>
      </div>
    </template>
  </div>

  <CreateApiFromAgentDialog
    v-if="agent"
    v-model:open="showCreateApiDialog"
    :agent-id="agent.id"
  />
</template>

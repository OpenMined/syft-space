<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Header -->
    <div class="mb-10">
      <Button variant="ghost" @click="$router.back()" class="mb-4">
        <ArrowLeft class="h-4 w-4 mr-2" />
        Back
      </Button>
      <h1 class="heading-2 text-foreground mb-2">Create New Collective</h1>
      <p class="body-lg text-muted-foreground">
        Set up a new collective to organize your community
      </p>
    </div>

    <!-- Form -->
    <div class="space-y-8">
      <!-- Basic Information -->
      <Card>
        <CardHeader>
          <CardTitle>Basic Information</CardTitle>
          <CardDescription>Provide the core details about your collective</CardDescription>
        </CardHeader>
        <CardContent class="space-y-6">
          <div class="space-y-2">
            <Label for="name">Collective Name *</Label>
            <Input
              id="name"
              v-model="formData.name"
              placeholder="e.g., Harvard Research Collective"
            />
          </div>

          <div class="space-y-2">
            <Label for="slug">Slug *</Label>
            <Input
              id="slug"
              v-model="formData.slug"
              placeholder="e.g., harvard-research"
              @input="formatSlug"
            />
            <p class="text-xs text-muted-foreground">
              Your collective will be available at: {{ formData.slug || 'your-slug' }}.syftbox.net
            </p>
          </div>

          <div class="space-y-2">
            <Label for="description">Description *</Label>
            <Textarea
              id="description"
              v-model="formData.description"
              placeholder="Describe the purpose and goals of your collective..."
              rows="4"
            />
          </div>
        </CardContent>
      </Card>

      <!-- Capabilities -->
      <Card>
        <CardHeader>
          <CardTitle>Collective Capabilities</CardTitle>
          <CardDescription>Choose which features to enable for your collective</CardDescription>
        </CardHeader>
        <CardContent class="space-y-4">
          <div class="flex items-start gap-3 p-4 border border-border rounded-lg">
            <Switch
              id="endpoint"
              v-model="formData.capabilities.collectiveEndpoint"
              class="mt-1"
            />
            <div class="flex-1">
              <Label for="endpoint" class="cursor-pointer">
                <div class="flex items-center gap-2 mb-1">
                  <Zap class="h-4 w-4 text-primary" />
                  <span class="font-medium">Collective Endpoint</span>
                </div>
              </Label>
              <p class="text-sm text-muted-foreground">
                Provide a unified endpoint that aggregates queries across all member endpoints
              </p>
            </div>
          </div>

          <div class="flex items-start gap-3 p-4 border border-border rounded-lg">
            <Switch
              id="hosting"
              v-model="formData.capabilities.multiTenancyHosting"
              class="mt-1"
            />
            <div class="flex-1">
              <Label for="hosting" class="cursor-pointer">
                <div class="flex items-center gap-2 mb-1">
                  <Server class="h-4 w-4 text-green-600 dark:text-green-400" />
                  <span class="font-medium">Multi-Tenancy Hosting</span>
                </div>
              </Label>
              <p class="text-sm text-muted-foreground">
                Offer infrastructure hosting for members with dedicated subdomains
              </p>
            </div>
          </div>

          <div class="flex items-start gap-3 p-4 border border-border rounded-lg">
            <Switch
              id="vetting"
              v-model="formData.capabilities.memberVetting"
              class="mt-1"
            />
            <div class="flex-1">
              <Label for="vetting" class="cursor-pointer">
                <div class="flex items-center gap-2 mb-1">
                  <Shield class="h-4 w-4 text-purple-600 dark:text-purple-400" />
                  <span class="font-medium">Member Vetting</span>
                </div>
              </Label>
              <p class="text-sm text-muted-foreground">
                Review and approve membership requests before granting access
              </p>
            </div>
          </div>

          <div class="flex items-start gap-3 p-4 border border-border rounded-lg">
            <Switch
              id="terms"
              v-model="formData.capabilities.collectiveTerms"
              class="mt-1"
            />
            <div class="flex-1">
              <Label for="terms" class="cursor-pointer">
                <div class="flex items-center gap-2 mb-1">
                  <FileText class="h-4 w-4 text-orange-600 dark:text-orange-400" />
                  <span class="font-medium">Collective Terms</span>
                </div>
              </Label>
              <p class="text-sm text-muted-foreground">
                Define shared pricing and access policies that members can adopt
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- Membership -->
      <Card>
        <CardHeader>
          <CardTitle>Membership Visibility</CardTitle>
          <CardDescription>Control who can request to join your collective</CardDescription>
        </CardHeader>
        <CardContent>
          <div class="space-y-3">
            <div
              class="flex items-start gap-3 p-4 border-2 rounded-lg cursor-pointer transition-colors"
              :class="
                formData.membershipVisibility === 'anyone'
                  ? 'border-primary bg-primary/5'
                  : 'border-border hover:border-primary/30'
              "
              @click="formData.membershipVisibility = 'anyone'"
            >
              <div class="flex-1">
                <div class="flex items-center gap-2 mb-1">
                  <div
                    class="w-4 h-4 rounded-full border-2"
                    :class="
                      formData.membershipVisibility === 'anyone'
                        ? 'border-primary bg-primary'
                        : 'border-muted-foreground'
                    "
                  />
                  <span class="font-medium">Anyone can request to join</span>
                </div>
                <p class="text-sm text-muted-foreground ml-6">
                  Open membership - users can discover and request to join your collective
                </p>
              </div>
            </div>

            <div
              class="flex items-start gap-3 p-4 border-2 rounded-lg cursor-pointer transition-colors"
              :class="
                formData.membershipVisibility === 'invite-only'
                  ? 'border-primary bg-primary/5'
                  : 'border-border hover:border-primary/30'
              "
              @click="formData.membershipVisibility = 'invite-only'"
            >
              <div class="flex-1">
                <div class="flex items-center gap-2 mb-1">
                  <div
                    class="w-4 h-4 rounded-full border-2"
                    :class="
                      formData.membershipVisibility === 'invite-only'
                        ? 'border-primary bg-primary'
                        : 'border-muted-foreground'
                    "
                  />
                  <span class="font-medium">Invite-only</span>
                </div>
                <p class="text-sm text-muted-foreground ml-6">
                  Restricted - only users you invite can join the collective
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- Actions -->
      <div class="flex justify-between">
        <Button variant="outline" @click="$router.back()">Cancel</Button>
        <Button @click="createCollective" :disabled="!isFormValid">
          Create Collective
        </Button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Zap, Server, Shield, FileText } from 'lucide-vue-next'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { useCollectivesStore } from '@/stores/collectives'

const router = useRouter()
const collectivesStore = useCollectivesStore()

const formData = ref({
  name: '',
  slug: '',
  description: '',
  capabilities: {
    collectiveEndpoint: true,
    multiTenancyHosting: true,
    memberVetting: true,
    collectiveTerms: true,
  },
  membershipVisibility: 'anyone' as 'anyone' | 'invite-only',
})

const formatSlug = () => {
  formData.value.slug = formData.value.slug
    .toLowerCase()
    .replace(/[^a-z0-9-]/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
}

const isFormValid = computed(() => {
  return (
    formData.value.name.trim() !== '' &&
    formData.value.slug.trim() !== '' &&
    formData.value.description.trim() !== ''
  )
})

const createCollective = () => {
  if (!isFormValid.value) return

  const newCollective = collectivesStore.addCollective({
    name: formData.value.name,
    slug: formData.value.slug,
    description: formData.value.description,
    domain: `${formData.value.slug}.syftbox.net`,
    capabilities: formData.value.capabilities,
    membershipVisibility: formData.value.membershipVisibility,
    role: 'admin',
  })

  router.push(`/collectives/${newCollective.slug}`)
}
</script>



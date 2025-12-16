<template>
  <div v-if="collective" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Header -->
    <div class="mb-8">
      <Button variant="ghost" @click="$router.push(`/collectives/${slug}`)" class="mb-4">
        <ArrowLeft class="h-4 w-4 mr-2" />
        Back to {{ collective.name }}
      </Button>
      
      <h1 class="heading-2 text-foreground mb-2">Collective Terms</h1>
      <p class="text-muted-foreground">
        Configure pricing and access terms that members can adopt for their endpoints
      </p>
    </div>

    <!-- Pricing Terms Section -->
    <Card class="mb-8">
      <CardHeader>
        <div class="flex items-center justify-between">
          <div>
            <CardTitle class="flex items-center gap-2">
              <DollarSign class="h-5 w-5 text-green-600 dark:text-green-400" />
              Pricing Tiers
            </CardTitle>
            <CardDescription class="mt-1">
              Define pricing tiers that members can apply to their endpoints
            </CardDescription>
          </div>
          <Button 
            v-if="collective.role === 'admin'" 
            @click="openCreateTierDialog"
            size="sm"
          >
            <Plus class="h-4 w-4 mr-2" />
            Add Tier
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div v-if="pricingTiers.length > 0" class="space-y-3">
          <div
            v-for="tier in pricingTiers"
            :key="tier.id"
            class="flex items-start justify-between p-4 border border-border rounded-lg hover:bg-muted/50 transition-colors"
          >
            <div class="flex-1">
              <div class="flex items-center gap-2 mb-1">
                <h4 class="font-semibold text-foreground">{{ tier.name }}</h4>
                <Badge v-if="tier.isDefault" variant="default" class="text-xs">Default</Badge>
              </div>
              <p class="text-sm text-muted-foreground mb-2">{{ tier.description }}</p>
              <div class="flex items-center gap-4">
                <div class="flex items-center gap-1.5">
                  <span class="text-lg font-semibold text-foreground">${{ tier.price }}</span>
                  <span class="text-sm text-muted-foreground">
                    per {{ tier.priceUnit === 'per_call' ? 'call' : 'token' }}
                  </span>
                </div>
                <div class="text-xs text-muted-foreground">
                  • Used by {{ countEndpointsUsingTier(tier.id) }} endpoints
                </div>
              </div>
            </div>
            <div v-if="collective.role === 'admin'" class="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                @click="openEditTierDialog(tier)"
              >
                <Pencil class="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                @click="handleDeleteTier(tier.id)"
                :disabled="tier.isDefault"
              >
                <Trash2 class="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
        <div v-else class="text-center py-8 border-2 border-dashed border-border rounded-lg">
          <DollarSign class="h-12 w-12 text-muted-foreground mx-auto mb-3" />
          <p class="text-sm text-muted-foreground mb-4">No pricing tiers defined yet</p>
          <Button v-if="collective.role === 'admin'" @click="openCreateTierDialog" size="sm">
            <Plus class="h-4 w-4 mr-2" />
            Create First Tier
          </Button>
        </div>
      </CardContent>
    </Card>

    <!-- Access Terms Section -->
    <Card>
      <CardHeader>
        <div class="flex items-center justify-between">
          <div>
            <CardTitle class="flex items-center gap-2">
              <Shield class="h-5 w-5 text-blue-600 dark:text-blue-400" />
              Access Rules
            </CardTitle>
            <CardDescription class="mt-1">
              Define access policies that members can adopt for their endpoints
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div v-if="accessRules.length > 0" class="space-y-3">
          <div
            v-for="rule in accessRules"
            :key="rule.id"
            class="flex items-start justify-between p-4 border border-border rounded-lg"
          >
            <div class="flex-1">
              <h4 class="font-semibold text-foreground mb-1">{{ rule.name }}</h4>
              <p class="text-sm text-muted-foreground mb-2">{{ rule.description }}</p>
              <Badge variant="outline" class="text-xs">{{ rule.type }}</Badge>
            </div>
          </div>
        </div>
        <div v-else class="text-center py-8 border-2 border-dashed border-border rounded-lg">
          <Shield class="h-12 w-12 text-muted-foreground mx-auto mb-3" />
          <p class="text-sm text-muted-foreground">No access rules defined yet</p>
        </div>
      </CardContent>
    </Card>

    <!-- Create/Edit Tier Dialog -->
    <Dialog v-model:open="tierDialogOpen">
      <DialogContent class="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>{{ editingTier ? 'Edit' : 'Create' }} Pricing Tier</DialogTitle>
          <DialogDescription>
            {{ editingTier ? 'Update the pricing tier details' : 'Add a new pricing tier for members to use' }}
          </DialogDescription>
        </DialogHeader>
        <div class="space-y-4 py-4">
          <div class="space-y-2">
            <Label for="tier-name">Tier Name *</Label>
            <Input
              id="tier-name"
              v-model="tierForm.name"
              placeholder="e.g., Standard, Premium"
            />
          </div>
          <div class="space-y-2">
            <Label for="tier-description">Description *</Label>
            <Textarea
              id="tier-description"
              v-model="tierForm.description"
              placeholder="Describe this pricing tier..."
              rows="2"
            />
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div class="space-y-2">
              <Label for="tier-price">Price ($) *</Label>
              <Input
                id="tier-price"
                v-model="tierForm.price"
                type="number"
                step="0.0001"
                placeholder="0.001"
              />
            </div>
            <div class="space-y-2">
              <Label for="tier-unit">Price Unit *</Label>
              <Select v-model="tierForm.priceUnit">
                <SelectTrigger>
                  <SelectValue placeholder="Select unit" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="per_call">Per Call</SelectItem>
                  <SelectItem value="per_token">Per Token</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <input
              id="tier-default"
              v-model="tierForm.isDefault"
              type="checkbox"
              class="h-4 w-4 rounded border-border"
            />
            <Label for="tier-default" class="text-sm cursor-pointer">
              Set as default tier for new endpoints
            </Label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="closeTierDialog">Cancel</Button>
          <Button @click="saveTier" :disabled="!isTierFormValid">
            {{ editingTier ? 'Update' : 'Create' }} Tier
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  DollarSign,
  Shield,
  Plus,
  Pencil,
  Trash2,
} from 'lucide-vue-next'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useCollectivesStore } from '@/stores/collectives'
import type { PricingTier } from '@/stores/collectives'

const route = useRoute()
const router = useRouter()
const collectivesStore = useCollectivesStore()

const slug = route.params.slug as string
const collective = computed(() => collectivesStore.getCollectiveBySlug(slug))
const pricingTiers = computed(() => 
  collective.value ? collectivesStore.pricingTiers[collective.value.id] || [] : []
)
const accessRules = computed(() =>
  collective.value ? collectivesStore.accessRules[collective.value.id] || [] : []
)
const members = computed(() =>
  collective.value ? collectivesStore.getMembersByCollectiveId(collective.value.id) : []
)

const tierDialogOpen = ref(false)
const editingTier = ref<PricingTier | null>(null)
const tierForm = ref({
  name: '',
  description: '',
  price: '',
  priceUnit: 'per_token' as 'per_call' | 'per_token',
  isDefault: false,
})

const isTierFormValid = computed(() => {
  return (
    tierForm.value.name.trim() !== '' &&
    tierForm.value.description.trim() !== '' &&
    tierForm.value.price !== '' &&
    parseFloat(tierForm.value.price) >= 0
  )
})

const openCreateTierDialog = () => {
  editingTier.value = null
  tierForm.value = {
    name: '',
    description: '',
    price: '',
    priceUnit: 'per_token',
    isDefault: false,
  }
  tierDialogOpen.value = true
}

const openEditTierDialog = (tier: PricingTier) => {
  editingTier.value = tier
  tierForm.value = {
    name: tier.name,
    description: tier.description,
    price: tier.price.toString(),
    priceUnit: tier.priceUnit,
    isDefault: tier.isDefault || false,
  }
  tierDialogOpen.value = true
}

const closeTierDialog = () => {
  tierDialogOpen.value = false
  editingTier.value = null
}

const saveTier = () => {
  if (!collective.value || !isTierFormValid.value) return

  const tierData = {
    name: tierForm.value.name,
    description: tierForm.value.description,
    price: parseFloat(tierForm.value.price),
    priceUnit: tierForm.value.priceUnit,
    isDefault: tierForm.value.isDefault,
  }

  if (editingTier.value) {
    collectivesStore.updatePricingTier(collective.value.id, editingTier.value.id, tierData)
  } else {
    collectivesStore.addPricingTier(collective.value.id, tierData)
  }

  closeTierDialog()
}

const handleDeleteTier = (tierId: string) => {
  if (!collective.value) return
  
  const tier = pricingTiers.value.find(t => t.id === tierId)
  if (tier?.isDefault) {
    alert('Cannot delete the default tier')
    return
  }

  const endpointsUsing = countEndpointsUsingTier(tierId)
  if (endpointsUsing > 0) {
    if (!confirm(`This tier is used by ${endpointsUsing} endpoint(s). Are you sure you want to delete it?`)) {
      return
    }
  }

  collectivesStore.deletePricingTier(collective.value.id, tierId)
}

const countEndpointsUsingTier = (tierId: string) => {
  let count = 0
  members.value.forEach(member => {
    member.endpoints.forEach(endpoint => {
      if (endpoint.assignedPricingTier === tierId) {
        count++
      }
    })
  })
  return count
}
</script>

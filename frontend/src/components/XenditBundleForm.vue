<template>
  <div class="space-y-4">
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <div class="space-y-1">
        <Label class="body-sm text-muted-foreground font-medium">Currency</Label>
        <Select :model-value="form.currency" @update:model-value="updateField('currency', $event)">
          <SelectTrigger class="h-9 rounded-lg border-border bg-card body-sm">
            <SelectValue placeholder="Select currency" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem v-for="c in XENDIT_CURRENCIES" :key="c.value" :value="c.value">
              {{ c.label }}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div class="space-y-1">
        <Label class="body-sm text-muted-foreground font-medium">Country</Label>
        <Select :model-value="form.country" @update:model-value="updateField('country', $event)">
          <SelectTrigger class="h-9 rounded-lg border-border bg-card body-sm">
            <SelectValue placeholder="Select country" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem v-for="c in XENDIT_COUNTRIES" :key="c.value" :value="c.value">
              {{ c.label }}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>

    <!-- Bundle Tiers -->
    <div class="space-y-2">
      <Label class="body-sm text-muted-foreground font-medium">Bundle Tiers</Label>
      <div v-for="(tier, index) in form.tiers" :key="index" class="flex items-end gap-2">
        <div class="space-y-1 flex-1">
          <Label v-if="index === 0" class="text-xs text-muted-foreground">Name</Label>
          <Input
            :model-value="tier.name"
            placeholder="e.g. Starter"
            class="h-9 rounded-lg border-border bg-card body-sm placeholder:text-muted-foreground"
            @input="updateTierField(index, 'name', ($event.target as HTMLInputElement).value)"
          />
        </div>
        <div class="space-y-1 w-20">
          <Label v-if="index === 0" class="text-xs text-muted-foreground">Units</Label>
          <Input
            :model-value="tier.units"
            type="number"
            placeholder="100"
            class="h-9 rounded-lg border-border bg-card body-sm placeholder:text-muted-foreground"
            @input="updateTierField(index, 'units', ($event.target as HTMLInputElement).value)"
          />
        </div>
        <div class="space-y-1 w-28">
          <Label v-if="index === 0" class="text-xs text-muted-foreground">Unit Type</Label>
          <Select
            :model-value="tier.unitType"
            @update:model-value="updateTierField(index, 'unitType', $event)"
          >
            <SelectTrigger class="h-9 rounded-lg border-border bg-card body-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="requests">Requests</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="space-y-1 w-24">
          <Label v-if="index === 0" class="text-xs text-muted-foreground">Price</Label>
          <Input
            :model-value="tier.price"
            type="number"
            step="any"
            placeholder="10.00"
            class="h-9 rounded-lg border-border bg-card body-sm placeholder:text-muted-foreground"
            @input="updateTierField(index, 'price', ($event.target as HTMLInputElement).value)"
          />
        </div>
        <Button
          v-if="form.tiers.length > 1"
          variant="ghost"
          size="sm"
          class="h-9 w-9 p-0 shrink-0"
          @click="removeTier(index)"
        >
          <X class="h-4 w-4" />
        </Button>
      </div>
      <Button variant="outline" size="sm" @click="addTier">
        <Plus class="h-4 w-4 mr-1" />
        Add Tier
      </Button>
    </div>

    <!-- Applied To -->
    <div class="flex flex-col sm:flex-row gap-3 sm:gap-4">
      <div class="space-y-1 sm:flex-shrink-0 sm:w-32">
        <Label class="body-sm text-muted-foreground font-medium">Apply To</Label>
        <Select :model-value="form.userType" @update:model-value="updateField('userType', $event)">
          <SelectTrigger class="h-9 rounded-lg border-border bg-card body-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Users</SelectItem>
            <SelectItem value="specific">Specific Users</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div v-if="form.userType === 'specific'" class="space-y-1 flex-1">
        <Label class="body-sm text-muted-foreground font-medium">Users</Label>
        <Input
          :model-value="form.users"
          placeholder="user1@example.com, user2@example.com"
          class="h-9 rounded-lg border-border bg-card body-sm placeholder:text-muted-foreground"
          @input="updateField('users', ($event.target as HTMLInputElement).value)"
        />
        <p class="text-xs text-muted-foreground">
          Comma-separated list. Wildcard supported (e.g., *@company.com, *.edu, *@contractors.org)
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Plus, X } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { XenditFormData, XenditTier } from '@/composables/usePolicyCreation'
import { XENDIT_CURRENCIES, XENDIT_COUNTRIES } from '@/config/policyTypes'

const props = defineProps<{
  form: XenditFormData
}>()

const emit = defineEmits<{
  'update:form': [value: XenditFormData]
}>()

const updateField = (field: keyof XenditFormData, value: unknown) => {
  emit('update:form', { ...props.form, [field]: String(value ?? '') })
}

const updateTierField = (index: number, field: keyof XenditTier, value: unknown) => {
  const updatedTiers = props.form.tiers.map((tier, i) =>
    i === index ? { ...tier, [field]: String(value ?? '') } : tier,
  )
  emit('update:form', { ...props.form, tiers: updatedTiers })
}

const addTier = () => {
  const updatedTiers = [
    ...props.form.tiers,
    { name: '', units: '', unitType: 'requests', price: '' },
  ]
  emit('update:form', { ...props.form, tiers: updatedTiers })
}

const removeTier = (index: number) => {
  const updatedTiers = props.form.tiers.filter((_, i) => i !== index)
  emit('update:form', { ...props.form, tiers: updatedTiers })
}
</script>

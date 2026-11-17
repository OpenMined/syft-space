<template>
  <!-- Providers are installation-wide: an edit applies to every Space sharing this benchmark. -->
  <section v-if="view" class="border border-border/50 rounded-lg p-5 space-y-5">
    <div>
      <h2 class="heading-3 text-foreground flex items-center gap-2">
        <KeyRound class="h-5 w-5 text-muted-foreground" />
        Model providers
        <InfoTip
          text="Each role can use its own provider and key; the key's owner pays for its calls."
        />
      </h2>
      <p class="text-xs text-muted-foreground mt-1 max-w-2xl">
        What each role sends, and whether it leaves this machine.
      </p>
    </div>

    <div class="space-y-4">
      <ProviderRow
        v-for="role in MODEL_ACCESS_ROLES"
        :key="role.key"
        v-model:url="urls[role.key]"
        :label="role.label"
        :tip="role.tip"
        :sends="role.sends"
        :placeholder="view[role.key].url_default || targets[role.key] || ''"
        :target="targets[role.key]"
        :local="localOf(role.key)"
        :key-set="view[role.key].key_set"
        :key-source="keySource(view, role.key)"
        :busy="busyRoles.has(role.key)"
        :save-key="(value: string) => saveKey(role.key, value)"
        @clear-key="clearKey(role.key)"
      />
    </div>

    <div class="flex items-center gap-2">
      <Button size="sm" :disabled="savingUrls" @click="saveUrls">
        {{ savingUrls ? 'Saving…' : 'Save addresses' }}
      </Button>
      <span v-if="urlsDirty" class="text-xs text-muted-foreground">Unsaved changes</span>
    </div>
  </section>
</template>

<script setup lang="ts">
/** The model providers a benchmark calls, one row per role: address, key, and where it goes. */
import { computed, onMounted, reactive, ref } from 'vue'
import { toast } from 'vue-sonner'
import { KeyRound } from 'lucide-vue-next'

import InfoTip from '@/components/benchmark/InfoTip.vue'
import ProviderRow from '@/components/benchmark/ProviderRow.vue'
import {
  MODEL_ACCESS_ROLES,
  effectiveUrl,
  keySource,
  type ProviderKey,
} from '@/components/benchmark/modelAccess'
import { Button } from '@/components/ui/button'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import type { ProviderKeyState, ProviderResponse } from '@/api/types'

const props = defineProps<{ connectionId: string }>()

/** What the benchmark reported; null until loaded or when it could not be read. */
const view = ref<ProviderResponse | null>(null)
/** The addresses as typed, by role. */
const urls = reactive<Record<ProviderKey, string>>({
  shared: '',
  generator: '',
  filter: '',
  subject: '',
  judge: '',
})
const savingUrls = ref(false)
/** Roles with a key save or clear in flight; each role's controls wait only for its own. */
const busyRoles = reactive(new Set<ProviderKey>())

const urlsDirty = computed(() => {
  const stored = view.value
  return !!stored && MODEL_ACCESS_ROLES.some(({ key }) => urls[key] !== stored[key].url)
})

/** Each role's effective address, from `typed` over the benchmark's defaults. */
function targetsOf(typed: Record<ProviderKey, string>): Record<ProviderKey, string> {
  const out = {} as Record<ProviderKey, string>
  const stored = view.value
  if (!stored) return out
  for (const { key } of MODEL_ACCESS_ROLES) out[key] = effectiveUrl(typed, stored, key)
  return out
}

const targets = computed(() => targetsOf(urls))
const savedTargets = computed(() =>
  targetsOf(
    Object.fromEntries(
      MODEL_ACCESS_ROLES.map(({ key }) => [key, view.value?.[key].url ?? '']),
    ) as Record<ProviderKey, string>,
  ),
)

/**
 * The benchmark's verdict on a role's address; null while an unsaved edit
 * changes where the role calls, since only a saved address has been judged.
 */
function localOf(key: ProviderKey): boolean | null {
  const stored = view.value
  if (!stored || targets.value[key] !== savedTargets.value[key]) return null
  return stored[key].local
}

const KEY_NAMES = Object.fromEntries(
  MODEL_ACCESS_ROLES.map((role) => [role.key, role.keyName]),
) as Record<ProviderKey, string>

/** Takes the benchmark's full view and sets every address box to the stored address. */
function adopt(fresh: ProviderResponse): void {
  view.value = fresh
  for (const { key } of MODEL_ACCESS_ROLES) urls[key] = fresh[key]?.url ?? ''
}

async function load(): Promise<void> {
  try {
    adopt(await benchmarksApi.getProvider(props.connectionId))
  } catch {
    view.value = null
  }
}

/**
 * Takes from an address-save reply only the address side of each role; key
 * state comes from key replies alone, since a key save may be in flight. A box
 * edited since `sent` keeps the newer text.
 */
function adoptAddresses(fresh: ProviderResponse, sent: Record<ProviderKey, string>): void {
  const stored = view.value
  if (!stored) return
  for (const { key } of MODEL_ACCESS_ROLES) {
    const { url, url_default, local } = fresh[key]
    stored[key] = { ...stored[key], url, url_default, local }
    if (urls[key] === sent[key]) urls[key] = url
  }
}

async function saveUrls(): Promise<void> {
  savingUrls.value = true
  const sent = { ...urls }
  try {
    adoptAddresses(
      await benchmarksApi.saveProvider(props.connectionId, {
        ollama_url: sent.shared,
        generator_url: sent.generator,
        subject_url: sent.subject,
        judge_url: sent.judge,
        filter_url: sent.filter,
      }),
      sent,
    )
    toast.success('Saved')
  } catch {
    toast.error('Could not save those addresses')
  } finally {
    savingUrls.value = false
  }
}

/** Takes a key reply into `role`'s key state; address boxes are left alone. */
function adoptKey(role: ProviderKey, fresh: ProviderKeyState): void {
  const stored = view.value
  if (!stored) return
  const { key_set, key_updated_at } = fresh
  stored[role] = { ...stored[role], key_set, key_updated_at }
}

/** Stores a role's key; true once the benchmark took it. */
async function saveKey(role: ProviderKey, value: string): Promise<boolean> {
  busyRoles.add(role)
  try {
    adoptKey(
      role,
      await benchmarksApi.saveProviderCredential(props.connectionId, KEY_NAMES[role], value),
    )
    toast.success('Key stored')
    return true
  } catch {
    toast.error('Could not store that key')
    return false
  } finally {
    busyRoles.delete(role)
  }
}

async function clearKey(role: ProviderKey): Promise<void> {
  busyRoles.add(role)
  try {
    adoptKey(
      role,
      await benchmarksApi.deleteProviderCredential(props.connectionId, KEY_NAMES[role]),
    )
    toast.success('Key cleared')
  } catch {
    toast.error('Could not clear that key')
  } finally {
    busyRoles.delete(role)
  }
}

onMounted(load)
</script>

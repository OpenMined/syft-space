<script setup lang="ts">
import { Menu } from 'lucide-vue-next'
import { useRouter, useRoute } from 'vue-router'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet'
import AppSidebar from '@/components/AppSidebar.vue'
import { useSidebar } from '@/composables/useSidebar'
import { useCollectiveMode } from '@/composables/useCollectiveMode'
import { collectiveStatsSummary } from '@/stores/mockCollective'
import SyftLogo from '@/assets/syftbox-logo.svg'

const router = useRouter()
const route = useRoute()
const { isMobileOpen, closeMobile, toggleMobile } = useSidebar()
const {
  isCollectiveAdmin,
  isCollectiveMember,
  isCollectiveViewActive,
  toggleCollectiveView,
  collectiveBadgeLabel,
} = useCollectiveMode()

const collectiveName = collectiveStatsSummary.name

const collectiveOnlyRoutes = ['members', 'collective-apis', 'analytics']

const handleViewToggle = () => {
  const wasCollective = isCollectiveViewActive.value
  toggleCollectiveView()
  if (wasCollective && collectiveOnlyRoutes.includes(route.name as string)) {
    router.push({ name: 'home' })
  }
}
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-background">
    <!-- Desktop sidebar -->
    <div class="hidden md:flex shrink-0">
      <AppSidebar />
    </div>

    <!-- Mobile top bar + sheet -->
    <div
      class="md:hidden fixed top-0 left-0 right-0 z-40 flex items-center h-14 px-4 bg-background border-b border-border"
    >
      <Button variant="ghost" size="icon" class="h-9 w-9" @click="toggleMobile">
        <Menu class="h-5 w-5" />
      </Button>
      <div class="flex items-center gap-2 ml-3">
        <img :src="SyftLogo" alt="Syft Space" class="h-6 w-6" />
        <div class="flex flex-col gap-0.5">
          <span class="text-base font-bold text-foreground leading-none">Syft Space</span>
          <button
            v-if="isCollectiveAdmin"
            type="button"
            class="rounded-md w-fit focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            @click="handleViewToggle"
          >
            <Badge
              :variant="isCollectiveViewActive ? 'default' : 'outline'"
              class="text-[10px] cursor-pointer"
            >
              {{ collectiveBadgeLabel }}
            </Badge>
          </button>
          <Badge v-else-if="isCollectiveMember" variant="secondary" class="text-[10px] w-fit">
            {{ collectiveName }}
          </Badge>
        </div>
      </div>
    </div>

    <Sheet
      :open="isMobileOpen"
      @update:open="
        (val: boolean) => {
          if (!val) closeMobile()
        }
      "
    >
      <SheetContent side="left" class="p-0 w-60">
        <SheetTitle class="sr-only">Navigation</SheetTitle>
        <AppSidebar />
      </SheetContent>
    </Sheet>

    <!-- Main content area -->
    <main class="flex-1 overflow-y-auto md:pt-0 pt-14">
      <slot />
    </main>
  </div>
</template>

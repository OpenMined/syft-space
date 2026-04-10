<script setup lang="ts">
import { Menu } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet'
import AppSidebar from '@/components/AppSidebar.vue'
import { useSidebar } from '@/composables/useSidebar'
import SyftLogo from '@/assets/syftbox-logo.svg'

const { isMobileOpen, closeMobile, toggleMobile } = useSidebar()
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
        <span class="text-base font-bold text-foreground">Syft Space</span>
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

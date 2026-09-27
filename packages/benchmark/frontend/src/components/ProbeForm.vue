<script setup lang="ts">
// A settings layer for this one target, drawn from the fields the benchmark
// itself describes (name, type, bounds, choices, group) — nothing here knows
// what a setting means beyond that. Every field has three states, not two:
// set here, or left to fall back to the installation's own default, shown
// beside it rather than left blank. An empty box is a fallback, not a zero,
// so an unset field is simply absent from what gets saved.
import { computed } from "vue";
import type { ProbeField, ProbeLayer } from "@/api/types";

const props = defineProps<{
  fields: ProbeField[];
  modelValue: ProbeLayer;
  inherited: ProbeLayer;
}>();
const emit = defineEmits<{ "update:modelValue": [ProbeLayer] }>();

function humanise(name: string): string {
  const words = name.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

const groups = computed(() => {
  const order: string[] = [];
  const buckets = new Map<string, ProbeField[]>();
  for (const field of props.fields) {
    if (!buckets.has(field.group)) {
      buckets.set(field.group, []);
      order.push(field.group);
    }
    buckets.get(field.group)!.push(field);
  }
  return order.map((code) => ({
    code,
    label: humanise(code),
    fields: buckets.get(code)!,
  }));
});

function isSet(name: string): boolean {
  return Object.prototype.hasOwnProperty.call(props.modelValue, name);
}

function write(name: string, next: unknown): void {
  const out = { ...props.modelValue };
  if (next === undefined) {
    delete out[name];
  } else {
    out[name] = next;
  }
  emit("update:modelValue", out);
}

function clear(name: string): void {
  write(name, undefined);
}

function inheritedText(field: ProbeField): string {
  const fallback = props.inherited[field.name];
  if (fallback === undefined || fallback === null) return "default";
  if (Array.isArray(fallback))
    return fallback.length ? fallback.join(", ") : "none";
  if (typeof fallback === "boolean") return fallback ? "yes" : "no";
  return String(fallback);
}

function value(name: string): unknown {
  return props.modelValue[name];
}

function listText(name: string): string {
  const own = props.modelValue[name];
  return Array.isArray(own) ? own.join(", ") : "";
}

function setList(field: ProbeField, text: string): void {
  if (!text.trim()) {
    write(field.name, undefined);
    return;
  }
  const parts = text
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  write(
    field.name,
    field.item_type === "number" || field.item_type === "integer"
      ? parts.map(Number).filter((n) => !Number.isNaN(n))
      : parts,
  );
}

const INHERIT = "__inherit__";

function choiceValue(name: string): string {
  const own = props.modelValue[name];
  return own === undefined ? INHERIT : String(own);
}

function setChoice(name: string, raw: string): void {
  write(name, raw === INHERIT ? undefined : raw);
}

function boolValue(name: string): string {
  const own = props.modelValue[name];
  if (typeof own !== "boolean") return INHERIT;
  return own ? "true" : "false";
}

function setBool(name: string, raw: string): void {
  write(name, raw === INHERIT ? undefined : raw === "true");
}

function setNumber(name: string, raw: string): void {
  const text = raw.trim();
  if (!text) {
    write(name, undefined);
    return;
  }
  const parsed = Number(text);
  write(name, Number.isNaN(parsed) ? undefined : parsed);
}

function setText(name: string, raw: string): void {
  write(name, raw.trim() ? raw : undefined);
}
</script>

<template>
  <div class="space-y-5">
    <section v-for="group in groups" :key="group.code" class="space-y-3">
      <h3
        class="text-xs font-medium text-muted-foreground uppercase tracking-wide"
      >
        {{ group.label }}
      </h3>
      <div v-for="field in group.fields" :key="field.name" class="space-y-1">
        <div class="flex items-baseline justify-between gap-3">
          <label :for="field.name" class="text-sm">{{
            humanise(field.name)
          }}</label>
          <button
            v-if="isSet(field.name)"
            type="button"
            class="text-xs text-muted-foreground hover:text-foreground underline underline-offset-2"
            @click="clear(field.name)"
          >
            Clear
          </button>
          <span v-else class="text-xs text-muted-foreground">
            default: {{ inheritedText(field) }}
          </span>
        </div>

        <input
          v-if="field.type === 'array'"
          :id="field.name"
          :value="listText(field.name)"
          :placeholder="inheritedText(field)"
          class="h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
          @input="setList(field, ($event.target as HTMLInputElement).value)"
        />

        <select
          v-else-if="field.choices"
          :id="field.name"
          :value="choiceValue(field.name)"
          class="h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
          @change="
            setChoice(field.name, ($event.target as HTMLSelectElement).value)
          "
        >
          <option :value="INHERIT">default: {{ inheritedText(field) }}</option>
          <option
            v-for="choice in field.choices"
            :key="String(choice)"
            :value="String(choice)"
          >
            {{ choice }}
          </option>
        </select>

        <select
          v-else-if="field.type === 'boolean'"
          :id="field.name"
          :value="boolValue(field.name)"
          class="h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
          @change="
            setBool(field.name, ($event.target as HTMLSelectElement).value)
          "
        >
          <option :value="INHERIT">default: {{ inheritedText(field) }}</option>
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>

        <input
          v-else-if="field.type === 'integer' || field.type === 'number'"
          :id="field.name"
          type="number"
          :min="field.minimum"
          :max="field.maximum"
          :step="field.type === 'integer' ? 1 : 'any'"
          :value="(value(field.name) as number | undefined) ?? ''"
          :placeholder="inheritedText(field)"
          class="h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
          @input="
            setNumber(field.name, ($event.target as HTMLInputElement).value)
          "
        />

        <input
          v-else
          :id="field.name"
          :value="(value(field.name) as string | undefined) ?? ''"
          :placeholder="inheritedText(field)"
          class="h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
          @input="
            setText(field.name, ($event.target as HTMLInputElement).value)
          "
        />
      </div>
    </section>
  </div>
</template>

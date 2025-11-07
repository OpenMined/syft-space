# SyftAI Design Standards

## Typography Hierarchy (Based on HomePage.vue)

### Primary Typography Classes
- `heading-1` - Main hero headings (HomePage welcome)
- `heading-3` - Section headings (Recent Activity, etc.) 
- `text-2xl font-light` - Statistics/Numbers display
- `text-lg` - Large descriptive text (hero descriptions)
- `text-sm` - Standard body text, labels, descriptions
- `text-xs` - Small metadata, timestamps, helper text

### Button Standards
Use **only** shadcn Button variants:
- `<Button>` - Primary actions (default variant)
- `<Button variant="outline">` - Secondary actions
- `<Button variant="destructive">` - Delete/dangerous actions  
- `<Button variant="ghost">` - Subtle actions
- `<Button size="sm">`, `<Button size="lg">` - Size variants

### Color Standards
Use **only** shadcn semantic tokens:
- `text-foreground` - Primary text
- `text-muted-foreground` - Secondary/helper text
- `bg-background` - Main background
- `bg-card` - Card backgrounds
- `bg-muted` - Subtle backgrounds
- `border-border` - Standard borders
- `text-primary` - Brand/accent text
- `text-destructive` - Error states

### Component Standards

#### Page Layout
```vue
<div class="page-container">
  <div class="page-header">
    <div class="page-title-section">
      <Icon class="h-6 w-6 text-primary" />
      <h1 class="heading-3">Page Title</h1>
    </div>
    <p class="text-lg text-muted-foreground">Page description</p>
  </div>
  <!-- Content -->
</div>
```

#### Cards
```vue
<Card class="transition-all hover:shadow-md">
  <CardContent class="p-6">
    <!-- Card content -->
  </CardContent>
</Card>
```

#### Status Indicators
```vue
<Badge variant="outline" class="text-xs">
  <div class="w-2 h-2 bg-green-500 rounded-full mr-2"></div>
  Status Text
</Badge>
```

## Prohibited Patterns

### ❌ Don't Use
- Custom CSS variables like `var(--color-accent)`
- Hardcoded colors like `bg-purple-600`
- Inconsistent typography like `text-2xl font-bold` for page titles
- Custom button styling with classes like `px-5 py-2.5 rounded-lg`
- Mix of `text-gray-600` and `text-muted-foreground`

### ✅ Use Instead
- Shadcn semantic tokens: `text-primary`, `bg-card`, etc.
- Consistent typography hierarchy
- Shadcn Button variants only
- Semantic color classes

## Migration Guidelines

1. Replace page titles: `text-2xl font-bold` → `heading-3`
2. Replace descriptions: `text-gray-600` → `text-muted-foreground`  
3. Replace buttons: Custom styling → shadcn variants
4. Replace colors: CSS variables → shadcn tokens
5. Maintain the same visual hierarchy from HomePage.vue
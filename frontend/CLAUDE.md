# Claude Code Instructions

## UI Component Library

This project uses **shadcn/ui** as the primary component library. When implementing UI features, ALWAYS prefer shadcn/ui components over custom implementations.

### Available shadcn/ui Components

Located in `@/components/ui/`:

- Alert, AlertDescription, AlertTitle
- Badge
- Button
- Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle
- Checkbox
- Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger
- Input
- Label
- RadioGroup, RadioGroupItem
- Select, SelectContent, SelectItem, SelectTrigger, SelectValue
- Separator
- Tabs, TabsContent, TabsList, TabsTrigger
- Textarea
- Tooltip, TooltipContent, TooltipProvider, TooltipTrigger
- And more...

### Adding New Components

If a required shadcn/ui component is not yet installed in the project, use the following command to add it:

```bash
npx shadcn-vue@latest add <component-name>
```

For example:

- `npx shadcn-vue@latest add toast` - for Toast notifications
- `npx shadcn-vue@latest add dropdown-menu` - for DropdownMenu
- `npx shadcn-vue@latest add switch` - for Switch toggle

This ensures you get the latest version of the component and preserves tokens.

### Guidelines

1. **Always check for existing shadcn/ui components** before creating custom UI elements
2. **Install missing shadcn components** using the add command rather than implementing custom versions
3. **Use Tooltip components** instead of custom hover tooltips
4. **Use Dialog components** instead of custom modals
5. **Use Select components** instead of custom dropdowns
6. **Follow the existing import pattern**:

   ```typescript
   import { Button } from '@/components/ui/button'
   import { Card, CardContent } from '@/components/ui/card'
   ```

### Icon Library

This project uses **lucide-vue-next** for icons. Import icons as needed:

```typescript
import { Save, ArrowLeft, Plus, X } from 'lucide-vue-next'
```

### Styling

- Use Tailwind CSS classes for styling
- Follow the existing color scheme and spacing patterns
- Maintain consistency with shadows, borders, and hover states

### Form Handling

- Use shadcn/ui form components (Input, Textarea, Select, etc.)
- Maintain consistent validation patterns
- Use Label components for form field labels

## Code Style Preferences

- Use Vue 3 Composition API with `<script setup>` syntax
- Prefer TypeScript for type safety
- Use reactive refs and computed properties appropriately
- Follow the existing file structure and naming conventions

## Testing Commands

When code changes are made, run these commands to ensure quality:

- `bun run lint:oxlint` - Check for linting errors
- `bun run type-check` - Verify TypeScript types
- `bun run test:unit` - Run tests (if available)

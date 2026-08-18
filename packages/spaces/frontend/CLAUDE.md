# Claude Code Instructions

**Important**: For detailed design guidelines, color schemes, and UI patterns, refer to `DESIGN_STANDARDS.md` in this directory.

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
- **NEVER leave historical comments or leftover code** - code should be self-explanatory without needing to know previous context or implementation history. Git history exists for tracking changes.

## Package Management

This project uses **bun** as the package manager. Always use bun for package operations:

```bash
bun add <package-name>        # Install dependencies
bun add -D <package-name>     # Install dev dependencies
bun install                   # Install all dependencies
bun remove <package-name>     # Remove dependencies
```

## API Integration

### Folder Structure
```
src/
├── api/
│   ├── client.ts          # Axios configuration
│   ├── types/
│   │   └── index.ts       # TypeScript interfaces matching backend schemas
│   └── endpoints/
│       ├── datasets.ts    # Dataset-related API calls
│       ├── models.ts      # Model-related API calls
│       └── endpoints.ts   # Endpoint-related API calls
├── composables/
│   └── useFeatureName.ts  # Reactive API hooks with loading/error states
└── stores/
    └── featureName.ts     # Pinia stores using API calls
```

### Integration Steps

1. **Define Types** - Match backend Pydantic schemas:
   ```typescript
   // src/api/types/index.ts
   export interface BrowseResponse {
     path: string
     parent?: string
     items: FileItem[]
   }
   ```

2. **Create API Module**:
   ```typescript
   // src/api/endpoints/datasets.ts
   import { apiClient } from '../client'
   import type { BrowseResponse } from '../types'

   export const datasetsApi = {
     browse: async (path = '~'): Promise<BrowseResponse> => {
       const response = await apiClient.get('/datasets/browse', { params: { path } })
       return response.data
     }
   }
   ```

3. **Create Composable** for complex features:
   ```typescript
   // src/composables/useDatasetBrowser.ts
   export function useDatasetBrowser() {
     const data = ref([])
     const loading = ref(false)
     const error = ref(null)

     const load = async () => {
       loading.value = true
       try {
         data.value = await datasetsApi.browse()
       } catch (e) {
         error.value = e
       } finally {
         loading.value = false
       }
     }

     return { data, loading, error, load }
   }
   ```

4. **Update Components** to use the composable or store

### API Configuration
- Base URL: `http://localhost:8080/api/v1` (configured in `.env`)
- Uses axios with interceptors for auth and error handling
- CORS is enabled on backend for `http://localhost:5173`

## Testing Commands

When code changes are made, run these commands to ensure quality:

- `bun run lint` - Check for linting errors
- `bun run typecheck` - Verify TypeScript types
- `bun run test:unit` - Run tests (if available)

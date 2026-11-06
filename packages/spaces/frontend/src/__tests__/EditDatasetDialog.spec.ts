import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import EditDatasetDialog from '@/components/EditDatasetDialog.vue'
import type { ConfigSchema } from '@/api/types'

const api = vi.hoisted(() => ({
  getType: vi.fn(),
  update: vi.fn(),
  healthcheckWith: vi.fn(),
}))
vi.mock('@/api/endpoints/datasets', () => ({ datasetsApi: api }))
vi.mock('vue-sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const weaviate: ConfigSchema = {
  required: ['http_url', 'grpc_url', 'api_key', 'collection_name'],
  properties: {
    http_url: { type: 'string', axis: 'vector_store', editable: true },
    api_key: { type: 'string', axis: 'vector_store', editable: true, visibility: 'secret' },
    collection_name: { type: 'string', axis: 'vector_store' },
    headers: {
      anyOf: [{ type: 'object' }, { type: 'null' }],
      axis: 'vector_store',
      editable: true,
      visibility: 'secret',
    },
    filters: { anyOf: [{ type: 'object' }, { type: 'null' }], axis: 'vector_store' },
  },
}

const stored = {
  http_url: 'https://old.weaviate',
  collection_name: 'Docs',
  headers: { 'X-Org': null },
}

const mountDialog = async () => {
  const wrapper = mount(EditDatasetDialog, {
    attachTo: document.body,
    props: {
      open: true,
      dataset: {
        name: 'wv',
        dtype: 'remote_weaviate',
        summary: 'A store',
        tags: ['a'],
        configuration: stored,
      },
    },
  })
  await flushPromises()
  return wrapper
}

const bodyText = () => document.body.textContent ?? ''
const input = (id: string) => document.body.querySelector<HTMLInputElement>(`#${id}`)!
const buttonNamed = (text: string) =>
  Array.from(document.body.querySelectorAll('button')).find((b) => b.textContent?.trim() === text)!

describe('EditDatasetDialog', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
    api.getType.mockReset().mockResolvedValue({ name: 'remote_weaviate', config_schema: weaviate })
    api.update.mockReset()
    api.healthcheckWith.mockReset()
  })

  it('shows only editable fields, secrets as configured, locked fields hidden', async () => {
    await mountDialog()
    expect(api.getType).toHaveBeenCalledWith('remote_weaviate')
    expect(input('cfg-http_url').value).toBe('https://old.weaviate')
    expect(bodyText()).toContain('API key')
    expect(bodyText()).toContain('Configured')
    const headerNames = Array.from(document.body.querySelectorAll<HTMLInputElement>('input')).map(
      (i) => i.value,
    )
    expect(headerNames).toContain('X-Org')
    expect(bodyText()).not.toContain('collection_name')
    expect(bodyText()).not.toContain('filters')
  })

  it('saves only what changed and reports a configuration change', async () => {
    api.update.mockResolvedValue({ name: 'wv', connected_endpoints: [] })
    const wrapper = await mountDialog()

    await wrapper.findComponent({ name: 'DatasetConfigFields' }).vm.$emit('update', 'http_url', {
      kind: 'value',
      value: 'https://new.weaviate',
    })
    buttonNamed('Replace').click()
    await flushPromises()
    const secret = input('cfg-api_key')
    secret.value = 'fresh-key'
    secret.dispatchEvent(new Event('input'))
    await flushPromises()

    buttonNamed('Save Changes').click()
    await flushPromises()

    expect(api.update).toHaveBeenCalledWith('wv', {
      name: 'wv',
      summary: 'A store',
      tags: 'a',
      configuration: { http_url: 'https://new.weaviate', api_key: 'fresh-key' },
    })
    expect(wrapper.emitted('dataset-updated')?.[0]?.[1]).toBe(true)
  })

  it('sends no configuration when only the name changed', async () => {
    api.update.mockResolvedValue({ name: 'wv2', connected_endpoints: [] })
    const wrapper = await mountDialog()
    const name = input('edit-dataset-name')
    name.value = 'wv2'
    name.dispatchEvent(new Event('input'))
    await flushPromises()

    buttonNamed('Save Changes').click()
    await flushPromises()

    expect(api.update).toHaveBeenCalledWith('wv', { name: 'wv2', summary: 'A store', tags: 'a' })
    expect(wrapper.emitted('dataset-updated')?.[0]?.[1]).toBe(false)
  })

  it('shows the backend reason when the save is refused', async () => {
    api.update.mockRejectedValue({
      isAxiosError: true,
      response: { status: 400, data: { detail: "'collection_name' is not editable" } },
    })
    await mountDialog()
    buttonNamed('Save Changes').click()
    await flushPromises()
    expect(bodyText()).toContain("'collection_name' is not editable")
  })

  it('runs a dry-run health check with the drafted changes', async () => {
    api.healthcheckWith.mockResolvedValue({ status: 'unhealthy', message: 'auth failed' })
    const wrapper = await mountDialog()
    await wrapper.findComponent({ name: 'DatasetConfigFields' }).vm.$emit('update', 'http_url', {
      kind: 'value',
      value: 'https://new.weaviate',
    })
    buttonNamed('Test connection').click()
    await flushPromises()
    expect(api.healthcheckWith).toHaveBeenCalledWith('wv', { http_url: 'https://new.weaviate' })
    expect(bodyText()).toContain('Connection failed')
    expect(bodyText()).toContain('auth failed')
  })
})

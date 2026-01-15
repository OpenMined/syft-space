import { ref, type Ref } from 'vue'
import { marketplacesApi } from '@/api/endpoints/marketplaces'
import { settingsApi } from '@/api/endpoints/settings'

// Helper function to check if user is already onboarded
export async function checkOnboardingStatus(): Promise<boolean> {
  try {
    // Check if any marketplaces exist
    const marketplaces = await marketplacesApi.list()
    return marketplaces.length > 0
  } catch (error) {
    console.error('Failed to check onboarding status:', error)
    return false
  }
}

export function useOnboarding() {
  // Current step tracking
  const currentStep = ref(1)
  const completedSteps = ref(new Set<number>())

  // Auth state
  const authMode: Ref<'register' | 'signin'> = ref('register')
  const registerForm = ref({
    username: '',
    email: '',
    name: '',
    password: '',
  })
  const signinForm = ref({
    username: '',
    password: '',
  })

  // Network setup state
  const networkMode: Ref<'subdomain' | 'custom' | ''> = ref('')
  const publicUrl = ref(window.location.origin)

  // Username availability checking
  const checkingUsername = ref(false)
  const usernameAvailable: Ref<boolean | null> = ref(null)
  let usernameCheckTimeout: number | null = null

  // Loading states
  const registering = ref(false)
  const signingIn = ref(false)
  const completing = ref(false)

  // Error states
  const authError = ref('')
  const networkError = ref('')

  // Stored marketplace data after successful auth
  const marketplaceData: Ref<{ id: string; username: string } | null> = ref(null)

  // Check username availability with debouncing
  const checkUsernameAvailability = async (username: string) => {
    // Clear previous timeout
    if (usernameCheckTimeout) {
      clearTimeout(usernameCheckTimeout)
    }

    // Reset availability state
    usernameAvailable.value = null

    // Validate username format
    if (!username || !/^[a-zA-Z0-9_-]+$/.test(username)) {
      return
    }

    // Debounce the check
    usernameCheckTimeout = setTimeout(async () => {
      checkingUsername.value = true
      try {
        const available = await marketplacesApi.checkUsernameAvailability(username)
        usernameAvailable.value = available
      } catch (error) {
        console.error('Failed to check username availability:', error)
        usernameAvailable.value = null
      } finally {
        checkingUsername.value = false
      }
    }, 500) as unknown as number
  }

  // Register new account
  const register = async (): Promise<boolean> => {
    registering.value = true
    authError.value = ''

    try {
      const response = await marketplacesApi.register({
        name: registerForm.value.name,
        username: registerForm.value.username,
        email: registerForm.value.email,
        password: registerForm.value.password,
        // url and accounting_url will use backend defaults
      })

      // Store marketplace data for later use
      marketplaceData.value = {
        id: response.id,
        username: registerForm.value.username,
      }

      return true
    } catch (error) {
      console.error('Registration failed:', error)
      if (error && typeof error === 'object' && 'response' in error) {
        const axiosError = error as { response?: { data?: { detail?: string } } }
        if (axiosError.response?.data?.detail) {
          authError.value = axiosError.response.data.detail
        } else {
          authError.value = 'Failed to create account. Please try again.'
        }
      } else {
        authError.value = 'Failed to create account. Please try again.'
      }
      return false
    } finally {
      registering.value = false
    }
  }

  // Sign in to existing account
  const signIn = async (): Promise<boolean> => {
    signingIn.value = true
    authError.value = ''

    try {
      const response = await marketplacesApi.connect({
        username: signinForm.value.username,
        password: signinForm.value.password,
        // url will use backend default
      })

      // Store marketplace data for later use
      marketplaceData.value = {
        id: response.id,
        username: signinForm.value.username,
      }

      return true
    } catch (error) {
      console.error('Sign in failed:', error)
      if (error && typeof error === 'object' && 'response' in error) {
        const axiosError = error as { response?: { data?: { detail?: string } } }
        if (axiosError.response?.data?.detail) {
          authError.value = axiosError.response.data.detail
        } else {
          authError.value = 'Invalid username or password. Please try again.'
        }
      } else {
        authError.value = 'Invalid username or password. Please try again.'
      }
      return false
    } finally {
      signingIn.value = false
    }
  }

  // Complete setup (save network configuration)
  const completeSetup = async (): Promise<boolean> => {
    completing.value = true
    networkError.value = ''

    try {
      // Determine the final URL based on network mode
      let finalUrl: string
      if (networkMode.value === 'subdomain') {
        // Use the username subdomain
        const username =
          marketplaceData.value?.username ||
          registerForm.value.username ||
          signinForm.value.username
        finalUrl = `https://${username}.syfthub.net`
      } else if (networkMode.value === 'custom') {
        finalUrl = publicUrl.value
      } else {
        networkError.value = 'Please select a networking option'
        return false
      }

      // Update the public URL in the backend
      await settingsApi.updatePublicUrl({ public_url: finalUrl })

      console.log('Network setup completed with URL:', finalUrl)

      return true
    } catch (error) {
      console.error('Failed to complete setup:', error)
      networkError.value = 'Failed to save network configuration. Please try again.'
      return false
    } finally {
      completing.value = false
    }
  }

  // Reset all forms and state
  const reset = () => {
    currentStep.value = 1
    completedSteps.value.clear()
    authMode.value = 'register'
    registerForm.value = {
      username: '',
      email: '',
      name: '',
      password: '',
    }
    signinForm.value = {
      username: '',
      password: '',
    }
    networkMode.value = ''
    publicUrl.value = window.location.origin
    usernameAvailable.value = null
    authError.value = ''
    networkError.value = ''
    marketplaceData.value = null
  }

  return {
    // Step tracking
    currentStep,
    completedSteps,

    // Auth state
    authMode,
    registerForm,
    signinForm,

    // Network state
    networkMode,
    publicUrl,

    // Username checking
    checkingUsername,
    usernameAvailable,

    // Loading states
    registering,
    signingIn,
    completing,

    // Error states
    authError,
    networkError,

    // Methods
    checkUsernameAvailability,
    register,
    signIn,
    completeSetup,
    reset,
  }
}

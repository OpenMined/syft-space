import { ref, type Ref } from 'vue'
import axios from 'axios'
import { marketplacesApi } from '@/api/endpoints/marketplaces'
import { settingsApi } from '@/api/endpoints/settings'
import { MarketplaceErrorCode } from '@/api/types'

interface ErrorDetail {
  code?: string
  message?: string
  field?: string
}

function extractDetail(error: unknown): ErrorDetail | null {
  if (!axios.isAxiosError(error)) return null
  const detail = error.response?.data?.detail
  if (typeof detail === 'string') return { message: detail }
  if (detail && typeof detail === 'object') return detail as ErrorDetail
  return null
}

function extractDetailMessage(error: unknown, fallback: string): string {
  return extractDetail(error)?.message || fallback
}

interface PendingVerification {
  email: string
  password: string
  url?: string
  // 'signin' triggers an auto-resend when the dialog opens; 'register' doesn't.
  origin: 'register' | 'signin'
}

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

  // Managed mode: a station launched this space, so onboarding drops the
  // SyftHub signup and the hub-generated tunnel URL — sign-in only, and the
  // station-assigned public URL is pre-filled (still editable).
  const managed = ref(false)

  const loadManagedMode = async (): Promise<void> => {
    try {
      const response = await settingsApi.getManaged()
      managed.value = response.managed
      if (response.managed) {
        authMode.value = 'signin'
        networkMode.value = 'custom'
        if (response.public_url) publicUrl.value = response.public_url
      }
    } catch {
      // Treat as self-hosted if the check fails
    }
  }

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

  // OTP / email verification state
  const pendingVerification: Ref<PendingVerification | null> = ref(null)
  const verifyingOtp = ref(false)
  const resendingOtp = ref(false)
  const otpError = ref('')

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

  const register = async (): Promise<boolean> => {
    registering.value = true
    authError.value = ''

    try {
      const result = await marketplacesApi.register({
        name: registerForm.value.name,
        username: registerForm.value.username,
        email: registerForm.value.email,
        password: registerForm.value.password,
      })

      if (result.kind === 'verification_required') {
        pendingVerification.value = {
          email: result.email,
          password: registerForm.value.password,
          url: result.url,
          origin: 'register',
        }
        return false
      }

      marketplaceData.value = {
        id: result.marketplace.id,
        username: registerForm.value.username,
      }

      return true
    } catch (error) {
      console.error('Registration failed:', error)
      authError.value = extractDetailMessage(error, 'Failed to create account. Please try again.')
      return false
    } finally {
      registering.value = false
    }
  }

  const signIn = async (): Promise<boolean> => {
    signingIn.value = true
    authError.value = ''

    try {
      const response = await marketplacesApi.connect({
        username: signinForm.value.username,
        password: signinForm.value.password,
      })

      marketplaceData.value = {
        id: response.id,
        username: signinForm.value.username,
      }

      return true
    } catch (error) {
      console.error('Sign in failed:', error)
      const detail = extractDetail(error)
      // Only route into the OTP dialog when we have an email to address the
      // resend to — SyftHub's login form also accepts username, in which case
      // we can't drive the verification flow and fall back to the error toast.
      if (
        detail?.code === MarketplaceErrorCode.EmailNotVerified &&
        signinForm.value.username.includes('@')
      ) {
        pendingVerification.value = {
          email: signinForm.value.username,
          password: signinForm.value.password,
          origin: 'signin',
        }
        return false
      }
      authError.value = detail?.message || 'Invalid username or password. Please try again.'
      return false
    } finally {
      signingIn.value = false
    }
  }

  const verifyOtp = async (code: string): Promise<boolean> => {
    if (!pendingVerification.value) {
      otpError.value = 'No verification is in progress.'
      return false
    }

    verifyingOtp.value = true
    otpError.value = ''

    try {
      const response = await marketplacesApi.verifyOtp({
        email: pendingVerification.value.email,
        password: pendingVerification.value.password,
        url: pendingVerification.value.url,
        code,
      })

      marketplaceData.value = {
        id: response.id,
        username: response.name,
      }
      pendingVerification.value = null
      return true
    } catch (error) {
      console.error('OTP verification failed:', error)
      otpError.value = extractDetailMessage(
        error,
        'Could not verify that code. Try again or request a new one.',
      )
      return false
    } finally {
      verifyingOtp.value = false
    }
  }

  const resendOtp = async (): Promise<boolean> => {
    if (!pendingVerification.value) {
      otpError.value = 'No verification is in progress.'
      return false
    }

    resendingOtp.value = true
    otpError.value = ''

    try {
      await marketplacesApi.resendOtp({
        email: pendingVerification.value.email,
        url: pendingVerification.value.url,
      })
      return true
    } catch (error) {
      console.error('OTP resend failed:', error)
      otpError.value = extractDetailMessage(
        error,
        'Could not resend the code. Please try again in a minute.',
      )
      return false
    } finally {
      resendingOtp.value = false
    }
  }

  const cancelVerification = () => {
    pendingVerification.value = null
    otpError.value = ''
  }

  // Complete setup (save network configuration)
  const completeSetup = async (): Promise<boolean> => {
    completing.value = true
    networkError.value = ''

    try {
      // Determine the final URL based on network mode
      let finalUrl: string
      if (networkMode.value === 'subdomain') {
        const proxyResponse = await settingsApi.configureProxy()

        if (!proxyResponse.connected || !proxyResponse.public_url) {
          networkError.value = 'Failed to connect proxy tunnel. Please try again.'
          return false
        }

        finalUrl = proxyResponse.public_url
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

  // Load existing onboarding state (for page refresh after partial completion)
  const loadExistingState = async (): Promise<boolean> => {
    try {
      const marketplaces = await marketplacesApi.list()
      const mp = marketplaces[0]
      if (mp) {
        marketplaceData.value = {
          id: mp.id,
          username: mp.username,
        }
        return true
      }
      return false
    } catch {
      return false
    }
  }

  // Reset all forms and state (managed spaces keep their sign-in-only modes)
  const reset = () => {
    currentStep.value = 1
    completedSteps.value.clear()
    authMode.value = managed.value ? 'signin' : 'register'
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
    networkMode.value = managed.value ? 'custom' : ''
    publicUrl.value = window.location.origin
    usernameAvailable.value = null
    authError.value = ''
    networkError.value = ''
    marketplaceData.value = null
    pendingVerification.value = null
    otpError.value = ''
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
    managed,
    loadManagedMode,

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

    // Marketplace data (set after auth success)
    marketplaceData,

    // OTP / email verification state
    pendingVerification,
    verifyingOtp,
    resendingOtp,
    otpError,

    // Methods
    checkUsernameAvailability,
    register,
    signIn,
    verifyOtp,
    resendOtp,
    cancelVerification,
    completeSetup,
    loadExistingState,
    reset,
  }
}

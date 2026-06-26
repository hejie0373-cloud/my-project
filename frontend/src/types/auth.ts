export interface User {
  id: string
  name: string | null
  phone: string | null
  email: string | null
  avatarUrl: string | null
  isActive: boolean
  roles: string[]
  storeId: string | null
  createdAt: string
}

export interface TokenResponse {
  accessToken: string
  refreshToken: string
  tokenType: string
  expiresIn: number
}

export interface LoginByPhoneForm {
  phone: string
  code: string
}

export interface LoginByEmailForm {
  email: string
  password: string
}


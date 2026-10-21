import { initializeApp, type FirebaseApp } from 'firebase/app'
import {
  GoogleAuthProvider,
  getAuth,
  onAuthStateChanged,
  signInWithPopup,
  signOut,
  type Auth,
  type User,
} from 'firebase/auth'

const config = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
}

export const authEnabled = Boolean(config.apiKey)

let app: FirebaseApp | undefined
let auth: Auth | undefined
if (authEnabled) {
  app = initializeApp(config)
  auth = getAuth(app)
}

export async function getIdToken(): Promise<string | null> {
  return auth?.currentUser ? auth.currentUser.getIdToken() : null
}

export function watchUser(cb: (user: User | null) => void): () => void {
  if (!auth) {
    cb(null)
    return () => {}
  }
  return onAuthStateChanged(auth, cb)
}

export async function signIn(): Promise<void> {
  if (auth) await signInWithPopup(auth, new GoogleAuthProvider())
}

export async function logOut(): Promise<void> {
  if (auth) await signOut(auth)
}

import './app.css'
import App from './App.svelte'

// Default to dark mode (override system). We'll add a user toggle later.
document.documentElement.dataset.theme = 'dark'

const app = new App({
  target: document.getElementById('app')!,
})

export default app

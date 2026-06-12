import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
    rules: {
      // Срабатывает на корректном паттерне «загрузка по mount → setState» (fetch-on-mount)
      // и на стандартной инициализации auth — это не дефекты. Держим как предупреждение.
      'react-hooks/set-state-in-effect': 'warn',
      // Контекст + хук в одном файле (AuthContext + useAuth) — обычная и допустимая форма.
      'react-refresh/only-export-components': 'warn',
    },
  },
])

'use client'

import { createTheme, ThemeOptions } from '@mui/material/styles'

const getDesignTokens = (mode: 'light' | 'dark'): ThemeOptions => ({
  palette: {
    mode,
    ...(mode === 'light'
      ? {
          primary: {
            main: '#1976d2',
          },
          secondary: {
            main: '#dc004e',
          },
          success: {
            main: '#2e7d32',
          },
          background: {
            default: '#f5f5f5',
            paper: '#ffffff',
          },
        }
      : {
          primary: {
            main: '#64b5f6',
          },
          secondary: {
            main: '#f06292',
          },
          success: {
            main: '#81c784',
          },
          background: {
            default: '#121212',
            paper: '#1e1e1e',
          },
        }),
  },
})

export const lightTheme = createTheme(getDesignTokens('light'))
export const darkTheme = createTheme(getDesignTokens('dark'))

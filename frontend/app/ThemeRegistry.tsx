'use client'

import { ThemeProvider } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import { useState, useEffect, createContext, useContext, useCallback } from 'react'
import { lightTheme, darkTheme } from './theme'
import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const DarkModeContext = createContext<{
  darkMode: boolean
  setDarkMode: (value: boolean) => void
}>({
  darkMode: false,
  setDarkMode: () => { },
})

export const useDarkMode = () => useContext(DarkModeContext)

export default function ThemeRegistry({ children }: { children: React.ReactNode }) {
  const [darkMode, setDarkModeState] = useState(false)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    const loadDarkMode = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/config`)
        if (response.data.dark_mode !== undefined) {
          setDarkModeState(response.data.dark_mode)
        } else {
          const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
          setDarkModeState(prefersDark)
        }
      } catch (error) {
        // Fallback to system preference if API fails
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
        setDarkModeState(prefersDark)
      } finally {
        setLoaded(true)
      }
    }
    loadDarkMode()
  }, [])

  const setDarkMode = useCallback((value: boolean) => {
    setDarkModeState(value)
    axios.get(`${API_URL}/api/config`).then(response => {
      const config = response.data
      config.dark_mode = value
      axios.put(`${API_URL}/api/config`, config).catch(err => {
        console.error('Error saving dark mode to config:', err)
      })
    }).catch(err => {
      console.error('Error loading config for dark mode update:', err)
    })
  }, [])

  return (
    <DarkModeContext.Provider value={{ darkMode, setDarkMode }}>
      <ThemeProvider theme={darkMode ? darkTheme : lightTheme}>
        <CssBaseline enableColorScheme />
        <div style={{ position: 'relative', zIndex: 1 }}>
          {children}
        </div>
      </ThemeProvider>
    </DarkModeContext.Provider>
  )
}

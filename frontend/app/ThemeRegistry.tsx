'use client'

import { ThemeProvider } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import { useState, useEffect, createContext, useContext } from 'react'
import { lightTheme, darkTheme } from './theme'

const DarkModeContext = createContext<{
  darkMode: boolean
  setDarkMode: (value: boolean) => void
}>({
  darkMode: false,
  setDarkMode: () => {},
})

export const useDarkMode = () => useContext(DarkModeContext)

export default function ThemeRegistry({ children }: { children: React.ReactNode }) {
  const [darkMode, setDarkMode] = useState(false)

  useEffect(() => {
    const savedDarkMode = localStorage.getItem('darkMode')
    if (savedDarkMode !== null) {
      setDarkMode(savedDarkMode === 'true')
    } else {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      setDarkMode(prefersDark)
    }
  }, [])

  useEffect(() => {
    localStorage.setItem('darkMode', darkMode.toString())
  }, [darkMode])

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

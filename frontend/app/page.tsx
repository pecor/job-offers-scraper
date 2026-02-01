'use client'

import { useState, useEffect, useMemo, useCallback, useRef, memo } from 'react'
import {
  Container,
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Box,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControlLabel,
  Checkbox,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Card,
  CardContent,
  Chip,
  Grid,
  CircularProgress,
  Alert,
  Snackbar,
  Badge,
  Tooltip,
} from '@mui/material'
import SettingsIcon from '@mui/icons-material/Settings'
import FilterListIcon from '@mui/icons-material/FilterList'
import FilterAltIcon from '@mui/icons-material/FilterAlt'
import SortIcon from '@mui/icons-material/Sort'
import RefreshIcon from '@mui/icons-material/Refresh'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import OpenInNewIcon from '@mui/icons-material/OpenInNew'
import FileDownloadIcon from '@mui/icons-material/FileDownload'
import FileUploadIcon from '@mui/icons-material/FileUpload'
import HelpOutlineIcon from '@mui/icons-material/HelpOutline'
import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface JobOffer {
  id: number
  url: string
  title: string
  company: string | null
  location: string | null
  description: string | null
  technologies: string | null
  seen: boolean
  salary_min: number | null
  salary_max: number | null
  salary_period: string | null
  work_type: string | null
  contract_type: string | null
  employment_type: string | null
  valid_until: string | null
  source: string
  scraped_at: string
  created_at: string
}

interface Config {
  search_keyword: string
  max_pages: number
  delay: number
  pracuj_pl_domain: string
  excluded_keywords: string[]
  sources: string[]
}

interface OfferCardProps {
  offer: JobOffer
  isSelected: boolean
  onToggle: (id: number) => void
}

interface TechListItemProps {
  tech: string
  isSelected: boolean
  onToggle: (tech: string) => void
}

const TechListItem = memo(({ tech, isSelected, onToggle }: TechListItemProps) => {
  const handleClick = useCallback(() => {
    onToggle(tech)
  }, [tech, onToggle])

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        p: 1,
        cursor: 'pointer',
        '&:hover': { bgcolor: 'action.hover' },
      }}
      onClick={handleClick}
    >
      <Checkbox checked={isSelected} />
      <Typography>{tech}</Typography>
    </Box>
  )
})

TechListItem.displayName = 'TechListItem'

const OfferCard = memo(({ offer, isSelected, onToggle }: OfferCardProps) => {
  const handleClick = useCallback(() => {
    onToggle(offer.id)
  }, [offer.id, onToggle])

  const handleCheckboxChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    e.stopPropagation()
    onToggle(offer.id)
  }, [offer.id, onToggle])

  const handleCheckboxClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
  }, [])

  return (
    <Grid item xs={12}>
      <Card
        sx={{
          cursor: 'pointer',
          backgroundColor: isSelected ? '#e3f2fd' : offer.seen ? '#f5f5f5' : 'white',
          opacity: offer.seen ? 0.85 : 1,
          '&:hover': { boxShadow: 4 },
        }}
        onClick={handleClick}
      >
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'start', gap: 2 }}>
            <Checkbox
              checked={isSelected}
              onChange={handleCheckboxChange}
              onClick={handleCheckboxClick}
            />
            <Box sx={{ flexGrow: 1 }}>
              <Typography variant="h6" component="h2">
                {offer.title}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {offer.company} {offer.location && `• ${offer.location}`}
              </Typography>
              {offer.technologies && (
                <Box sx={{ mt: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {offer.technologies.split(',').slice(0, 10).map((tech, idx) => (
                    <Chip key={idx} label={tech.trim()} size="small" />
                  ))}
                  {offer.technologies.split(',').length > 10 && (
                    <Chip label={`+${offer.technologies.split(',').length - 10} więcej`} size="small" />
                  )}
                </Box>
              )}
              <Box sx={{ mt: 1, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                {offer.salary_min && (
                  <Typography variant="body2" color="success.main">
                    Wynagrodzenie: {offer.salary_min}
                    {offer.salary_max && offer.salary_max !== offer.salary_min && ` - ${offer.salary_max}`}
                    {offer.salary_period && ` /${offer.salary_period}`}
                  </Typography>
                )}
                {offer.work_type && (
                  <Typography variant="body2" color="primary.main">
                    Praca: {offer.work_type}
                  </Typography>
                )}
                {offer.contract_type && (
                  <Typography variant="body2" color="secondary.main">
                    Umowa: {offer.contract_type}
                  </Typography>
                )}
              </Box>
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                Scraped: {new Date(offer.scraped_at).toLocaleDateString('pl-PL')}
                {offer.valid_until && ` • Ważna do: ${new Date(offer.valid_until).toLocaleDateString('pl-PL')}`}
              </Typography>
            </Box>
          </Box>
        </CardContent>
      </Card>
    </Grid>
  )
})

OfferCard.displayName = 'OfferCard'

export default function Home() {
  const [offers, setOffers] = useState<JobOffer[]>([])
  const [selectedOffers, setSelectedOffers] = useState<Set<number>>(new Set())
  const [configDialogOpen, setConfigDialogOpen] = useState(false)
  const [filterDialogOpen, setFilterDialogOpen] = useState(false)
  const [sortDialogOpen, setSortDialogOpen] = useState(false)
  const [exportImportDialogOpen, setExportImportDialogOpen] = useState(false)
  const [exportAll, setExportAll] = useState(false)
  const [loading, setLoading] = useState(false)
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'info' as 'success' | 'error' | 'warning' | 'info' })
  const [config, setConfig] = useState<Config>({
    search_keyword: 'junior',
    max_pages: 5,
    delay: 1.0,
    pracuj_pl_domain: 'it',
    excluded_keywords: [],
    sources: ['pracuj_pl'],
  })
  const [selectedTechnologies, setSelectedTechnologies] = useState<Set<string>>(new Set())
  const [allTechnologies, setAllTechnologies] = useState<string[]>([])
  const [techSearchTerm, setTechSearchTerm] = useState('')
  const [techSearchTermDebounced, setTechSearchTermDebounced] = useState('')
  const [requiredKeywords, setRequiredKeywords] = useState<string>('')
  const [excludedKeywords, setExcludedKeywords] = useState<string>('')
  const [tempSelectedTechnologies, setTempSelectedTechnologies] = useState<Set<string>>(new Set())
  const [tempRequiredKeywords, setTempRequiredKeywords] = useState<string>('')
  const [tempExcludedKeywords, setTempExcludedKeywords] = useState<string>('')
  const [sortBy, setSortBy] = useState('scraped_at')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [showSeen, setShowSeen] = useState(false)
  const observerTarget = useRef<HTMLDivElement>(null)

  const JOB_OFFERS_LIMIT = 100

  useEffect(() => {
    loadConfig()
    loadTechnologies()
  }, [])

  // Debounce tech search term
  useEffect(() => {
    const timer = setTimeout(() => {
      setTechSearchTermDebounced(techSearchTerm)
    }, 300)
    return () => clearTimeout(timer)
  }, [techSearchTerm])

  const filteredTechnologies = useMemo(() => {
    if (!techSearchTermDebounced) {
      return allTechnologies
    }
    const searchLower = techSearchTermDebounced.toLowerCase()
    return allTechnologies.filter(tech => tech.toLowerCase().includes(searchLower))
  }, [allTechnologies, techSearchTermDebounced])

  const [localRequiredKeywords, setLocalRequiredKeywords] = useState('')
  const [localExcludedKeywords, setLocalExcludedKeywords] = useState('')

  useEffect(() => {
    if (filterDialogOpen) {
      setTempSelectedTechnologies(new Set(selectedTechnologies))
      setTempRequiredKeywords(requiredKeywords)
      setTempExcludedKeywords(excludedKeywords)
      setLocalRequiredKeywords(requiredKeywords)
      setLocalExcludedKeywords(excludedKeywords)
    }
  }, [filterDialogOpen, selectedTechnologies, requiredKeywords, excludedKeywords])

  const handleRequiredKeywordsChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setLocalRequiredKeywords(e.target.value)
  }, [])

  const handleExcludedKeywordsChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setLocalExcludedKeywords(e.target.value)
  }, [])

  const handleTechToggle = useCallback((tech: string) => {
    setTempSelectedTechnologies(prev => {
      const newSelected = new Set(prev)
      if (newSelected.has(tech)) {
        newSelected.delete(tech)
      } else {
        newSelected.add(tech)
      }
      return newSelected
    })
  }, [])

  const loadTechnologies = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/technologies`)
      setAllTechnologies(response.data)
    } catch (error) {
      console.error('Error loading technologies:', error)
    }
  }

  const loadConfig = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/config`)
      setConfig(response.data)
    } catch (error) {
      console.error('Error loading config:', error)
      // Keep default config if API fails
    }
  }

  const applyFilters = useCallback((offersList: JobOffer[]) => {
    let filtered = offersList

    // Apply technology filter
    if (selectedTechnologies.size > 0) {
      filtered = filtered.filter((offer: JobOffer) => {
        if (!offer.technologies) return false
        const techs = offer.technologies.split(',').map((t: string) => t.trim().toLowerCase())
        return Array.from(selectedTechnologies).some((selected) =>
          techs.includes(selected.toLowerCase())
        )
      })
    }

    // Apply required keywords filter (only title, company, technologies)
    if (requiredKeywords) {
      const required = requiredKeywords.split(',').map((k) => k.trim().toLowerCase()).filter(Boolean)
      filtered = filtered.filter((offer: JobOffer) => {
        const searchText = `${offer.title || ''} ${offer.company || ''} ${offer.technologies || ''}`.toLowerCase()
        return required.some((kw) => searchText.includes(kw))
      })
    }

    // Apply excluded keywords filter (only title, company, technologies)
    if (excludedKeywords) {
      const excluded = excludedKeywords.split(',').map((k) => k.trim().toLowerCase()).filter(Boolean)
      filtered = filtered.filter((offer: JobOffer) => {
        const searchText = `${offer.title || ''} ${offer.company || ''} ${offer.technologies || ''}`.toLowerCase()
        return !excluded.some((kw) => searchText.includes(kw))
      })
    }

    return filtered
  }, [selectedTechnologies, requiredKeywords, excludedKeywords])

  const showSnackbar = useCallback((message: string, severity: 'success' | 'error' | 'warning' | 'info' = 'info') => {
    setSnackbar({ open: true, message, severity })
  }, [])

  const loadOffers = useCallback(async (reset = false) => {
    if (reset) {
      setOffset(0)
      setHasMore(true)
      setLoading(true)
    } else {
      setLoadingMore(true)
    }

    try {
      const currentOffset = reset ? 0 : offset
      const params: any = {
        limit: JOB_OFFERS_LIMIT,
        offset: currentOffset,
        sort_by: sortBy,
        sort_order: sortOrder,
        show_seen: showSeen,
      }
      
      // Add filter parameters
      if (selectedTechnologies.size > 0) {
        params.selected_technologies = Array.from(selectedTechnologies).join(',')
      }
      if (requiredKeywords) {
        params.required_keywords = requiredKeywords
      }
      if (excludedKeywords) {
        params.excluded_keywords = excludedKeywords
      }
      
      const response = await axios.get(`${API_URL}/api/offers`, {
        params,
        timeout: 10000,
      })
      
      const newOffers = response.data
      
      if (reset) {
        setOffers(newOffers)
        setOffset(newOffers.length)
      } else {
        setOffers(prev => [...prev, ...newOffers])
        setOffset(prev => prev + newOffers.length)
      }

      setHasMore(newOffers.length === JOB_OFFERS_LIMIT)
    } catch (error) {
      console.error('Error loading offers:', error)
      showSnackbar('Błąd podczas ładowania ofert', 'error')
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }, [offset, sortBy, sortOrder, showSeen, selectedTechnologies, requiredKeywords, excludedKeywords, showSnackbar])

  useEffect(() => {
    loadOffers(true)
  }, [sortBy, sortOrder, showSeen, selectedTechnologies, requiredKeywords, excludedKeywords])

  // Infinite scroll observer
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loadingMore && !loading) {
          loadOffers(false)
        }
      },
      { threshold: 0.1 }
    )

    const currentTarget = observerTarget.current
    if (currentTarget) {
      observer.observe(currentTarget)
    }

    return () => {
      if (currentTarget) {
        observer.unobserve(currentTarget)
      }
    }
  }, [hasMore, loadingMore, loading, loadOffers])


  const handleSaveConfig = async () => {
    try {
      await axios.put(`${API_URL}/api/config`, config)
      showSnackbar('Konfiguracja zapisana!', 'success')
      setConfigDialogOpen(false)
    } catch (error) {
      showSnackbar('Błąd podczas zapisywania konfiguracji', 'error')
    }
  }

  const handleRunScraper = async () => {
    try {
      await handleSaveConfig()
      const response = await axios.post(`${API_URL}/api/scrape/start`, config)
      const taskId = response.data.task_id
      showSnackbar('Scraper uruchomiony! To może chwilę potrwać...', 'info')
      setConfigDialogOpen(false)
      
      // Poll for scraping results
      const checkStatus = async () => {
        try {
          const statusResponse = await axios.get(`${API_URL}/api/scrape/status/${taskId}`)
          const status = statusResponse.data
          
          if (status.status === 'completed') {
            // Build result message
            const results = status.results
            const messages: string[] = []
            
            if (results.pracuj_pl !== undefined) {
              messages.push(`Dodano ${results.pracuj_pl} ofert z Pracuj.pl`)
            }
            if (results.justjoin_it !== undefined) {
              messages.push(` i ${results.justjoin_it} ofert z JustJoin.it`)
            }
            
            if (messages.length > 0) {
              showSnackbar(messages.join(''), 'success')
            } else {
              showSnackbar('Scraping zakończony', 'success')
            }
            
            // Refresh offers
            loadOffers(true)
          } else {
            // Still running, check again in 2 seconds
            setTimeout(checkStatus, 2000)
          }
        } catch (error) {
          console.error('Error checking scrape status:', error)
          // If task not found, assume it's done and refresh
          setTimeout(() => {
            loadOffers(true)
          }, 5000)
        }
      }
      
      // Start checking status after 3 seconds
      setTimeout(checkStatus, 3000)
    } catch (error) {
      showSnackbar('Błąd podczas uruchamiania scrapera', 'error')
    }
  }

  const toggleOfferSelection = useCallback((id: number) => {
    setSelectedOffers(prev => {
      const newSelected = new Set(prev)
      if (newSelected.has(id)) {
        newSelected.delete(id)
      } else {
        newSelected.add(id)
      }
      return newSelected
    })
  }, [])

  const selectAll = useCallback(() => {
    setSelectedOffers(new Set(offers.map((o) => o.id)))
  }, [offers])

  const deselectAll = useCallback(() => {
    setSelectedOffers(new Set())
  }, [])

  // Memoize rendered offers to prevent unnecessary re-renders
  const renderedOffers = useMemo(() => 
    offers.map((offer) => (
      <OfferCard
        key={offer.id}
        offer={offer}
        isSelected={selectedOffers.has(offer.id)}
        onToggle={toggleOfferSelection}
      />
    )), [offers, selectedOffers, toggleOfferSelection]
  )

  const openSelected = () => {
    const selected = offers.filter((o) => selectedOffers.has(o.id))
    selected.forEach((offer) => {
      window.open(offer.url, '_blank')
    })
    showSnackbar(`Otwarto ${selected.length} ofert w nowych kartach`, 'info')
  }

  const markSelectedAsSeen = async () => {
    if (selectedOffers.size === 0) {
      showSnackbar('Nie zaznaczono żadnych ofert', 'warning')
      return
    }
    try {
      const offerIds = Array.from(selectedOffers)
      const response = await axios.post(`${API_URL}/api/offers/mark-seen`, {
        offer_ids: offerIds,
      })
      
      setOffers(prevOffers => 
        prevOffers.map(offer => 
          offerIds.includes(offer.id) ? { ...offer, seen: true } : offer
        )
      )
      
      showSnackbar(`Oznaczono ${response.data.updated_count} ofert jako wyświetlone`, 'success')
      setSelectedOffers(new Set())
    } catch (error) {
      console.error('Error marking offers as seen:', error)
      showSnackbar('Błąd podczas oznaczania ofert', 'error')
    }
  }

  const deleteExpired = async () => {
    try {
      const response = await axios.delete(`${API_URL}/api/offers/delete-expired`)
      showSnackbar(`Usunięto ${response.data.deleted_count} wygasłych ofert`, 'success')
      loadOffers(true)
    } catch (error) {
      console.error('Error deleting expired offers:', error)
      showSnackbar('Błąd podczas usuwania wygasłych ofert', 'error')
    }
  }

  const exportOffers = async (format: 'json' | 'csv', exportType: 'selected' | 'filtered' | 'all') => {
    try {
      let params: any = {}
      
      if (exportType === 'selected') {
        // Export selected offers
        if (selectedOffers.size === 0) {
          showSnackbar('Nie zaznaczono żadnych ofert', 'warning')
          return
        }
        params = { offer_ids: Array.from(selectedOffers) }
      } else if (exportType === 'all') {
        // Export all offers
        params = { export_all: true }
      } else {
        // Export filtered offers (current filters)
        params = {
          export_all: false,
          show_seen: showSeen,
          sort_by: sortBy,
          sort_order: sortOrder,
          selected_technologies: selectedTechnologies.size > 0 ? Array.from(selectedTechnologies) : undefined,
          required_keywords: requiredKeywords || undefined,
          excluded_keywords: excludedKeywords || undefined,
        }
      }
      
      const response = await axios.post(`${API_URL}/api/offers/export/${format}`, params, {
        responseType: 'blob',
      })
      
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      const filename = exportType === 'selected' 
        ? `job_offers_selected.${format}`
        : exportType === 'all'
        ? `job_offers_all.${format}`
        : `job_offers_filtered.${format}`
      link.setAttribute('download', filename)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      
      const count = exportType === 'selected' 
        ? selectedOffers.size 
        : exportType === 'all'
        ? 'wszystkie'
        : 'filtrowane'
      showSnackbar(`Eksport zakończony pomyślnie (${count} ofert)`, 'success')
      setExportImportDialogOpen(false)
    } catch (error) {
      console.error('Error exporting offers:', error)
      showSnackbar('Błąd podczas eksportu ofert', 'error')
    }
  }

  const importOffers = async (format: 'json' | 'csv', file: File) => {
    try {
      const formData = new FormData()
      formData.append('file', file)
      
      const response = await axios.post(`${API_URL}/api/offers/import/${format}`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })
      
      showSnackbar(response.data.message, 'success')
      setExportImportDialogOpen(false)
      loadOffers(true)
    } catch (error: any) {
      console.error('Error importing offers:', error)
      const message = error.response?.data?.detail || 'Błąd podczas importu ofert'
      showSnackbar(message, 'error')
    }
  }

  const handleFileImport = (format: 'json' | 'csv') => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = format === 'json' ? '.json' : '.csv'
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0]
      if (file) {
        importOffers(format, file)
      }
    }
    input.click()
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <AppBar position="sticky" sx={{ top: 0, zIndex: 1100 }}>
        <Toolbar>
          <IconButton edge="start" color="inherit" onClick={() => setConfigDialogOpen(true)}>
            <SettingsIcon />
          </IconButton>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1, ml: 2 }}>
            Job Offers Scraper
          </Typography>
        </Toolbar>
      </AppBar>

      <Box sx={{ position: 'sticky', top: 64, zIndex: 1000, bgcolor: 'background.paper', borderBottom: 1, borderColor: 'divider', py: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center'}}>
              <Typography variant="body2" color="text.secondary">
                wybrane: {selectedOffers.size}/{offers.length}
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button onClick={selectAll} size="small">Zaznacz wszystkie</Button>
              <Button onClick={deselectAll} size="small">Odznacz wszystkie</Button>
            </Box>
            <Box sx={{ display: 'flex', gap: 1 }}>
            <Badge badgeContent={selectedTechnologies.size + (requiredKeywords + excludedKeywords).split(',').filter(Boolean).length} color="secondary">
              <Button
                variant="contained"
                color="secondary"
                startIcon={<FilterListIcon />}
                onClick={() => setFilterDialogOpen(true)}
              >
                Filtry
              </Button>
            </Badge>
            <Button
              variant="contained"
              startIcon={<SortIcon />}
              onClick={() => setSortDialogOpen(true)}
            >
              Sortuj
            </Button>
            <Button variant="outlined" startIcon={<RefreshIcon />} onClick={() => loadOffers(true)}>
              Odśwież
            </Button>
            <Button
              variant="contained"
              color="success"
              startIcon={<OpenInNewIcon />}
              onClick={openSelected}
              disabled={selectedOffers.size === 0}
            >
              Otwórz
            </Button>
            <Button
              variant="outlined"
              color="secondary"
              onClick={markSelectedAsSeen}
              disabled={selectedOffers.size === 0}
            >
              Wyświetlone
            </Button>
            <Button
              variant="outlined"
              startIcon={<FileDownloadIcon />}
              onClick={() => setExportImportDialogOpen(true)}
            >
              Eksport/Import
            </Button>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center'}}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={showSeen}
                  onChange={(e) => setShowSeen(e.target.checked)}
                />
              }
              label="Pokaż wszystkie ogłoszenia"
            />
          </Box>
        </Box>
      </Box>

      <Container maxWidth="lg" sx={{ mt: 4, mb: 4, flex: 1 }}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <CircularProgress />
          </Box>
        ) : (
          <Grid container spacing={2} sx={{ justifyContent: 'center' }}>
            {renderedOffers}
          </Grid>
        )}

        {offers.length === 0 && !loading && (
          <Box sx={{ textAlign: 'center', p: 4 }}>
            <Typography variant="body1" color="text.secondary">
              Brak ofert
            </Typography>
          </Box>
        )}

        {/* Infinite scroll trigger */}
        {hasMore && !loading && (
          <Box ref={observerTarget} sx={{ minHeight: 60, mt: 4, mb: 4 }}>
            {loadingMore && (
              <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', py: 4 }}>
                <CircularProgress size={48} thickness={4} />
              </Box>
            )}
          </Box>
        )}
      </Container>

      <Box 
        component="footer" 
        sx={{ 
          bgcolor: 'grey.100', 
          py: 1.5, 
          mt: 'auto',
          position: 'sticky',
          bottom: 0,
          zIndex: 100,
          textAlign: 'center',
          borderTop: 1,
          borderColor: 'divider'
        }}
      >
        <Container maxWidth="xl">
          <Typography variant="body2" color="text.secondary">
            Created by{' '}
            <a href="https://github.com/pecor" target="_blank" rel="noopener noreferrer" style={{ color: '#1976d2', textDecoration: 'none' }}>
              pecor
            </a>
            {' • '}
            <a href="https://github.com/pecor/job-offers-scraper" target="_blank" rel="noopener noreferrer" style={{ color: '#1976d2', textDecoration: 'none' }}>
              GitHub Repository
            </a>
          </Typography>
        </Container>
      </Box>

      {/* Config Dialog */}
      <Dialog open={configDialogOpen} onClose={() => setConfigDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Konfiguracja scrapera</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Słowo kluczowe"
            value={config.search_keyword}
            onChange={(e) => setConfig({ ...config, search_keyword: e.target.value })}
            margin="normal"
          />
          <TextField
            fullWidth
            label="Maksymalna liczba stron"
            type="number"
            value={config.max_pages}
            onChange={(e) => setConfig({ ...config, max_pages: parseInt(e.target.value) || 5 })}
            margin="normal"
          />
          <TextField
            fullWidth
            label="Opóźnienie (sekundy)"
            type="number"
            value={config.delay}
            onChange={(e) => setConfig({ ...config, delay: parseFloat(e.target.value) || 1.0 })}
            margin="normal"
            inputProps={{ step: 0.1 }}
          />
          <FormControl fullWidth margin="normal">
            <InputLabel>Domena Pracuj.pl</InputLabel>
            <Select
              value={config.pracuj_pl_domain}
              onChange={(e) => setConfig({ ...config, pracuj_pl_domain: e.target.value })}
              label="Domena Pracuj.pl"
            >
              <MenuItem value="it">IT (it.pracuj.pl)</MenuItem>
              <MenuItem value="www">Wszystkie (www.pracuj.pl)</MenuItem>
            </Select>
          </FormControl>
          <TextField
            fullWidth
            label="Wykluczone słowa kluczowe (jedno na linię)"
            multiline
            rows={4}
            value={config.excluded_keywords.join('\n')}
            onChange={(e) => setConfig({ ...config, excluded_keywords: e.target.value.split('\n').filter(Boolean) })}
            margin="normal"
          />
          <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle2">Źródła:</Typography>
            <FormControlLabel
              control={
                <Checkbox
                  checked={config.sources.includes('pracuj_pl')}
                  onChange={(e) => {
                    const sources = e.target.checked
                      ? [...config.sources, 'pracuj_pl']
                      : config.sources.filter((s) => s !== 'pracuj_pl')
                    setConfig({ ...config, sources })
                  }}
                />
              }
              label="Pracuj.pl"
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={config.sources.includes('justjoin_it')}
                  onChange={(e) => {
                    const sources = e.target.checked
                      ? [...config.sources, 'justjoin_it']
                      : config.sources.filter((s) => s !== 'justjoin_it')
                    setConfig({ ...config, sources })
                  }}
                />
              }
              label="JustJoin.it"
            />
          </Box>
          <Box sx={{ mt: 3, pt: 2, borderTop: 1, borderColor: 'divider' }}>
            <Typography variant="subtitle2" sx={{ mb: 2 }}>Zarządzanie ofertami:</Typography>
            <Button
              variant="outlined"
              color="error"
              onClick={deleteExpired}
              fullWidth
            >
              Usuń wygasłe oferty
            </Button>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfigDialogOpen(false)}>Anuluj</Button>
          <Button onClick={handleSaveConfig} variant="contained">
            Zapisz
          </Button>
          <Button onClick={handleRunScraper} variant="contained" color="success" startIcon={<PlayArrowIcon />}>
            Uruchom scraper
          </Button>
        </DialogActions>
      </Dialog>

      {/* Unified Filter Dialog */}
      <Dialog 
        open={filterDialogOpen} 
        onClose={() => {
          setTempSelectedTechnologies(new Set(selectedTechnologies))
          setLocalRequiredKeywords(requiredKeywords)
          setLocalExcludedKeywords(excludedKeywords)
          setFilterDialogOpen(false)
        }} 
        maxWidth="md" 
        fullWidth
      >
        <DialogTitle>Filtry</DialogTitle>
        <DialogContent>
          {/* Technologies Filter */}
          <Box sx={{ mb: 4 }}>
            <Typography variant="h6" sx={{ mb: 1 }}>Technologie</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Wybierz technologie, które mają być w ofercie
            </Typography>
            <TextField
              fullWidth
              placeholder="Szukaj technologii..."
              margin="normal"
              value={techSearchTerm}
              onChange={(e) => setTechSearchTerm(e.target.value)}
            />
            <Box sx={{ mt: 2, maxHeight: 300, overflow: 'auto' }}>
              {allTechnologies.length === 0 ? (
                <Typography variant="body2" color="text.secondary" sx={{ p: 2, textAlign: 'center' }}>
                  Brak technologii. Najpierw uruchom scraper, aby załadować oferty.
                </Typography>
              ) : (
                filteredTechnologies.map((tech) => (
                  <TechListItem
                    key={tech}
                    tech={tech}
                    isSelected={tempSelectedTechnologies.has(tech)}
                    onToggle={handleTechToggle}
                  />
                ))
              )}
            </Box>
            <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
              <Button
                size="small"
                onClick={() => {
                  const newSelected = new Set(tempSelectedTechnologies)
                  filteredTechnologies.forEach((tech) => newSelected.add(tech))
                  setTempSelectedTechnologies(newSelected)
                }}
              >
                Zaznacz widoczne
              </Button>
              <Button
                size="small"
                onClick={() => {
                  const newSelected = new Set(tempSelectedTechnologies)
                  filteredTechnologies.forEach((tech) => newSelected.delete(tech))
                  setTempSelectedTechnologies(newSelected)
                }}
              >
                Odznacz widoczne
              </Button>
            </Box>
          </Box>

          {/* Keywords Filter */}
          <Box sx={{ pt: 2, borderTop: 1, borderColor: 'divider' }}>
            <Typography variant="h6" sx={{ mb: 1 }}>Słowa kluczowe</Typography>
            <TextField
              fullWidth
              label="Wymagane słowa kluczowe (oddzielone przecinkami)"
              multiline
              rows={3}
              value={localRequiredKeywords}
              onChange={handleRequiredKeywordsChange}
              margin="normal"
              helperText="Oferty muszą zawierać przynajmniej jedno z tych słów"
            />
            <TextField
              fullWidth
              label="Wykluczone słowa kluczowe (oddzielone przecinkami)"
              multiline
              rows={3}
              value={localExcludedKeywords}
              onChange={handleExcludedKeywordsChange}
              margin="normal"
              helperText="Oferty zawierające którekolwiek z tych słów będą wykluczone"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setTempSelectedTechnologies(new Set())
              setLocalRequiredKeywords('')
              setLocalExcludedKeywords('')
            }}
          >
            Wyczyść wszystko
          </Button>
          <Button 
            onClick={() => {
              setTempSelectedTechnologies(new Set(selectedTechnologies))
              setLocalRequiredKeywords(requiredKeywords)
              setLocalExcludedKeywords(excludedKeywords)
              setFilterDialogOpen(false)
            }}
          >
            Anuluj
          </Button>
          <Button 
            onClick={() => { 
              setSelectedTechnologies(new Set(tempSelectedTechnologies))
              setRequiredKeywords(localRequiredKeywords)
              setExcludedKeywords(localExcludedKeywords)
              setFilterDialogOpen(false)
              loadOffers(true)
            }} 
            variant="contained"
          >
            Zastosuj
          </Button>
        </DialogActions>
      </Dialog>

      {/* Export/Import Dialog */}
      <Dialog open={exportImportDialogOpen} onClose={() => setExportImportDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogContent>
          <Box sx={{ mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <Typography variant="h6">Eksport</Typography>
              <Tooltip
                title={
                  <Box>
                    <Typography variant="body2" sx={{ mb: 1, fontWeight: 'bold' }}>Logika eksportu:</Typography>
                    <Typography variant="body2">• Jeśli zaznaczono oferty → eksportuje zaznaczone</Typography>
                    <Typography variant="body2">• Jeśli zaznaczono "Wszystkie" → eksportuje wszystkie z bazy</Typography>
                    <Typography variant="body2">• W przeciwnym razie → eksportuje wszystkie pasujące do filtrów (nie tylko załadowane)</Typography>
                  </Box>
                }
                arrow
                placement="right"
              >
                <IconButton size="small" sx={{ color: 'text.secondary' }}>
                  <HelpOutlineIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
            
            <FormControlLabel
              control={
                <Checkbox
                  checked={exportAll}
                  onChange={(e) => setExportAll(e.target.checked)}
                />
              }
              label="Wszystkie oferty z bazy danych"
              sx={{ mb: 2 }}
            />
            
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                {exportAll 
                  ? 'Eksportuj wszystkie oferty z bazy danych (ignoruje filtry)'
                  : selectedOffers.size > 0
                  ? `Eksportuj zaznaczone oferty (${selectedOffers.size}) lub pasujące do filtrów`
                  : 'Eksportuj oferty pasujące do aktualnych filtrów'}
              </Typography>
            </Box>
            
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Button
                variant="outlined"
                startIcon={<FileDownloadIcon />}
                onClick={() => exportOffers('json', exportAll ? 'all' : selectedOffers.size > 0 ? 'selected' : 'filtered')}
                fullWidth
                disabled={!exportAll && selectedOffers.size === 0 && offers.length === 0}
              >
                Eksportuj JSON
              </Button>
              <Button
                variant="outlined"
                startIcon={<FileDownloadIcon />}
                onClick={() => exportOffers('csv', exportAll ? 'all' : selectedOffers.size > 0 ? 'selected' : 'filtered')}
                fullWidth
                disabled={!exportAll && selectedOffers.size === 0 && offers.length === 0}
              >
                Eksportuj CSV
              </Button>
            </Box>
            
            {selectedOffers.size > 0 && !exportAll && (
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                Zaznaczono {selectedOffers.size} ofert - zostaną wyeksportowane zaznaczone oferty
              </Typography>
            )}
            
            {selectedOffers.size > 0 && !exportAll && (
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                Zaznaczono {selectedOffers.size} ofert - zostaną wyeksportowane zaznaczone oferty
              </Typography>
            )}
          </Box>
          
          <Box sx={{ pt: 2, borderTop: 1, borderColor: 'divider' }}>
            <Typography variant="h6" sx={{ mb: 2 }}>Import</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Zaimportuj oferty z pliku (duplikaty zostaną pominięte)
            </Typography>
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Button
                variant="outlined"
                startIcon={<FileUploadIcon />}
                onClick={() => handleFileImport('json')}
                fullWidth
              >
                Importuj JSON
              </Button>
              <Button
                variant="outlined"
                startIcon={<FileUploadIcon />}
                onClick={() => handleFileImport('csv')}
                fullWidth
              >
                Importuj CSV
              </Button>
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setExportImportDialogOpen(false)}>Zamknij</Button>
        </DialogActions>
      </Dialog>

      {/* Sort Dialog */}
      <Dialog open={sortDialogOpen} onClose={() => setSortDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Sortuj</DialogTitle>
        <DialogContent>
          <FormControl fullWidth margin="normal">
            <InputLabel>Sortuj według</InputLabel>
            <Select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              label="Sortuj według"
            >
              <MenuItem value="scraped_at">Data scrapowania</MenuItem>
              <MenuItem value="valid_until">Ważna do</MenuItem>
              <MenuItem value="title">Tytuł</MenuItem>
              <MenuItem value="company">Firma</MenuItem>
            </Select>
          </FormControl>
          <FormControl fullWidth margin="normal">
            <InputLabel>Kolejność</InputLabel>
            <Select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value as 'asc' | 'desc')}
              label="Kolejność"
            >
              <MenuItem value="desc">Malejąco</MenuItem>
              <MenuItem value="asc">Rosnąco</MenuItem>
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSortDialogOpen(false)}>Anuluj</Button>
          <Button onClick={() => { setSortDialogOpen(false); loadOffers() }} variant="contained">
            Zastosuj
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        <Alert onClose={() => setSnackbar({ ...snackbar, open: false })} severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  )
}

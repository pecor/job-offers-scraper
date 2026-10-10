'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography,
  CircularProgress,
  Alert,
  Divider,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  IconButton,
  Chip,
} from '@mui/material'
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import UploadFileIcon from '@mui/icons-material/UploadFile'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import SaveIcon from '@mui/icons-material/Save'
import VisibilityIcon from '@mui/icons-material/Visibility'
import HistoryIcon from '@mui/icons-material/History'
import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const CV_STORAGE_KEY = 'job-scraper-cv-text'
const INSTRUCTIONS_STORAGE_KEY = 'job-scraper-ai-instructions'
const MANUAL_CV = 'manual'

interface AiDialogProps {
  open: boolean
  offer: {
    id: number
    title: string
    company: string | null
  } | null
  onClose: () => void
  onSnackbar: (message: string, severity?: 'success' | 'error' | 'warning' | 'info') => void
}

interface AiConfig {
  configured: boolean
  model: string
  base_url: string
}

interface CvDocument {
  id: number
  filename: string
  extraction_method: string | null
  text_length: number
  created_at: string | null
}

interface GenerateResult {
  id: number
  message: string
  model: string
  prompt_tokens: number | null
  completion_tokens: number | null
}

interface StoredMessage {
  id: number
  model: string
  message: string
  prompt_tokens: number | null
  completion_tokens: number | null
  created_at: string | null
}

const methodLabel = (method: string | null): string => {
  switch (method) {
    case 'pdf-text':
      return 'PDF (warstwa tekstu)'
    case 'ocr':
      return 'PDF (OCR)'
    case 'plain':
      return 'plik tekstowy'
    default:
      return method || ''
  }
}

export default function AiDialog({ open, offer, onClose, onSnackbar }: AiDialogProps) {
  const [manualCvText, setManualCvText] = useState('')
  const [instructions, setInstructions] = useState('')
  const [aiConfig, setAiConfig] = useState<AiConfig | null>(null)
  const [cvDocs, setCvDocs] = useState<CvDocument[]>([])
  const [selectedCvId, setSelectedCvId] = useState<number | 'manual'>('manual')
  const [uploading, setUploading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [result, setResult] = useState<GenerateResult | null>(null)
  const [cvFullText, setCvFullText] = useState('')
  const [cvEditorOpen, setCvEditorOpen] = useState(false)
  const [cvDirty, setCvDirty] = useState(false)
  const [savingCv, setSavingCv] = useState(false)
  const [systemPrompt, setSystemPrompt] = useState('')
  const [defaultSystemPrompt, setDefaultSystemPrompt] = useState('')
  const [promptSectionOpen, setPromptSectionOpen] = useState(false)
  const [userPromptPreview, setUserPromptPreview] = useState<string | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [history, setHistory] = useState<StoredMessage[]>([])
  const [historyOpen, setHistoryOpen] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const loadCvList = useCallback(async () => {
    try {
      const response = await axios.get<CvDocument[]>(`${API_URL}/api/cv`)
      setCvDocs(response.data)
      return response.data
    } catch {
      return []
    }
  }, [])

  const loadHistory = useCallback(async (offerId: number) => {
    try {
      const response = await axios.get<StoredMessage[]>(`${API_URL}/api/ai/messages/${offerId}`)
      setHistory(response.data)
    } catch {
      setHistory([])
    }
  }, [])

  useEffect(() => {
    if (open) {
      setManualCvText(localStorage.getItem(CV_STORAGE_KEY) || '')
      setInstructions(localStorage.getItem(INSTRUCTIONS_STORAGE_KEY) || '')
      setResult(null)
      setUserPromptPreview(null)
      axios
        .get<{ system_prompt: string }>(`${API_URL}/api/ai/prompt`)
        .then((res) => {
          setDefaultSystemPrompt(res.data.system_prompt)
          setSystemPrompt(res.data.system_prompt)
        })
        .catch(() => {})
      if (offer) loadHistory(offer.id)
      loadCvList().then((docs) => {
        // Preselect saved CV when one exists; otherwise manual paste
        if (docs.length > 0) setSelectedCvId(docs[0].id)
        else setSelectedCvId('manual')
      })
      axios
        .get<AiConfig>(`${API_URL}/api/ai/config`)
        .then((res) => setAiConfig(res.data))
        .catch(() => setAiConfig(null))
    }
  }, [open, loadCvList, loadHistory, offer])

  const hasCv = selectedCvId !== 'manual' || manualCvText.trim().length > 0

  const handleUpload = useCallback(
    async (file: File) => {
      setUploading(true)
      try {
        const formData = new FormData()
        formData.append('file', file)
        const response = await axios.post(`${API_URL}/api/cv/upload`, formData)
        onSnackbar(
          `CV wgrane (${methodLabel(response.data.extraction_method)}, ${response.data.text_length} znaków)`,
          'success'
        )
        const docs = await loadCvList()
        if (docs.length > 0) setSelectedCvId(response.data.id)
      } catch (error: unknown) {
        const detail =
          (axios.isAxiosError(error) && error.response?.data?.detail) || 'Nieznany błąd'
        onSnackbar(`Błąd wgrywania CV: ${detail}`, 'error')
      } finally {
        setUploading(false)
        if (fileInputRef.current) fileInputRef.current.value = ''
      }
    },
    [loadCvList, onSnackbar]
  )

  const handleDeleteCv = useCallback(async () => {
    if (selectedCvId === 'manual') return
    try {
      await axios.delete(`${API_URL}/api/cv/${selectedCvId}`)
      onSnackbar('CV usunięte', 'info')
      const docs = await loadCvList()
      setSelectedCvId(docs.length > 0 ? docs[0].id : 'manual')
    } catch {
      onSnackbar('Błąd podczas usuwania CV', 'error')
    }
  }, [selectedCvId, loadCvList, onSnackbar])

  useEffect(() => {
    if (selectedCvId === 'manual') {
      setCvFullText('')
      setCvEditorOpen(false)
      setCvDirty(false)
      return
    }
    // Load full text of the selected CV
    let cancelled = false
    axios
      .get<{ id: number; text_content: string }>(`${API_URL}/api/cv/${selectedCvId}`)
      .then((res) => {
        if (!cancelled) {
          setCvFullText(res.data.text_content)
          setCvDirty(false)
        }
      })
      .catch(() => {
        if (!cancelled) setCvFullText('')
      })
    return () => {
      cancelled = true
    }
  }, [selectedCvId])

  const handleSaveCv = useCallback(async () => {
    if (selectedCvId === 'manual' || !cvDirty) return
    setSavingCv(true)
    try {
      await axios.put(`${API_URL}/api/cv/${selectedCvId}`, { text_content: cvFullText })
      onSnackbar('Zapisano zmiany w CV', 'success')
      setCvDirty(false)
      await loadCvList()
    } catch (error: unknown) {
      const detail =
        (axios.isAxiosError(error) && error.response?.data?.detail) || 'Nieznany błąd'
      onSnackbar(`Błąd zapisu CV: ${detail}`, 'error')
    } finally {
      setSavingCv(false)
    }
  }, [selectedCvId, cvDirty, cvFullText, loadCvList, onSnackbar])

  const handlePreviewPrompt = useCallback(async () => {
    if (!offer || !hasCv) return
    setPreviewLoading(true)
    setUserPromptPreview(null)
    try {
      const payload: Record<string, unknown> = { offer_id: offer.id, instructions }
      if (selectedCvId === 'manual') payload.cv_text = manualCvText
      else payload.cv_id = selectedCvId
      const response = await axios.post<{ user_prompt: string; approx_chars: number }>(
        `${API_URL}/api/ai/preview`,
        payload
      )
      setUserPromptPreview(response.data.user_prompt)
    } catch (error: unknown) {
      const detail =
        (axios.isAxiosError(error) && error.response?.data?.detail) || 'Nieznany błąd'
      onSnackbar(`Błąd podglądu prompta: ${detail}`, 'error')
    } finally {
      setPreviewLoading(false)
    }
  }, [offer, hasCv, selectedCvId, manualCvText, instructions, onSnackbar])

  const handleDeleteMessage = useCallback(
    async (messageId: number) => {
      try {
        await axios.delete(`${API_URL}/api/ai/messages/${messageId}`)
        if (offer) loadHistory(offer.id)
        onSnackbar('Wiadomość usunięta', 'info')
      } catch {
        onSnackbar('Błąd podczas usuwania wiadomości', 'error')
      }
    },
    [offer, loadHistory, onSnackbar]
  )

  const handleGenerate = useCallback(async () => {
    if (!offer || !hasCv) return
    localStorage.setItem(CV_STORAGE_KEY, manualCvText)
    localStorage.setItem(INSTRUCTIONS_STORAGE_KEY, instructions)
    setGenerating(true)
    setResult(null)
    try {
      const payload: Record<string, unknown> = {
        offer_id: offer.id,
        instructions,
        system_prompt: systemPrompt,
      }
      if (selectedCvId === 'manual') payload.cv_text = manualCvText
      else payload.cv_id = selectedCvId

      const response = await axios.post<GenerateResult>(`${API_URL}/api/ai/generate`, payload)
      setResult(response.data)
      loadHistory(offer.id)
    } catch (error: unknown) {
      const detail =
        (axios.isAxiosError(error) && error.response?.data?.detail) || 'Nieznany błąd generowania'
      onSnackbar(`Błąd generowania: ${detail}`, 'error')
    } finally {
      setGenerating(false)
    }
  }, [offer, hasCv, selectedCvId, manualCvText, instructions, systemPrompt, loadHistory, onSnackbar])

  const handleCopy = useCallback(() => {
    if (!result) return
    navigator.clipboard.writeText(result.message)
    onSnackbar('Skopiowano do schowka', 'success')
  }, [result, onSnackbar])

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <AutoAwesomeIcon color="primary" />
        Wiadomość aplikacyjna (AI)
      </DialogTitle>
      <DialogContent>
        {offer && (
          <Typography variant="subtitle1" sx={{ mt: 1 }}>
            {offer.title}
            {offer.company && ` • ${offer.company}`}
          </Typography>
        )}

        {aiConfig && !aiConfig.configured && (
          <Alert severity="warning" sx={{ mt: 2 }}>
            Brak klucza API. Ustaw <code>LLM_API_KEY</code> w pliku <code>.env</code> i zrestartuj
            backend.
          </Alert>
        )}

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 2, flexWrap: 'wrap' }}>
          <FormControl sx={{ minWidth: 240, flexGrow: 1 }} size="small">
            <InputLabel>CV</InputLabel>
            <Select
              value={selectedCvId}
              label="CV"
              onChange={(e) => setSelectedCvId(e.target.value as number | 'manual')}
            >
              {cvDocs.map((doc) => (
                <MenuItem key={doc.id} value={doc.id}>
                  {doc.filename} ({methodLabel(doc.extraction_method)}, {doc.text_length} znaków)
                </MenuItem>
              ))}
              <MenuItem value="manual">Wklej ręcznie…</MenuItem>
            </Select>
          </FormControl>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt"
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) handleUpload(file)
            }}
          />
          <Button
            variant="outlined"
            startIcon={
              uploading ? <CircularProgress size={16} color="inherit" /> : <UploadFileIcon />
            }
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? 'Przetwarzanie…' : 'Wgraj PDF/TXT'}
          </Button>
          <IconButton
            onClick={handleDeleteCv}
            disabled={selectedCvId === 'manual'}
            title="Usuń wybrane CV"
            size="small"
          >
            <DeleteOutlineIcon />
          </IconButton>
        </Box>

        {selectedCvId === 'manual' && (
          <TextField
            fullWidth
            label="Twoje CV (wklej treść)"
            multiline
            rows={8}
            margin="normal"
            value={manualCvText}
            onChange={(e) => setManualCvText(e.target.value)}
            helperText="Treść zostanie zapisana lokalnie (przeglądarka) — nie musisz wklejać za każdym razem."
          />
        )}

        {selectedCvId !== 'manual' && (
          <Box sx={{ mt: 1 }}>
            <Button
              size="small"
              onClick={() => setCvEditorOpen(!cvEditorOpen)}
              startIcon={
                <ExpandMoreIcon
                  sx={{ transform: cvEditorOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}
                />
              }
            >
              {cvEditorOpen ? 'Ukryj tekst CV' : 'Podgląd / edycja tekstu CV'}
            </Button>
            {cvEditorOpen && (
              <Box sx={{ mt: 1 }}>
                <TextField
                  fullWidth
                  multiline
                  rows={10}
                  value={cvFullText}
                  onChange={(e) => {
                    setCvFullText(e.target.value)
                    setCvDirty(true)
                  }}
                  helperText={`${cvFullText.length} znaków${cvDirty ? ' • niezapisane zmiany' : ''}`}
                />
                <Box sx={{ mt: 1, display: 'flex', gap: 1, alignItems: 'center' }}>
                  <Button
                    size="small"
                    variant="contained"
                    startIcon={
                      savingCv ? <CircularProgress size={14} color="inherit" /> : <SaveIcon />
                    }
                    onClick={handleSaveCv}
                    disabled={!cvDirty || savingCv}
                  >
                    Zapisz zmiany
                  </Button>
                  <Chip size="small" variant="outlined" label={methodLabel(
                    cvDocs.find((d) => d.id === selectedCvId)?.extraction_method ?? null
                  )} />
                </Box>
              </Box>
            )}
          </Box>
        )}

        <TextField
          fullWidth
          label="Dodatkowe wytyczne (opcjonalnie)"
          multiline
          rows={2}
          margin="normal"
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
          helperText="Np. podkreśl doświadczenie w Pythonie, ton swobodny, wspomnij o relokacji."
        />

        {/* Prompt section: system prompt editor + user prompt preview */}
        <Box sx={{ mt: 1 }}>
          <Button
            size="small"
            onClick={() => setPromptSectionOpen(!promptSectionOpen)}
            startIcon={
              <ExpandMoreIcon
                sx={{ transform: promptSectionOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}
              />
            }
          >
            Prompt systemowy i podgląd
          </Button>
          {promptSectionOpen && (
            <Box sx={{ mt: 1 }}>
              <TextField
                fullWidth
                multiline
                rows={5}
                label="Prompt systemowy"
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                helperText={
                  systemPrompt === defaultSystemPrompt
                    ? 'Domyślny prompt (bez zmian)'
                    : 'Zmodyfikowany — ta wersja zostanie użyta do generowania'
                }
              />
              <Box sx={{ mt: 1, display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                <Button
                  size="small"
                  onClick={() => setSystemPrompt(defaultSystemPrompt)}
                  disabled={systemPrompt === defaultSystemPrompt}
                >
                  Przywróć domyślny
                </Button>
                <Button
                  size="small"
                  startIcon={
                    previewLoading ? <CircularProgress size={14} color="inherit" /> : <VisibilityIcon />
                  }
                  onClick={handlePreviewPrompt}
                  disabled={previewLoading || !hasCv}
                >
                  {previewLoading ? 'Budowanie…' : 'Podejrzyj prompt (CV + oferta)'}
                </Button>
              </Box>
              {userPromptPreview && (
                <Box
                  sx={{
                    mt: 1,
                    p: 1.5,
                    borderRadius: 1,
                    maxHeight: 250,
                    overflow: 'auto',
                    fontFamily: 'monospace',
                    fontSize: '0.75rem',
                    whiteSpace: 'pre-wrap',
                    bgcolor: (theme) =>
                      theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)',
                  }}
                >
                  {userPromptPreview}
                </Box>
              )}
            </Box>
          )}
        </Box>

        {/* Generation history for this offer */}
        {offer && history.length > 0 && (
          <Box sx={{ mt: 1 }}>
            <Button
              size="small"
              onClick={() => setHistoryOpen(!historyOpen)}
              startIcon={
                <ExpandMoreIcon
                  sx={{ transform: historyOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}
                />
              }
            >
              Historia ({history.length})
            </Button>
            {historyOpen && (
              <Box sx={{ mt: 1 }}>
                {history.map((m) => (
                  <Box
                    key={m.id}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      py: 0.5,
                      borderBottom: 1,
                      borderColor: 'divider',
                    }}
                  >
                    <Button
                      size="small"
                      sx={{ justifyContent: 'flex-start', flexGrow: 1, textTransform: 'none' }}
                      onClick={() =>
                        setResult({
                          id: m.id,
                          message: m.message,
                          model: m.model,
                          prompt_tokens: m.prompt_tokens,
                          completion_tokens: m.completion_tokens,
                        })
                      }
                    >
                      <HistoryIcon fontSize="small" sx={{ mr: 1 }} />
                      {m.created_at ? new Date(m.created_at).toLocaleString('pl-PL') : ''} •{' '}
                      {m.model}
                      {m.prompt_tokens != null && ` (${m.prompt_tokens}+${m.completion_tokens})`}
                      {' — '}
                      {m.message.slice(0, 60)}…
                    </Button>
                    <IconButton size="small" onClick={() => handleDeleteMessage(m.id)}>
                      <DeleteOutlineIcon fontSize="small" />
                    </IconButton>
                  </Box>
                ))}
              </Box>
            )}
          </Box>
        )}

        {result && (
          <Box sx={{ mt: 3 }}>
            <Divider sx={{ mb: 2 }} />
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                mb: 1,
                flexWrap: 'wrap',
                gap: 1,
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="subtitle2" color="text.secondary">
                  Model: {result.model}
                </Typography>
                {result.prompt_tokens != null && (
                  <Chip
                    size="small"
                    label={`tokeny: ${result.prompt_tokens} + ${result.completion_tokens}`}
                    variant="outlined"
                  />
                )}
              </Box>
              <Button size="small" startIcon={<ContentCopyIcon />} onClick={handleCopy}>
                Kopiuj
              </Button>
            </Box>
            <Box
              sx={{
                whiteSpace: 'pre-wrap',
                p: 2,
                borderRadius: 1,
                bgcolor: (theme) =>
                  theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)',
                maxHeight: 400,
                overflow: 'auto',
              }}
            >
              <Typography variant="body2">{result.message}</Typography>
            </Box>
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Zamknij</Button>
        <Button
          variant="contained"
          color="primary"
          startIcon={generating ? <CircularProgress size={16} color="inherit" /> : <AutoAwesomeIcon />}
          onClick={handleGenerate}
          disabled={generating || !hasCv || !offer || (aiConfig !== null && !aiConfig.configured)}
        >
          {generating ? 'Generowanie...' : 'Generuj wiadomość'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

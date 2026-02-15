'use client'

import React, { useState, useRef, useEffect, useCallback } from 'react'
import {
  Play,
  Pause,
  X,
  SkipBack,
  SkipForward,
  Volume2,
  VolumeX,
  Loader2,
  PlayCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/** Tab sections that match the walkthrough script order */
const WALKTHROUGH_SECTIONS = [
  { id: 'intro', label: 'Introduction', icon: '👋', color: 'text-slate-500' },
  { id: 'the_brief', label: 'The Brief', icon: '📊', color: 'text-emerald-500' },
  { id: 'discovery', label: 'Discovery', icon: '🧭', color: 'text-teal-500' },
  { id: 'deep_research', label: 'Deep Research', icon: '🔍', color: 'text-emerald-500' },
  { id: 'core_industries', label: 'Core Industries', icon: '🏭', color: 'text-emerald-500' },
  { id: 'supply_network', label: 'Supply Network', icon: '🚢', color: 'text-indigo-500' },
  { id: 'architecture_evals', label: 'Architecture & AI Quality', icon: '🏗️', color: 'text-sky-500' },
  { id: 'tracked_entities', label: 'Tracked Entities', icon: '⚙️', color: 'text-cyan-500' },
  { id: 'closing', label: 'Wrap Up', icon: '✅', color: 'text-slate-500' },
]

interface WalkthroughModalProps {
  isOpen: boolean
  onClose: () => void
}

export default function WalkthroughModal({ isOpen, onClose }: WalkthroughModalProps) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)

  // Audio state
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolume] = useState(1)
  const [isMuted, setIsMuted] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Walkthrough state
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [generationStatus, setGenerationStatus] = useState<string>('')

  // Estimated section boundaries (evenly divided for now)
  const sectionCount = WALKTHROUGH_SECTIONS.length
  const getSectionProgress = (index: number) => {
    if (duration <= 0) return 0
    const sectionDuration = duration / sectionCount
    const sectionStart = index * sectionDuration
    if (currentTime < sectionStart) return 0
    if (currentTime >= sectionStart + sectionDuration) return 100
    return ((currentTime - sectionStart) / sectionDuration) * 100
  }

  const getCurrentSectionIndex = () => {
    if (duration <= 0) return 0
    const sectionDuration = duration / sectionCount
    return Math.min(Math.floor(currentTime / sectionDuration), sectionCount - 1)
  }

  // Check walkthrough availability on open
  useEffect(() => {
    if (!isOpen) return

    const checkStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/walkthrough/status`)
        if (res.ok) {
          const data = await res.json()
          if (data.available && data.audio_url) {
            setAudioUrl(`${API_BASE}${data.audio_url}`)
          }
        }
      } catch {
        // Silent failure — user can generate manually
      }
    }

    checkStatus()
  }, [isOpen])

  // Handle escape key and body scroll lock
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }

    if (isOpen) {
      document.addEventListener('keydown', handleEscape)
      document.body.style.overflow = 'hidden'
    }

    return () => {
      document.removeEventListener('keydown', handleEscape)
      document.body.style.overflow = 'unset'
    }
  }, [isOpen, onClose])

  // Pause audio when modal closes
  useEffect(() => {
    if (!isOpen && audioRef.current) {
      audioRef.current.pause()
      setIsPlaying(false)
    }
  }, [isOpen])

  // Audio event listeners
  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const updateTime = () => setCurrentTime(audio.currentTime)
    const updateDuration = () => setDuration(audio.duration)
    const handleEnded = () => setIsPlaying(false)
    const handleError = () => {
      setError('Failed to load audio')
      setIsLoading(false)
    }
    const handleLoadStart = () => setIsLoading(true)
    const handleCanPlay = () => setIsLoading(false)

    audio.addEventListener('timeupdate', updateTime)
    audio.addEventListener('loadedmetadata', updateDuration)
    audio.addEventListener('ended', handleEnded)
    audio.addEventListener('error', handleError)
    audio.addEventListener('loadstart', handleLoadStart)
    audio.addEventListener('canplay', handleCanPlay)

    return () => {
      audio.removeEventListener('timeupdate', updateTime)
      audio.removeEventListener('loadedmetadata', updateDuration)
      audio.removeEventListener('ended', handleEnded)
      audio.removeEventListener('error', handleError)
      audio.removeEventListener('loadstart', handleLoadStart)
      audio.removeEventListener('canplay', handleCanPlay)
    }
  }, [audioUrl])

  // Generate walkthrough audio
  const handleGenerate = useCallback(async () => {
    setIsGenerating(true)
    setGenerationStatus('Generating walkthrough audio with ElevenLabs...')
    setError(null)

    try {
      const res = await fetch(`${API_BASE}/api/walkthrough/generate`, { method: 'POST' })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || 'Failed to generate audio')
      }

      const data = await res.json()
      if (data.audio_url) {
        setAudioUrl(`${API_BASE}${data.audio_url}`)
        setGenerationStatus('')
      }
    } catch (err: any) {
      setError(err.message || 'Failed to generate walkthrough audio')
      setGenerationStatus('')
    } finally {
      setIsGenerating(false)
    }
  }, [])

  const togglePlay = () => {
    const audio = audioRef.current
    if (!audio) return

    if (isPlaying) {
      audio.pause()
    } else {
      audio.play().catch((err) => {
        console.error('Error playing audio:', err)
        setError('Failed to play audio')
      })
    }
    setIsPlaying(!isPlaying)
  }

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const audio = audioRef.current
    if (!audio) return
    const time = parseFloat(e.target.value)
    audio.currentTime = time
    setCurrentTime(time)
  }

  const skip = (seconds: number) => {
    const audio = audioRef.current
    if (!audio) return
    audio.currentTime = Math.max(0, Math.min(audio.currentTime + seconds, duration))
  }

  const toggleMute = () => {
    const audio = audioRef.current
    if (!audio) return
    audio.muted = !isMuted
    setIsMuted(!isMuted)
  }

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const audio = audioRef.current
    if (!audio) return
    const vol = parseFloat(e.target.value)
    audio.volume = vol
    setVolume(vol)
    setIsMuted(vol === 0)
  }

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60)
    const s = Math.floor(seconds % 60)
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  const jumpToSection = (index: number) => {
    const audio = audioRef.current
    if (!audio || duration <= 0) return
    const sectionDuration = duration / sectionCount
    audio.currentTime = index * sectionDuration
    setCurrentTime(index * sectionDuration)
    if (!isPlaying) {
      audio.play().catch(() => {})
      setIsPlaying(true)
    }
  }

  if (!isOpen) return null

  const currentSectionIdx = getCurrentSectionIndex()

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose()
      }}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4 overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-emerald-600 to-teal-600 px-6 py-5 text-white">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
                <PlayCircle size={22} />
              </div>
              <div>
                <h2 className="text-lg font-semibold">Platform Walkthrough</h2>
                <p className="text-emerald-100 text-sm">A guided audio tour of the Intelligence Hub</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-lg bg-white/20 hover:bg-white/30 flex items-center justify-center transition-colors"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="px-6 py-4">
          {/* Section progress list */}
          <div className="space-y-1 mb-5 max-h-[280px] overflow-y-auto pr-1">
            {WALKTHROUGH_SECTIONS.map((section, idx) => {
              const progress = getSectionProgress(idx)
              const isCurrent = idx === currentSectionIdx && isPlaying
              const isCompleted = progress >= 100

              return (
                <button
                  key={section.id}
                  onClick={() => audioUrl && jumpToSection(idx)}
                  disabled={!audioUrl}
                  className={cn(
                    'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-all',
                    isCurrent
                      ? 'bg-emerald-50 border border-emerald-200'
                      : isCompleted
                        ? 'bg-slate-50 opacity-70'
                        : 'hover:bg-slate-50',
                    !audioUrl && 'opacity-50 cursor-default',
                  )}
                >
                  <span className="text-lg shrink-0">{section.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className={cn(
                      'text-sm font-medium',
                      isCurrent ? 'text-emerald-700' : 'text-slate-700',
                    )}>
                      {section.label}
                    </div>
                    {/* Section progress bar */}
                    {audioUrl && (
                      <div className="mt-1 h-1 bg-slate-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-emerald-500 rounded-full transition-all duration-300"
                          style={{ width: `${progress}%` }}
                        />
                      </div>
                    )}
                  </div>
                  {isCurrent && (
                    <span className="shrink-0 text-xs font-medium text-emerald-600 bg-emerald-100 px-2 py-0.5 rounded-full">
                      Playing
                    </span>
                  )}
                  {isCompleted && !isCurrent && audioUrl && (
                    <span className="shrink-0 text-xs text-slate-400">✓</span>
                  )}
                </button>
              )
            })}
          </div>

          {/* Generate button (if no audio available) */}
          {!audioUrl && (
            <div className="mb-4 text-center">
              {isGenerating ? (
                <div className="flex items-center justify-center gap-2 text-sm text-slate-500 py-3">
                  <Loader2 size={18} className="animate-spin" />
                  <span>{generationStatus || 'Generating...'}</span>
                </div>
              ) : (
                <button
                  onClick={handleGenerate}
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium text-sm transition-colors"
                >
                  <PlayCircle size={18} />
                  Generate Walkthrough Audio
                </button>
              )}
              {!isGenerating && (
                <p className="text-xs text-slate-400 mt-2">
                  Uses ElevenLabs to narrate a ~2 min tour of the platform
                </p>
              )}
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="mb-4 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
              {error}
            </div>
          )}

          {/* Audio player */}
          {audioUrl && (
            <>
              <audio ref={audioRef} src={audioUrl} preload="metadata" />

              {/* Progress bar */}
              <div className="flex items-center gap-3 mb-3">
                <span className="text-xs text-slate-400 w-10 text-right tabular-nums">
                  {formatTime(currentTime)}
                </span>
                <input
                  type="range"
                  min={0}
                  max={duration || 0}
                  value={currentTime}
                  onChange={handleSeek}
                  className="flex-1 h-1.5 bg-slate-200 rounded-full appearance-none cursor-pointer accent-emerald-500
                    [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-emerald-500 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:appearance-none"
                />
                <span className="text-xs text-slate-400 w-10 tabular-nums">
                  {formatTime(duration)}
                </span>
              </div>

              {/* Controls */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1">
                  <button onClick={toggleMute} className="p-2 rounded-lg hover:bg-slate-100 text-slate-500">
                    {isMuted ? <VolumeX size={18} /> : <Volume2 size={18} />}
                  </button>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.1}
                    value={isMuted ? 0 : volume}
                    onChange={handleVolumeChange}
                    className="w-20 h-1 bg-slate-200 rounded-full appearance-none cursor-pointer accent-slate-400
                      [&::-webkit-slider-thumb]:w-2.5 [&::-webkit-slider-thumb]:h-2.5 [&::-webkit-slider-thumb]:bg-slate-400 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:appearance-none"
                  />
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => skip(-10)}
                    className="p-2 rounded-lg hover:bg-slate-100 text-slate-500"
                    title="Back 10s"
                  >
                    <SkipBack size={18} />
                  </button>
                  <button
                    onClick={togglePlay}
                    disabled={isLoading}
                    className="w-12 h-12 rounded-full bg-emerald-600 hover:bg-emerald-700 text-white flex items-center justify-center transition-colors disabled:opacity-50"
                  >
                    {isLoading ? (
                      <Loader2 size={22} className="animate-spin" />
                    ) : isPlaying ? (
                      <Pause size={22} />
                    ) : (
                      <Play size={22} className="ml-0.5" />
                    )}
                  </button>
                  <button
                    onClick={() => skip(10)}
                    className="p-2 rounded-lg hover:bg-slate-100 text-slate-500"
                    title="Forward 10s"
                  >
                    <SkipForward size={18} />
                  </button>
                </div>

                <div className="w-[88px]" /> {/* Spacer to balance layout */}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

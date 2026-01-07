'use client'

import { useState, useRef, useEffect } from 'react'
import { X, Play, Pause, Volume2 } from 'lucide-react'
import { cn } from '@/lib/utils'

interface WelcomeTourModalProps {
  isOpen: boolean
  onClose: () => void
}

export default function WelcomeTourModal({ isOpen, onClose }: WelcomeTourModalProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [progress, setProgress] = useState(0)
  const [duration, setDuration] = useState(0)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    // Create audio element
    audioRef.current = new Audio('/11labs_c1_hub_walkthrough_2mins.mp3')

    const audio = audioRef.current

    audio.addEventListener('loadedmetadata', () => {
      setDuration(audio.duration)
    })

    audio.addEventListener('timeupdate', () => {
      setProgress((audio.currentTime / audio.duration) * 100)
    })

    audio.addEventListener('ended', () => {
      setIsPlaying(false)
      setProgress(0)
    })

    return () => {
      audio.pause()
      audio.src = ''
    }
  }, [])

  const togglePlay = () => {
    if (!audioRef.current) return

    if (isPlaying) {
      audioRef.current.pause()
    } else {
      audioRef.current.play()
    }
    setIsPlaying(!isPlaying)
  }

  const handleClose = () => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
    }
    setIsPlaying(false)
    setProgress(0)
    onClose()
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Modal */}
      <div className="relative bg-slate-900 rounded-2xl shadow-2xl border border-slate-700 max-w-md w-full mx-4 overflow-hidden">
        {/* Close button */}
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white transition-colors z-10"
        >
          <X size={20} />
        </button>

        {/* Content */}
        <div className="p-8 text-center">
          {/* Icon/Visual */}
          <div className="mb-6">
            <div className="w-20 h-20 mx-auto rounded-full bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center shadow-lg shadow-emerald-500/30">
              <Volume2 size={36} className="text-white" />
            </div>
          </div>

          {/* Title */}
          <h2 className="text-2xl font-bold text-white mb-2">
            Take the 2 Minute Tour
          </h2>

          {/* Sound tip */}
          <div className="flex items-center justify-center gap-2 text-emerald-400 text-sm mb-8">
            <Volume2 size={16} />
            <span>Sound on recommended</span>
          </div>

          {/* Play button */}
          <button
            onClick={togglePlay}
            className={cn(
              "w-24 h-24 mx-auto rounded-full flex items-center justify-center transition-all transform hover:scale-105",
              isPlaying
                ? "bg-slate-700 hover:bg-slate-600"
                : "bg-gradient-to-br from-emerald-400 to-emerald-600 hover:from-emerald-500 hover:to-emerald-700 shadow-lg shadow-emerald-500/30"
            )}
          >
            {isPlaying ? (
              <Pause size={40} className="text-white" />
            ) : (
              <Play size={40} className="text-white ml-2" />
            )}
          </button>

          {/* Progress bar */}
          {(isPlaying || progress > 0) && (
            <div className="mt-8">
              <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-emerald-400 to-emerald-600 transition-all duration-200"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="flex justify-between text-xs text-slate-400 mt-2">
                <span>{formatTime((progress / 100) * duration)}</span>
                <span>{formatTime(duration)}</span>
              </div>
            </div>
          )}

          {/* Skip link */}
          <button
            onClick={handleClose}
            className="mt-6 text-slate-400 hover:text-white text-sm transition-colors"
          >
            {isPlaying ? "Close & continue listening" : "Skip tour"}
          </button>
        </div>
      </div>
    </div>
  )
}

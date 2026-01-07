'use client'

import React, { useState, useRef, useEffect } from 'react'
import { Play, Pause, Download, Volume2, VolumeX, X, SkipBack, SkipForward } from 'lucide-react'
import { cn } from '@/lib/utils'

interface PodcastModalProps {
    isOpen: boolean
    onClose: () => void
    audioUrl: string
    duration?: number
    title: string
}

export default function PodcastModal({ isOpen, onClose, audioUrl, duration, title }: PodcastModalProps) {
    const audioRef = useRef<HTMLAudioElement>(null)
    const overlayRef = useRef<HTMLDivElement>(null)
    const [isPlaying, setIsPlaying] = useState(false)
    const [currentTime, setCurrentTime] = useState(0)
    const [audioDuration, setAudioDuration] = useState(duration || 0)
    const [isLoading, setIsLoading] = useState(false)
    const [volume, setVolume] = useState(1)
    const [isMuted, setIsMuted] = useState(false)
    const [error, setError] = useState<string | null>(null)

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

    // Update current time as audio plays
    useEffect(() => {
        const audio = audioRef.current
        if (!audio) return

        const updateTime = () => setCurrentTime(audio.currentTime)
        const updateDuration = () => setAudioDuration(audio.duration)
        const handleEnded = () => setIsPlaying(false)
        const handleError = () => {
            setError('Failed to load audio file')
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

        const newTime = Number(e.target.value)
        audio.currentTime = newTime
        setCurrentTime(newTime)
    }

    const skipBackward = () => {
        const audio = audioRef.current
        if (!audio) return
        audio.currentTime = Math.max(0, audio.currentTime - 15)
    }

    const skipForward = () => {
        const audio = audioRef.current
        if (!audio) return
        audio.currentTime = Math.min(audioDuration, audio.currentTime + 15)
    }

    const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const audio = audioRef.current
        if (!audio) return

        const newVolume = Number(e.target.value)
        audio.volume = newVolume
        setVolume(newVolume)
        setIsMuted(newVolume === 0)
    }

    const toggleMute = () => {
        const audio = audioRef.current
        if (!audio) return

        if (isMuted) {
            audio.volume = volume || 0.5
            setVolume(volume || 0.5)
            setIsMuted(false)
        } else {
            audio.volume = 0
            setIsMuted(true)
        }
    }

    const formatTime = (seconds: number) => {
        if (isNaN(seconds)) return '0:00'
        const mins = Math.floor(seconds / 60)
        const secs = Math.floor(seconds % 60)
        return `${mins}:${secs.toString().padStart(2, '0')}`
    }

    const handleOverlayClick = (e: React.MouseEvent) => {
        if (e.target === overlayRef.current) onClose()
    }

    if (!isOpen) return null

    return (
        <div
            ref={overlayRef}
            onClick={handleOverlayClick}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200"
        >
            <div className="relative bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden animate-in zoom-in-95 duration-200">
                {/* Hidden audio element */}
                <audio ref={audioRef} src={audioUrl} preload="metadata" />

                {/* Close button */}
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 p-2 rounded-full text-slate-400 hover:text-white hover:bg-slate-700/50 transition-colors z-10"
                >
                    <X size={20} />
                </button>

                {/* Header / Album Art Area */}
                <div className="relative px-8 pt-8 pb-6">
                    {/* Decorative background glow */}
                    <div className="absolute inset-0 bg-gradient-to-b from-emerald-500/10 to-transparent pointer-events-none" />
                    
                    {/* Podcast Icon */}
                    <div className="relative flex justify-center mb-6">
                        <div className="w-32 h-32 bg-gradient-to-br from-emerald-400 to-emerald-600 rounded-2xl shadow-lg shadow-emerald-500/30 flex items-center justify-center">
                            <span className="text-6xl">🎙️</span>
                        </div>
                    </div>

                    {/* Title */}
                    <div className="text-center">
                        <p className="text-emerald-400 text-xs font-bold uppercase tracking-widest mb-1">
                            Executive Briefing
                        </p>
                        <h3 className="text-white font-bold text-lg leading-tight line-clamp-2">
                            {title}
                        </h3>
                    </div>
                </div>

                {/* Error State */}
                {error && (
                    <div className="mx-8 mb-4 bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-400">
                        {error}
                    </div>
                )}

                {/* Progress Bar */}
                <div className="px-8 pb-4">
                    <input
                        type="range"
                        min={0}
                        max={audioDuration || 100}
                        value={currentTime}
                        onChange={handleSeek}
                        className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer
                            [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 
                            [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:bg-emerald-400 
                            [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer
                            [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:shadow-emerald-500/30
                            [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4 
                            [&::-moz-range-thumb]:bg-emerald-400 [&::-moz-range-thumb]:rounded-full 
                            [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:cursor-pointer"
                        style={{
                            background: `linear-gradient(to right, #34d399 0%, #34d399 ${(currentTime / (audioDuration || 1)) * 100}%, #334155 ${(currentTime / (audioDuration || 1)) * 100}%, #334155 100%)`
                        }}
                    />
                    <div className="flex justify-between text-xs text-slate-400 mt-1.5">
                        <span>{formatTime(currentTime)}</span>
                        <span>{formatTime(audioDuration)}</span>
                    </div>
                </div>

                {/* Playback Controls */}
                <div className="px-8 pb-6">
                    <div className="flex items-center justify-center gap-6">
                        {/* Skip backward 15s */}
                        <button
                            onClick={skipBackward}
                            className="p-2 text-slate-400 hover:text-white transition-colors"
                            title="Skip back 15 seconds"
                        >
                            <SkipBack size={24} />
                        </button>

                        {/* Play/Pause */}
                        <button
                            onClick={togglePlay}
                            disabled={isLoading}
                            className={cn(
                                "w-16 h-16 rounded-full flex items-center justify-center transition-all",
                                "bg-emerald-500 hover:bg-emerald-400 text-white shadow-lg shadow-emerald-500/40 hover:shadow-emerald-400/50",
                                isLoading && "opacity-50 cursor-not-allowed"
                            )}
                        >
                            {isLoading ? (
                                <div className="w-6 h-6 border-3 border-white border-t-transparent rounded-full animate-spin" />
                            ) : isPlaying ? (
                                <Pause size={28} fill="white" />
                            ) : (
                                <Play size={28} fill="white" className="ml-1" />
                            )}
                        </button>

                        {/* Skip forward 15s */}
                        <button
                            onClick={skipForward}
                            className="p-2 text-slate-400 hover:text-white transition-colors"
                            title="Skip forward 15 seconds"
                        >
                            <SkipForward size={24} />
                        </button>
                    </div>
                </div>

                {/* Bottom Controls */}
                <div className="px-8 pb-6 flex items-center justify-between">
                    {/* Volume */}
                    <div className="flex items-center gap-2">
                        <button
                            onClick={toggleMute}
                            className="p-1.5 text-slate-400 hover:text-white transition-colors"
                        >
                            {isMuted ? (
                                <VolumeX size={18} />
                            ) : (
                                <Volume2 size={18} />
                            )}
                        </button>
                        <input
                            type="range"
                            min={0}
                            max={1}
                            step={0.1}
                            value={isMuted ? 0 : volume}
                            onChange={handleVolumeChange}
                            className="w-20 h-1 bg-slate-700 rounded-full appearance-none cursor-pointer
                                [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 
                                [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-slate-300 
                                [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer
                                [&::-moz-range-thumb]:w-3 [&::-moz-range-thumb]:h-3 
                                [&::-moz-range-thumb]:bg-slate-300 [&::-moz-range-thumb]:rounded-full 
                                [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:cursor-pointer"
                        />
                    </div>

                    {/* Download */}
                    <a
                        href={audioUrl}
                        download={`${title}.mp3`}
                        className="p-2 text-slate-400 hover:text-white transition-colors"
                        title="Download podcast"
                    >
                        <Download size={18} />
                    </a>
                </div>
            </div>
        </div>
    )
}

'use client'

import React, { useState, useRef, useEffect } from 'react'
import { Play, Pause, Download, Volume2, VolumeX } from 'lucide-react'
import { cn } from '@/lib/utils'

interface PodcastPlayerProps {
    /** URL to the podcast audio file */
    audioUrl: string
    /** Duration in seconds (estimated) */
    duration?: number
    /** Podcast title */
    title: string
}

export default function PodcastPlayer({ audioUrl, duration, title }: PodcastPlayerProps) {
    const audioRef = useRef<HTMLAudioElement>(null)
    const [isPlaying, setIsPlaying] = useState(false)
    const [currentTime, setCurrentTime] = useState(0)
    const [audioDuration, setAudioDuration] = useState(duration || 0)
    const [isLoading, setIsLoading] = useState(false)
    const [volume, setVolume] = useState(1)
    const [isMuted, setIsMuted] = useState(false)
    const [error, setError] = useState<string | null>(null)

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

    if (error) {
        return (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
                <p className="font-medium">Audio Error</p>
                <p className="text-red-600 mt-1">{error}</p>
            </div>
        )
    }

    return (
        <div className="bg-gradient-to-r from-emerald-50 to-emerald-50 border border-emerald-200 rounded-xl p-4 shadow-sm">
            {/* Hidden audio element */}
            <audio ref={audioRef} src={audioUrl} preload="metadata" />

            {/* Header */}
            <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">
                    <span className="text-2xl">🎙️</span>
                </div>
                <div className="flex-1">
                    <h4 className="text-sm font-bold text-slate-900">Listen to Podcast</h4>
                    <p className="text-xs text-slate-600">{title}</p>
                </div>
                <a
                    href={audioUrl}
                    download={`${title}.mp3`}
                    className="p-2 hover:bg-emerald-100 rounded-lg transition-colors"
                    title="Download podcast"
                >
                    <Download size={18} className="text-slate-600" />
                </a>
            </div>

            {/* Controls */}
            <div className="space-y-3">
                {/* Progress bar */}
                <div className="space-y-1">
                    <input
                        type="range"
                        min={0}
                        max={audioDuration || 100}
                        value={currentTime}
                        onChange={handleSeek}
                        className="w-full h-2 bg-emerald-200 rounded-lg appearance-none cursor-pointer
                     [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 
                     [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:bg-emerald-600 
                     [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer
                     [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4 
                     [&::-moz-range-thumb]:bg-emerald-600 [&::-moz-range-thumb]:rounded-full 
                     [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:cursor-pointer"
                    />
                    <div className="flex justify-between text-xs text-slate-500">
                        <span>{formatTime(currentTime)}</span>
                        <span>{formatTime(audioDuration)}</span>
                    </div>
                </div>

                {/* Play/pause and volume controls */}
                <div className="flex items-center gap-3">
                    {/* Play/Pause button */}
                    <button
                        onClick={togglePlay}
                        disabled={isLoading}
                        className={cn(
                            "w-10 h-10 rounded-full flex items-center justify-center transition-all",
                            "bg-emerald-600 hover:bg-emerald-700 text-white shadow-md hover:shadow-lg",
                            isLoading && "opacity-50 cursor-not-allowed"
                        )}
                    >
                        {isLoading ? (
                            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        ) : isPlaying ? (
                            <Pause size={20} fill="white" />
                        ) : (
                            <Play size={20} fill="white" className="ml-0.5" />
                        )}
                    </button>

                    {/* Volume controls */}
                    <div className="flex items-center gap-2 flex-1">
                        <button
                            onClick={toggleMute}
                            className="p-1.5 hover:bg-emerald-100 rounded transition-colors"
                        >
                            {isMuted ? (
                                <VolumeX size={18} className="text-slate-600" />
                            ) : (
                                <Volume2 size={18} className="text-slate-600" />
                            )}
                        </button>
                        <input
                            type="range"
                            min={0}
                            max={1}
                            step={0.1}
                            value={isMuted ? 0 : volume}
                            onChange={handleVolumeChange}
                            className="w-20 h-1.5 bg-emerald-200 rounded-lg appearance-none cursor-pointer
                       [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 
                       [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-emerald-600 
                       [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer
                       [&::-moz-range-thumb]:w-3 [&::-moz-range-thumb]:h-3 
                       [&::-moz-range-thumb]:bg-emerald-600 [&::-moz-range-thumb]:rounded-full 
                       [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:cursor-pointer"
                        />
                    </div>
                </div>
            </div>
        </div>
    )
}

'use client'

import { useState, useEffect } from 'react'
import { cn } from '@/lib/utils'

interface TypewriterEffectProps {
    text: string
    className?: string
    cursorClassName?: string
    speed?: number
    startDelay?: number
    onComplete?: () => void
}

export default function TypewriterEffect({
    text,
    className,
    cursorClassName,
    speed = 30,
    startDelay = 0,
    onComplete
}: TypewriterEffectProps) {
    const [displayedText, setDisplayedText] = useState('')
    const [isTyping, setIsTyping] = useState(false)
    const [hasStarted, setHasStarted] = useState(false)

    useEffect(() => {
        let timeoutId: NodeJS.Timeout
        let currentIndex = 0

        // Reset state when text changes
        setDisplayedText('')
        setIsTyping(false)
        setHasStarted(false)

        const startTyping = () => {
            setHasStarted(true)
            setIsTyping(true)

            const typeChar = () => {
                if (currentIndex < text.length) {
                    setDisplayedText(text.slice(0, currentIndex + 1))
                    currentIndex++

                    // Vary speed slightly for realism
                    const randomSpeed = speed + (Math.random() * 20 - 10)
                    timeoutId = setTimeout(typeChar, randomSpeed)
                } else {
                    setIsTyping(false)
                    if (onComplete) onComplete()
                }
            }

            typeChar()
        }

        if (startDelay > 0) {
            timeoutId = setTimeout(startTyping, startDelay)
        } else {
            startTyping()
        }

        return () => clearTimeout(timeoutId)
    }, [text, speed, startDelay, onComplete])

    return (
        <span className={cn("inline-block", className)}>
            {displayedText}
            <span
                className={cn(
                    "inline-block w-[2px] h-[1em] bg-current ml-0.5 align-middle",
                    isTyping ? "animate-pulse" : "opacity-0",
                    cursorClassName
                )}
            />
        </span>
    )
}

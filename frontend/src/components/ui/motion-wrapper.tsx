'use client'

import { motion } from 'framer-motion'
import { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface MotionWrapperProps {
    children: ReactNode
    className?: string
    delay?: number
}

export default function MotionWrapper({ children, className, delay = 0 }: MotionWrapperProps) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{
                duration: 0.3,
                ease: "easeOut",
                delay: delay
            }}
            className={cn("h-full", className)}
        >
            {children}
        </motion.div>
    )
}

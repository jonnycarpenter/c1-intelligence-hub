'use client'

import { useDeepResearchContext } from '@/contexts/DeepResearchContext'
import type { DeepResearchState } from '@/contexts/DeepResearchContext'

export function useDeepResearch() {
    return useDeepResearchContext()
}

export type { DeepResearchState }

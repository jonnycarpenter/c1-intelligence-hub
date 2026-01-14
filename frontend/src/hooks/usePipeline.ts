'use client'

import { usePipelineContext } from '@/contexts/PipelineContext'

export function usePipeline() {
  return usePipelineContext()
}

'use client'

import React from 'react'
import { Mic, Eye, Share2 } from 'lucide-react'
import Image from 'next/image'

export default function FieldIntelDashboard() {
  return (
    <div className="h-full flex flex-col overflow-hidden p-6">
      {/* Header */}
      <div className="shrink-0 mb-4">
        <h1 className="text-2xl font-bold text-slate-800 mb-2">Field Scout</h1>
        <p className="text-slate-500">Capture and share field intelligence from customer visits and site observations</p>
      </div>

      {/* What FieldScout Does - Compact Icon Row */}
      <div className="shrink-0 mb-4 flex items-center gap-4">
        <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 rounded-full border border-blue-200">
          <Mic className="w-3.5 h-3.5 text-blue-600" />
          <span className="text-xs font-medium text-blue-700">Voice Memos</span>
        </div>

        <div className="flex items-center gap-2 px-3 py-1.5 bg-purple-50 rounded-full border border-purple-200">
          <Eye className="w-3.5 h-3.5 text-purple-600" />
          <span className="text-xs font-medium text-purple-700">Competitive Sightings</span>
        </div>

        <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-50 rounded-full border border-emerald-200">
          <Share2 className="w-3.5 h-3.5 text-emerald-600" />
          <span className="text-xs font-medium text-emerald-700">Share Intel</span>
        </div>
      </div>

      {/* Main Content: Sneak Peek + Video Side by Side */}
      <div className="flex-1 flex gap-6 min-h-0 overflow-y-auto">
        {/* Left Column: Sneak Peek Images */}
        <div className="w-64 shrink-0 flex flex-col gap-3">
          <h2 className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Sneak Peek</h2>

          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden shadow-sm hover:shadow-md transition-shadow">
            <div className="relative h-28 bg-slate-100">
              <Image
                src="/FIELDSCOUT_TERRITORYRADAR.jpg"
                alt="Territory Radar - Intelligence feed"
                fill
                className="object-cover"
              />
            </div>
            <div className="p-2 border-t border-slate-200">
              <h3 className="text-xs font-semibold text-slate-800">Territory Radar</h3>
              <p className="text-xs text-slate-500">Real-time intelligence feed</p>
            </div>
          </div>

          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden shadow-sm hover:shadow-md transition-shadow">
            <div className="relative h-28 bg-slate-100">
              <Image
                src="/FIELDSCOUT_VOICENOTE.jpg"
                alt="Voice Note Recording"
                fill
                className="object-cover"
              />
            </div>
            <div className="p-2 border-t border-slate-200">
              <h3 className="text-xs font-semibold text-slate-800">Voice Note Capture</h3>
              <p className="text-xs text-slate-500">Record on the go</p>
            </div>
          </div>
        </div>

        {/* Right Column: Video Player */}
        <div className="flex-1 flex flex-col">
          <div className="bg-slate-900 rounded-xl overflow-hidden shadow-2xl">
            <video
              className="w-full aspect-video"
              controls
              poster="/video-poster.png"
              preload="metadata"
            >
              <source src="/FieldScout_for_CompositesOne.mp4" type="video/mp4" />
              Your browser does not support the video tag.
            </video>
          </div>

          {/* Video Caption */}
          <div className="mt-4 text-center">
            <h2 className="text-lg font-semibold text-slate-700">FieldScout for Composites One</h2>
            <p className="text-sm text-slate-500 mt-1">Product demo and overview</p>
          </div>
        </div>
      </div>
    </div>
  )
}

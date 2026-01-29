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

      {/* What FieldScout Does - Icon Cards */}
      <div className="shrink-0 mb-4">
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-slate-50 rounded-lg p-3 text-center border border-slate-200">
            <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center mx-auto mb-2">
              <Mic className="w-4 h-4 text-blue-600" />
            </div>
            <h3 className="text-xs font-semibold text-slate-700">Voice Memos</h3>
            <p className="text-xs text-slate-500 mt-1">Record field observations</p>
          </div>
          
          <div className="bg-slate-50 rounded-lg p-3 text-center border border-slate-200">
            <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center mx-auto mb-2">
              <Eye className="w-4 h-4 text-purple-600" />
            </div>
            <h3 className="text-xs font-semibold text-slate-700">Competitor Sightings</h3>
            <p className="text-xs text-slate-500 mt-1">Track field observations</p>
          </div>
          
          <div className="bg-slate-50 rounded-lg p-3 text-center border border-slate-200">
            <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-2">
              <Share2 className="w-4 h-4 text-emerald-600" />
            </div>
            <h3 className="text-xs font-semibold text-slate-700">Share Intel</h3>
            <p className="text-xs text-slate-500 mt-1">Distribute to team</p>
          </div>
        </div>
      </div>

      {/* Main Content: Sneak Peek + Video Side by Side */}
      <div className="flex-1 flex gap-6 min-h-0 overflow-y-auto">
        {/* Left Column: Sneak Peek Images */}
        <div className="w-64 shrink-0 flex flex-col gap-3">
          <h2 className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Sneak Peek</h2>
          
          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden shadow-sm hover:shadow-md transition-shadow">
            <div className="relative h-36 bg-slate-100">
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
            <div className="relative h-36 bg-slate-100">
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

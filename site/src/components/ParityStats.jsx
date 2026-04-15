import React from 'react'

export default function ParityStats({ stats, sdks, sdkOrder }) {
  // Compute overall stats
  const totalFeatures = stats[sdkOrder[0]]?.total || 0

  return (
    <div className="bg-white rounded-lg shadow-sm border p-4">
      <h2 className="text-sm font-semibold text-gray-600 mb-3">Feature Coverage Comparison</h2>
      <div className="space-y-2">
        {sdkOrder.map(sdkId => {
          const s = stats[sdkId]
          const applicable = s.total - (s.n_a || 0)
          const gaPct = applicable > 0 ? (s.ga / applicable) * 100 : 0
          const previewPct = applicable > 0 ? (s.preview / applicable) * 100 : 0
          const inProgressPct = applicable > 0 ? ((s.in_progress || 0) / applicable) * 100 : 0

          return (
            <div key={sdkId} className="flex items-center gap-3">
              <div className="w-16 text-sm font-medium text-right" style={{ color: sdks[sdkId]?.color }}>
                {sdks[sdkId]?.name}
              </div>
              <div className="flex-1 flex h-5 rounded-full overflow-hidden bg-gray-100">
                {gaPct > 0 && (
                  <div
                    className="bg-green-500 transition-all duration-500"
                    style={{ width: `${gaPct}%` }}
                    title={`GA: ${s.ga} features`}
                  />
                )}
                {previewPct > 0 && (
                  <div
                    className="bg-yellow-400 transition-all duration-500"
                    style={{ width: `${previewPct}%` }}
                    title={`Preview: ${s.preview} features`}
                  />
                )}
                {inProgressPct > 0 && (
                  <div
                    className="bg-blue-400 transition-all duration-500"
                    style={{ width: `${inProgressPct}%` }}
                    title={`In Progress: ${s.in_progress} features`}
                  />
                )}
              </div>
              <div className="w-12 text-xs text-gray-500 text-right">
                {Math.round(gaPct + previewPct)}%
              </div>
            </div>
          )
        })}
      </div>
      <div className="flex gap-4 mt-3 text-xs text-gray-500 justify-center">
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-green-500 inline-block" /> GA</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-yellow-400 inline-block" /> Preview</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-blue-400 inline-block" /> In Progress</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-gray-100 inline-block border" /> Not Started</span>
      </div>
    </div>
  )
}

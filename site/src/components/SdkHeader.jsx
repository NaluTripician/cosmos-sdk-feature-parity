import React from 'react'

export default function SdkHeader({ sdk, stats, scrapeData }) {
  if (!sdk || !stats) return null

  const applicable = stats.total - (stats.n_a || 0)
  const implemented = stats.ga + (stats.preview || 0)
  const pct = applicable > 0 ? Math.round((implemented / applicable) * 100) : 0

  return (
    <div className="bg-white rounded-lg shadow-sm border p-3">
      <div className="flex items-center gap-2 mb-2">
        <div
          className="w-3 h-3 rounded-full"
          style={{ backgroundColor: sdk.color }}
        />
        <h3 className="font-bold text-sm">{sdk.name}</h3>
      </div>

      {/* Version info */}
      <div className="text-xs text-gray-500 space-y-0.5">
        <div>Stable: <span className="font-mono font-medium text-gray-700">{sdk.latest_stable}</span></div>
        {sdk.latest_preview && (
          <div>Preview: <span className="font-mono text-gray-500">{sdk.latest_preview}</span></div>
        )}
      </div>

      {/* Parity bar */}
      <div className="mt-2">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-gray-500">Parity</span>
          <span className="font-bold" style={{ color: pct >= 80 ? '#16a34a' : pct >= 50 ? '#d97706' : '#dc2626' }}>
            {pct}%
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="h-2 rounded-full transition-all duration-500"
            style={{
              width: `${pct}%`,
              backgroundColor: pct >= 80 ? '#16a34a' : pct >= 50 ? '#d97706' : '#dc2626',
            }}
          />
        </div>
        <div className="flex justify-between text-[10px] text-gray-400 mt-1">
          <span>{stats.ga} GA</span>
          <span>{stats.preview || 0} Preview</span>
          <span>{stats.not_started || 0} Missing</span>
        </div>
      </div>

      {/* Commit activity */}
      {scrapeData && (
        <div className="mt-2 pt-2 border-t text-xs text-gray-500">
          <span title="Commits in last 30 days">
            📊 {scrapeData.commits_last_30d ?? '?'} commits/30d
          </span>
        </div>
      )}
    </div>
  )
}

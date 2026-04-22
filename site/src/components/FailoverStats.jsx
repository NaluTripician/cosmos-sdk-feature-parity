import React from 'react'

const PPAF_SCENARIO_ID = 'ppaf_implemented'

function resolveCell(perSdk, sdkMeta) {
  if (!perSdk) return null
  if (perSdk.status !== undefined) return perSdk
  const modes = sdkMeta?.connection_modes || ['gateway']
  const primary = modes.includes('direct') ? 'direct' : modes[0]
  return perSdk[primary] || perSdk[modes[0]] || null
}

const PPAF_BADGE = {
  supported: { label: 'GA', className: 'bg-green-100 text-green-800' },
  partial: { label: 'Preview', className: 'bg-yellow-100 text-yellow-800' },
  not_supported: { label: 'No', className: 'bg-red-100 text-red-800' },
  not_started: { label: 'Not started', className: 'bg-gray-200 text-gray-600' },
  unknown: { label: 'Unknown', className: 'bg-yellow-50 text-yellow-700' },
  n_a: { label: 'N/A', className: 'bg-gray-100 text-gray-500' },
}

export default function FailoverStats({ failovers, sdks, sdkOrder }) {
  if (!failovers) return null

  const sdkConnModes = failovers.sdks || {}
  const scenarios = (failovers.categories || [])
    .flatMap((c) => c.scenarios || [])
    .concat(failovers.scenarios || [])

  const tallies = {}
  sdkOrder.forEach((sdkId) => {
    tallies[sdkId] = {
      supported: 0,
      partial: 0,
      not_supported: 0,
      not_started: 0,
      n_a: 0,
      unknown: 0,
      total: 0,
    }
  })

  scenarios.forEach((sc) => {
    sdkOrder.forEach((sdkId) => {
      const cell = resolveCell(sc.sdks?.[sdkId], sdkConnModes[sdkId])
      const status = cell?.status || 'unknown'
      tallies[sdkId].total += 1
      if (status in tallies[sdkId]) tallies[sdkId][status] += 1
      else tallies[sdkId].unknown += 1
    })
  })

  // PPAF-readiness callout
  const ppafScenario = scenarios.find((s) => s.id === PPAF_SCENARIO_ID)

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg shadow-sm border p-4">
        <h2 className="text-sm font-semibold text-gray-600 mb-3">
          Failover Scenario Coverage
        </h2>
        <div className="space-y-2">
          {sdkOrder.map((sdkId) => {
            const t = tallies[sdkId]
            const applicable = t.total - t.n_a
            const pct = (k) => (applicable > 0 ? (t[k] / applicable) * 100 : 0)
            return (
              <div key={sdkId} className="flex items-center gap-3">
                <div
                  className="w-16 text-sm font-medium text-right"
                  style={{ color: sdks[sdkId]?.color }}
                >
                  {sdks[sdkId]?.name}
                </div>
                <div className="flex-1 flex h-5 rounded-full overflow-hidden bg-gray-100">
                  {pct('supported') > 0 && (
                    <div
                      className="bg-green-500"
                      style={{ width: `${pct('supported')}%` }}
                      title={`Supported: ${t.supported}`}
                    />
                  )}
                  {pct('partial') > 0 && (
                    <div
                      className="bg-yellow-400"
                      style={{ width: `${pct('partial')}%` }}
                      title={`Partial: ${t.partial}`}
                    />
                  )}
                  {pct('not_supported') > 0 && (
                    <div
                      className="bg-red-400"
                      style={{ width: `${pct('not_supported')}%` }}
                      title={`Not supported: ${t.not_supported}`}
                    />
                  )}
                  {pct('not_started') > 0 && (
                    <div
                      className="bg-gray-300"
                      style={{ width: `${pct('not_started')}%` }}
                      title={`Not started: ${t.not_started}`}
                    />
                  )}
                  {pct('unknown') > 0 && (
                    <div
                      className="bg-yellow-200"
                      style={{ width: `${pct('unknown')}%` }}
                      title={`Unknown: ${t.unknown}`}
                    />
                  )}
                </div>
                <div className="w-28 text-xs text-gray-500 text-right">
                  {t.supported + t.partial}/{applicable} covered
                </div>
              </div>
            )
          })}
        </div>
        <div className="flex gap-4 mt-3 text-xs text-gray-500 justify-center flex-wrap">
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-green-500 inline-block" /> Supported
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-yellow-400 inline-block" /> Partial
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-red-400 inline-block" /> Not supported
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-gray-300 inline-block" /> Not started
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-yellow-200 inline-block" /> Unknown
          </span>
        </div>
      </div>

      {ppafScenario && (
        <div className="bg-gradient-to-r from-indigo-50 to-blue-50 border border-indigo-200 rounded-lg p-4">
          <h2 className="text-sm font-semibold text-indigo-900 mb-2">
            🚦 Per-Partition Automatic Failover (PPAF) readiness
          </h2>
          <p className="text-xs text-indigo-800/80 mb-3">
            PPAF is the headline differentiator right now — it lets the client route around a
            single unhealthy partition region without failing the whole request.
          </p>
          <div className="grid grid-cols-5 gap-2">
            {sdkOrder.map((sdkId) => {
              const cell = resolveCell(ppafScenario.sdks?.[sdkId], sdkConnModes[sdkId])
              const status = cell?.status || 'unknown'
              const badge = PPAF_BADGE[status] || PPAF_BADGE.unknown
              return (
                <div
                  key={sdkId}
                  className="bg-white rounded border border-indigo-100 px-2 py-2 text-center"
                >
                  <div
                    className="text-xs font-medium mb-1"
                    style={{ color: sdks[sdkId]?.color }}
                  >
                    {sdks[sdkId]?.name}
                  </div>
                  <span
                    className={`inline-block text-[10px] font-semibold px-2 py-0.5 rounded ${badge.className}`}
                  >
                    {badge.label}
                  </span>
                  {cell?.notes && (
                    <div className="text-[9px] text-gray-500 mt-1 leading-tight">
                      {cell.notes.length > 80 ? `${cell.notes.slice(0, 80)}…` : cell.notes}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

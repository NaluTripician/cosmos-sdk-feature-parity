import React from 'react'

/**
 * Per-SDK summary of retry scenarios: how many have explicit retries vs fail-fast vs n_a.
 */
export default function RetryStats({ retries, sdks, sdkOrder }) {
  if (!retries) return null

  const sdkConnModes = retries.sdks || {}
  const scenarios = (retries.categories || [])
    .flatMap((c) => c.scenarios || [])
    .concat(retries.scenarios || [])

  const tallies = {}
  sdkOrder.forEach((sdkId) => {
    tallies[sdkId] = { retries: 0, no_retry: 0, n_a: 0, not_started: 0, unknown: 0, total: 0 }
  })

  scenarios.forEach((sc) => {
    sdkOrder.forEach((sdkId) => {
      const modes = sdkConnModes[sdkId]?.connection_modes || ['gateway']
      // Use the "best" mode (prefer direct over gateway) for the headline summary.
      const primaryMode = modes.includes('direct') ? 'direct' : modes[0]
      const perSdk = sc.sdks?.[sdkId]
      const cell =
        perSdk && (perSdk[primaryMode] !== undefined ? perSdk[primaryMode] : perSdk)
      const status = cell?.status || 'unknown'
      tallies[sdkId].total += 1
      if (status in tallies[sdkId]) tallies[sdkId][status] += 1
      else tallies[sdkId].unknown += 1
    })
  })

  return (
    <div className="bg-white rounded-lg shadow-sm border p-4">
      <h2 className="text-sm font-semibold text-gray-600 mb-3">
        Retry Scenario Coverage (primary mode)
      </h2>
      <div className="space-y-2">
        {sdkOrder.map((sdkId) => {
          const t = tallies[sdkId]
          const applicable = t.total - t.n_a
          const retriesPct = applicable > 0 ? (t.retries / applicable) * 100 : 0
          const failPct = applicable > 0 ? (t.no_retry / applicable) * 100 : 0
          const notStartedPct = applicable > 0 ? (t.not_started / applicable) * 100 : 0
          const unknownPct = applicable > 0 ? (t.unknown / applicable) * 100 : 0

          return (
            <div key={sdkId} className="flex items-center gap-3">
              <div
                className="w-16 text-sm font-medium text-right"
                style={{ color: sdks[sdkId]?.color }}
              >
                {sdks[sdkId]?.name}
              </div>
              <div className="flex-1 flex h-5 rounded-full overflow-hidden bg-gray-100">
                {retriesPct > 0 && (
                  <div
                    className="bg-green-500"
                    style={{ width: `${retriesPct}%` }}
                    title={`Retries: ${t.retries} scenarios`}
                  />
                )}
                {failPct > 0 && (
                  <div
                    className="bg-red-400"
                    style={{ width: `${failPct}%` }}
                    title={`Fails fast: ${t.no_retry} scenarios`}
                  />
                )}
                {notStartedPct > 0 && (
                  <div
                    className="bg-gray-300"
                    style={{ width: `${notStartedPct}%` }}
                    title={`Not implemented: ${t.not_started} scenarios`}
                  />
                )}
                {unknownPct > 0 && (
                  <div
                    className="bg-yellow-300"
                    style={{ width: `${unknownPct}%` }}
                    title={`Unknown: ${t.unknown} scenarios`}
                  />
                )}
              </div>
              <div className="w-24 text-xs text-gray-500 text-right">
                {t.retries}/{applicable} retry
              </div>
            </div>
          )
        })}
      </div>
      <div className="flex gap-4 mt-3 text-xs text-gray-500 justify-center flex-wrap">
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-green-500 inline-block" /> Retries
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-red-400 inline-block" /> Fails fast
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-gray-300 inline-block" /> Not implemented
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-yellow-300 inline-block" /> Unknown
        </span>
      </div>
    </div>
  )
}

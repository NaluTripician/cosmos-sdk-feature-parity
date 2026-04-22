import React, { useState } from 'react'

const STATUS_CONFIG = {
  supported: { label: 'Supported', bg: 'bg-green-100', text: 'text-green-800', dot: '🟢' },
  partial: { label: 'Partial', bg: 'bg-yellow-100', text: 'text-yellow-800', dot: '🟡' },
  not_supported: { label: 'Not supp.', bg: 'bg-red-100', text: 'text-red-800', dot: '🔴' },
  not_started: { label: 'Not impl.', bg: 'bg-gray-100', text: 'text-gray-500', dot: '⚪' },
  n_a: { label: 'N/A', bg: 'bg-gray-50', text: 'text-gray-400', dot: '➖' },
  unknown: { label: 'Unknown', bg: 'bg-yellow-50', text: 'text-yellow-700', dot: '❔' },
}

const REPO_BY_SDK = {
  dotnet: 'Azure/azure-cosmos-dotnet-v3',
  java: 'Azure/azure-sdk-for-java',
  python: 'Azure/azure-sdk-for-python',
  go: 'Azure/azure-sdk-for-go',
  rust: 'Azure/azure-sdk-for-rust',
}

function sourceLink(sdkId, ref) {
  if (!ref) return null
  const repo = REPO_BY_SDK[sdkId]
  if (!repo) return null
  const [path, anchor] = ref.split('#')
  const line = anchor ? `#${anchor}` : ''
  return `https://github.com/${repo}/blob/HEAD/${path}${line}`
}

function formatCell(cell) {
  if (!cell) return null
  const bits = []
  if (cell.api) bits.push(cell.api)
  if (cell.default) bits.push(`default: ${cell.default}`)
  return bits.join(' · ')
}

function Cell({ sdkId, cell, mode }) {
  const status = cell?.status || 'unknown'
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.unknown
  const summary = formatCell(cell)
  const link = sourceLink(sdkId, cell?.source_ref)

  return (
    <td className="px-1.5 py-1.5 align-top text-center group relative">
      <div
        className={`inline-flex flex-col items-center gap-0.5 px-1.5 py-1 rounded text-[10px] font-medium leading-tight ${config.bg} ${config.text} min-w-[70px]`}
      >
        <span className="text-[11px]">
          {config.dot} {config.label}
        </span>
        {summary && (
          <span className="text-[9px] font-normal opacity-80 whitespace-normal">
            {summary}
          </span>
        )}
        {cell?.configurable === true && (
          <span className="text-[8px] font-normal opacity-70" title="User-configurable">
            ⚙️ configurable
          </span>
        )}
      </div>
      {(cell?.notes || link) && (
        <div className="absolute z-20 hidden group-hover:block bg-gray-900 text-white text-xs rounded p-2 w-72 -translate-x-1/2 left-1/2 mt-1 shadow-lg text-left normal-case">
          <div className="font-semibold mb-1">
            {STATUS_CONFIG[status]?.label}
            {mode ? ` — ${mode}` : ''}
          </div>
          {cell?.notes && <div className="mb-2">{cell.notes}</div>}
          {link && (
            <a
              href={link}
              target="_blank"
              rel="noreferrer"
              className="text-blue-300 hover:text-blue-200 underline break-all"
            >
              {cell.source_ref}
            </a>
          )}
        </div>
      )}
    </td>
  )
}

export default function FailoverMatrix({ failovers, sdks, sdkOrder, filter }) {
  const [groupByCategory, setGroupByCategory] = useState(true)

  if (!failovers) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded p-4 text-sm text-yellow-800">
        No failover data available yet. Populate <code>data/failovers.yaml</code>.
      </div>
    )
  }

  const sdkConnModes = failovers.sdks || {}

  // Failover behavior is mostly mode-agnostic: one column per SDK by default.
  // If a scenario uses per-mode cells, they're surfaced inside the cell notes.
  const columns = sdkOrder.map((sdkId) => ({ sdkId }))

  let categories = failovers.categories
  if (!categories) {
    categories = [{ name: 'Failover Scenarios', scenarios: failovers.scenarios || [] }]
  }

  if (filter === 'gaps') {
    categories = categories
      .map((cat) => ({
        ...cat,
        scenarios: (cat.scenarios || []).filter((sc) => {
          const statuses = columns.map(({ sdkId }) => {
            const perSdk = sc.sdks?.[sdkId]
            const cell = resolveCell(perSdk, sdkConnModes[sdkId])
            return cell?.status || 'unknown'
          })
          const anySupported = statuses.some((s) => s === 'supported' || s === 'partial')
          const anyGap = statuses.some(
            (s) => s === 'not_supported' || s === 'not_started'
          )
          return anySupported && anyGap
        }),
      }))
      .filter((cat) => cat.scenarios.length > 0)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs text-gray-500">
          Hover a cell for notes and source pin. Failover behavior is mostly mode-agnostic, so
          columns show one cell per SDK.
        </div>
        <label className="text-xs text-gray-500 flex items-center gap-1.5">
          <input
            type="checkbox"
            checked={groupByCategory}
            onChange={(e) => setGroupByCategory(e.target.checked)}
          />
          Group by category
        </label>
      </div>

      <div className="overflow-x-auto border rounded">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 bg-white">
            <tr className="border-b-2 border-gray-300">
              <th className="text-left px-3 py-2 text-sm font-semibold text-gray-600 w-72 bg-white">
                Scenario
              </th>
              {sdkOrder.map((sdkId) => (
                <th
                  key={sdkId}
                  className="px-2 py-1 text-center text-xs font-semibold border-l border-gray-200"
                  style={{ color: sdks[sdkId]?.color }}
                >
                  {sdks[sdkId]?.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {categories.map((category) => (
              <React.Fragment key={category.id || category.name}>
                {groupByCategory && (
                  <tr>
                    <td
                      colSpan={columns.length + 1}
                      className="bg-gray-100 px-3 py-1.5 text-xs font-bold text-gray-700 border-t border-gray-200"
                    >
                      {category.name}
                    </td>
                  </tr>
                )}
                {(category.scenarios || []).map((sc) => (
                  <tr
                    key={sc.id}
                    className="border-b border-gray-100 hover:bg-blue-50/30 transition-colors"
                  >
                    <td className="px-3 py-2 align-top">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-sm font-medium text-gray-800">{sc.name}</span>
                      </div>
                      {sc.description && (
                        <div className="text-xs text-gray-500 mt-0.5">{sc.description}</div>
                      )}
                    </td>
                    {columns.map(({ sdkId }) => {
                      const perSdk = sc.sdks?.[sdkId]
                      const cell = resolveCell(perSdk, sdkConnModes[sdkId])
                      return (
                        <td key={sdkId} className="border-l border-gray-200 p-0">
                          <table className="w-full">
                            <tbody>
                              <tr>
                                <Cell sdkId={sdkId} cell={cell} mode={null} />
                              </tr>
                            </tbody>
                          </table>
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 mt-4 text-xs text-gray-600 justify-center">
        {Object.entries(STATUS_CONFIG).map(([key, config]) => (
          <span key={key} className="flex items-center gap-1">
            <span>{config.dot}</span> {config.label}
          </span>
        ))}
      </div>

      {failovers.last_audited && (
        <div className="text-center text-xs text-gray-400 mt-3">
          Curated data last audited: {failovers.last_audited}
        </div>
      )}
    </div>
  )
}

/**
 * Cells may be either flat or keyed by connection mode. If mode-keyed, prefer
 * `direct` when the SDK supports it, else the first declared mode.
 */
function resolveCell(perSdk, sdkMeta) {
  if (!perSdk) return null
  if (perSdk.status !== undefined) return perSdk
  const modes = sdkMeta?.connection_modes || ['gateway']
  const primary = modes.includes('direct') ? 'direct' : modes[0]
  return perSdk[primary] || perSdk[modes[0]] || null
}

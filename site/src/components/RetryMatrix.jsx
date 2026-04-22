import React, { useState } from 'react'

const STATUS_CONFIG = {
  retries: { label: 'Retries', bg: 'bg-green-100', text: 'text-green-800', dot: '🟢' },
  no_retry: { label: 'Fails fast', bg: 'bg-red-100', text: 'text-red-800', dot: '🔴' },
  not_started: { label: 'Not impl.', bg: 'bg-gray-100', text: 'text-gray-500', dot: '⚪' },
  n_a: { label: 'N/A', bg: 'bg-gray-50', text: 'text-gray-400', dot: '➖' },
  unknown: { label: 'Unknown', bg: 'bg-yellow-100', text: 'text-yellow-700', dot: '🟡' },
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
  // ref format: "path/to/file.ext#Lnn"
  const [path, anchor] = ref.split('#')
  const line = anchor ? `#${anchor}` : ''
  return `https://github.com/${repo}/blob/HEAD/${path}${line}`
}

function formatCell(cell) {
  if (!cell) return null
  const bits = []
  if (cell.max_retries !== undefined && cell.max_retries !== null) {
    bits.push(cell.max_retries === 'unbounded' ? '∞×' : `${cell.max_retries}×`)
  }
  if (cell.total_wait_cap_s) {
    bits.push(`${cell.total_wait_cap_s}s cap`)
  }
  if (cell.wait_strategy) {
    bits.push(cell.wait_strategy)
  }
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
        {cell?.cross_region && cell.cross_region !== false && (
          <span
            className="text-[8px] font-normal opacity-70"
            title={`cross-region: ${cell.cross_region}`}
          >
            🌐 {cell.cross_region === true ? 'region' : cell.cross_region}
          </span>
        )}
      </div>
      {(cell?.notes || link) && (
        <div className="absolute z-20 hidden group-hover:block bg-gray-900 text-white text-xs rounded p-2 w-72 -translate-x-1/2 left-1/2 mt-1 shadow-lg text-left normal-case">
          <div className="font-semibold mb-1">
            {STATUS_CONFIG[status]?.label} — {mode}
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

export default function RetryMatrix({ retries, sdks, sdkOrder, filter }) {
  const [groupByCategory, setGroupByCategory] = useState(true)

  if (!retries) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded p-4 text-sm text-yellow-800">
        No retry data available yet. Populate <code>data/retries.yaml</code>.
      </div>
    )
  }

  const sdkConnModes = retries.sdks || {}

  // Build column headers: per SDK, one column per declared connection mode.
  const columns = []
  sdkOrder.forEach((sdkId) => {
    const modes = sdkConnModes[sdkId]?.connection_modes || ['gateway']
    modes.forEach((mode) => {
      columns.push({ sdkId, mode })
    })
  })

  // Group scenarios by category (if the YAML has a `categories:` list) or fall back to a flat list.
  let categories = retries.categories
  if (!categories) {
    categories = [{ name: 'Retry Scenarios', scenarios: retries.scenarios || [] }]
  }

  if (filter === 'gaps') {
    categories = categories
      .map((cat) => ({
        ...cat,
        scenarios: (cat.scenarios || []).filter((sc) => {
          // A "gap" = at least one SDK retries while at least one doesn't (and isn't n_a).
          const statuses = columns.map(({ sdkId, mode }) => {
            const cell = sc.sdks?.[sdkId]?.[mode] || sc.sdks?.[sdkId]
            return cell?.status || 'unknown'
          })
          const anyRetry = statuses.some((s) => s === 'retries')
          const anyFail = statuses.some((s) => s === 'no_retry' || s === 'not_started')
          return anyRetry && anyFail
        }),
      }))
      .filter((cat) => cat.scenarios.length > 0)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs text-gray-500">
          Hover a cell for notes and source pin. Columns are grouped by SDK; direct and gateway
          shown separately when both are supported.
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
              <th
                rowSpan={2}
                className="text-left px-3 py-2 text-sm font-semibold text-gray-600 w-72 bg-white"
              >
                Scenario
              </th>
              {sdkOrder.map((sdkId) => {
                const modes = sdkConnModes[sdkId]?.connection_modes || ['gateway']
                return (
                  <th
                    key={sdkId}
                    colSpan={modes.length}
                    className="px-2 py-1 text-center text-xs font-semibold border-l border-gray-200"
                    style={{ color: sdks[sdkId]?.color }}
                  >
                    {sdks[sdkId]?.name}
                  </th>
                )
              })}
            </tr>
            <tr className="border-b border-gray-200">
              {columns.map(({ sdkId, mode }, i) => (
                <th
                  key={`${sdkId}-${mode}`}
                  className={`px-1 py-1 text-center text-[10px] font-medium text-gray-500 uppercase ${
                    i === 0 || columns[i - 1].sdkId !== sdkId ? 'border-l border-gray-200' : ''
                  }`}
                >
                  {mode}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {categories.map((category) => (
              <React.Fragment key={category.name}>
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
                        {sc.direct_only && (
                          <span
                            className="text-[9px] px-1 rounded bg-indigo-100 text-indigo-700 uppercase"
                            title="Only surfaces in direct/TCP mode"
                          >
                            direct-only
                          </span>
                        )}
                        {(sc.status_code || sc.sub_status) && (
                          <code className="text-[10px] bg-gray-100 text-gray-600 px-1 rounded">
                            {sc.status_code}
                            {sc.sub_status ? `/${sc.sub_status}` : ''}
                          </code>
                        )}
                      </div>
                      {sc.description && (
                        <div className="text-xs text-gray-500 mt-0.5">{sc.description}</div>
                      )}
                    </td>
                    {columns.map(({ sdkId, mode }, i) => {
                      const perSdk = sc.sdks?.[sdkId]
                      // Cell may live at sc.sdks[sdk][mode] OR directly at sc.sdks[sdk] if SDK
                      // only has one mode.
                      const cell =
                        perSdk && (perSdk[mode] !== undefined ? perSdk[mode] : perSdk)
                      const borderLeft =
                        i === 0 || columns[i - 1].sdkId !== sdkId
                          ? 'border-l border-gray-200'
                          : ''
                      return (
                        <td key={`${sdkId}-${mode}`} className={borderLeft + ' p-0'}>
                          <table className="w-full">
                            <tbody>
                              <tr>
                                <Cell sdkId={sdkId} cell={cell} mode={mode} />
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
        <span className="flex items-center gap-1">
          <span className="text-[9px] px-1 rounded bg-indigo-100 text-indigo-700 uppercase">
            direct-only
          </span>{' '}
          only surfaces in direct/TCP mode
        </span>
      </div>

      {retries.last_audited && (
        <div className="text-center text-xs text-gray-400 mt-3">
          Curated data last audited: {retries.last_audited}
        </div>
      )}
    </div>
  )
}

import React, { useMemo, useState } from 'react'

const STATUS_CONFIG = {
  ga: { label: 'GA', bg: 'bg-green-100', text: 'text-green-800', dot: '🟢' },
  preview: { label: 'Preview', bg: 'bg-yellow-100', text: 'text-yellow-800', dot: '🟡' },
  in_progress: { label: 'In Progress', bg: 'bg-blue-100', text: 'text-blue-800', dot: '🔵' },
  planned: { label: 'Planned', bg: 'bg-purple-100', text: 'text-purple-800', dot: '🟣' },
  not_started: { label: 'Not Started', bg: 'bg-gray-100', text: 'text-gray-500', dot: '⚪' },
  removed: { label: 'Removed', bg: 'bg-red-100', text: 'text-red-800', dot: '🔴' },
  n_a: { label: 'N/A', bg: 'bg-gray-50', text: 'text-gray-400', dot: '➖' },
}

const LAGGING_STATUSES = new Set(['not_started', 'in_progress', 'planned'])
const NEAR_GA_STATUSES = new Set(['preview'])

function StatusPill({ status }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.not_started
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${config.bg} ${config.text}`}>
      <span>{config.dot}</span>
      <span>{config.label}</span>
    </span>
  )
}

function SdkPill({ sdk }) {
  if (!sdk) return null
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium text-white"
      style={{ backgroundColor: sdk.color || '#4b5563' }}
    >
      {sdk.name}
    </span>
  )
}

function computeGaps(features, sdkOrder, targetSdk) {
  const rows = []
  if (!features?.categories) return rows
  features.categories.forEach((category, catIdx) => {
    category.features.forEach(feature => {
      const targetStatus = feature.sdks?.[targetSdk]?.status || 'not_started'
      if (!LAGGING_STATUSES.has(targetStatus)) return
      const otherGa = sdkOrder.filter(
        s => s !== targetSdk && feature.sdks?.[s]?.status === 'ga'
      )
      if (otherGa.length === 0) return
      rows.push({
        categoryName: category.name,
        categoryIndex: catIdx,
        feature,
        targetStatus,
        otherGa,
        gaCount: otherGa.length,
      })
    })
  })
  return rows
}

function GapsTable({ rows, sdks, targetSdk }) {
  // Group by category preserving category order.
  const byCategory = []
  const seen = new Map()
  rows.forEach(r => {
    if (!seen.has(r.categoryName)) {
      seen.set(r.categoryName, byCategory.length)
      byCategory.push({ name: r.categoryName, index: r.categoryIndex, items: [] })
    }
    byCategory[seen.get(r.categoryName)].items.push(r)
  })
  byCategory.sort((a, b) => a.index - b.index)
  byCategory.forEach(c => c.items.sort((a, b) => b.gaCount - a.gaCount))

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr className="border-b-2 border-gray-300">
            <th className="text-left px-3 py-2 text-sm font-semibold text-gray-600 w-56">Feature</th>
            <th className="text-left px-3 py-2 text-sm font-semibold text-gray-600">Description</th>
            <th className="px-3 py-2 text-center text-sm font-semibold text-gray-600 whitespace-nowrap">
              {sdks[targetSdk]?.name} status
            </th>
            <th className="px-3 py-2 text-center text-sm font-semibold text-gray-600 whitespace-nowrap">GA on others</th>
            <th className="text-left px-3 py-2 text-sm font-semibold text-gray-600">SDKs at GA</th>
          </tr>
        </thead>
        <tbody>
          {byCategory.map(cat => (
            <React.Fragment key={cat.name}>
              <tr>
                <td colSpan={5} className="bg-gray-100 px-3 py-2 text-sm font-bold text-gray-700 border-t border-gray-200">
                  {cat.name}
                </td>
              </tr>
              {cat.items.map(row => (
                <tr key={row.feature.id} className="border-b border-gray-100 hover:bg-blue-50/30 transition-colors">
                  <td className="px-3 py-2 text-sm font-medium text-gray-800">{row.feature.name}</td>
                  <td className="px-3 py-2 text-xs text-gray-600">{row.feature.description || ''}</td>
                  <td className="px-3 py-2 text-center"><StatusPill status={row.targetStatus} /></td>
                  <td className="px-3 py-2 text-center text-sm font-semibold text-gray-700">{row.gaCount}</td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      {row.otherGa.map(s => <SdkPill key={s} sdk={sdks[s]} />)}
                    </div>
                  </td>
                </tr>
              ))}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function GaReadinessView({ features, sdks, sdkOrder, targetSdk, onTargetSdkChange }) {
  const [copied, setCopied] = useState(false)

  const allGaps = useMemo(
    () => computeGaps(features, sdkOrder, targetSdk),
    [features, sdkOrder, targetSdk]
  )
  const mustHaveGaps = allGaps.filter(r => r.gaCount >= 2)
  const stretchGaps = allGaps.filter(r => r.gaCount === 1)

  const copyPermalink = async () => {
    const url = new URL(window.location.href)
    url.searchParams.set('tab', 'ga-readiness')
    url.searchParams.set('sdk', targetSdk)
    try {
      await navigator.clipboard.writeText(url.toString())
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch (e) {
      // Fallback: update the address bar at least.
      window.history.replaceState({}, '', url)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }
  }

  return (
    <div>
      <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6 shadow-sm">
        <div className="flex flex-wrap items-center gap-3">
          <div>
            <label htmlFor="ga-target-sdk" className="block text-xs font-medium text-gray-500 mb-1">
              Target SDK
            </label>
            <select
              id="ga-target-sdk"
              value={targetSdk}
              onChange={e => onTargetSdkChange(e.target.value)}
              className="border border-gray-300 rounded-md px-3 py-1.5 text-sm bg-white"
            >
              {sdkOrder.map(s => (
                <option key={s} value={s}>{sdks[s]?.name || s}</option>
              ))}
            </select>
          </div>
          <div className="flex-1 min-w-[14rem] text-sm text-gray-600">
            Features where <strong style={{ color: sdks[targetSdk]?.color }}>{sdks[targetSdk]?.name}</strong> is
            not GA yet but other SDKs are — i.e., likely GA-blockers.
          </div>
          <button
            onClick={copyPermalink}
            className="px-3 py-1.5 rounded text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors"
            title="Copy a shareable link to this view"
          >
            {copied ? '✓ Copied' : '🔗 Copy permalink'}
          </button>
        </div>
      </div>

      <section className="mb-8">
        <div className="flex items-baseline justify-between mb-2">
          <h2 className="text-lg font-bold text-gray-800">
            GA-blocker gaps
            <span className="ml-2 text-sm font-normal text-gray-500">
              ({mustHaveGaps.length} feature{mustHaveGaps.length === 1 ? '' : 's'}, ≥2 other SDKs at GA)
            </span>
          </h2>
        </div>
        {mustHaveGaps.length === 0 ? (
          <div className="text-sm text-gray-500 italic border border-dashed border-gray-300 rounded p-4">
            🎉 No GA-blocker gaps for {sdks[targetSdk]?.name}.
          </div>
        ) : (
          <GapsTable rows={mustHaveGaps} sdks={sdks} targetSdk={targetSdk} />
        )}
      </section>

      <section>
        <div className="flex items-baseline justify-between mb-2">
          <h3 className="text-base font-semibold text-gray-700">
            Stretch gaps
            <span className="ml-2 text-xs font-normal text-gray-500">
              ({stretchGaps.length} feature{stretchGaps.length === 1 ? '' : 's'}, only 1 other SDK at GA)
            </span>
          </h3>
        </div>
        {stretchGaps.length === 0 ? (
          <div className="text-xs text-gray-500 italic border border-dashed border-gray-300 rounded p-3">
            No stretch gaps for {sdks[targetSdk]?.name}.
          </div>
        ) : (
          <GapsTable rows={stretchGaps} sdks={sdks} targetSdk={targetSdk} />
        )}
      </section>
    </div>
  )
}

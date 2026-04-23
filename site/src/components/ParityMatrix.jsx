import React from 'react'

const STATUS_CONFIG = {
  ga: { label: 'GA', bg: 'bg-green-100', text: 'text-green-800', dot: '🟢' },
  preview: { label: 'Preview', bg: 'bg-yellow-100', text: 'text-yellow-800', dot: '🟡' },
  in_progress: { label: 'In Progress', bg: 'bg-blue-100', text: 'text-blue-800', dot: '🔵' },
  planned: { label: 'Planned', bg: 'bg-purple-100', text: 'text-purple-800', dot: '🟣' },
  not_started: { label: 'Not Started', bg: 'bg-gray-100', text: 'text-gray-500', dot: '⚪' },
  removed: { label: 'Removed', bg: 'bg-red-100', text: 'text-red-800', dot: '🔴' },
  n_a: { label: 'N/A', bg: 'bg-gray-50', text: 'text-gray-400', dot: '➖' },
}

const OPT_IN_LABELS = {
  cargo_feature: 'Cargo feature',
  system_property: 'System property',
  separate_package: 'Separate package',
  env_var: 'Environment variable',
  preview_flag: 'Preview flag',
}

const TIER_CONFIG = {
  ga_blocker: {
    label: 'GA blocker',
    bg: 'bg-rose-100',
    text: 'text-rose-800',
    border: 'border-rose-300',
    icon: '🚧',
    description: 'Must ship before this SDK goes GA',
  },
  post_ga: {
    label: 'Post-GA',
    bg: 'bg-slate-100',
    text: 'text-slate-700',
    border: 'border-slate-300',
    icon: '⏭️',
    description: 'Intentionally deferred past GA',
  },
  nice_to_have: {
    label: 'Nice-to-have',
    bg: 'bg-sky-50',
    text: 'text-sky-700',
    border: 'border-sky-200',
    icon: '✨',
    description: 'Low-priority; not blocking any milestone',
  },
}

function TierBadge({ tier }) {
  if (!tier) return null
  const config = TIER_CONFIG[tier]
  if (!config) return null
  return (
    <span
      title={`${config.label} — ${config.description}`}
      aria-label={`Tier: ${config.label}`}
      className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-medium border ${config.bg} ${config.text} ${config.border} cursor-help`}
    >
      <span>{config.icon}</span>
      <span>{config.label}</span>
    </span>
  )
}

function IssueLinks({ issues, issuesIndex }) {
  if (!issues || issues.length === 0) return null
  return (
    <div className="inline-flex flex-wrap gap-0.5 align-middle">
      {issues.map((issue, idx) => {
        const m = /github\.com\/[^/]+\/[^/]+\/(?:issues|pull)\/(\d+)/.exec(issue.url || '')
        const label = m ? `#${m[1]}` : '🐛'
        const live = issuesIndex?.[issue.url]
        const title = live?.title || issue.title
        const state = live?.state
        // Prefer live state when available; fall back to neutral styling.
        let icon = '🐛'
        let stateClass = 'bg-indigo-50 text-indigo-700 border-indigo-200 hover:bg-indigo-100'
        if (state === 'open') {
          icon = '🟢'
          stateClass = 'bg-green-50 text-green-800 border-green-300 hover:bg-green-100'
        } else if (state === 'closed') {
          const reason = live?.state_reason
          if (reason === 'not_planned') {
            icon = '⚫'
            stateClass = 'bg-gray-100 text-gray-600 border-gray-300 hover:bg-gray-200'
          } else {
            icon = '🟣'
            stateClass = 'bg-purple-50 text-purple-800 border-purple-300 hover:bg-purple-100'
          }
        }
        const stateLabel = state ? ` [${state}${live?.state_reason ? `: ${live.state_reason}` : ''}]` : ''
        const tip = title ? `${label}${stateLabel}: ${title}` : (issue.url + stateLabel)
        return (
          <a
            key={idx}
            href={issue.url}
            target="_blank"
            rel="noopener noreferrer"
            title={tip}
            onClick={e => e.stopPropagation()}
            className={`inline-flex items-center px-1 py-0 rounded text-[10px] font-medium border ${stateClass}`}
          >
            {icon} {label}
          </a>
        )
      })}
    </div>
  )
}

function StatusCell({ sdkFeature, issuesIndex }) {
  const status = sdkFeature?.status || 'not_started'
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.not_started
  const since = sdkFeature?.since
  const notes = sdkFeature?.notes
  const requiresOptIn = sdkFeature?.requires_opt_in
  const optInName = sdkFeature?.opt_in_name
  const publicApi = sdkFeature?.public_api
  const isInternalOnly = publicApi === false
  const tier = sdkFeature?.tier
  const issues = Array.isArray(sdkFeature?.issues) ? sdkFeature.issues : []

  const optInLabel = requiresOptIn ? (OPT_IN_LABELS[requiresOptIn] || requiresOptIn) : null
  const badgeTitle = [
    optInLabel && `Opt-in: ${optInLabel}${optInName ? ` (${optInName})` : ''}`,
    isInternalOnly && 'Internal-only API',
  ].filter(Boolean).join(' · ')

  const hasTooltip = notes || requiresOptIn || isInternalOnly || tier

  return (
    <td className="px-2 py-2 text-center group relative">
      <div className="inline-flex items-center gap-1">
        <div className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${config.bg} ${config.text}`}>
          <span>{config.dot}</span>
          <span>{config.label}</span>
        </div>
        {(requiresOptIn || isInternalOnly) && (
          <span
            role="img"
            aria-label={badgeTitle}
            title={badgeTitle}
            className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-amber-100 text-amber-800 text-[10px] leading-none border border-amber-300 cursor-help"
          >
            {isInternalOnly && !requiresOptIn ? '🔒' : '⚑'}
          </span>
        )}
      </div>
      {tier && (
        <div className="mt-1 flex justify-center">
          <TierBadge tier={tier} />
        </div>
      )}
      {since && (
        <div className="text-[10px] text-gray-400 mt-0.5">v{since}</div>
      )}
      {issues.length > 0 && (
        <div className="mt-1 flex justify-center">
          <IssueLinks issues={issues} issuesIndex={issuesIndex} />
        </div>
      )}
      {hasTooltip && (
        <div className="absolute z-10 hidden group-hover:block bg-gray-900 text-white text-xs rounded p-2 max-w-xs -translate-x-1/2 left-1/2 mt-1 shadow-lg text-left">
          {tier && TIER_CONFIG[tier] && (
            <div className="mb-1">
              <span className="font-semibold">Tier:</span> {TIER_CONFIG[tier].label}
              <div className="text-[10px] text-gray-300">{TIER_CONFIG[tier].description}</div>
            </div>
          )}
          {optInLabel && (
            <div className="mb-1">
              <span className="font-semibold">Opt-in:</span> {optInLabel}
              {optInName && <div className="font-mono text-[10px] break-all">{optInName}</div>}
            </div>
          )}
          {isInternalOnly && (
            <div className="mb-1"><span className="font-semibold">Internal-only</span> (not public API)</div>
          )}
          {notes && <div>{notes}</div>}
        </div>
      )}
    </td>
  )
}

export default function ParityMatrix({ features, sdks, sdkOrder, filter, issuesIndex }) {
  if (!features?.categories) return null

  const filteredCategories = features.categories.map(category => {
    if (filter === 'all') return category

    const filteredFeatures = category.features.filter(feat => {
      if (filter === 'gaps') {
        // A feature is a "gap" if at least one SDK has shipped (ga/preview)
        // and at least one other SDK has NOT shipped. `in_progress` counts
        // as "not shipped" — without it, a .NET-only in-progress feature
        // would vanish from the Gaps view, making in-progress work invisible.
        const statuses = sdkOrder.map(sdk => feat.sdks?.[sdk]?.status || 'not_started')
        const hasGa = statuses.some(s => s === 'ga' || s === 'preview')
        const hasMissing = statuses.some(s => s === 'not_started' || s === 'planned' || s === 'in_progress')
        return hasGa && hasMissing
      }
      return true
    })

    return { ...category, features: filteredFeatures }
  }).filter(cat => cat.features.length > 0)

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr className="border-b-2 border-gray-300">
            <th className="text-left px-3 py-2 text-sm font-semibold text-gray-600 w-64">Feature</th>
            {sdkOrder.map(sdkId => (
              <th key={sdkId} className="px-2 py-2 text-center text-sm font-semibold" style={{ color: sdks[sdkId]?.color }}>
                {sdks[sdkId]?.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filteredCategories.map(category => (
            <React.Fragment key={category.name}>
              <tr>
                <td colSpan={sdkOrder.length + 1} className="bg-gray-100 px-3 py-2 text-sm font-bold text-gray-700 border-t border-gray-200">
                  {category.name}
                </td>
              </tr>
              {category.features.map(feature => (
                <tr key={feature.id} className="border-b border-gray-100 hover:bg-blue-50/30 transition-colors">
                  <td className="px-3 py-2">
                    <div className="text-sm font-medium text-gray-800">{feature.name}</div>
                    {feature.description && (
                      <div className="text-xs text-gray-500 mt-0.5">{feature.description}</div>
                    )}
                  </td>
                  {sdkOrder.map(sdkId => (
                    <StatusCell key={sdkId} sdkFeature={feature.sdks?.[sdkId]} issuesIndex={issuesIndex} />
                  ))}
                </tr>
              ))}
            </React.Fragment>
          ))}
        </tbody>
      </table>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 mt-4 text-xs text-gray-600 justify-center">
        {Object.entries(STATUS_CONFIG).map(([key, config]) => (
          <span key={key} className="flex items-center gap-1">
            <span>{config.dot}</span> {config.label}
          </span>
        ))}
      </div>
    </div>
  )
}

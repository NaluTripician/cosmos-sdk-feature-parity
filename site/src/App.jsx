import React, { useState, useEffect } from 'react'
import yaml from 'js-yaml'
import ParityMatrix from './components/ParityMatrix.jsx'
import ParityStats from './components/ParityStats.jsx'
import SdkHeader from './components/SdkHeader.jsx'
import RetryMatrix from './components/RetryMatrix.jsx'
import RetryStats from './components/RetryStats.jsx'
import FailoverMatrix from './components/FailoverMatrix.jsx'
import FailoverStats from './components/FailoverStats.jsx'
import RecentPrs from './components/RecentPrs.jsx'
import GaReadinessView from './components/GaReadinessView.jsx'

const SDK_ORDER = ['dotnet', 'java', 'python', 'go', 'rust']
const VALID_TABS = new Set(['features', 'retries', 'failovers', 'recent', 'ga-readiness'])

function readInitialUrlState() {
  if (typeof window === 'undefined') return { tab: 'features', sdk: 'rust' }
  const params = new URLSearchParams(window.location.search)
  const tab = params.get('tab')
  const sdk = params.get('sdk')
  return {
    tab: VALID_TABS.has(tab) ? tab : 'features',
    sdk: SDK_ORDER.includes(sdk) ? sdk : 'rust',
  }
}

export default function App() {
  const [features, setFeatures] = useState(null)
  const [sdks, setSdks] = useState(null)
  const [retries, setRetries] = useState(null)
  const [failovers, setFailovers] = useState(null)
  const [scrapeData, setScrapeData] = useState(null)
  const [lastRun, setLastRun] = useState(null)
  const [recentPrs, setRecentPrs] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('all') // all, gaps
  const initialUrl = readInitialUrlState()
  const [tab, setTab] = useState(initialUrl.tab) // features, retries, failovers, ga-readiness
  const [gaTargetSdk, setGaTargetSdk] = useState(initialUrl.sdk)

  useEffect(() => {
    if (typeof window === 'undefined') return
    const params = new URLSearchParams(window.location.search)
    params.set('tab', tab)
    if (tab === 'ga-readiness') {
      params.set('sdk', gaTargetSdk)
    } else {
      params.delete('sdk')
    }
    const newUrl = `${window.location.pathname}?${params.toString()}${window.location.hash}`
    window.history.replaceState({}, '', newUrl)
  }, [tab, gaTargetSdk])

  useEffect(() => {
    async function loadData() {
      try {
        const base = import.meta.env.BASE_URL
        const [featuresResp, sdksResp] = await Promise.all([
          fetch(`${base}data/features.yaml`),
          fetch(`${base}data/sdks.yaml`),
        ])
        const featuresText = await featuresResp.text()
        const sdksText = await sdksResp.text()
        setFeatures(yaml.load(featuresText))
        setSdks(yaml.load(sdksText).sdks)

        // retries.yaml is optional while the audit is in flight.
        try {
          const retriesResp = await fetch(`${base}data/retries.yaml`)
          if (retriesResp.ok) {
            const retriesText = await retriesResp.text()
            setRetries(yaml.load(retriesText))
          }
        } catch (e) {
          // optional
        }

        // failovers.yaml is optional while the audit is in flight.
        try {
          const failoversResp = await fetch(`${base}data/failovers.yaml`)
          if (failoversResp.ok) {
            const failoversText = await failoversResp.text()
            setFailovers(yaml.load(failoversText))
          }
        } catch (e) {
          // optional
        }

        // Try to load scrape data (may not exist yet)
        try {
          const scrapeResp = await fetch(`${base}data/scraped/latest.json`)
          if (scrapeResp.ok) {
            setScrapeData(await scrapeResp.json())
          }
        } catch (e) {
          // Scrape data is optional
        }

        // Try to load last-successful-run heartbeat written by the weekly workflow.
        try {
          const lastRunResp = await fetch(`${base}data/scraped/last_successful_run.json`)
          if (lastRunResp.ok) {
            setLastRun(await lastRunResp.json())
          }
        } catch (e) {
          // Heartbeat is optional
        }

        // Try to load recent-PRs data (may not exist yet)
        try {
          const prsResp = await fetch(`${base}data/scraped/recent_prs_latest.json`)
          if (prsResp.ok) {
            setRecentPrs(await prsResp.json())
          }
        } catch (e) {
          // Optional
        }

        setLoading(false)
      } catch (e) {
        setError(e.message)
        setLoading(false)
      }
    }
    loadData()
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-lg text-gray-500">Loading feature parity data...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-lg text-red-500">Error: {error}</div>
      </div>
    )
  }

  const computeStats = () => {
    const stats = {}
    SDK_ORDER.forEach(sdk => {
      stats[sdk] = { ga: 0, preview: 0, in_progress: 0, not_started: 0, total: 0, n_a: 0 }
    })
    features.categories.forEach(cat => {
      cat.features.forEach(feat => {
        SDK_ORDER.forEach(sdk => {
          const status = feat.sdks?.[sdk]?.status || 'not_started'
          stats[sdk].total++
          if (status in stats[sdk]) stats[sdk][status]++
        })
      })
    })
    return stats
  }

  const stats = computeStats()

  const lastRunBadge = (() => {
    if (!lastRun) return null
    const timestampStr = lastRun.timestamp || lastRun.run_started_at
    if (!timestampStr) return null
    const started = new Date(timestampStr)
    if (Number.isNaN(started.getTime())) return null
    const ageMs = Date.now() - started.getTime()
    const ageDays = ageMs / (1000 * 60 * 60 * 24)
    const stale = ageDays > 10
    const failed = lastRun.success === false
    const failedScrapers = Array.isArray(lastRun.failed_scrapers) ? lastRun.failed_scrapers : []

    const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
    let relative
    if (ageDays < 1) {
      const hours = Math.round(ageMs / (1000 * 60 * 60))
      relative = rtf.format(-hours, 'hour')
    } else {
      relative = rtf.format(-Math.round(ageDays), 'day')
    }

    let classes
    let icon
    let title
    let label
    if (failed) {
      classes = 'bg-red-600 text-red-50'
      icon = '🛑 '
      const list = failedScrapers.length ? failedScrapers.join(', ') : 'unknown'
      title = `Last weekly run failed — broken scrapers: ${list}. Ran ${started.toUTCString()}.`
      label = `Scrapers failing (${failedScrapers.length || '?'})`
    } else if (stale) {
      classes = 'bg-amber-500 text-amber-950'
      icon = '⚠️ '
      title = 'Weekly refresh may be stale — check Actions'
      label = `Last updated ${relative}`
    } else {
      classes = 'bg-blue-800/60 text-blue-100'
      icon = '🟢 '
      title = `Last successful workflow run: ${started.toUTCString()}`
      label = `Last updated ${relative}`
    }

    return (
      <span
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium mt-2 ${classes}`}
        title={title}
      >
        {icon}{label}
      </span>
    )
  })()

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-gradient-to-r from-blue-900 to-indigo-900 text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 py-6 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">🌍 Cosmos DB SDK Feature Parity</h1>
            <p className="text-blue-200 mt-1">
              Tracking feature support across .NET, Java, Python, Go, and Rust SDKs
            </p>
            {lastRunBadge}
            {scrapeData && (
              <p className="text-blue-300 text-sm mt-1">
                Last updated: {new Date(scrapeData.scraped_at).toLocaleDateString()}
              </p>
            )}
          </div>
          <a
            href="./CONTRIBUTING.md"
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 inline-flex items-center gap-1 bg-white/10 hover:bg-white/20 border border-white/30 text-white text-sm font-medium px-3 py-1.5 rounded-md transition-colors"
            title="How to contribute edits to the parity matrices"
          >
            ✏️ Contribute
          </a>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* SDK Overview Cards */}
        <div className="grid grid-cols-5 gap-3 mb-6">
          {SDK_ORDER.map(sdkId => (
            <SdkHeader
              key={sdkId}
              sdk={sdks[sdkId]}
              stats={stats[sdkId]}
              scrapeData={scrapeData?.sdks?.[sdkId]}
            />
          ))}
        </div>

        {/* Tab bar */}
        <div className="border-b border-gray-200 mb-4">
          <nav className="flex gap-1" aria-label="Tabs">
            {[
              { id: 'features', label: '📋 Features' },
              { id: 'retries', label: '🔁 Retries' },
              { id: 'failovers', label: '🌐 Failovers' },
              { id: 'recent', label: '🆕 Recent Activity' },
              { id: 'ga-readiness', label: '🚀 GA Readiness' },
            ].map(t => (
              <button
                key={t.id}
                role="tab"
                aria-selected={tab === t.id}
                aria-controls={`${t.id}-panel`}
                id={`${t.id}-tab`}
                onClick={() => setTab(t.id)}
                className={`px-4 py-2 text-sm font-medium rounded-t-md -mb-px border-b-2 transition-colors ${
                  tab === t.id
                    ? 'border-blue-600 text-blue-700 bg-white'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>

        {tab === 'features' && (
          <>
            <ParityStats stats={stats} sdks={sdks} sdkOrder={SDK_ORDER} />

            <div className="flex gap-2 mb-4 mt-6">
              <button
                onClick={() => setFilter('all')}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                  filter === 'all'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                All Features
              </button>
              <button
                onClick={() => setFilter('gaps')}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                  filter === 'gaps'
                    ? 'bg-orange-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                🔍 Show Gaps Only
              </button>
            </div>

            <ParityMatrix
              features={features}
              sdks={sdks}
              sdkOrder={SDK_ORDER}
              filter={filter}
            />
          </>
        )}

        {tab === 'retries' && (
          <>
            <RetryStats retries={retries} sdks={sdks} sdkOrder={SDK_ORDER} />

            <div className="flex gap-2 mb-4 mt-6">
              <button
                onClick={() => setFilter('all')}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                  filter === 'all'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                All Scenarios
              </button>
              <button
                onClick={() => setFilter('gaps')}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                  filter === 'gaps'
                    ? 'bg-orange-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                🔍 Divergent Only
              </button>
            </div>

            <RetryMatrix
              retries={retries}
              sdks={sdks}
              sdkOrder={SDK_ORDER}
              filter={filter}
            />
          </>
        )}

        {tab === 'recent' && (
          <RecentPrs data={recentPrs} sdks={sdks} />
        )}

        {tab === 'failovers' && (
          <>
            <FailoverStats failovers={failovers} sdks={sdks} sdkOrder={SDK_ORDER} />

            <div className="flex gap-2 mb-4 mt-6">
              <button
                onClick={() => setFilter('all')}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                  filter === 'all'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                All Scenarios
              </button>
              <button
                onClick={() => setFilter('gaps')}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                  filter === 'gaps'
                    ? 'bg-orange-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                🔍 Divergent Only
              </button>
            </div>

            <FailoverMatrix
              failovers={failovers}
              sdks={sdks}
              sdkOrder={SDK_ORDER}
              filter={filter}
            />
          </>
        )}

        {tab === 'ga-readiness' && (
          <GaReadinessView
            features={features}
            sdks={sdks}
            sdkOrder={SDK_ORDER}
            targetSdk={gaTargetSdk}
            onTargetSdkChange={setGaTargetSdk}
          />
        )}
      </main>

      <footer className="border-t mt-12 py-6 text-center text-sm text-gray-500">
        Data sourced from SDK changelogs and pinned source files. Edit{' '}
        <code className="bg-gray-100 px-1 rounded">data/features.yaml</code>,{' '}
        <code className="bg-gray-100 px-1 rounded">data/retries.yaml</code>, or{' '}
        <code className="bg-gray-100 px-1 rounded">data/failovers.yaml</code>{' '}
        to update.
      </footer>
    </div>
  )
}

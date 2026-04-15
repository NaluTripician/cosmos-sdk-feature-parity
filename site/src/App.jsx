import React, { useState, useEffect } from 'react'
import yaml from 'js-yaml'
import ParityMatrix from './components/ParityMatrix.jsx'
import ParityStats from './components/ParityStats.jsx'
import SdkHeader from './components/SdkHeader.jsx'

const SDK_ORDER = ['dotnet', 'java', 'python', 'go', 'rust']

export default function App() {
  const [features, setFeatures] = useState(null)
  const [sdks, setSdks] = useState(null)
  const [scrapeData, setScrapeData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('all') // all, gaps, recent

  useEffect(() => {
    async function loadData() {
      try {
        const [featuresResp, sdksResp] = await Promise.all([
          fetch('/data/features.yaml'),
          fetch('/data/sdks.yaml'),
        ])
        const featuresText = await featuresResp.text()
        const sdksText = await sdksResp.text()
        setFeatures(yaml.load(featuresText))
        setSdks(yaml.load(sdksText).sdks)

        // Try to load scrape data (may not exist yet)
        try {
          const scrapeResp = await fetch('/data/scraped/latest.json')
          if (scrapeResp.ok) {
            setScrapeData(await scrapeResp.json())
          }
        } catch (e) {
          // Scrape data is optional
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

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-gradient-to-r from-blue-900 to-indigo-900 text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <h1 className="text-2xl font-bold">🌍 Cosmos DB SDK Feature Parity</h1>
          <p className="text-blue-200 mt-1">
            Tracking feature support across .NET, Java, Python, Go, and Rust SDKs
          </p>
          {scrapeData && (
            <p className="text-blue-300 text-sm mt-1">
              Last updated: {new Date(scrapeData.scraped_at).toLocaleDateString()}
            </p>
          )}
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

        {/* Parity Summary Bar */}
        <ParityStats stats={stats} sdks={sdks} sdkOrder={SDK_ORDER} />

        {/* Filter Controls */}
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

        {/* Feature Parity Matrix */}
        <ParityMatrix
          features={features}
          sdks={sdks}
          sdkOrder={SDK_ORDER}
          filter={filter}
        />
      </main>

      <footer className="border-t mt-12 py-6 text-center text-sm text-gray-500">
        Data sourced from SDK changelogs. Edit{' '}
        <code className="bg-gray-100 px-1 rounded">data/features.yaml</code>{' '}
        to update.
      </footer>
    </div>
  )
}

import React from 'react'

const SDK_ORDER = ['dotnet', 'java', 'python', 'go', 'rust']

function formatDate(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return iso.slice(0, 10)
  }
}

export default function RecentPrs({ data, sdks }) {
  if (!data) {
    return (
      <div className="bg-white rounded-lg border p-6 text-gray-500">
        No recent-PR data available yet. Run{' '}
        <code className="bg-gray-100 px-1 rounded">scripts/fetch_recent_prs.py</code>{' '}
        to generate it.
      </div>
    )
  }

  const bySdk = data.by_sdk || {}
  const windowDays = data.window_days ?? 14

  return (
    <div className="space-y-4">
      <div className="text-sm text-gray-600">
        Merged PRs touching each SDK's Cosmos subtree in the last {windowDays} days.
        {data.generated_at && (
          <span className="ml-2 text-gray-400">
            (generated {new Date(data.generated_at).toLocaleString()})
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {SDK_ORDER.map(sdkId => {
          const sdk = sdks?.[sdkId]
          const prs = bySdk[sdkId] || []
          if (!sdk) return null
          return (
            <div key={sdkId} className="bg-white rounded-lg shadow-sm border">
              <div
                className="flex items-center gap-2 px-4 py-2 border-b"
                style={{ borderLeft: `4px solid ${sdk.color}` }}
              >
                <h3 className="font-bold text-sm">{sdk.name}</h3>
                <span className="text-xs text-gray-500">
                  {prs.length} PR{prs.length === 1 ? '' : 's'}
                </span>
                <a
                  href={`https://github.com/${sdk.repo}`}
                  target="_blank"
                  rel="noreferrer"
                  className="ml-auto text-xs text-blue-600 hover:underline"
                >
                  {sdk.repo}
                </a>
              </div>

              {prs.length === 0 ? (
                <div className="px-4 py-4 text-sm text-gray-500">
                  No merged PRs in Cosmos paths in last {windowDays} days
                </div>
              ) : (
                <ul className="divide-y">
                  {prs.map(pr => (
                    <li key={pr.number} className="px-4 py-2 text-sm">
                      <a
                        href={pr.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-blue-700 hover:underline font-medium"
                      >
                        #{pr.number}
                      </a>{' '}
                      <span className="text-gray-800">{pr.title}</span>
                      <div className="text-xs text-gray-500 mt-0.5">
                        {pr.author && <>by {pr.author} · </>}
                        merged {formatDate(pr.merged_at)}
                        {pr.labels && pr.labels.length > 0 && (
                          <span className="ml-2">
                            {pr.labels.slice(0, 4).map(l => (
                              <span
                                key={l}
                                className="inline-block bg-gray-100 text-gray-600 rounded px-1.5 py-0.5 mr-1 text-[10px]"
                              >
                                {l}
                              </span>
                            ))}
                          </span>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

/**
 * Copy data files from the repo root into the site's public directory
 * so they're accessible at runtime via fetch().
 */
const fs = require('fs')
const path = require('path')

const dataDir = path.resolve(__dirname, '../../data')
const publicDataDir = path.resolve(__dirname, '../public/data')

function copyRecursive(src, dest) {
  if (!fs.existsSync(src)) return

  if (fs.statSync(src).isDirectory()) {
    fs.mkdirSync(dest, { recursive: true })
    for (const entry of fs.readdirSync(src)) {
      copyRecursive(path.join(src, entry), path.join(dest, entry))
    }
  } else {
    fs.copyFileSync(src, dest)
  }
}

// Create public/data and copy
fs.mkdirSync(publicDataDir, { recursive: true })

// Copy key data files
const filesToCopy = ['features.yaml', 'sdks.yaml', 'retries.yaml', 'failovers.yaml']
for (const file of filesToCopy) {
  const src = path.join(dataDir, file)
  if (fs.existsSync(src)) {
    fs.copyFileSync(src, path.join(publicDataDir, file))
    console.log(`Copied ${file}`)
  }
}

// Copy last_successful_run.json heartbeat if it exists (written by the
// weekly update-parity workflow so the site can surface freshness).
const heartbeatSrc = path.join(dataDir, 'scraped', 'last_successful_run.json')
if (fs.existsSync(heartbeatSrc)) {
  const heartbeatDestDir = path.join(publicDataDir, 'scraped')
  fs.mkdirSync(heartbeatDestDir, { recursive: true })
  fs.copyFileSync(heartbeatSrc, path.join(heartbeatDestDir, 'last_successful_run.json'))
  console.log('Copied scraped/last_successful_run.json')
}

// Copy scraped directory if it exists
const scrapedSrc = path.join(dataDir, 'scraped')
const scrapedDest = path.join(publicDataDir, 'scraped')
if (fs.existsSync(scrapedSrc)) {
  copyRecursive(scrapedSrc, scrapedDest)
  console.log('Copied scraped/')
}

// Copy history directory if it exists
const historySrc = path.join(dataDir, 'history')
const historyDest = path.join(publicDataDir, 'history')
if (fs.existsSync(historySrc)) {
  copyRecursive(historySrc, historyDest)
  console.log('Copied history/')
}

console.log('Data files copied to public/data/')

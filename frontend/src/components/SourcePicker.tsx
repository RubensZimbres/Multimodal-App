import { useId, useState } from 'react'
import { uploadFile } from '../lib/api'
import type { DemoAsset, MediaRef } from '../lib/types'

interface Props {
  demo?: DemoAsset
  accept: string
  value: MediaRef | null
  onChange: (media: MediaRef | null) => void
  uploadsEnabled: boolean
}

function Preview({ asset }: { asset: DemoAsset }) {
  if (asset.mime_type.startsWith('image/')) return <img src={asset.preview_url} alt={asset.title} />
  if (asset.mime_type.startsWith('video/')) return <video src={asset.preview_url} controls preload="metadata" />
  return (
    <a href={asset.preview_url} target="_blank" rel="noopener noreferrer">
      Open {asset.title} ↗
    </a>
  )
}

export function SourcePicker({ demo, accept, value, onChange, uploadsEnabled }: Props) {
  const name = useId()
  // The demo manifest loads asynchronously, so default to it until the user chooses.
  const [choice, setMode] = useState<'demo' | 'upload' | null>(null)
  const mode = choice ?? (demo ? 'demo' : 'upload')
  const [uploading, setUploading] = useState(false)
  const [fileName, setFileName] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const pickDemo = () => {
    setMode('demo')
    onChange(demo ? { uri: demo.uri, mime_type: demo.mime_type } : null)
  }

  const pickFile = async (file: File | undefined) => {
    if (!file) return
    setError(null)
    setUploading(true)
    setFileName(file.name)
    onChange(null)
    try {
      onChange(await uploadFile(file))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setFileName(null)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="source">
      <div className="segmented" role="radiogroup">
        {demo && (
          <label>
            <input type="radio" name={name} checked={mode === 'demo'} onChange={pickDemo} />
            Demo file
          </label>
        )}
        <label className={uploadsEnabled ? '' : 'disabled'}>
          <input
            type="radio"
            name={name}
            checked={mode === 'upload'}
            disabled={!uploadsEnabled}
            onChange={() => {
              setMode('upload')
              onChange(null)
            }}
          />
          Upload your own
        </label>
      </div>

      {mode === 'demo' && demo && (
        <div className="preview">
          <Preview asset={demo} />
          <small>{demo.title}</small>
        </div>
      )}
      {mode === 'upload' && (
        <div className="upload">
          <input
            type="file"
            accept={accept}
            aria-label="Choose file"
            disabled={uploading}
            onChange={(e) => pickFile(e.target.files?.[0])}
          />
          {uploading && <small>Uploading {fileName}…</small>}
          {!uploading && value && fileName && <small>✓ {fileName} uploaded</small>}
          {error && <small className="error-text">{error}</small>}
        </div>
      )}
    </div>
  )
}

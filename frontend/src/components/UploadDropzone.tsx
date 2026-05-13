import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'

interface Props {
  onDrop: (file: File) => void
  loading: boolean
}

export default function UploadDropzone({ onDrop, loading }: Props) {
  const handleDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) onDrop(acceptedFiles[0])
    },
    [onDrop]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: handleDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    disabled: loading,
  })

  return (
    <div
      {...getRootProps()}
      className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors
        ${isDragActive ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'}
        ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      <input {...getInputProps()} />
      <div className="text-4xl mb-3">📄</div>
      {loading ? (
        <p className="text-blue-600 font-medium">Uploading…</p>
      ) : isDragActive ? (
        <p className="text-blue-600 font-medium">Drop your PDF here</p>
      ) : (
        <>
          <p className="text-gray-600 font-medium">Drag & drop a PDF, or click to select</p>
          <p className="text-xs text-gray-400 mt-1">PDF only · Max 20 MB</p>
        </>
      )}
    </div>
  )
}

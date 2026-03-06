export default function LoadingSpinner() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="flex flex-col items-center space-y-4">
        <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-discord-blue"></div>
        <p className="text-gray-400">Loading...</p>
      </div>
    </div>
  )
}

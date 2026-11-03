import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileQuestion } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function NotFoundPage() {
  const navigate = useNavigate()

  useEffect(() => {
    document.title = 'Page Not Found - Cloud Notes'
  }, [])
  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--background)] px-6">
      <div className="max-w-sm text-center space-y-6">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-[var(--accent-soft)]">
          <FileQuestion className="h-8 w-8 text-[var(--accent)]" strokeWidth={1.75} />
        </div>
        <div className="space-y-2">
          <h1 className="text-4xl font-bold text-[var(--foreground)]">404</h1>
          <h2 className="text-lg font-semibold text-[var(--foreground)]">Page not found</h2>
          <p className="text-sm text-[var(--muted-foreground)]">
            The page you're looking for doesn't exist or has been moved.
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:justify-center">
          <Button onClick={() => navigate('/app')}>Go to notes</Button>
          <Button variant="outline" onClick={() => navigate(-1)}>Go back</Button>
        </div>
      </div>
    </div>
  )
}

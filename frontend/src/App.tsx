import { lazy, Suspense, useEffect, useState } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { LandingPage } from './components/Landing/LandingPage'
import { config } from './lib/config'
import type { MatchResponse } from './lib/api'

/* Route-level code splitting: Landing (the first paint) stays eager; every
   other surface — and the floating chat — loads on demand, which also defers
   the ~217 kB Supabase SDK chunk until a signed-in surface actually needs it
   (App and Landing reach it through the dynamic imports below). */
const AssessmentPage = lazy(() =>
  import('./components/Assessment/AssessmentPage').then((m) => ({ default: m.AssessmentPage }))
)
const ChatWidget = lazy(() =>
  import('./components/Chat/ChatWidget').then((m) => ({ default: m.ChatWidget }))
)
const DashboardRoute = lazy(() =>
  import('./components/Dashboard/DashboardRoute').then((m) => ({ default: m.DashboardRoute }))
)
const LoginPage = lazy(() =>
  import('./components/Login/LoginPage').then((m) => ({ default: m.LoginPage }))
)
const SignUpPage = lazy(() =>
  import('./components/Login/SignUpPage').then((m) => ({ default: m.SignUpPage }))
)
const ProgressPage = lazy(() =>
  import('./components/Progress/ProgressPage').then((m) => ({ default: m.ProgressPage }))
)
const QuestionsPage = lazy(() =>
  import('./components/Questions/QuestionsPage').then((m) => ({ default: m.QuestionsPage }))
)
const ResultsPage = lazy(() =>
  import('./components/Results/ResultsPage').then((m) => ({ default: m.ResultsPage }))
)

interface ResultsLocationState {
  matchData?: MatchResponse
}

function RouteLoading() {
  return (
    <div className="route-loading" role="status" aria-live="polite">
      <div className="loading-spinner" />
    </div>
  )
}

function ResultsRoute() {
  const location = useLocation()
  const navigate = useNavigate()
  const state = (location.state ?? {}) as ResultsLocationState

  return (
    <ResultsPage
      matchData={state.matchData ?? null}
      onBackToHome={() => navigate('/')}
      onEditAssessment={() => navigate('/assessment')}
      onExplorePath={(recommendation) => {
        navigate(`/dashboard/${recommendation.role_id}`, {
          state: {
            roleTitle: recommendation.role_title,
            skillReadiness: recommendation.score_breakdown.skill_readiness,
          },
        })
        window.scrollTo({ top: 0, behavior: 'smooth' })
      }}
    />
  )
}

function App() {
  const navigate = useNavigate()
  const [userEmail, setUserEmail] = useState<string | null>(null)

  useEffect(() => {
    if (!config.hasSupabaseAuth) return
    let cancelled = false
    let unsubscribe: (() => void) | undefined

    // Deferred import: auth restore needs the SDK, but not before first paint.
    void import('./lib/supabase').then(({ supabase }) => {
      if (cancelled || !supabase) return

      supabase.auth.getSession().then(({ data: { session } }) => {
        if (!cancelled && session?.user?.email) {
          setUserEmail(session.user.email)
        }
      })

      const {
        data: { subscription },
      } = supabase.auth.onAuthStateChange((_event, session) => {
        setUserEmail(session?.user?.email ?? null)
      })
      unsubscribe = () => subscription.unsubscribe()
    })

    return () => {
      cancelled = true
      unsubscribe?.()
    }
  }, [])

  async function handleSignOut() {
    const { supabase } = await import('./lib/supabase')
    if (!supabase) return
    await supabase.auth.signOut()
    setUserEmail(null)
    navigate('/')
  }

  return (
    <>
      <Suspense fallback={<RouteLoading />}>
        <Routes>
        <Route
          path="/"
          element={
            <LandingPage
              userEmail={userEmail}
              onSignIn={() => navigate('/login')}
              onStart={() => navigate(userEmail ? '/assessment' : '/signup')}
              onSignOut={handleSignOut}
              onAskQuestions={() => navigate('/questions')}
              onOpenDashboard={(roleId, roleTitle) => {
                navigate(`/dashboard/${roleId}`, { state: { roleTitle } })
                window.scrollTo({ top: 0, behavior: 'smooth' })
              }}
              onTrackProgress={() => navigate('/progress')}
              onViewResults={() => navigate('/results')}
            />
          }
        />
        <Route
          path="/login"
          element={
            <LoginPage
              userEmail={userEmail}
              onBackToHome={() => navigate('/')}
              onContinue={() => navigate('/assessment')}
              onGoToSignUp={() => navigate('/signup')}
            />
          }
        />
        <Route
          path="/signup"
          element={
            <SignUpPage
              userEmail={userEmail}
              onBackToHome={() => navigate('/')}
              onContinue={() => navigate('/assessment')}
              onGoToLogin={() => navigate('/login')}
            />
          }
        />
        <Route
          path="/assessment"
          element={
            <main>
              <AssessmentPage onBackToHome={() => navigate('/')} />
            </main>
          }
        />
        <Route
          path="/questions"
          element={
            <QuestionsPage
              userEmail={userEmail}
              onBackToHome={() => navigate('/')}
              onSignIn={() => navigate('/login')}
              onSignUp={() => navigate('/signup')}
            />
          }
        />
        <Route
          path="/results"
          element={
            <main>
              <ResultsRoute />
            </main>
          }
        />
        <Route
          path="/progress"
          element={
            <main>
              <ProgressPage
                onBackToHome={() => navigate('/')}
                onOpenDashboard={(roleId, roleTitle) => {
                  navigate(`/dashboard/${roleId}`, { state: { roleTitle } })
                  window.scrollTo({ top: 0, behavior: 'smooth' })
                }}
                onViewResults={() => navigate('/results')}
              />
            </main>
          }
        />
        <Route
          path="/dashboard/:roleId"
          element={
            <main>
              <DashboardRoute />
            </main>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
      <Suspense fallback={null}>
        <ChatWidget />
      </Suspense>
    </>
  )
}

export default App

import { useEffect, useState } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { AssessmentPage } from './components/Assessment/AssessmentPage'
import { ChatWidget } from './components/Chat/ChatWidget'
import { DashboardRoute } from './components/Dashboard/DashboardRoute'
import { LandingPage } from './components/Landing/LandingPage'
import { LoginPage } from './components/Login/LoginPage'
import { SignUpPage } from './components/Login/SignUpPage'
import { QuestionsPage } from './components/Questions/QuestionsPage'
import { ResultsPage, type MatchResponse } from './components/Results/ResultsPage'
import { supabase } from './lib/supabase'

interface ResultsLocationState {
  matchData?: MatchResponse
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
    if (!supabase) return

    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session?.user?.email) {
        setUserEmail(session.user.email)
      }
    })

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUserEmail(session?.user?.email ?? null)
    })

    return () => {
      subscription.unsubscribe()
    }
  }, [])

  async function handleSignOut() {
    if (!supabase) return
    await supabase.auth.signOut()
    setUserEmail(null)
    navigate('/')
  }

  return (
    <>
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
          path="/dashboard/:roleId"
          element={
            <main>
              <DashboardRoute />
            </main>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <ChatWidget />
    </>
  )
}

export default App

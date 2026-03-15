import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { profileApi, getUserId } from './api/client'

import Onboarding from './pages/Onboarding'
import Dashboard from './pages/Dashboard'
import Transactions from './pages/Transactions'
import Goals from './pages/Goals'
import Achievements from './pages/Achievements'
import Recap from './pages/Recap'
import Demo from './pages/Demo'
import Layout from './components/layout/Layout'

export default function App() {
  const [hasProfile, setHasProfile] = useState(null) // null = loading

  useEffect(() => {
    checkProfile()
  }, [])

  const checkProfile = async () => {
    const userId = getUserId()
    if (!userId) {
      setHasProfile(false)
      return
    }
    try {
      const res = await profileApi.exists(userId)
      setHasProfile(res.data.exists)
    } catch {
      setHasProfile(false)
    }
  }

  if (hasProfile === null) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-400 text-sm">Loading...</div>
      </div>
    )
  }

  return (
    <BrowserRouter>
      <Routes>
        {/* Onboarding — shown if no profile exists */}
        <Route
          path="/onboarding"
          element={
            hasProfile
              ? <Navigate to="/dashboard" replace />
              : <Onboarding onComplete={() => setHasProfile(true)} />
          }
        />

        {/* Protected routes — redirect to onboarding if no profile */}
        <Route
          path="/"
          element={
            hasProfile
              ? <Layout />
              : <Navigate to="/onboarding" replace />
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="transactions" element={<Transactions />} />
          <Route path="goals" element={<Goals />} />
          <Route path="achievements" element={<Achievements />} />
          <Route path="recap" element={<Recap />} />
        </Route>

        {/* Demo control panel — unlisted */}
        <Route path="/demo" element={<Demo />} />

        {/* Catch-all */}
        <Route
          path="*"
          element={<Navigate to={hasProfile ? '/dashboard' : '/onboarding'} replace />}
        />
      </Routes>
    </BrowserRouter>
  )
}

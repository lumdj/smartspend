import { useState, useEffect, useCallback } from 'react'
import { transactionsApi, insightsApi, reportsApi, goalsApi, nudgesApi, achievementsApi, educationApi } from '../api/client'

// ── Transactions ──────────────────────────────────────────────────────────────

export function useTransactions(filters = {}) {
  const [transactions, setTransactions] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetch = useCallback(async () => {
    try {
      setLoading(true)
      const res = await transactionsApi.list(filters)
      setTransactions(res.data.transactions)
      setTotal(res.data.total)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [JSON.stringify(filters)])

  useEffect(() => { fetch() }, [fetch])

  return { transactions, total, loading, error, refetch: fetch }
}

// ── Insights ──────────────────────────────────────────────────────────────────

export function useInsights(useAi = true) {
  const [insights, setInsights] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetch = useCallback(async () => {
    try {
      setLoading(true)
      const res = await insightsApi.get(useAi)
      setInsights(res.data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [useAi])

  useEffect(() => { fetch() }, [fetch])

  return { insights, loading, error, refetch: fetch }
}

// ── Reports ───────────────────────────────────────────────────────────────────

export function useMonthlyReport(month = null, useAi = true) {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetch = useCallback(async () => {
    try {
      setLoading(true)
      const res = await reportsApi.monthly(month, useAi)
      setReport(res.data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [month, useAi])

  useEffect(() => { fetch() }, [fetch])

  return { report, loading, error, refetch: fetch }
}

// ── Goals ─────────────────────────────────────────────────────────────────────

export function useGoals() {
  const [goals, setGoals] = useState([])
  const [activeCount, setActiveCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetch = useCallback(async () => {
    try {
      setLoading(true)
      const res = await goalsApi.list()
      setGoals(res.data.goals)
      setActiveCount(res.data.active_count)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetch() }, [fetch])

  const createGoal = async (data) => {
    const res = await goalsApi.create(data)
    await fetch()
    return res.data
  }

  const updateGoal = async (goalId, data) => {
    const res = await goalsApi.update(goalId, data)
    await fetch()
    return res.data
  }

  const addProgress = async (goalId, data) => {
    const res = await goalsApi.addProgress(goalId, data)
    await fetch()
    return res.data
  }

  const deleteGoal = async (goalId) => {
    await goalsApi.delete(goalId)
    await fetch()
  }

  return {
    goals, activeCount, loading, error,
    refetch: fetch, createGoal, updateGoal, addProgress, deleteGoal,
  }
}

// ── Nudges ────────────────────────────────────────────────────────────────────

export function useNudges() {
  const [nudges, setNudges] = useState([])
  const [loading, setLoading] = useState(true)

  const fetch = useCallback(async () => {
    try {
      setLoading(true)
      const res = await nudgesApi.list(true)
      setNudges(res.data)
    } catch (err) {
      console.error('Failed to fetch nudges:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetch() }, [fetch])

  const dismiss = async (nudgeId) => {
    await nudgesApi.dismiss(nudgeId)
    setNudges(prev => prev.filter(n => n.id !== nudgeId))
  }

  const submitFeedback = async (nudgeId, feedback) => {
    await nudgesApi.feedback(nudgeId, feedback)
    setNudges(prev => prev.map(n =>
      n.id === nudgeId ? { ...n, feedback } : n
    ))
  }

  return { nudges, loading, refetch: fetch, dismiss, submitFeedback }
}

// ── Achievements ──────────────────────────────────────────────────────────────

export function useAchievements() {
  const [achievements, setAchievements] = useState([])
  const [totalPoints, setTotalPoints] = useState(0)
  const [earnedCount, setEarnedCount] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    achievementsApi.list()
      .then(res => {
        setAchievements(res.data.achievements)
        setTotalPoints(res.data.total_points)
        setEarnedCount(res.data.earned_count)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  return { achievements, totalPoints, earnedCount, loading }
}

// ── Education Cards ───────────────────────────────────────────────────────────

export function useEducationCards() {
  const [cards, setCards] = useState([])
  const [loading, setLoading] = useState(true)

  const fetch = useCallback(async () => {
    try {
      setLoading(true)
      const res = await educationApi.list()
      setCards(res.data.cards)
    } catch (err) {
      console.error('Failed to fetch education cards:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetch() }, [fetch])

  const markViewed = async (cardId) => {
    const res = await educationApi.markViewed(cardId)
    setCards(prev => prev.map(c =>
      c.id === cardId ? { ...c, viewed_at: new Date().toISOString() } : c
    ))
    // If achievement was unlocked, show a brief alert
    if (res.data.achievement_unlocked) {
      const a = res.data.achievement_unlocked
      alert(`${a.icon} Achievement unlocked: ${a.name} (+${a.points} pts)`)
    }
  }

  const submitFeedback = async (cardId, wasHelpful) => {
    await educationApi.feedback(cardId, wasHelpful)
    setCards(prev => prev.map(c =>
      c.id === cardId ? { ...c, was_helpful: wasHelpful } : c
    ))
  }

  return { cards, loading, refetch: fetch, markViewed, submitFeedback }
}

export function useHealthHistory(months = 6) {
  const [history, setHistory] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    healthHistoryApi.get(months)
      .then(res => setHistory(res.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [months])

  return { history, loading }
}
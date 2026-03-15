// ─────────────────────────────────────────────────────────────────────────────
// Transactions.jsx
// ─────────────────────────────────────────────────────────────────────────────

import { useState } from 'react'
import { useTransactions } from '../hooks/useData'
import { transactionsApi } from '../api/client'

const PRIORITY_STYLES = {
  essential: 'bg-green-100 text-green-700',
  'semi-essential': 'bg-blue-100 text-blue-700',
  discretionary: 'bg-orange-100 text-orange-700',
}

export function Transactions() {
  const [month, setMonth] = useState('')
  const [priority, setPriority] = useState('')
  const { transactions, total, loading } = useTransactions({
    ...(month && { month }),
    ...(priority && { priority }),
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black text-gray-900">Transactions</h1>
        <p className="text-gray-500 text-sm mt-0.5">{total} total transactions</p>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <input
          type="month"
          value={month}
          onChange={e => setMonth(e.target.value)}
          className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-green-500"
        />
        <select
          value={priority}
          onChange={e => setPriority(e.target.value)}
          className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-green-500 bg-white"
        >
          <option value="">All priorities</option>
          <option value="essential">Essential</option>
          <option value="semi-essential">Semi-essential</option>
          <option value="discretionary">Discretionary</option>
        </select>
        {(month || priority) && (
          <button
            onClick={() => { setMonth(''); setPriority('') }}
            className="px-3 py-2 text-sm text-gray-400 hover:text-gray-600"
          >
            Clear filters
          </button>
        )}
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-400 animate-pulse">Loading transactions…</div>
      ) : (
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
          {transactions.length === 0 ? (
            <div className="text-center py-12 text-gray-400 text-sm">No transactions found</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">Date</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">Merchant</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">Category</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">Priority</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {transactions.map(txn => (
                  <tr key={txn.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{txn.date}</td>
                    <td className="px-4 py-3 font-medium text-gray-900">{txn.merchant}</td>
                    <td className="px-4 py-3 text-gray-500 capitalize">{txn.raw_category}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${PRIORITY_STYLES[txn.priority] || 'bg-gray-100 text-gray-600'}`}>
                        {txn.priority}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-semibold text-gray-900">
                      ${Number(txn.amount).toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Goals.jsx
// ─────────────────────────────────────────────────────────────────────────────

import { useGoals } from '../hooks/useData'

const GOAL_TYPE_ICONS = {
  travel: '✈️', purchase: '🛍️', emergency_fund: '🛡️',
  debt_paydown: '📉', savings: '💰', custom: '🎯',
}

export function Goals() {
  const { goals, activeCount, loading, createGoal, addProgress, deleteGoal } = useGoals()
  const [showForm, setShowForm] = useState(false)
  const [progressGoal, setProgressGoal] = useState(null)
  const [progressAmount, setProgressAmount] = useState('')
  const [newGoal, setNewGoal] = useState({
    name: '', goal_type: 'savings', target_amount: '',
    icon: '🎯', reason: '', target_date: '',
  })
  const [submitting, setSubmitting] = useState(false)

  const handleCreate = async () => {
    if (!newGoal.name || !newGoal.target_amount) return
    setSubmitting(true)
    try {
      await createGoal({
        ...newGoal,
        target_amount: parseFloat(newGoal.target_amount),
        target_date: newGoal.target_date || null,
      })
      setShowForm(false)
      setNewGoal({ name: '', goal_type: 'savings', target_amount: '', icon: '🎯', reason: '', target_date: '' })
    } catch (err) {
      alert(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleProgress = async () => {
    if (!progressAmount || isNaN(parseFloat(progressAmount))) return
    try {
      await addProgress(progressGoal, { amount: parseFloat(progressAmount), source: 'manual' })
      setProgressGoal(null)
      setProgressAmount('')
    } catch (err) {
      alert(err.message)
    }
  }

  if (loading) return <div className="text-center py-12 text-gray-400 animate-pulse">Loading goals…</div>

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-black text-gray-900">Goals</h1>
          <p className="text-gray-500 text-sm mt-0.5">{activeCount}/3 active goals</p>
        </div>
        {activeCount < 3 && (
          <button
            onClick={() => setShowForm(true)}
            className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-semibold hover:bg-green-700 transition-colors"
          >
            + New Goal
          </button>
        )}
      </div>

      {/* Create form */}
      {showForm && (
        <div className="bg-white rounded-2xl border border-gray-200 p-6">
          <h3 className="font-semibold text-gray-900 mb-4">New Goal</h3>
          <div className="space-y-3">
            <input
              placeholder="Goal name (e.g. Trip to Japan)"
              value={newGoal.name}
              onChange={e => setNewGoal(g => ({ ...g, name: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-green-500"
            />
            <div className="grid grid-cols-2 gap-3">
              <select
                value={newGoal.goal_type}
                onChange={e => setNewGoal(g => ({ ...g, goal_type: e.target.value }))}
                className="px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:outline-none focus:border-green-500"
              >
                {Object.keys(GOAL_TYPE_ICONS).map(t => (
                  <option key={t} value={t}>{GOAL_TYPE_ICONS[t]} {t.replace('_', ' ')}</option>
                ))}
              </select>
              <input
                type="number"
                placeholder="Target amount ($)"
                value={newGoal.target_amount}
                onChange={e => setNewGoal(g => ({ ...g, target_amount: e.target.value }))}
                className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-green-500"
              />
            </div>
            <input
              placeholder="Why does this matter to you? (optional)"
              value={newGoal.reason}
              onChange={e => setNewGoal(g => ({ ...g, reason: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-green-500"
            />
            <div className="flex gap-3">
              <button
                onClick={handleCreate}
                disabled={submitting}
                className="flex-1 py-2 bg-green-600 text-white rounded-lg text-sm font-semibold hover:bg-green-700 transition-colors disabled:opacity-50"
              >
                {submitting ? 'Creating…' : 'Create Goal'}
              </button>
              <button
                onClick={() => setShowForm(false)}
                className="px-4 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm font-medium hover:bg-gray-200"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Goals list */}
      {goals.length === 0 ? (
        <div className="bg-green-50 rounded-2xl border border-green-100 p-8 text-center">
          <p className="text-2xl mb-2">🌱</p>
          <p className="text-gray-600 text-sm">No goals yet. What are you saving for?</p>
        </div>
      ) : (
        <div className="space-y-4">
          {goals.map(goal => (
            <div key={goal.id} className="bg-white rounded-2xl border border-gray-200 p-5">
              <div className="flex justify-between items-start mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-2xl">{goal.icon}</span>
                  <div>
                    <h3 className="font-semibold text-gray-900">{goal.name}</h3>
                    {goal.reason && <p className="text-xs text-gray-400 mt-0.5">{goal.reason}</p>}
                  </div>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  goal.status === 'active' ? 'bg-green-100 text-green-700' :
                  goal.status === 'completed' ? 'bg-blue-100 text-blue-700' :
                  'bg-gray-100 text-gray-600'
                }`}>{goal.status}</span>
              </div>

              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-500">${Number(goal.current_amount).toFixed(0)} saved</span>
                <span className="font-semibold text-gray-900">${Number(goal.target_amount).toFixed(0)} goal</span>
              </div>
              <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden mb-1">
                <div
                  className="h-full bg-green-500 rounded-full transition-all duration-700"
                  style={{ width: `${Math.min(goal.progress_pct, 100)}%` }}
                />
              </div>
              <p className="text-xs text-gray-400">{goal.progress_pct.toFixed(1)}% complete</p>

              {goal.status === 'active' && (
                <div className="mt-3 flex gap-2">
                  {progressGoal === goal.id ? (
                    <div className="flex gap-2 w-full">
                      <input
                        type="number"
                        placeholder="Amount ($)"
                        value={progressAmount}
                        onChange={e => setProgressAmount(e.target.value)}
                        className="flex-1 px-3 py-1.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-green-500"
                      />
                      <button onClick={handleProgress} className="px-3 py-1.5 bg-green-600 text-white rounded-lg text-xs font-semibold">Save</button>
                      <button onClick={() => setProgressGoal(null)} className="px-3 py-1.5 bg-gray-100 text-gray-600 rounded-lg text-xs">Cancel</button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setProgressGoal(goal.id)}
                      className="text-xs text-green-600 font-medium hover:underline"
                    >
                      + Add progress
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Achievements.jsx
// ─────────────────────────────────────────────────────────────────────────────

import { useAchievements } from '../hooks/useData'

export function Achievements() {
  const { achievements, totalPoints, earnedCount, loading } = useAchievements()

  const categories = ['credit', 'spending', 'goals', 'streak', 'learning']

  if (loading) return <div className="text-center py-12 text-gray-400 animate-pulse">Loading achievements…</div>

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black text-gray-900">Achievements</h1>
        <p className="text-gray-500 text-sm mt-0.5">{earnedCount} earned · {totalPoints} points</p>
      </div>

      {/* Points card */}
      <div className="bg-gradient-to-br from-green-600 to-green-700 rounded-2xl p-6 text-white">
        <p className="text-green-200 text-sm">Total Points</p>
        <p className="text-4xl font-black mt-1">{totalPoints}</p>
        <p className="text-green-200 text-sm mt-1">{earnedCount} of {achievements.length} achievements unlocked</p>
      </div>

      {categories.map(cat => {
        const catAchievements = achievements.filter(a => a.category === cat)
        if (catAchievements.length === 0) return null
        return (
          <div key={cat}>
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
              {cat}
            </h2>
            <div className="grid grid-cols-1 gap-3">
              {catAchievements.map(a => (
                <div key={a.key} className={`bg-white rounded-xl border p-4 flex items-center gap-4 ${
                  a.unlocked ? 'border-green-200' : 'border-gray-200 opacity-60'
                }`}>
                  <span className={`text-3xl ${!a.unlocked && 'grayscale'}`}>{a.icon}</span>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <p className="font-semibold text-gray-900 text-sm">{a.name}</p>
                      {a.unlocked && <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">Earned</span>}
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">{a.description}</p>
                    {a.unlocked_at && (
                      <p className="text-xs text-gray-400 mt-0.5">
                        {new Date(a.unlocked_at).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                  <span className="text-sm font-bold text-gray-400">+{a.points}</span>
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Recap.jsx
// ─────────────────────────────────────────────────────────────────────────────

import { useMonthlyReport } from '../hooks/useData'

export function Recap() {
  const [selectedMonth, setSelectedMonth] = useState(null)
  const { report, loading } = useMonthlyReport(selectedMonth, true)

  if (loading) return <div className="text-center py-12 text-gray-400 animate-pulse">Generating your report…</div>

  if (!report) return (
    <div className="text-center py-12 text-gray-400 text-sm">No data available yet.</div>
  )

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-black text-gray-900">Monthly Recap</h1>
          <p className="text-gray-500 text-sm mt-0.5">{report.month}</p>
        </div>
        {report.available_months?.length > 1 && (
          <select
            value={selectedMonth || report.month}
            onChange={e => setSelectedMonth(e.target.value)}
            className="px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:outline-none focus:border-green-500"
          >
            {report.available_months.map(m => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        )}
      </div>

      {/* Health score */}
      <div className="bg-gradient-to-br from-green-50 to-blue-50 rounded-2xl p-6">
        <div className="flex items-center gap-4">
          <div className="text-5xl font-black text-green-700">{report.health_score}</div>
          <div>
            <p className="text-sm text-gray-500">Financial Health Score</p>
            <p className="text-sm text-gray-600 mt-1 max-w-xs">{report.ai_narrative}</p>
          </div>
        </div>
      </div>

      {/* Spending breakdown */}
      <div className="bg-white rounded-2xl border border-gray-200 p-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Spending Breakdown</h2>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-xs text-gray-400">Total</p>
            <p className="text-xl font-black text-gray-900">${Number(report.summary?.total_spend || 0).toFixed(0)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-400">Essential</p>
            <p className="text-xl font-bold text-green-700">${Number(report.summary?.essential_spend || 0).toFixed(0)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-400">Discretionary</p>
            <p className="text-xl font-bold text-orange-500">${Number(report.summary?.discretionary_spend || 0).toFixed(0)}</p>
          </div>
        </div>

        {report.summary?.top_categories?.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <p className="text-xs font-semibold text-gray-500 mb-2">Top Categories</p>
            {report.summary.top_categories.map((c, i) => (
              <div key={i} className="flex justify-between text-sm mb-1">
                <span className="text-gray-600 capitalize">{c.category}</span>
                <span className="font-semibold text-gray-900">${Number(c.amount).toFixed(0)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Badges */}
      {report.badges_earned?.length > 0 && (
        <div className="bg-white rounded-2xl border border-yellow-200 p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">🏆 Badges Earned This Month</h2>
          <div className="flex flex-wrap gap-2">
            {report.badges_earned.map((b, i) => (
              <span key={i} className="px-3 py-1 bg-yellow-50 text-yellow-800 rounded-full text-sm font-medium border border-yellow-200">
                {b}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Action items */}
      {report.action_items?.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-200 p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">✅ Action Items for Next Month</h2>
          <ul className="space-y-2">
            {report.action_items.map((item, i) => (
              <li key={i} className="flex gap-3 text-sm text-gray-600">
                <span className="text-green-500 font-bold shrink-0">{i + 1}.</span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Biggest risk */}
      {report.biggest_risk && (
        <div className="bg-red-50 rounded-2xl border border-red-100 p-4">
          <p className="text-xs font-semibold text-red-600 mb-1">⚠️ Biggest Risk</p>
          <p className="text-sm text-red-700">{report.biggest_risk}</p>
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Demo.jsx — control panel
// ─────────────────────────────────────────────────────────────────────────────

import { demoApi, getUserId } from '../api/client'

export function Demo() {
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)
  const userId = getUserId()

  const run = async (label, fn) => {
    setLoading(true)
    setStatus(`Running: ${label}…`)
    try {
      const res = await fn()
      setStatus(`✅ ${label}: ${JSON.stringify(res.data)}`)
    } catch (err) {
      setStatus(`❌ Error: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  if (!userId) return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center text-white">
      <p>No user session. Complete onboarding first.</p>
    </div>
  )

  const btn = (label, fn) => (
    <button
      key={label}
      onClick={() => run(label, fn)}
      disabled={loading}
      className="w-full text-left px-4 py-3 bg-gray-800 hover:bg-gray-700 text-gray-200 rounded-lg text-sm font-mono transition-colors disabled:opacity-50"
    >
      {label}
    </button>
  )

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <div className="max-w-xl mx-auto">
        <div className="mb-6">
          <h1 className="text-xl font-black">SmartSpend Demo Controls</h1>
          <p className="text-gray-400 text-sm mt-1">user_id: {userId}</p>
        </div>

        <div className="space-y-6">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Load Persona</p>
            <div className="space-y-2">
              {['alex', 'jordan', 'taylor'].map(p =>
                btn(`Load ${p}`, () => demoApi.loadPersona(p))
              )}
            </div>
          </div>

          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Trigger Events</p>
            <div className="space-y-2">
              {btn('Spike dining spend (2.5x)', () => demoApi.spikeCategory('dining', 2.5))}
              {btn('Spike shopping spend (2.5x)', () => demoApi.spikeCategory('shopping', 2.5))}
              {btn('Reset + reload Alex', () => demoApi.reset('alex'))}
              {btn('Reset + reload Jordan', () => demoApi.reset('jordan'))}
              {btn('Reset + reload Taylor', () => demoApi.reset('taylor'))}
            </div>
          </div>

          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Navigation</p>
            <div className="space-y-2">
              {btn('Go to Dashboard', () => { window.location.href = '/dashboard'; return Promise.resolve({ data: 'navigating' }) })}
            </div>
          </div>
        </div>

        {status && (
          <div className="mt-6 p-4 bg-gray-800 rounded-lg font-mono text-xs text-green-400 break-all">
            {status}
          </div>
        )}
      </div>
    </div>
  )
}

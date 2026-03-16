import { useInsights } from '../hooks/useData'
import { useProfile } from '../hooks/useProfile'
import { useNudges } from '../hooks/useData'
import { useGoals } from '../hooks/useData'
import { Link } from 'react-router-dom'
import HealthScoreChart from '../components/dashboard/HealthScoreChart'

function AlertBadge({ severity }) {
  const styles = {
    critical: 'bg-red-100 text-red-700',
    warning: 'bg-yellow-100 text-yellow-700',
    info: 'bg-blue-100 text-blue-700',
  }
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${styles[severity] || styles.info}`}>
      {severity}
    </span>
  )
}

function NudgeCard({ nudge, onDismiss, onFeedback }) {
  const typeIcons = {
    spending_alert: '⚠️',
    goal_progress: '🎯',
    achievement: '🏆',
    credit_education: '💳',
    education_card: '📚',
    weekly_tip: '💡',
  }

  // Parse [[term|definition]] tooltip markup — render as highlighted spans
  const parseMessage = (msg) => {
    const parts = msg.split(/\[\[([^\]|]+)\|([^\]]+)\]\]/)
    return parts.map((part, i) => {
      if (i % 3 === 1) {
        // term
        return (
          <span key={i} className="font-semibold text-green-700 cursor-help border-b border-dashed border-green-400" title={parts[i + 1]}>
            {part}
          </span>
        )
      }
      if (i % 3 === 2) return null // definition (used as title above)
      return part
    })
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 mb-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex gap-3">
          <span className="text-xl">{typeIcons[nudge.nudge_type] || '💬'}</span>
          <p className="text-sm text-gray-700 leading-relaxed">{parseMessage(nudge.message)}</p>
        </div>
        <button onClick={() => onDismiss(nudge.id)} className="text-gray-300 hover:text-gray-500 text-xs shrink-0">✕</button>
      </div>
      {!nudge.feedback && (
        <div className="flex gap-2 mt-3 ml-8">
          <button onClick={() => onFeedback(nudge.id, 'helpful')} className="text-xs text-gray-400 hover:text-green-600 transition-colors">👍 Helpful</button>
          <button onClick={() => onFeedback(nudge.id, 'not_helpful')} className="text-xs text-gray-400 hover:text-red-500 transition-colors">👎 Not helpful</button>
        </div>
      )}
      {nudge.feedback && (
        <p className="text-xs text-gray-400 mt-2 ml-8">Thanks for the feedback</p>
      )}
    </div>
  )
}

function GoalProgressBar({ goal }) {
  const pct = Math.min(goal.progress_pct, 100)
  return (
    <div className="mb-3">
      <div className="flex justify-between items-center mb-1">
        <div className="flex items-center gap-2">
          <span>{goal.icon}</span>
          <span className="text-sm font-medium text-gray-800">{goal.name}</span>
        </div>
        <span className="text-xs text-gray-500">${Number(goal.current_amount).toFixed(0)} / ${Number(goal.target_amount).toFixed(0)}</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-green-500 rounded-full transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs text-gray-400 mt-0.5">{pct.toFixed(1)}% complete</p>
    </div>
  )
}

export default function Dashboard() {
  const { profile, loading: profileLoading } = useProfile()
  const { insights, loading: insightsLoading } = useInsights(true)
  const { nudges, dismiss, submitFeedback } = useNudges()
  const { goals } = useGoals()

  const activeGoals = goals.filter(g => g.status === 'active')

  if (profileLoading || insightsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400 text-sm animate-pulse">Loading your dashboard…</div>
      </div>
    )
  }

  const summary = insights?.summary
  const alerts = insights?.alerts || []
  const recommendations = insights?.recommendations || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-black text-gray-900">
          Hey, {profile?.name?.split(' ')[0]} 👋
        </h1>
        <p className="text-gray-500 text-sm mt-0.5">Here's your financial picture right now.</p>
      </div>

      <HealthScoreChart />
      {/* Billing period stats */}
      {summary && (
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-white rounded-2xl border border-gray-100 p-4">
            <p className="text-xs text-gray-400 mb-1"> Spending This Period</p>
            <p className="text-xl font-black text-gray-900">${Number(summary.total_spend || 0).toFixed(0)}</p>
          </div>
          <div className="bg-white rounded-2xl border border-gray-100 p-4">
            <p className="text-xs text-gray-400 mb-1">Discretionary</p>
            <p className="text-xl font-black text-gray-900">${Number(summary.discretionary_spend || 0).toFixed(0)}</p>
            <p className="text-xs text-gray-400 mt-0.5">${Number(summary.essential_spend || 0).toFixed(0)} essential</p>
          </div>
          <div className="bg-white rounded-2xl border border-gray-100 p-4">
            <p className="text-xs text-gray-400 mb-1">Utilization</p>
            <p className={`text-xl font-black ${
              (summary.utilization_rate || 0) > 70 ? 'text-red-600' :
              (summary.utilization_rate || 0) > 50 ? 'text-yellow-500' : 'text-green-600'
            }`}>{summary.utilization_rate?.toFixed(1) || 0}%</p>
            <p className="text-xs text-gray-400 mt-0.5">of credit limit</p>
          </div>
        </div>
      )}

      {/* Alerts */}
      {alerts.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-200 p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">⚠️ Alerts</h2>
          <div className="space-y-3">
            {alerts.map((alert, i) => (
              <div key={i} className="flex items-start gap-3">
                <AlertBadge severity={alert.severity} />
                <p className="text-sm text-gray-600">{alert.message}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Nudges */}
      {nudges.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-700 mb-3">💬 Your Coach Says</h2>
          {nudges.slice(0, 3).map(n => (
            <NudgeCard key={n.id} nudge={n} onDismiss={dismiss} onFeedback={submitFeedback} />
          ))}
        </div>
      )}

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-200 p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">🎯 Recommendations</h2>
          <ul className="space-y-2">
            {recommendations.map((r, i) => (
              <li key={i} className="flex gap-3 text-sm text-gray-600">
                <span className="text-green-500 font-bold shrink-0">{i + 1}.</span>
                {r}
              </li>
            ))}
          </ul>
          {insights?.credit_education_tip && (
            <div className="mt-4 pt-4 border-t border-gray-100">
              <p className="text-xs font-semibold text-gray-500 mb-1">💳 Credit Tip</p>
              <p className="text-sm text-gray-600">{insights.credit_education_tip}</p>
            </div>
          )}
        </div>
      )}

      {/* Goals */}
      {activeGoals.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-200 p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-sm font-semibold text-gray-700">🎯 Active Goals</h2>
            <Link to="/goals" className="text-xs text-green-600 hover:underline">View all →</Link>
          </div>
          {activeGoals.map(g => <GoalProgressBar key={g.id} goal={g} />)}
        </div>
      )}

      {activeGoals.length === 0 && (
        <div className="bg-green-50 rounded-2xl border border-green-100 p-6 text-center">
          <p className="text-gray-600 text-sm mb-3">No active goals yet. Setting a goal is the first step.</p>
          <Link to="/goals" className="text-sm font-semibold text-green-700 hover:underline">
            Set your first goal →
          </Link>
        </div>
      )}
    </div>
  )
}

import { useState, useEffect } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Area, AreaChart
} from 'recharts'
import { healthHistoryApi } from '../../api/client'

const TREND_CONFIG = {
  improving: { label: '↑ Improving', color: '#16a34a', bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-100' },
  declining:  { label: '↓ Declining', color: '#ef4444', bg: 'bg-red-50',   text: 'text-red-700',   border: 'border-red-100'   },
  neutral:    { label: '→ Steady',    color: '#6b7280', bg: 'bg-gray-50',  text: 'text-gray-600',  border: 'border-gray-100'  },
}

function ScoreTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const score = payload[0]?.value
  const color = score >= 75 ? '#16a34a' : score >= 50 ? '#eab308' : '#ef4444'

  return (
    <div className="bg-white border border-gray-200 rounded-xl px-3 py-2 shadow-sm text-xs">
      <p className="text-gray-500 mb-0.5">{label}</p>
      <p className="font-bold text-base" style={{ color }}>{score}</p>
    </div>
  )
}

export default function HealthScoreChart() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    healthHistoryApi.get(6)
      .then(res => setData(res.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="bg-white rounded-2xl border border-gray-100 p-6 h-48 flex items-center justify-center">
      <div className="flex gap-1">
        {[0,1,2].map(i => (
          <div key={i} className="w-1.5 h-1.5 rounded-full bg-green-300 animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
        ))}
      </div>
    </div>
  )

  if (!data || !data.history?.length) return null

  const trend = TREND_CONFIG[data.trend] || TREND_CONFIG.neutral
  const history = data.history
  const currentScore = data.current_score
  const scoreColor = currentScore >= 75 ? '#16a34a' : currentScore >= 50 ? '#eab308' : '#ef4444'
  const gradientId = 'healthGradient'

  // Determine Y axis domain with some padding
  const scores = history.map(h => h.score)
  const minScore = Math.max(0, Math.min(...scores) - 10)
  const maxScore = Math.min(100, Math.max(...scores) + 10)

  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-6">

      {/* Header row */}
      <div className="flex items-start justify-between mb-5">
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Financial Health</p>
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-black" style={{ color: scoreColor }}>{currentScore}</span>
              <span className="text-sm text-gray-400">/ 100</span>
              {data.delta !== 0 && (
                <span className={`flex items-center gap-0.5 text-sm font-semibold ${data.delta > 0 ? 'text-green-600' : 'text-red-500'}`}>
                  {data.delta > 0 ? (
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M6 10V2M6 2L2.5 5.5M6 2L9.5 5.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  ) : (
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M6 2v8M6 10L2.5 6.5M6 10L9.5 6.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  )}
                  {Math.abs(data.delta)} pts
                </span>
              )}
            </div>
        </div>

        <div className="text-right" />
      </div>

      {/* Chart */}
      <div className="h-36">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={history} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={scoreColor} stopOpacity={0.15} />
                <stop offset="95%" stopColor={scoreColor} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 11, fill: '#9ca3af' }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              domain={[minScore, maxScore]}
              tick={{ fontSize: 11, fill: '#9ca3af' }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<ScoreTooltip />} />
            {/* Reference line at 75 — the "healthy" threshold */}
            <ReferenceLine
              y={75}
              stroke="#d1fae5"
              strokeDasharray="4 4"
              label={{ value: 'healthy', position: 'insideTopRight', fontSize: 10, fill: '#86efac' }}
            />
            <Area
              type="monotone"
              dataKey="score"
              stroke={scoreColor}
              strokeWidth={2.5}
              fill={`url(#${gradientId})`}
              dot={{ r: 3, fill: scoreColor, strokeWidth: 0 }}
              activeDot={{ r: 5, fill: scoreColor, strokeWidth: 0 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Footer stats */}
      <div className="flex gap-4 mt-4 pt-4 border-t border-gray-50">
        <div>
          <p className="text-xs text-gray-400">{history.length} month trend</p>
          <p className={`text-sm font-semibold ${data.delta > 0 ? 'text-green-600' : data.delta < 0 ? 'text-red-500' : 'text-gray-700'}`}>
            {data.delta > 0 ? '+' : ''}{data.delta} pts
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-400">Best month</p>
          <p className="text-sm font-semibold text-gray-700">{data.best_month}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400">Needs work</p>
          <p className="text-sm font-semibold text-gray-700">{data.worst_month}</p>
        </div>
      </div>
    </div>
  )
}

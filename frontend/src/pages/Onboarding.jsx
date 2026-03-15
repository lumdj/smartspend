import { useState } from 'react'
import { profileApi, setUserId } from '../api/client'

const STEPS = [
  { id: 'intro', title: "Let's get to know you", subtitle: "SmartSpend adapts to your life — not the other way around." },
  { id: 'basics', title: "The basics", subtitle: "No judgment here. Just context." },
  { id: 'money', title: "Your money situation", subtitle: "Rough estimates are totally fine." },
  { id: 'credit', title: "Your credit experience", subtitle: "We'll tailor advice to where you actually are." },
  { id: 'goals', title: "What matters to you", subtitle: "We'll focus your insights around this." },
  { id: 'habits', title: "Be honest with yourself", subtitle: "Self-awareness is already half the battle." },
]

const OPTIONS = {
  age_range: ['18-22', '23-29', '30-39', '40+'],
  occupation: [
    { value: 'undergraduate_student', label: 'Undergrad Student' },
    { value: 'graduate_student', label: 'Grad Student' },
    { value: 'recent_graduate', label: 'Recent Graduate' },
    { value: 'working_professional', label: 'Working Professional' },
    { value: 'part_time_worker', label: 'Part-Time Worker' },
    { value: 'unemployed', label: 'Between Jobs' },
    { value: 'other', label: 'Something Else' },
  ],
  income_source: [
    { value: 'full_time_job', label: 'Full-Time Job' },
    { value: 'part_time_job', label: 'Part-Time Job' },
    { value: 'parental_support', label: 'Family Support' },
    { value: 'financial_aid_scholarships', label: 'Financial Aid / Scholarships' },
    { value: 'freelance_gig', label: 'Freelance / Gig Work' },
    { value: 'mixed_sources', label: 'Mix of Sources' },
    { value: 'none_currently', label: 'None Right Now' },
  ],
  monthly_income_range: [
    'Under $500', '$500–$1,000', '$1,000–$2,000',
    '$2,000–$3,500', '$3,500–$5,000', '$5,000+',
  ],
  credit_experience: [
    { value: 'brand_new', label: 'Brand new — just starting out' },
    { value: '1_2_years', label: '1–2 years — still learning' },
    { value: '3_plus_years', label: '3+ years — I know my way around' },
  ],
  financial_goal: [
    { value: 'build_credit', label: '🏗️ Build my credit score' },
    { value: 'reduce_debt', label: '📉 Pay down debt' },
    { value: 'saving_for_something', label: '🎯 Save for a specific goal' },
    { value: 'just_track_spending', label: '👀 See where my money goes' },
    { value: 'learn_financial_basics', label: '📚 Learn the financial basics' },
  ],
  spending_weakness: [
    { value: 'dining_out', label: '🍜 Dining out / delivery' },
    { value: 'online_shopping', label: '📦 Online shopping' },
    { value: 'subscriptions', label: '📱 Subscriptions I forget about' },
    { value: 'nightlife_social', label: '🎉 Going out / nightlife' },
    { value: 'impulse_buys', label: '⚡ Impulse purchases' },
    { value: 'coffee_drinks', label: '☕ Coffee & drinks' },
    { value: 'none_im_disciplined', label: '💪 Honestly? Pretty disciplined' },
  ],
}

function OptionButton({ label, selected, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-3 rounded-xl border-2 text-sm font-medium transition-all mb-2 ${
        selected
          ? 'border-green-500 bg-green-50 text-green-900'
          : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300'
      }`}
    >
      {label}
    </button>
  )
}

function GridButton({ label, selected, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-2 rounded-lg border-2 text-sm font-medium transition-all ${
        selected
          ? 'border-green-500 bg-green-50 text-green-900'
          : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
      }`}
    >
      {label}
    </button>
  )
}

export default function Onboarding({ onComplete }) {
  const [step, setStep] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [form, setForm] = useState({
    name: '',
    age_range: '',
    occupation: '',
    income_source: '',
    monthly_income_range: '',
    credit_limit: '',
    billing_cycle_day: '',
    credit_experience: '',
    financial_goal: '',
    spending_weakness: '',
    stress_level: 3,
    pays_full_balance: null,
    persona_key: 'alex',
  })

  const set = (key, val) => setForm(f => ({ ...f, [key]: val }))

  const canAdvance = () => {
    if (step === 0) return form.name.trim().length > 1
    if (step === 1) return form.age_range && form.occupation
    if (step === 2) return form.income_source && form.monthly_income_range && form.credit_limit
    if (step === 3) return form.credit_experience
    if (step === 4) return form.financial_goal
    if (step === 5) return form.spending_weakness && form.pays_full_balance !== null
    return false
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    setError(null)
    try {
      const payload = {
        name: form.name.trim(),
        age_range: form.age_range,
        occupation: form.occupation,
        income_source: form.income_source,
        monthly_income_range: form.monthly_income_range,
        credit_limit: parseFloat(form.credit_limit),
        billing_cycle_day: form.billing_cycle_day ? parseInt(form.billing_cycle_day) : null,
        credit_experience: form.credit_experience,
        financial_goal: form.financial_goal,
        spending_weakness: form.spending_weakness,
        stress_level: form.stress_level,
        pays_full_balance: form.pays_full_balance,
        persona_key: form.persona_key,
      }
      const res = await profileApi.create(payload)
      setUserId(res.data.user_id)
      onComplete()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const stressLabels = ['', 'Totally chill', 'Mostly fine', "It's a lot", 'Pretty stressed', 'Very anxious']
  const stressColors = ['', 'text-green-600', 'text-lime-600', 'text-yellow-600', 'text-orange-500', 'text-red-500']

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 via-white to-blue-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-8">

        {/* Header */}
        {step === 0 && (
          <div className="mb-6">
            <span className="text-2xl font-black tracking-tight">
              Smart<span className="text-green-600">Spend</span>
            </span>
            <p className="text-gray-500 text-sm mt-1">Your AI financial coach</p>
          </div>
        )}

        {/* Progress */}
        <div className="mb-6">
          <div className="flex justify-between text-xs text-gray-400 mb-1">
            <span>Step {step + 1} of {STEPS.length}</span>
            <span className="text-green-600 font-medium">{Math.round((step + 1) / STEPS.length * 100)}%</span>
          </div>
          <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 rounded-full transition-all duration-500"
              style={{ width: `${(step + 1) / STEPS.length * 100}%` }}
            />
          </div>
        </div>

        {/* Step title */}
        <div className="mb-5">
          <h2 className="text-xl font-bold text-gray-900">{STEPS[step].title}</h2>
          <p className="text-sm text-gray-500 mt-0.5">{STEPS[step].subtitle}</p>
        </div>

        {/* Content */}
        <div className="min-h-64">

          {/* Step 0 — Name */}
          {step === 0 && (
            <div>
              <p className="text-sm text-gray-600 mb-4 leading-relaxed">
                SmartSpend gives you personalized financial coaching — not generic advice.
                To do that well, we need to understand <em>your</em> situation first.
              </p>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                What should we call you?
              </label>
              <input
                autoFocus
                type="text"
                placeholder="Your first name"
                value={form.name}
                onChange={e => set('name', e.target.value)}
                onKeyDown={e => e.key === 'Enter' && canAdvance() && setStep(s => s + 1)}
                className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl text-sm focus:outline-none focus:border-green-500 transition-colors"
              />
            </div>
          )}

          {/* Step 1 — Age + Occupation */}
          {step === 1 && (
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">How old are you?</p>
              <div className="grid grid-cols-4 gap-2 mb-4">
                {OPTIONS.age_range.map(a => (
                  <GridButton key={a} label={a} selected={form.age_range === a} onClick={() => set('age_range', a)} />
                ))}
              </div>
              <p className="text-sm font-medium text-gray-700 mb-2">What best describes your situation?</p>
              {OPTIONS.occupation.map(o => (
                <OptionButton key={o.value} label={o.label} selected={form.occupation === o.value} onClick={() => set('occupation', o.value)} />
              ))}
            </div>
          )}

          {/* Step 2 — Income */}
          {step === 2 && (
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">Where does your income come from?</p>
              {OPTIONS.income_source.map(o => (
                <OptionButton key={o.value} label={o.label} selected={form.income_source === o.value} onClick={() => set('income_source', o.value)} />
              ))}
              <p className="text-sm font-medium text-gray-700 mt-4 mb-2">Monthly take-home?</p>
              <div className="grid grid-cols-2 gap-2 mb-4">
                {OPTIONS.monthly_income_range.map(r => (
                  <GridButton key={r} label={r} selected={form.monthly_income_range === r} onClick={() => set('monthly_income_range', r)} />
                ))}
              </div>
              <p className="text-sm font-medium text-gray-700 mb-2">Credit limit (approximate)?</p>
              <input
                type="number"
                placeholder="e.g. 1500"
                value={form.credit_limit}
                onChange={e => set('credit_limit', e.target.value)}
                className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl text-sm focus:outline-none focus:border-green-500 transition-colors"
              />
            </div>
          )}

          {/* Step 3 — Credit experience */}
          {step === 3 && (
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">How long have you had a credit card?</p>
              {OPTIONS.credit_experience.map(o => (
                <OptionButton key={o.value} label={o.label} selected={form.credit_experience === o.value} onClick={() => set('credit_experience', o.value)} />
              ))}
              <p className="text-sm font-medium text-gray-700 mt-4 mb-2">
                When does your statement close? <span className="text-gray-400 font-normal">(optional)</span>
              </p>
              <div className="grid grid-cols-3 gap-2">
                {[1, 5, 10, 15, 20, 25].map(d => (
                  <GridButton
                    key={d}
                    label={`${d}th`}
                    selected={form.billing_cycle_day === String(d)}
                    onClick={() => set('billing_cycle_day', String(d))}
                  />
                ))}
              </div>
              <button
                onClick={() => set('billing_cycle_day', '')}
                className="mt-2 text-xs text-gray-400 hover:text-gray-600"
              >
                Not sure — skip for now
              </button>
            </div>
          )}

          {/* Step 4 — Goals */}
          {step === 4 && (
            <div>
              <p className="text-sm text-gray-600 mb-3">
                Pick the one that matters most right now.
              </p>
              {OPTIONS.financial_goal.map(o => (
                <OptionButton key={o.value} label={o.label} selected={form.financial_goal === o.value} onClick={() => set('financial_goal', o.value)} />
              ))}
            </div>
          )}

          {/* Step 5 — Habits */}
          {step === 5 && (
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">Your biggest spending weakness?</p>
              {OPTIONS.spending_weakness.map(o => (
                <OptionButton key={o.value} label={o.label} selected={form.spending_weakness === o.value} onClick={() => set('spending_weakness', o.value)} />
              ))}

              <p className="text-sm font-medium text-gray-700 mt-4 mb-2">
                Money stress level — <span className={stressColors[form.stress_level]}>{stressLabels[form.stress_level]}</span>
              </p>
              <input
                type="range" min={1} max={5} value={form.stress_level}
                onChange={e => set('stress_level', parseInt(e.target.value))}
                className="w-full accent-green-500 mb-1"
              />
              <div className="flex justify-between text-xs text-gray-400">
                <span>1 — Chill</span><span>5 — Anxious</span>
              </div>

              <p className="text-sm font-medium text-gray-700 mt-4 mb-2">Pay your full balance monthly?</p>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { val: true, label: '✅ Yes, always' },
                  { val: false, label: '🔄 No, I carry a balance' },
                ].map(({ val, label }) => (
                  <GridButton
                    key={String(val)}
                    label={label}
                    selected={form.pays_full_balance === val}
                    onClick={() => set('pays_full_balance', val)}
                  />
                ))}
              </div>

              {error && (
                <p className="mt-3 text-sm text-red-500">{error}</p>
              )}
            </div>
          )}
        </div>

        {/* Navigation */}
        <div className="flex gap-3 mt-6">
          {step > 0 && (
            <button
              onClick={() => setStep(s => s - 1)}
              className="flex-1 py-3 bg-gray-100 text-gray-600 rounded-xl text-sm font-medium hover:bg-gray-200 transition-colors"
            >
              ← Back
            </button>
          )}
          {step < STEPS.length - 1 ? (
            <button
              onClick={() => setStep(s => s + 1)}
              disabled={!canAdvance()}
              className={`flex-2 flex-grow py-3 rounded-xl text-sm font-bold transition-all ${
                canAdvance()
                  ? 'bg-green-600 text-white hover:bg-green-700'
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'
              }`}
            >
              Continue →
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={!canAdvance() || submitting}
              className={`flex-2 flex-grow py-3 rounded-xl text-sm font-bold transition-all ${
                canAdvance() && !submitting
                  ? 'bg-green-600 text-white hover:bg-green-700'
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'
              }`}
            >
              {submitting ? 'Setting up…' : `Let's go, ${form.name || 'you'} 🚀`}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

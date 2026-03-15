import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { clearUserId } from '../../api/client'

export function Navbar() {
  const navigate = useNavigate()

  const handleReset = () => {
    if (confirm('Reset your account? This will clear all data.')) {
      clearUserId()
      window.location.href = '/onboarding'
    }
  }

  const linkClass = ({ isActive }) =>
    `px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
      isActive
        ? 'bg-green-100 text-green-800'
        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
    }`

  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-5xl mx-auto px-4 flex items-center justify-between h-14">
        <div className="flex items-center gap-1">
          <span className="font-black text-gray-900 text-lg tracking-tight">
            Smart<span className="text-green-600">Spend</span>
          </span>
        </div>
        <div className="flex items-center gap-1">
          <NavLink to="/dashboard" className={linkClass}>Dashboard</NavLink>
          <NavLink to="/transactions" className={linkClass}>Transactions</NavLink>
          <NavLink to="/goals" className={linkClass}>Goals</NavLink>
          <NavLink to="/achievements" className={linkClass}>Achievements</NavLink>
          <NavLink to="/recap" className={linkClass}>Recap</NavLink>
          <button
            onClick={handleReset}
            className="ml-2 px-3 py-2 text-sm text-gray-400 hover:text-red-500 transition-colors"
          >
            Reset
          </button>
        </div>
      </div>
    </nav>
  )
}

export default function Layout() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main className="max-w-5xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}

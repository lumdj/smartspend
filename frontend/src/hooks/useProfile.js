import { useState, useEffect } from 'react'
import { profileApi, getUserId } from '../api/client'

export function useProfile() {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const userId = getUserId()

  useEffect(() => {
    if (!userId) {
      setLoading(false)
      return
    }
    fetchProfile()
  }, [userId])

  const fetchProfile = async () => {
    try {
      setLoading(true)
      const res = await profileApi.get(userId)
      setProfile(res.data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const updateProfile = async (data) => {
    try {
      const res = await profileApi.update(userId, data)
      setProfile(res.data)
      return res.data
    } catch (err) {
      setError(err.message)
      throw err
    }
  }

  return { profile, loading, error, refetch: fetchProfile, updateProfile }
}

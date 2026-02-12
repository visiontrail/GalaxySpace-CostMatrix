import { Routes, Route } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import Dashboard from './pages/Dashboard'
import Upload from './pages/Upload'
import Projects from './pages/Projects'
import Departments from './pages/Departments'
import Anomalies from './pages/Anomalies'
import Users from './pages/Users'
import TrendAnalysis from './pages/TrendAnalysis'
import Login from './pages/Login'
import RequireAuth from './components/RequireAuth'
import './App.css'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <MainLayout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="upload" element={<Upload />} />
        <Route path="projects" element={<Projects />} />
        <Route path="departments" element={<Departments />} />
        <Route path="anomalies" element={<Anomalies />} />
        <Route path="trends" element={<TrendAnalysis />} />
        <Route path="users" element={<Users />} />
      </Route>
    </Routes>
  )
}

export default App

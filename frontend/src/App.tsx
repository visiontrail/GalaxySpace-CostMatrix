import { Routes, Route } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import Dashboard from './pages/Dashboard'
import Upload from './pages/Upload'
import Projects from './pages/Projects'
import Departments from './pages/Departments'
import './App.css'

function App() {
  return (
    <Routes>
      <Route path="/" element={<MainLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="upload" element={<Upload />} />
        <Route path="projects" element={<Projects />} />
        <Route path="departments" element={<Departments />} />
      </Route>
    </Routes>
  )
}

export default App


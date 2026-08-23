import { useEffect, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { fetchCatalogData } from '../../data/assessmentCatalog'
import { DashboardPage } from './DashboardPage'

interface DashboardLocationState {
  roleTitle?: string
  skillReadiness?: number
}

interface CatalogRoleDetails {
  roleTitle: string
  portfolioProject: {
    title: string
    brief: string
    evidenceOfReadiness: string[]
  }
}

/**
 * Route wrapper for /dashboard/:roleId. Navigation from the results page carries
 * the role title and readiness score in router state (which survives refresh);
 * the portfolio brief always comes from the public roles catalog so direct deep
 * links render fully without prior in-app state.
 */
export function DashboardRoute() {
  const { roleId = '' } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const state = (location.state ?? {}) as DashboardLocationState
  const [catalogDetails, setCatalogDetails] = useState<CatalogRoleDetails | null>(null)

  useEffect(() => {
    let active = true
    fetchCatalogData()
      .then((bundle) => {
        const role = bundle.roles.roles.find((item) => item.id === roleId)
        if (active && role) {
          setCatalogDetails({
            roleTitle: role.title,
            portfolioProject: {
              title: role.portfolio_project.title,
              brief: role.portfolio_project.brief,
              evidenceOfReadiness: role.portfolio_project.evidence_of_readiness,
            },
          })
        }
      })
      .catch(() => {
        // The catalog only enriches the page; the roadmap loads without it.
      })
    return () => {
      active = false
    }
  }, [roleId])

  return (
    <DashboardPage
      roleId={roleId}
      roleTitle={state.roleTitle ?? catalogDetails?.roleTitle ?? roleId.replace(/-/g, ' ')}
      skillReadiness={state.skillReadiness}
      portfolioProject={catalogDetails?.portfolioProject}
      onBackToHome={() => navigate('/')}
    />
  )
}

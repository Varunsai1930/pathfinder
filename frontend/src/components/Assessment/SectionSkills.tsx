import type { SkillDefinition } from '../../data/assessmentCatalog'
import type { SkillConfidence } from '../../types/assessment'

interface SectionSkillsProps {
  skills: SkillDefinition[]
  skillConfidence: Record<string, SkillConfidence>
  onChange: (skillId: string, value: SkillConfidence) => void
  onBulkSetNone?: () => void
  missingSkillIds: string[]
}

const CONFIDENCE_LEVELS: Array<{
  value: SkillConfidence
  label: string
  hint: string
}> = [
  { value: 'none', label: 'None', hint: 'No prior experience' },
  { value: 'aware', label: 'Aware', hint: 'Understand concepts' },
  { value: 'practised', label: 'Practised', hint: 'Built tutorials or labs' },
  { value: 'project-ready', label: 'Project-ready', hint: 'Shipped in real projects' },
]

const DOMAIN_ORDER = ['foundation', 'frontend', 'backend', 'data', 'infrastructure']

const DOMAIN_METADATA: Record<string, { title: string; subtitle: string }> = {
  foundation: {
    title: 'Core Foundations',
    subtitle: 'Essential collaboration, revision control, and quality verification tools.',
  },
  frontend: {
    title: 'Frontend Development',
    subtitle: 'User interfaces, component state, markup, and browser accessibility.',
  },
  backend: {
    title: 'Backend & Systems',
    subtitle: 'Server logic, RESTful API design, relational data, and authentication.',
  },
  data: {
    title: 'Data & Analytics',
    subtitle: 'Spreadsheet models, data cleaning, exploratory statistics, and visual reporting.',
  },
  infrastructure: {
    title: 'Cloud & Infrastructure',
    subtitle: 'Shell navigation, containers, cloud fundamentals, CI/CD, and system health.',
  },
}

export function SectionSkills({
  skills,
  skillConfidence,
  onChange,
  onBulkSetNone,
  missingSkillIds,
}: SectionSkillsProps) {
  // Group skills by domain according to fixed order
  const groupedSkills = DOMAIN_ORDER.map((domain) => ({
    domain,
    metadata: DOMAIN_METADATA[domain] ?? { title: domain, subtitle: '' },
    skills: skills.filter((s: SkillDefinition) => s.domain === domain),
  }))

  const unassignedCount = skills.filter((s: SkillDefinition) => !skillConfidence[s.id]).length

  return (
    <div className="assessment-section" role="region" aria-labelledby="section-skills-heading">
      <div className="section-intro">
        <div className="section-intro-header">
          <div>
            <h3 id="section-skills-heading" className="section-title">
              Technical Skill Confidence
            </h3>
            <p className="section-subtitle">
              Select your current comfort level for each technical skill. Be realistic—identifying knowledge gaps creates a more targeted roadmap.
            </p>
          </div>
          {unassignedCount > 0 && onBulkSetNone && (
            <button
              type="button"
              className="btn-secondary btn-compact"
              onClick={onBulkSetNone}
              title="Set all unselected skills to 'None'"
            >
              Set unrated ({unassignedCount}) to "None"
            </button>
          )}
        </div>
      </div>

      <div className="skills-domain-groups">
        {groupedSkills.map(({ domain, metadata, skills: domainSkills }) => (
          <section key={domain} className="domain-group" aria-labelledby={`domain-${domain}`}>
            <header className="domain-header">
              <span className="domain-badge">{domain.toUpperCase()}</span>
              <h4 id={`domain-${domain}`} className="domain-title">
                {metadata.title}
              </h4>
              <p className="domain-subtitle">{metadata.subtitle}</p>
            </header>

            <div className="skills-list">
              {domainSkills.map((skill: SkillDefinition) => {
                const currentVal = skillConfidence[skill.id]
                const isMissing = missingSkillIds.includes(skill.id)

                return (
                  <article
                    key={skill.id}
                    id={`skill-${skill.id}`}
                    className={`skill-card ${isMissing ? 'skill-card--missing' : ''} ${
                      currentVal ? 'skill-card--rated' : ''
                    }`}
                  >
                    <div className="skill-info">
                      <div className="skill-name-row">
                        <h5 className="skill-name">{skill.name}</h5>
                        {isMissing && <span className="missing-badge">Rating required</span>}
                      </div>
                      <p className="skill-prompt">{skill.profile_prompt}</p>
                    </div>

                    <fieldset className="skill-confidence-selector" aria-label={`Confidence for ${skill.name}`}>
                      <legend className="sr-only">Confidence level for {skill.name}</legend>
                      <div className="confidence-pills">
                        {CONFIDENCE_LEVELS.map(({ value, label, hint }) => {
                          const isSelected = currentVal === value
                          const inputId = `skill-${skill.id}-${value}`

                          return (
                            <label
                              key={value}
                              htmlFor={inputId}
                              className={`confidence-pill confidence-pill--${value} ${
                                isSelected ? 'confidence-pill--selected' : ''
                              }`}
                              title={hint}
                            >
                              <input
                                type="radio"
                                id={inputId}
                                name={`skill-${skill.id}`}
                                value={value}
                                checked={isSelected}
                                onChange={() => onChange(skill.id, value)}
                                className="sr-only"
                              />
                              <span className="pill-dot" />
                              <span className="pill-text">{label}</span>
                            </label>
                          )
                        })}
                      </div>
                    </fieldset>
                  </article>
                )
              })}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}

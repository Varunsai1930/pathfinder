from app.catalog.assessment_loader import get_assessment_catalog
from app.catalog.loader import get_catalog


def test_catalog_has_exactly_four_supported_roles() -> None:
    catalog = get_catalog()

    assert catalog.schema_version == "1.0.0"
    assert [role.id for role in catalog.roles] == [
        "frontend-developer",
        "backend-developer",
        "data-analyst",
        "cloud-devops-engineer",
    ]


def test_each_role_has_a_complete_five_milestone_path() -> None:
    for role in get_catalog().roles:
        assert len(role.milestones) == 5
        assert [milestone.sequence for milestone in role.milestones] == [1, 2, 3, 4, 5]
        assert sum(milestone.estimated_effort_hours for milestone in role.milestones) >= 40
        assert all(milestone.resources for milestone in role.milestones)


def test_each_role_is_explicitly_grounded_without_claiming_an_onet_equivalence() -> None:
    for role in get_catalog().roles:
        assert role.grounding.source_updated == "2026"
        assert "original" in role.grounding.relationship.lower()
        assert str(role.onet_soc_code) in str(role.onet_reference_url)


def test_role_references_match_the_intended_student_paths() -> None:
    roles = {role.id: role for role in get_catalog().roles}

    assert roles["frontend-developer"].grounding.occupation_title == "Web Developers"
    assert roles["backend-developer"].grounding.occupation_title == "Software Developers"
    assert roles["data-analyst"].grounding.occupation_title == "Business Intelligence Analysts"
    assert roles["cloud-devops-engineer"].grounding.occupation_title == "Network and Computer Systems Administrators"


def test_assessment_has_eighteen_original_interest_questions() -> None:
    assessment = get_assessment_catalog()

    assert assessment.schema_version == "1.0.0"
    assert len(assessment.interest_questions) == 18
    assert len(assessment.response_scale) == 5
    assert "not a clinical" in assessment.purpose_note.lower()


def test_shared_skill_taxonomy_covers_every_role_requirement() -> None:
    profile_skill_ids = {skill.id for skill in get_assessment_catalog().skills}
    role_skill_ids = {
        skill.id for role in get_catalog().roles for skill in role.skills
    }

    assert role_skill_ids <= profile_skill_ids


def test_each_roadmap_teaches_every_core_skill_before_the_portfolio_stage() -> None:
    for role in get_catalog().roles:
        core_skill_ids = {skill.id for skill in role.skills if skill.tier.value == "core"}
        taught_before_final_stage = {
            skill_id
            for milestone in role.milestones[:-1]
            for skill_id in milestone.skills
        }
        assert core_skill_ids <= taught_before_final_stage

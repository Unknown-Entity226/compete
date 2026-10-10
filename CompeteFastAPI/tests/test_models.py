"""Tests for database models and schema initialization."""
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.user import User
from app.models.problem import Problem
from app.models.user_problem import UserProblem
from app.models.statistic import Statistic
from app.models.submission import Submission


@pytest.fixture
def db_session():
    """In-memory SQLite database session for testing models."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_user_and_relationships_creation(db_session):
    """Verify that User, Statistic, Problem, UserProblem, and Submission models persist and link."""
    user = User(
        username="code_warrior",
        real_name="Warrior",
        contest_rating=1920,
        global_ranking=5000,
    )
    db_session.add(user)
    db_session.flush()

    assert user.id is not None
    assert user.username == "code_warrior"

    # Add Problem
    problem = Problem(
        frontend_question_id=1,
        title="Two Sum",
        title_slug="two-sum",
        difficulty="Easy",
        topic_tags=["Array", "Hash Table"],
    )
    db_session.add(problem)
    db_session.flush()

    assert problem.id is not None

    # Link UserProblem
    user_problem = UserProblem(
        user_id=user.id,
        problem_id=problem.id,
        status="SOLVED",
        solved_at=datetime.now(timezone.utc),
    )
    db_session.add(user_problem)

    # Add Statistic snapshot
    stat = Statistic(
        user_id=user.id,
        total_solved=300,
        easy_solved=100,
        medium_solved=150,
        hard_solved=50,
        contest_rating=1920,
        global_ranking=5000,
        solving_velocity_7d=12.5,
    )
    db_session.add(stat)

    # Add Submission
    sub = Submission(
        user_id=user.id,
        problem_id=problem.id,
        submission_id="sub_999",
        problem_title="Two Sum",
        problem_slug="two-sum",
        status_display="Accepted",
        lang="python3",
        submitted_at=datetime.now(timezone.utc),
    )
    db_session.add(sub)
    db_session.commit()

    # Query back
    result = db_session.execute(select(User).where(User.username == "code_warrior"))
    fetched_user = result.scalar_one()

    assert fetched_user.username == "code_warrior"
    assert fetched_user.contest_rating == 1920
    assert len(fetched_user.statistics) == 1
    assert fetched_user.statistics[0].total_solved == 300
    assert len(fetched_user.user_problems) == 1
    assert fetched_user.user_problems[0].status == "SOLVED"
    assert len(fetched_user.submissions) == 1
    assert fetched_user.submissions[0].submission_id == "sub_999"


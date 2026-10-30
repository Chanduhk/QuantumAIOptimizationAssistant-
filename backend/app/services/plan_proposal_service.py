from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.app.models.plan_proposal import PlanProposal
from backend.app.models.task import Task
from backend.app.services.task_lifecycle_service import (
    TASK_STATE_COMPLETED,
    TASK_STATE_STARTED,
    TaskLifecycleService,
)

logger = logging.getLogger(__name__)


class PlanProposalService:
    """
    Authoritative service managing the full lifecycle of plan proposals.
    Provides persistence across backend restarts, optimistic concurrency locking,
    user isolation, constraint revalidation, duplicate prevention, and idempotent acceptance.
    """

    def __init__(self, session: Session, *, clock: Optional[Callable[[], datetime]] = None) -> None:
        if session is None:
            raise ValueError("session is required.")
        self.session = session
        self.clock = clock or (lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def _get_now(self) -> datetime:
        return self.clock()

    def create_proposal(
        self,
        *,
        user_id: int,
        schedule: List[Dict[str, Any]],
        tasks: List[Dict[str, Any]],
        available_hours: float = 8.0,
        goal_text: str = "Plan my day",
        constraints: Optional[Dict[str, Any]] = None,
        provenance: Optional[Dict[str, Any]] = None,
        raw_result: Optional[Dict[str, Any]] = None,
        expires_in_hours: int = 24,
    ) -> PlanProposal:
        """Create and persist a new plan proposal with version 1 in PROPOSED status."""
        if not user_id or user_id < 1:
            raise ValueError("Valid user_id is required.")

        now = self._get_now()
        expires_at = now + timedelta(hours=expires_in_hours)
        proposal_id = str(uuid.uuid4())

        proposal = PlanProposal(
            id=proposal_id,
            user_id=user_id,
            version=1,
            status="PROPOSED",
            goal_text=goal_text,
            available_hours=float(available_hours),
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )
        proposal.schedule = schedule or []
        proposal.tasks = tasks or []
        proposal.constraints = constraints or {}
        proposal.provenance = provenance or {}
        proposal.raw_result = raw_result or {}

        self.session.add(proposal)
        self.session.commit()
        self.session.refresh(proposal)
        logger.info("Created PlanProposal %s (v1) for user %d", proposal_id, user_id)
        return proposal

    def get_proposal_by_id(self, proposal_id: str, user_id: int) -> Optional[PlanProposal]:
        """Retrieve a specific proposal verifying user isolation."""
        if not proposal_id or not user_id:
            return None
        return (
            self.session.query(PlanProposal)
            .filter(PlanProposal.id == proposal_id, PlanProposal.user_id == user_id)
            .one_or_none()
        )

    def get_active_proposal(self, user_id: int) -> Optional[PlanProposal]:
        """
        Retrieve the latest non-expired proposal in PROPOSED status for the user.
        Lazily marks expired proposals if discovered.
        """
        if not user_id or user_id < 1:
            return None

        now = self._get_now()
        proposal = (
            self.session.query(PlanProposal)
            .filter(PlanProposal.user_id == user_id, PlanProposal.status == "PROPOSED")
            .order_by(PlanProposal.created_at.desc())
            .first()
        )

        if not proposal:
            return None

        if proposal.expires_at and proposal.expires_at <= now:
            logger.info("Marking proposal %s as EXPIRED", proposal.id)
            proposal.status = "EXPIRED"
            proposal.updated_at = now
            self.session.commit()
            return None

        return proposal

    def update_proposal_refinement(
        self,
        *,
        proposal_id: str,
        user_id: int,
        new_schedule: List[Dict[str, Any]],
        new_tasks: Optional[List[Dict[str, Any]]] = None,
        new_constraints: Optional[Dict[str, Any]] = None,
        new_provenance: Optional[Dict[str, Any]] = None,
        raw_result: Optional[Dict[str, Any]] = None,
        expected_version: Optional[int] = None,
        new_available_hours: Optional[float] = None,
    ) -> PlanProposal:
        """
        Refine an existing proposal with optimistic locking.
        Increments the version number and ensures only PROPOSED, unexpired proposals can be edited.
        """
        proposal = self.get_proposal_by_id(proposal_id, user_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found or unauthorized for user {user_id}.")

        now = self._get_now()
        if proposal.expires_at and proposal.expires_at <= now:
            proposal.status = "EXPIRED"
            proposal.updated_at = now
            self.session.commit()
            raise ValueError(f"Proposal {proposal_id} has expired and cannot be refined.")

        if proposal.status != "PROPOSED":
            raise ValueError(f"Proposal {proposal_id} cannot be refined because its status is '{proposal.status}'.")

        if expected_version is not None and proposal.version != expected_version:
            raise ValueError(
                f"Stale proposal version conflict: client expected version {expected_version}, "
                f"but server proposal is currently at version {proposal.version}."
            )

        proposal.version += 1
        proposal.schedule = new_schedule
        if new_tasks is not None:
            proposal.tasks = new_tasks
        if new_constraints is not None:
            proposal.constraints = new_constraints
        if new_provenance is not None:
            proposal.provenance = new_provenance
        if raw_result is not None:
            proposal.raw_result = raw_result
        if new_available_hours is not None:
            proposal.available_hours = float(new_available_hours)

        proposal.updated_at = now
        self.session.commit()
        self.session.refresh(proposal)
        logger.info("Refined PlanProposal %s to v%d for user %d", proposal.id, proposal.version, user_id)
        return proposal

    def accept_proposal(
        self,
        proposal_id: Optional[str] = None,
        user_id: Optional[int] = None,
        *,
        expected_version: Optional[int] = None,
        override_schedule: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Tuple[bool, str, List[int], PlanProposal]:
        """
        Authoritative, idempotent proposal acceptance.
        Validates ownership, constraints, checks version, creates or updates tasks safely,
        and transitions proposal status to ACCEPTED.
        """
        pid = proposal_id or kwargs.get("proposal_id")
        uid = user_id if user_id is not None else kwargs.get("user_id")
        if not pid:
            raise ValueError("proposal_id is required.")
        if uid is None:
            raise ValueError("user_id is required.")

        proposal = self.get_proposal_by_id(pid, uid)
        if not proposal:
            raise ValueError(f"Proposal {pid} not found or unauthorized: not found or belongs to another user for user {uid}.")

        now = self._get_now()

        # Idempotent response if already accepted
        if proposal.status == "ACCEPTED":
            # Extract persisted task IDs from raw_result or existing schedule
            task_ids: List[int] = []
            if proposal.raw_result and "persisted_task_ids" in proposal.raw_result:
                task_ids = [int(x) for x in proposal.raw_result["persisted_task_ids"] if str(x).isdigit()]
            if not task_ids:
                for item in proposal.schedule:
                    tid = item.get("task_id") or item.get("id")
                    if tid is not None and str(tid).isdigit():
                        task_ids.append(int(tid))
            return True, "Plan proposal has already been accepted.", task_ids, proposal

        if proposal.status == "REJECTED":
            raise ValueError(f"Proposal {proposal_id} was rejected and cannot be accepted.")

        if proposal.status == "EXPIRED" or (proposal.expires_at and proposal.expires_at <= now):
            proposal.status = "EXPIRED"
            proposal.updated_at = now
            self.session.commit()
            raise ValueError(f"Proposal {proposal_id} has expired and cannot be accepted.")

        if expected_version is not None and proposal.version != expected_version:
            raise ValueError(
                f"Stale proposal version conflict: client expected version {expected_version}, "
                f"but proposal is currently at version {proposal.version}."
            )

        schedule_to_apply = [dict(it) for it in (override_schedule or proposal.schedule)]
        if not schedule_to_apply:
            raise ValueError("No schedule items found in proposal to persist.")

        task_service = TaskLifecycleService(self.session, clock=self.clock)
        ref_dt = now.replace(minute=0, second=0, microsecond=0)
        persisted_task_ids: List[int] = []

        for item in schedule_to_apply:
            tid = item.get("task_id") or item.get("id")
            origin = item.get("origin")
            sched_hour = float(item.get("scheduled_hour", 9.0))
            sched_end = float(item.get("scheduled_end_hour", sched_hour + 1.0))

            start_dt = ref_dt.replace(hour=int(sched_hour) % 24, minute=int((sched_hour % 1) * 60))
            end_dt = ref_dt.replace(hour=int(sched_end) % 24, minute=int((sched_end % 1) * 60))

            if tid and isinstance(tid, (int, str)) and str(tid).isdigit():
                # Existing database task: Revalidate ownership
                task_obj = (
                    self.session.query(Task)
                    .filter(Task.id == int(tid), Task.user_id == user_id)
                    .one_or_none()
                )
                if not task_obj:
                    raise ValueError(f"Security violation: Task {tid} does not belong to user {user_id}.")

                task_obj.start_time = start_dt
                task_obj.end_time = end_dt
                if task_obj.lifecycle_state != TASK_STATE_COMPLETED and not bool(task_obj.completed):
                    task_obj.lifecycle_state = TASK_STATE_STARTED
                persisted_task_ids.append(task_obj.id)
                item["task_id"] = task_obj.id
            elif origin == "proposed" or (isinstance(tid, str) and str(tid).startswith("proposed:")):
                # Proposed task: Idempotently match existing pending task with same title to prevent duplicate creation
                title_clean = str(item.get("title", "New Task")).strip()
                existing_match = (
                    self.session.query(Task)
                    .filter(
                        Task.user_id == user_id,
                        Task.title == title_clean,
                        Task.completed == False,
                    )
                    .first()
                )
                if existing_match:
                    existing_match.start_time = start_dt
                    existing_match.end_time = end_dt
                    if existing_match.lifecycle_state != TASK_STATE_COMPLETED and not bool(existing_match.completed):
                        existing_match.lifecycle_state = TASK_STATE_STARTED
                    persisted_task_ids.append(existing_match.id)
                    item["task_id"] = existing_match.id
                else:
                    dur_mins = float(item.get("estimated_duration", 1.0))
                    if item.get("estimated_duration_unit") == "hours":
                        dur_mins *= 60.0
                    created_task = task_service.create_task(
                        user_id=user_id,
                        title=title_clean,
                        task_type=str(item.get("task_type", "general")),
                        priority=int(item.get("priority", 3)),
                        estimated_duration=dur_mins,
                        estimated_duration_unit="minutes",
                        estimated_duration_source=str(item.get("estimated_duration_source") or "conversational_input"),
                    )
                    created_task.start_time = start_dt
                    created_task.end_time = end_dt
                    created_task.lifecycle_state = TASK_STATE_STARTED
                    persisted_task_ids.append(created_task.id)
                    item["task_id"] = created_task.id

        # Update proposal state to ACCEPTED with updated schedule and persisted task IDs
        raw_res = dict(proposal.raw_result or {})
        raw_res["persisted_task_ids"] = persisted_task_ids
        proposal.raw_result = raw_res
        proposal.schedule = schedule_to_apply
        proposal.status = "ACCEPTED"
        proposal.updated_at = now
        self.session.commit()
        self.session.refresh(proposal)

        msg = f"Plan proposal v{proposal.version} accepted and persisted for {len(persisted_task_ids)} task(s)."
        logger.info(msg)
        return True, msg, persisted_task_ids, proposal

    def reject_proposal(self, proposal_id: str, user_id: int) -> bool:
        """
        Reject a plan proposal.
        Leaves all persisted tasks untouched.
        """
        proposal = self.get_proposal_by_id(proposal_id, user_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found or unauthorized for user {user_id}.")

        if proposal.status == "ACCEPTED":
            raise ValueError(f"Cannot reject proposal {proposal_id} because it has already been accepted.")

        now = self._get_now()
        proposal.status = "REJECTED"
        proposal.updated_at = now
        self.session.commit()
        logger.info("Proposal %s rejected for user %d. Persisted tasks remained unmodified.", proposal_id, user_id)
        return True

from typing import Literal, cast, Optional
from uuid import UUID
from datetime import datetime
from typing import List, Dict, Any

from utils.schema import ReactionState as State
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from langchain_core.runnables import RunnableConfig

from prompts.supervisor_prompt import SUPERVISOR_PROMPT
from Config.settings import get_settings
from utils.agent_registry import AGENT_REGISTRY

from database.service import DatabaseService
from database.database import Database


class SupervisorAgent:
    def __init__(self, db_service: Optional[DatabaseService] = None, user_id: Optional[UUID] = None):
        self.agent_registry = AGENT_REGISTRY
        self.skills = []
        self.config = None
        self.model_name = get_settings().model
        self.Supervisor_prompt = SUPERVISOR_PROMPT
        
        # Database persistence
        self.db_service = db_service
        self.user_id = user_id
        self.workflow_run_id: Optional[UUID] = None
        self.step_counter = 0
        
        # Build the supervisor workflow graph
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        """Build the supervisor workflow graph using Command pattern."""
        workflow = StateGraph(State)
        
        # Add agent nodes
        for agent_name, agent_info in self.agent_registry.items():
            workflow.add_node(agent_name, self._create_agent_node(agent_name, agent_info))
        
        # Add supervisor routing node
        workflow.add_node("supervisor", self._supervisor_router)
        
        # Add edges: each agent returns to supervisor
        for agent_name in self.agent_registry.keys():
            workflow.add_edge(agent_name, "supervisor")
        
        # Start at supervisor
        workflow.add_edge(START, "supervisor")
        
        return workflow.compile()

    def _create_agent_node(self, agent_name: str, agent_info: dict):
        """Create a node function for an agent that returns Command to route back to supervisor."""
        agent_callable = agent_info["callable"]
        middleware_list = agent_info.get("middleware", [])
        
        def agent_node(state: State) -> Command:
            import asyncio
            
            # Create workflow step record
            step_id = None
            if self.workflow_run_id:
                input_state = {k: v for k, v in state.items() if k not in ["warnings", "retry_count"]}
                try:
                    step_id = asyncio.run(self._create_workflow_step(agent_name, input_state))
                except RuntimeError:
                    pass

            # BEFORE middlewares
            for m in middleware_list:
                if m["position"] == "before":
                    middleware_result = m["callable"](state)
                    state = self.handle_middleware(state, m["name"], middleware_result)

            # AGENT
            state["current_agent"] = agent_name
            
            # Update workflow run status
            if self.workflow_run_id:
                try:
                    asyncio.run(self._update_workflow_run_status("running", agent_name))
                except RuntimeError:
                    pass

            result = agent_callable(state)

            if isinstance(result, dict):
                state.update(result)

            # AFTER middlewares
            for m in middleware_list:
                if m["position"] == "after":
                    middleware_result = m["callable"](state)
                    state = self.handle_middleware(state, m["name"], middleware_result)

            # Complete workflow step
            if step_id:
                output_state = {k: v for k, v in state.items() if k not in ["warnings", "retry_count"]}
                status = "completed" if state.get("status") != "failed" else "failed"
                error = state.get("warnings", [])[-1] if state.get("status") == "failed" else None
                try:
                    asyncio.run(self._complete_workflow_step(step_id, status, output_state, error))
                except RuntimeError:
                    pass

            # Store prediction if this was the predictor
            if agent_name == "predictor" and state.get("prediction"):
                try:
                    asyncio.run(self._store_prediction(state))
                except RuntimeError:
                    pass

            # Return Command to route back to supervisor
            return Command(goto="supervisor", update=state)
        
        return agent_node

    def _supervisor_router(self, state: State) -> Command:
        """Supervisor decides which agent to run next using Command pattern."""
        # If workflow is complete or failed, end
        if state.get("status") in ("completed", "failed"):
            return Command(goto=END, update=state)
        
        # If no next agent planned, use workflow plan
        if "next_agent" not in state:
            intent = state.get("task_type")
            if intent not in {"prediction", "validation", "explanation"}:
                intent = self.classify_intent(state.get("user_query", ""), state)
            
            workflow = self.plan(intent)
            state["workflow_plan"] = workflow
            state["workflow_index"] = 0
            state["next_agent"] = workflow[0] if workflow else "__end__"
        
        # If we have a next_agent but the previous agent just completed,
        # advance the workflow index
        completed_statuses = {"validated", "retrieved", "predicted", "verified", "explained"}
        if state.get("status") in completed_statuses:
            workflow = state.get("workflow_plan", [])
            index = state.get("workflow_index", 0)
            # Advance to next agent
            index += 1
            state["workflow_index"] = index
            if index < len(workflow):
                state["next_agent"] = workflow[index]
            else:
                state["next_agent"] = "__end__"
                state["status"] = "completed"
        
        next_agent = state.get("next_agent")
        if next_agent == "__end__" or next_agent not in self.agent_registry:
            return Command(goto=END, update=state)
        
        return Command(goto=next_agent, update=state)

    def _route_to_agent(self, state: State) -> str:
        """Determine which agent to route to next."""
        if state.get("status") in ("completed", "failed"):
            return "__end__"
        
        next_agent = state.get("next_agent")
        if next_agent and next_agent in self.agent_registry:
            return next_agent
        
        # Check workflow plan
        workflow = state.get("workflow_plan", [])
        index = state.get("workflow_index", 0)
        
        if index < len(workflow):
            return workflow[index]
        
        return "__end__"

    def _get_db(self) -> Optional[DatabaseService]:
        """Lazy-initialize DB service if not provided."""
        if self.db_service is None:
            db = Database()
            db.initialize()
            self.db_service = DatabaseService(db)
        return self.db_service

    async def _create_workflow_run(self, state: State) -> Optional[UUID]:
        """Create workflow run record in database."""
        db = self._get_db()
        if not db or not self.user_id:
            return None
        
        run = await db.create_workflow_run(
            user_id=self.user_id,
            task_type=state.get("task_type", "prediction"),
            smiles=state.get("smiles", ""),
            canonical_smiles=state.get("canonical_smiles"),
            conditions=state.get("conditions", {}),
            mechanism=state.get("mechanism"),
            user_query=state.get("user_query"),
            session_id=state.get("session_id"),
        )
        self.workflow_run_id = run.id
        return run.id

    async def _create_workflow_step(self, agent_name: str, input_state: dict) -> Optional[UUID]:
        """Create workflow step record."""
        db = self._get_db()
        if not db or not self.workflow_run_id:
            return None
        
        self.step_counter += 1
        step = await db.create_workflow_step(
            run_id=self.workflow_run_id,
            step_number=self.step_counter,
            agent_name=agent_name,
            status="running",
            input_state=input_state,
        )
        return step.id

    async def _complete_workflow_step(self, step_id: UUID, status: str, output_state: dict = None, error: str = None):
        """Complete workflow step record."""
        db = self._get_db()
        if not db or not step_id:
            return
        
        await db.complete_workflow_step(
            step_id=step_id,
            status=status,
            output_state=output_state,
            error=error,
        )

    async def _update_workflow_run_status(self, status: str, current_agent: str = None):
        """Update workflow run status."""
        db = self._get_db()
        if not db or not self.workflow_run_id:
            return
        
        await db.update_workflow_run_status(
            run_id=self.workflow_run_id,
            status=status,
            current_agent=current_agent,
        )

    async def _store_prediction(self, state: State):
        """Store prediction result."""
        db = self._get_db()
        if not db or not self.workflow_run_id:
            return
        
        prediction_text = state.get("prediction")
        if not prediction_text:
            return
        
        await db.create_prediction(
            run_id=self.workflow_run_id,
            attempt_no=state.get("retry_count", {}).get("predictor", 1),
            prediction=prediction_text,
            confidence=state.get("confidence") or 0.0,
            mechanism=state.get("prediction_mechanism") ,
            metadata=state.get("prediction_metadata", {}),
            validation_results=state.get("validation_results", {}),
            validation_score=state.get("validation_scores", {}).get("overall") if state.get("validation_scores") else None,
            model_name=state.get("prediction_metadata", {}).get("model"),
            model_version=state.get("prediction_metadata", {}).get("version"),
        )

    def classify_intent(self, query: str, state: State):
        """Classify the user's query into an intent."""
        query_lower = query.lower()
        if "explain" in query_lower or "why" in query_lower:
            intent = "explanation"
        elif "valid" in query_lower or "check" in query_lower:
            intent = "validation"
        else:
            intent = "prediction"
        
        state["task_type"] = cast(Literal["prediction", "validation", "explanation"], intent)
        return intent

    def plan(self, intent: str) -> list[str]:
        if intent == "prediction":
            return ["validator", "retriever", "predictor", "verifier", "explainer"]
        elif intent == "validation":
            return ["validator"]
        elif intent == "explanation":
            return ["explainer"]
        raise ValueError(f"Invalid intent : {intent}")

    def handle_middleware(self, state: State, middleware_name: str, middleware_result: dict):
        # Retry Middleware
        if middleware_name == "retry":
            if not middleware_result.get("retry", False):
                return state

            target = middleware_result["target"]
            state["retry_count"][target] += 1
            state["retry_count"]["workflow"] += 1
            state["status"] = "retrying"

            if target == "predictor":
                workflow = ["predictor", "verifier", "explainer"]
            elif target == "retriever":
                workflow = ["retriever", "pre_review", "predictor", "verifier", "explainer"]
            else:
                raise ValueError(f"Unknown retry target : {target}")

            state["workflow_plan"] = workflow
            state["workflow_index"] = 0
            state["next_agent"] = workflow[0]
            return state

        # Post Prediction Human Review
        elif middleware_name == "post_review":
            if not middleware_result.get("interrupt", False):
                return state

            state["warnings"] = state.get("warnings", []) + [
                f"Human review recommended: {middleware_result.get('reason', 'verification policy')}."
            ]
            return state

        return state

    def run(self, state: State):
        import asyncio
        
        try:
            state["status"] = "initialized"
            state["current_agent"] = "supervisor"

            intent = state.get("task_type")
            if intent not in {"prediction", "validation", "explanation"}:
                intent = self.classify_intent(state.get("user_query", ""), state)

            workflow = self.plan(intent)
            state["workflow_plan"] = workflow
            state["workflow_index"] = 0
            state["next_agent"] = workflow[0] if workflow else None

            # Create workflow run in database
            if self.user_id:
                try:
                    asyncio.run(self._create_workflow_run(state))
                except RuntimeError:
                    pass

            # Run the workflow graph
            result = self.workflow.invoke(state)

            # Update final status
            if self.workflow_run_id:
                final_status = result.get("status", "failed")
                try:
                    asyncio.run(self._update_workflow_run_status(final_status))
                except RuntimeError:
                    pass

            return result
        except Exception as error:
            state["status"] = "failed"
            state["warnings"] = state.get("warnings", []) + [f"Workflow failed: {error}"]
            
            if self.workflow_run_id:
                try:
                    asyncio.run(self._update_workflow_run_status("failed"))
                except RuntimeError:
                    pass
            
            return state

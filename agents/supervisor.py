from typing import Any, Dict, List

from pydantic import json

from utils.schema import ReactionState as State
from langchain.tools import tool
from langchain.agents import create_agent
from utils.llm import get_gemini_model as model
model = model()
from agents.explainer import explainer_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.agents import create_agent
from deepagents.middleware.filesystem import FilesystemMiddleware
from utils.agent_registry import AGENT_REGISTRY


class SupervisorAgent:
    def __init__(self,agent_registry,skills,config,model):
        self.agent_registry = agent_registry
        self.skills = skills
        self.config = config
        self.model = model
        
    
    def invoke(self,state, agent_name):
        agent_info = self.agent_registry.get(agent_name)
        
        if agent_info is None:
            raise ValueError(f"Agent '{agent_name}' not found in the registry.")
        
        middleware_list = agent_info.get("middleware", [])

        # BEFORE
        for m in middleware_list:
            if m["position"] == "before":
                middleware_result = m["callable"](state)
                state = self.handle_middleware(
                    state,
                    m["name"],
                    middleware_result
                )

        # AGENT
        agent = agent_info["callable"]
        state = agent(state)

        # AFTER
        for m in middleware_list:
            if m["position"] == "after":
                middleware_result = m["callable"](state)
                state = self.handle_middleware(
                    state,
                    m["name"],
                    middleware_result
                )

        return state
    
            
        
        return state
    
    def plan(self, intent: str) -> list[str]:

        if intent == "prediction":

            return [
                "validator",
                "retriever",
                "pre_review",
                "predictor",
                "verifier",
                "explainer",
            ]

        elif intent == "validation":

            return [
                "validator"
            ]

        elif intent == "explanation":

            return [
                "explainer"
            ]

        raise ValueError(f"Invalid intent : {intent}")

    def execute_workflow(
        self,
        state: State,
        workflow: list[str]
    ) -> State:
        if state == "failed":
            return state
            
        for agent in workflow:
            state = self.invoke(state, agent)

        return state
    
        
    def handle_middleware(
    self,state: State,middleware_name: str,
    middleware_result: dict
    ):
        """
        Handle the result of a middleware and decide the next steps.
        """
    # ---------------------------------------------------
    # Retry Middleware
    # ---------------------------------------------------

        if middleware_name == "retry":

            if not middleware_result.get("retry", False):
                return state

            target = middleware_result["target"]

            # Increment retry counter

            state["retry_count"][target] += 1
            state["retry_count"]["workflow"] += 1

            state["status"] = "retrying"

            # Retry starts from predictor

            if target == "predictor":

                workflow = [
                    "predictor",
                    "verifier",
                    "explainer"
                ]

            # Retry starts from retriever

            elif target == "retriever":

                workflow = [
                    "retriever",
                    "pre_review",
                    "predictor",
                    "verifier",
                    "explainer"
                ]

            else:
                raise ValueError(f"Unknown retry target : {target}")

            return self.execute_workflow(state, workflow)

        # ---------------------------------------------------
        # Post Prediction Human Review
        # ---------------------------------------------------

        elif middleware_name == "post_review":

            if not middleware_result.get("interrupt", False):
                return state

            state = self.invoke(
                state,
                "human_review"
            )

            feedback_result = state.get("human_feedback")
            if not feedback_result:
                return state
            
            decision = feedback_result["decision"]
            if decision not in ["approve", "modify", "reject", "retry"]:
                raise ValueError(
                    f"Invalid decision : {decision}"
                )


            if decision == "approve":
                return state

            elif decision == "modify":

                edited_fields = feedback_result.get(
                    "edited_fields",
                    {}
                )

                # Update only existing fields
                for key, value in edited_fields.items():

                    if key in state:
                        state[key] = value
                
                state["human_feedback"] = None

                return state

            elif decision == "retry":

                state["retry_count"]["workflow"] += 1
                state["status"] = "retrying"

                workflow = [
                    "retriever",
                    "pre_review",
                    "predictor",
                    "verifier",
                    "explainer"
                ]

                return self.execute_workflow(
                    state,
                    workflow
                )

            elif decision == "reject":

                state["status"] = "failed"

                return state

            return state
    
        return state

def run(self, state: State, intent: str) -> State:
    state["status"] = "initialized"
    state["current_agent"] = "supervisor"

    workflow = self.plan(intent)

    return self.execute_workflow(state, workflow)
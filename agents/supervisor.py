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
        
        callable_agent = agent_info["callable"]
        before_middlware = agent_info.get("middleware", {}).get("before", [])
        after_middleware = agent_info.get("middleware", {}).get("after", [])
        
        for middleware in before_middlware:
            state = middleware(state)
            
        state = callable_agent(state)
        
        
        for middleware in after_middleware:
            state = middleware(state)
            
        
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
                    "predictor",
                    "verifier",
                    "explainer"
                ]

            else:
                raise ValueError(f"Unknown retry target : {target}")

            return self.execute_workflow(state, workflow)

        # ---------------------------------------------------
        # Pre Prediction Human Review
        # ---------------------------------------------------

        elif middleware_name == "pre_review":

            feedback = self.invoke(
                state,
                "human_review"
            )

            state["human_feedback"] = feedback

            decision = feedback["decision"]

            if decision == "modify":
                state.update(feedback["edited_fields"])

            elif decision == "reject":
                state["status"] = "failed"

            return state

        # ---------------------------------------------------
        # Post Prediction Human Review
        # ---------------------------------------------------

        elif middleware_name == "post_review":

            if not middleware_result.get("interrupt", False):
                return state

            feedback = self.invoke(
                state,
                "human_review"
            )

            state["human_feedback"] = feedback

            decision = feedback["decision"]

            if decision == "approve":
                return state

            elif decision == "modify":

                state.update(
                    feedback["edited_fields"]
                )

                return state

            elif decision == "retry":

                state["retry_count"]["workflow"] += 1
                state["status"] = "retrying"

                workflow = [
                    "retriever",
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


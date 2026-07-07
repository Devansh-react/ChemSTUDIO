from utils.schema import ReactionState as State
from tools.Human_in_loop.human_review import human_review_agent


def pre_review_agent(state: State) -> State:
    """
    Mandatory review before prediction.

    Shows the exact payload that will be sent to the
    prediction model and allows the user to modify it.
    """

    return human_review_agent(
        state,
        mode="pre_prediction"
    )
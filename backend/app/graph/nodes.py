"""The real node implementations wired into the production graph.

Nodes not listed here still run as stubs until their task is built.
"""

from app.agents.analysis import (
    eda_node,
    hypothesis_node,
    segmentation_node,
    survival_node,
)
from app.agents.cleaning import cleaning_node
from app.agents.human_review import human_review_node
from app.agents.impact import impact_node
from app.agents.ingest import ingest_node
from app.agents.llm_agents import insight_agent_node, recommendation_agent_node
from app.agents.modelling import modelling_node
from app.agents.schema_agent import schema_agent_node
from app.graph import builder as b
from app.graph.builder import NodeFn


def default_nodes() -> dict[str, NodeFn]:
    return {
        b.INGEST: ingest_node,
        b.SCHEMA_AGENT: schema_agent_node,
        b.HUMAN_REVIEW: human_review_node,
        b.CLEANING: cleaning_node,
        b.EDA: eda_node,
        b.SEGMENTATION: segmentation_node,
        b.SURVIVAL: survival_node,
        b.HYPOTHESIS: hypothesis_node,
        b.MODELLING: modelling_node,
        b.IMPACT: impact_node,
        b.INSIGHT_AGENT: insight_agent_node,
        b.RECOMMENDATION_AGENT: recommendation_agent_node,
    }

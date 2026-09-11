import dataclasses
import typing

from knowledge.models.document import Document
from knowledge.models.evidence import Evidence



@dataclasses.dataclass
class InvestigationContext:

    query: str

    incoming_ticket: dict

    freshdesk: list

    jira: list

    freshdesk_documents: typing.List[Document]

    jira_documents: typing.List[Document]

    documents: typing.List[Document]

    freshdesk_ranked_evidence: typing.List[Evidence]

    jira_ranked_evidence: typing.List[Evidence]

    evidence: typing.List[Evidence]

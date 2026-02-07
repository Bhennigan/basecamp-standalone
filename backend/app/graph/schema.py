"""Graph schema definitions for Neo4j"""
from enum import Enum
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


class NodeLabel(str, Enum):
    PERSON = "Person"
    ORGANIZATION = "Organization"
    EMAIL = "Email"
    DOMAIN = "Domain"
    IP_ADDRESS = "IPAddress"
    PHONE = "Phone"
    URL = "URL"
    USERNAME = "Username"
    SOCIAL_MEDIA = "SocialMedia"
    CRYPTOCURRENCY = "Cryptocurrency"
    ADDRESS = "Address"
    COUNTRY = "Country"
    CITY = "City"
    HASH = "Hash"
    FILE = "File"
    MALWARE = "Malware"
    CVE = "CVE"
    BANK_ACCOUNT = "BankAccount"
    CREDIT_CARD = "CreditCard"
    DOCUMENT = "Document"
    CREDENTIAL = "Credential"
    THREAT_ACTOR = "ThreatActor"
    CAMPAIGN = "Campaign"
    INDICATOR = "Indicator"
    ENTITY = "Entity"


class RelationshipType(str, Enum):
    USES_EMAIL = "USES_EMAIL"
    USES_PHONE = "USES_PHONE"
    USES_USERNAME = "USES_USERNAME"
    HAS_SOCIAL_MEDIA = "HAS_SOCIAL_MEDIA"
    WORKS_AT = "WORKS_AT"
    MEMBER_OF = "MEMBER_OF"
    LEADS = "LEADS"
    OWNS = "OWNS"
    OWNS_DOMAIN = "OWNS_DOMAIN"
    REGISTERED_TO = "REGISTERED_TO"
    HOSTED_ON = "HOSTED_ON"
    RESOLVES_TO = "RESOLVES_TO"
    SENT_FROM = "SENT_FROM"
    SENT_TO = "SENT_TO"
    COMMUNICATED_WITH = "COMMUNICATED_WITH"
    LOCATED_IN = "LOCATED_IN"
    RESIDES_AT = "RESIDES_AT"
    OPERATES_IN = "OPERATES_IN"
    IMPERSONATES = "IMPERSONATES"
    TARGETS = "TARGETS"
    ATTRIBUTED_TO = "ATTRIBUTED_TO"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    PART_OF = "PART_OF"
    CONTAINS = "CONTAINS"
    EXTRACTED_FROM = "EXTRACTED_FROM"
    CONNECTS_TO = "CONNECTS_TO"
    DERIVED_FROM = "DERIVED_FROM"
    OWNS_ACCOUNT = "OWNS_ACCOUNT"
    TRANSACTED_WITH = "TRANSACTED_WITH"
    PAID_TO = "PAID_TO"
    RECEIVED_FROM = "RECEIVED_FROM"
    RELATED_TO = "RELATED_TO"
    SAME_AS = "SAME_AS"
    SIMILAR_TO = "SIMILAR_TO"


@dataclass
class NodeProperty:
    name: str
    property_type: str
    required: bool = False
    indexed: bool = False
    description: str = ""


@dataclass  
class NodeDefinition:
    label: NodeLabel
    properties: List[NodeProperty] = field(default_factory=list)
    description: str = ""


@dataclass
class RelationshipDefinition:
    relationship_type: RelationshipType
    source_labels: List[NodeLabel]
    target_labels: List[NodeLabel]
    properties: List[NodeProperty] = field(default_factory=list)
    description: str = ""


class GraphSchema:
    COMMON_PROPERTIES = [
        NodeProperty("id", "string", required=True, indexed=True),
        NodeProperty("value", "string", required=True, indexed=True),
        NodeProperty("normalized_value", "string", required=True, indexed=True),
        NodeProperty("confidence", "float", required=False),
        NodeProperty("threat_level", "string", required=False, indexed=True),
        NodeProperty("source", "string", required=True),
        NodeProperty("workspace_id", "string", required=True, indexed=True),
        NodeProperty("tags", "array", required=False),
    ]
    
    NODE_DEFINITIONS: Dict[NodeLabel, NodeDefinition] = {
        NodeLabel.PERSON: NodeDefinition(label=NodeLabel.PERSON, description="A person entity"),
        NodeLabel.ORGANIZATION: NodeDefinition(label=NodeLabel.ORGANIZATION, description="An organization"),
        NodeLabel.EMAIL: NodeDefinition(label=NodeLabel.EMAIL, description="An email address"),
        NodeLabel.DOMAIN: NodeDefinition(label=NodeLabel.DOMAIN, description="A domain name"),
        NodeLabel.IP_ADDRESS: NodeDefinition(label=NodeLabel.IP_ADDRESS, description="An IP address"),
        NodeLabel.THREAT_ACTOR: NodeDefinition(label=NodeLabel.THREAT_ACTOR, description="A threat actor"),
    }
    
    RELATIONSHIP_DEFINITIONS: Dict[RelationshipType, RelationshipDefinition] = {
        RelationshipType.USES_EMAIL: RelationshipDefinition(
            relationship_type=RelationshipType.USES_EMAIL,
            source_labels=[NodeLabel.PERSON, NodeLabel.ORGANIZATION],
            target_labels=[NodeLabel.EMAIL],
            description="Entity uses this email"
        ),
        RelationshipType.WORKS_AT: RelationshipDefinition(
            relationship_type=RelationshipType.WORKS_AT,
            source_labels=[NodeLabel.PERSON],
            target_labels=[NodeLabel.ORGANIZATION],
            description="Person works at organization"
        ),
        RelationshipType.OWNS_DOMAIN: RelationshipDefinition(
            relationship_type=RelationshipType.OWNS_DOMAIN,
            source_labels=[NodeLabel.PERSON, NodeLabel.ORGANIZATION],
            target_labels=[NodeLabel.DOMAIN],
            description="Entity owns this domain"
        ),
        RelationshipType.IMPERSONATES: RelationshipDefinition(
            relationship_type=RelationshipType.IMPERSONATES,
            source_labels=[NodeLabel.THREAT_ACTOR, NodeLabel.PERSON, NodeLabel.EMAIL],
            target_labels=[NodeLabel.PERSON, NodeLabel.ORGANIZATION, NodeLabel.EMAIL],
            description="Entity impersonates another"
        ),
        RelationshipType.ASSOCIATED_WITH: RelationshipDefinition(
            relationship_type=RelationshipType.ASSOCIATED_WITH,
            source_labels=list(NodeLabel),
            target_labels=list(NodeLabel),
            description="Generic association"
        ),
    }
    
    @classmethod
    def get_node_definition(cls, label: NodeLabel) -> Optional[NodeDefinition]:
        return cls.NODE_DEFINITIONS.get(label)
        
    @classmethod
    def get_relationship_definition(cls, rel_type: RelationshipType) -> Optional[RelationshipDefinition]:
        return cls.RELATIONSHIP_DEFINITIONS.get(rel_type)
        
    @classmethod
    def entity_type_to_label(cls, entity_type: str) -> NodeLabel:
        normalized = entity_type.upper().replace(" ", "_").replace("-", "_")
        type_mapping = {
            "EMAIL": NodeLabel.EMAIL, "EMAIL_ADDRESS": NodeLabel.EMAIL,
            "DOMAIN": NodeLabel.DOMAIN, "DOMAIN_NAME": NodeLabel.DOMAIN,
            "IP": NodeLabel.IP_ADDRESS, "IP_ADDRESS": NodeLabel.IP_ADDRESS,
            "IPADDRESS": NodeLabel.IP_ADDRESS, "IPV4": NodeLabel.IP_ADDRESS,
            "PHONE": NodeLabel.PHONE, "PHONE_NUMBER": NodeLabel.PHONE,
            "PERSON": NodeLabel.PERSON, "NAME": NodeLabel.PERSON,
            "ORGANIZATION": NodeLabel.ORGANIZATION, "ORG": NodeLabel.ORGANIZATION,
            "URL": NodeLabel.URL, "LINK": NodeLabel.URL,
            "USERNAME": NodeLabel.USERNAME, "USER": NodeLabel.USERNAME,
            "HASH": NodeLabel.HASH, "MD5": NodeLabel.HASH, "SHA256": NodeLabel.HASH,
            "CRYPTOCURRENCY": NodeLabel.CRYPTOCURRENCY, "BITCOIN": NodeLabel.CRYPTOCURRENCY,
            "THREAT_ACTOR": NodeLabel.THREAT_ACTOR, "APT": NodeLabel.THREAT_ACTOR,
        }
        return type_mapping.get(normalized, NodeLabel.ENTITY)
        
    @classmethod
    def get_cypher_constraints(cls) -> List[str]:
        return [f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label.value}) REQUIRE n.id IS UNIQUE" for label in NodeLabel]
        
    @classmethod
    def get_cypher_indexes(cls) -> List[str]:
        indexes = []
        for label in NodeLabel:
            indexes.append(f"CREATE INDEX IF NOT EXISTS FOR (n:{label.value}) ON (n.normalized_value)")
            indexes.append(f"CREATE INDEX IF NOT EXISTS FOR (n:{label.value}) ON (n.workspace_id)")
        return indexes

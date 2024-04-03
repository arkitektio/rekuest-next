from rekuest_next.traits.node import Reserve
from rekuest_next.funcs import subscribe, aexecute, asubscribe, execute
from typing_extensions import Literal
from typing import Tuple, Optional, List, Iterator, Any, AsyncIterator
from rath.scalars import ID
from rekuest_next.scalars import InstanceId, NodeHash, SearchQuery, Identifier, ValueMap
from rekuest_next.traits.ports import ReturnWidgetInputTrait, PortTrait
from enum import Enum
from pydantic import BaseModel, Field
from rekuest_next.rath import RekuestNextRath
from datetime import datetime


class AssignWidgetKind(str, Enum):
    SEARCH = "SEARCH"
    CHOICE = "CHOICE"
    SLIDER = "SLIDER"
    CUSTOM = "CUSTOM"
    STRING = "STRING"


class ReturnWidgetKind(str, Enum):
    CHOICE = "CHOICE"
    CUSTOM = "CUSTOM"


class LogicalCondition(str, Enum):
    IS = "IS"
    IS_NOT = "IS_NOT"
    IN = "IN"


class GraphNodeKind(str, Enum):
    ARKITEKT = "ARKITEKT"
    REACTIVE = "REACTIVE"
    ARGS = "ARGS"
    RETURNS = "RETURNS"


class PortScope(str, Enum):
    GLOBAL = "GLOBAL"
    LOCAL = "LOCAL"


class PortKind(str, Enum):
    INT = "INT"
    STRING = "STRING"
    STRUCTURE = "STRUCTURE"
    LIST = "LIST"
    BOOL = "BOOL"
    DICT = "DICT"
    FLOAT = "FLOAT"
    DATE = "DATE"
    UNION = "UNION"


class MapStrategy(str, Enum):
    MAP = "MAP"
    MAP_TO = "MAP_TO"
    MAP_FROM = "MAP_FROM"


class NodeKind(str, Enum):
    FUNCTION = "FUNCTION"
    GENERATOR = "GENERATOR"


class GraphEdgeKind(str, Enum):
    VANILLA = "VANILLA"
    LOGGING = "LOGGING"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    ERROR = "ERROR"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class ReactiveImplementation(str, Enum):
    ZIP = "ZIP"
    COMBINELATEST = "COMBINELATEST"
    WITHLATEST = "WITHLATEST"
    BUFFER_COMPLETE = "BUFFER_COMPLETE"
    BUFFER_UNTIL = "BUFFER_UNTIL"
    DELAY = "DELAY"
    DELAY_UNTIL = "DELAY_UNTIL"
    CHUNK = "CHUNK"
    SPLIT = "SPLIT"
    OMIT = "OMIT"
    ENSURE = "ENSURE"
    ADD = "ADD"
    SUBTRACT = "SUBTRACT"
    MULTIPLY = "MULTIPLY"
    DIVIDE = "DIVIDE"
    MODULO = "MODULO"
    POWER = "POWER"
    PREFIX = "PREFIX"
    SUFFIX = "SUFFIX"
    FILTER = "FILTER"
    GATE = "GATE"
    TO_LIST = "TO_LIST"
    FOREACH = "FOREACH"
    IF = "IF"
    AND = "AND"
    ALL = "ALL"


class Ordering(str, Enum):
    ASC = "ASC"
    DESC = "DESC"


class NodeScope(str, Enum):
    GLOBAL = "GLOBAL"
    LOCAL = "LOCAL"
    BRIDGE_GLOBAL_TO_LOCAL = "BRIDGE_GLOBAL_TO_LOCAL"
    BRIDGE_LOCAL_TO_GLOBAL = "BRIDGE_LOCAL_TO_GLOBAL"


class AssignationStatus(str, Enum):
    ASSIGNING = "ASSIGNING"
    ONGOING = "ONGOING"
    CRITICAL = "CRITICAL"
    CANCELLED = "CANCELLED"
    DONE = "DONE"


class AssignationEventKind(str, Enum):
    BOUND = "BOUND"
    ASSIGN = "ASSIGN"
    UNASSIGN = "UNASSIGN"
    PROGRESS = "PROGRESS"
    YIELD = "YIELD"
    DONE = "DONE"
    LOG = "LOG"


class ReservationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    UNCONNECTED = "UNCONNECTED"
    ENDED = "ENDED"


class ProvisionStatus(str, Enum):
    DENIED = "DENIED"
    PENDING = "PENDING"
    BOUND = "BOUND"
    PROVIDING = "PROVIDING"
    ACTIVE = "ACTIVE"
    REFUSED = "REFUSED"
    INACTIVE = "INACTIVE"
    CANCELING = "CANCELING"
    DISCONNECTED = "DISCONNECTED"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    ENDED = "ENDED"
    CANCELLED = "CANCELLED"


class EffectKind(str, Enum):
    MESSAGE = "MESSAGE"
    CUSTOM = "CUSTOM"


class ReservationEventKind(str, Enum):
    CHANGE = "CHANGE"
    LOG = "LOG"


class ProvisionEventKind(str, Enum):
    CHANGE = "CHANGE"
    LOG = "LOG"


class NodeFilter(BaseModel):
    name: Optional["StrFilterLookup"]
    ids: Optional[Tuple[ID, ...]]
    and_: Optional["NodeFilter"] = Field(alias="AND")
    or_: Optional["NodeFilter"] = Field(alias="OR")

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class StrFilterLookup(BaseModel):
    exact: Optional[str]
    i_exact: Optional[str] = Field(alias="iExact")
    contains: Optional[str]
    i_contains: Optional[str] = Field(alias="iContains")
    in_list: Optional[Tuple[str, ...]] = Field(alias="inList")
    gt: Optional[str]
    gte: Optional[str]
    lt: Optional[str]
    lte: Optional[str]
    starts_with: Optional[str] = Field(alias="startsWith")
    i_starts_with: Optional[str] = Field(alias="iStartsWith")
    ends_with: Optional[str] = Field(alias="endsWith")
    i_ends_with: Optional[str] = Field(alias="iEndsWith")
    range: Optional[Tuple[str, ...]]
    is_null: Optional[bool] = Field(alias="isNull")
    regex: Optional[str]
    i_regex: Optional[str] = Field(alias="iRegex")
    n_exact: Optional[str] = Field(alias="nExact")
    n_i_exact: Optional[str] = Field(alias="nIExact")
    n_contains: Optional[str] = Field(alias="nContains")
    n_i_contains: Optional[str] = Field(alias="nIContains")
    n_in_list: Optional[Tuple[str, ...]] = Field(alias="nInList")
    n_gt: Optional[str] = Field(alias="nGt")
    n_gte: Optional[str] = Field(alias="nGte")
    n_lt: Optional[str] = Field(alias="nLt")
    n_lte: Optional[str] = Field(alias="nLte")
    n_starts_with: Optional[str] = Field(alias="nStartsWith")
    n_i_starts_with: Optional[str] = Field(alias="nIStartsWith")
    n_ends_with: Optional[str] = Field(alias="nEndsWith")
    n_i_ends_with: Optional[str] = Field(alias="nIEndsWith")
    n_range: Optional[Tuple[str, ...]] = Field(alias="nRange")
    n_is_null: Optional[bool] = Field(alias="nIsNull")
    n_regex: Optional[str] = Field(alias="nRegex")
    n_i_regex: Optional[str] = Field(alias="nIRegex")

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class NodeOrder(BaseModel):
    defined_at: Optional[Ordering] = Field(alias="definedAt")

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class OffsetPaginationInput(BaseModel):
    offset: int
    limit: int

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class AgentFilter(BaseModel):
    instance_id: str = Field(alias="instanceId")
    ids: Optional[Tuple[ID, ...]]
    and_: Optional["AgentFilter"] = Field(alias="AND")
    or_: Optional["AgentFilter"] = Field(alias="OR")

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class TemplateFilter(BaseModel):
    interface: Optional[StrFilterLookup]
    ids: Optional[Tuple[ID, ...]]
    and_: Optional["TemplateFilter"] = Field(alias="AND")
    or_: Optional["TemplateFilter"] = Field(alias="OR")

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class AssignationEventFilter(BaseModel):
    kind: Optional[Tuple[AssignationEventKind, ...]]
    and_: Optional["AssignationEventFilter"] = Field(alias="AND")
    or_: Optional["AssignationEventFilter"] = Field(alias="OR")

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class AssignationFilter(BaseModel):
    reservation: Optional["ReservationFilter"]
    ids: Optional[Tuple[ID, ...]]
    status: Optional[Tuple[AssignationStatus, ...]]
    and_: Optional["AssignationFilter"] = Field(alias="AND")
    or_: Optional["AssignationFilter"] = Field(alias="OR")

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class ReservationFilter(BaseModel):
    waiter: Optional["WaiterFilter"]
    ids: Optional[Tuple[ID, ...]]
    status: Optional[Tuple[ReservationStatus, ...]]
    and_: Optional["ReservationFilter"] = Field(alias="AND")
    or_: Optional["ReservationFilter"] = Field(alias="OR")

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class WaiterFilter(BaseModel):
    instance_id: InstanceId = Field(alias="instanceId")
    ids: Optional[Tuple[ID, ...]]
    and_: Optional["WaiterFilter"] = Field(alias="AND")
    or_: Optional["WaiterFilter"] = Field(alias="OR")

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class TestResultFilter(BaseModel):
    name: Optional[StrFilterLookup]
    ids: Optional[Tuple[ID, ...]]
    and_: Optional["TestResultFilter"] = Field(alias="AND")
    or_: Optional["TestResultFilter"] = Field(alias="OR")

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class TestCaseFilter(BaseModel):
    name: Optional[StrFilterLookup]
    ids: Optional[Tuple[ID, ...]]
    and_: Optional["TestCaseFilter"] = Field(alias="AND")
    or_: Optional["TestCaseFilter"] = Field(alias="OR")

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class ProvisionFilter(BaseModel):
    agent: Optional[AgentFilter]
    ids: Optional[Tuple[ID, ...]]
    status: Optional[Tuple[ProvisionStatus, ...]]
    and_: Optional["ProvisionFilter"] = Field(alias="AND")
    or_: Optional["ProvisionFilter"] = Field(alias="OR")

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class FlowFilter(BaseModel):
    workspace: Optional["WorkspaceFilter"]
    ids: Optional[Tuple[ID, ...]]
    and_: Optional["FlowFilter"] = Field(alias="AND")
    or_: Optional["FlowFilter"] = Field(alias="OR")

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class WorkspaceFilter(BaseModel):
    name: Optional[StrFilterLookup]
    ids: Optional[Tuple[ID, ...]]
    and_: Optional["WorkspaceFilter"] = Field(alias="AND")
    or_: Optional["WorkspaceFilter"] = Field(alias="OR")

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class ReactiveTemplateFilter(BaseModel):
    ids: Optional[Tuple[ID, ...]]
    implementations: Optional[Tuple[ReactiveImplementation, ...]]
    and_: Optional["ReactiveTemplateFilter"] = Field(alias="AND")
    or_: Optional["ReactiveTemplateFilter"] = Field(alias="OR")

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class CreateTemplateInput(BaseModel):
    definition: "DefinitionInput"
    interface: str
    params: Optional[Any]
    instance_id: Optional[InstanceId] = Field(alias="instanceId")

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class DefinitionInput(BaseModel):
    description: Optional[str]
    collections: Optional[Tuple[str, ...]]
    name: str
    port_groups: Optional[Tuple["PortGroupInput", ...]] = Field(alias="portGroups")
    args: Optional[Tuple["PortInput", ...]]
    returns: Optional[Tuple["PortInput", ...]]
    kind: NodeKind
    is_test_for: Optional[Tuple[str, ...]] = Field(alias="isTestFor")
    interfaces: Optional[Tuple[str, ...]]

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class PortGroupInput(BaseModel):
    key: str
    hidden: bool

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class PortInput(PortTrait, BaseModel):
    key: str
    scope: PortScope
    label: Optional[str]
    kind: PortKind
    description: Optional[str]
    identifier: Optional[str]
    nullable: bool
    effects: Optional[Tuple["EffectInput", ...]]
    default: Optional[Any]
    child: Optional["ChildPortInput"]
    variants: Optional[Tuple["ChildPortInput", ...]]
    assign_widget: Optional["AssignWidgetInput"] = Field(alias="assignWidget")
    return_widget: Optional["ReturnWidgetInput"] = Field(alias="returnWidget")
    groups: Optional[Tuple[str, ...]]

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class EffectInput(BaseModel):
    dependencies: Tuple["EffectDependencyInput", ...]
    kind: EffectKind

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class EffectDependencyInput(BaseModel):
    key: str
    condition: LogicalCondition
    value: Any

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class ChildPortInput(PortTrait, BaseModel):
    default: Optional[Any]
    label: Optional[str]
    kind: PortKind
    scope: PortScope
    description: Optional[str]
    child: Optional["ChildPortInput"]
    identifier: Optional[Identifier]
    nullable: bool
    variants: Optional[Tuple["ChildPortInput", ...]]
    effects: Optional[Tuple[EffectInput, ...]]
    assign_widget: Optional["AssignWidgetInput"] = Field(alias="assignWidget")
    return_widget: Optional["ReturnWidgetInput"] = Field(alias="returnWidget")

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class AssignWidgetInput(BaseModel):
    as_paragraph: Optional[bool] = Field(alias="asParagraph")
    kind: AssignWidgetKind
    query: Optional[SearchQuery]
    choices: Optional[Tuple["ChoiceInput", ...]]
    min: Optional[int]
    max: Optional[int]
    step: Optional[int]
    placeholder: Optional[str]
    hook: Optional[str]
    ward: Optional[str]

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class ChoiceInput(BaseModel):
    value: Any
    label: str
    description: Optional[str]

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class ReturnWidgetInput(ReturnWidgetInputTrait, BaseModel):
    kind: ReturnWidgetKind
    query: Optional[SearchQuery]
    choices: Optional[Tuple[ChoiceInput, ...]]
    min: Optional[int]
    max: Optional[int]
    step: Optional[int]
    placeholder: Optional[str]
    hook: Optional[str]
    ward: Optional[str]

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class AckInput(BaseModel):
    assignation: ID

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class AssignInput(BaseModel):
    reservation: ID
    args: Tuple[Any, ...]
    reference: Optional[str]
    parent: Optional[ID]

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class UnassignInput(BaseModel):
    assignation: ID

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class ReserveInput(BaseModel):
    instance_id: InstanceId = Field(alias="instanceId")
    node: Optional[ID]
    template: Optional[ID]
    title: Optional[str]
    hash: Optional[NodeHash]
    provision: Optional[ID]
    reference: Optional[str]
    binds: Optional["BindsInput"]

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class BindsInput(BaseModel):
    templates: Tuple[ID, ...]

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class UnreserveInput(BaseModel):
    reservation: ID

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class CreateTestCaseInput(BaseModel):
    node: ID
    key: str
    is_benchmark: bool = Field(alias="isBenchmark")
    description: Optional[str]
    name: Optional[str]

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class CreateTestResultInput(BaseModel):
    case: ID
    template: ID
    passed: bool
    result: Optional[str]

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class UpdateWorkspaceInput(BaseModel):
    workspace: ID
    graph: "GraphInput"
    title: Optional[str]
    description: Optional[str]

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class GraphInput(BaseModel):
    nodes: Tuple["GraphNodeInput", ...]
    edges: Tuple["GraphEdgeInput", ...]
    globals: Tuple["GlobalArgInput", ...]

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class GraphNodeInput(BaseModel):
    id: str
    kind: GraphNodeKind
    position: "PositionInput"
    parent_node: Optional[str] = Field(alias="parentNode")
    ins: Tuple[Tuple[PortInput, ...], ...]
    outs: Tuple[Tuple[PortInput, ...], ...]
    constants: Tuple[PortInput, ...]
    constants_map: ValueMap = Field(alias="constantsMap")
    globals_map: ValueMap = Field(alias="globalsMap")
    description: Optional[str]
    title: Optional[str]
    retries: Optional[int]
    retry_delay: Optional[int] = Field(alias="retryDelay")
    node_kind: Optional[NodeKind] = Field(alias="nodeKind")
    next_timeout: Optional[int] = Field(alias="nextTimeout")
    hash: Optional[str]
    map_strategy: Optional[MapStrategy] = Field(alias="mapStrategy")
    allow_local_execution: Optional[bool] = Field(alias="allowLocalExecution")
    binds: Optional[BindsInput]

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class PositionInput(BaseModel):
    x: float
    y: float

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class GraphEdgeInput(BaseModel):
    label: Optional[str]
    level: Optional[str]
    kind: GraphEdgeKind
    id: str
    source: str
    target: str
    source_handle: str = Field(alias="sourceHandle")
    target_handle: str = Field(alias="targetHandle")
    stream: Tuple["StreamItemInput", ...]

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class StreamItemInput(BaseModel):
    kind: PortKind
    label: str

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class GlobalArgInput(BaseModel):
    key: str
    port: PortInput

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class CreateWorkspaceInput(BaseModel):
    graph: Optional[GraphInput]
    title: Optional[str]
    description: Optional[str]
    vanilla: bool

    class Config:
        frozen = True
        extra = "forbid"
        use_enum_values = True


class ProvisionFragmentTemplate(BaseModel):
    typename: Optional[Literal["Template"]] = Field(alias="__typename", exclude=True)
    id: ID
    node: "NodeFragment"
    params: Any

    class Config:
        frozen = True


class ProvisionFragment(BaseModel):
    typename: Optional[Literal["Provision"]] = Field(alias="__typename", exclude=True)
    id: ID
    status: ProvisionStatus
    template: ProvisionFragmentTemplate

    class Config:
        frozen = True


class ProvisionEventFragmentProvision(BaseModel):
    typename: Optional[Literal["Provision"]] = Field(alias="__typename", exclude=True)
    id: ID

    class Config:
        frozen = True


class ProvisionEventFragment(BaseModel):
    typename: Optional[Literal["ProvisionEvent"]] = Field(
        alias="__typename", exclude=True
    )
    id: ID
    kind: ProvisionEventKind
    level: LogLevel
    provision: ProvisionEventFragmentProvision
    created_at: datetime = Field(alias="createdAt")

    class Config:
        frozen = True


class TestCaseFragmentNode(Reserve, BaseModel):
    typename: Optional[Literal["Node"]] = Field(alias="__typename", exclude=True)
    id: ID

    class Config:
        frozen = True


class TestCaseFragment(BaseModel):
    typename: Optional[Literal["TestCase"]] = Field(alias="__typename", exclude=True)
    id: ID
    node: TestCaseFragmentNode
    key: str
    is_benchmark: bool = Field(alias="isBenchmark")
    description: str
    name: str

    class Config:
        frozen = True


class TestResultFragmentCase(BaseModel):
    typename: Optional[Literal["TestCase"]] = Field(alias="__typename", exclude=True)
    id: ID
    key: str

    class Config:
        frozen = True


class TestResultFragment(BaseModel):
    typename: Optional[Literal["TestResult"]] = Field(alias="__typename", exclude=True)
    id: ID
    case: TestResultFragmentCase
    passed: bool

    class Config:
        frozen = True


class AgentFragmentRegistryApp(BaseModel):
    typename: Optional[Literal["App"]] = Field(alias="__typename", exclude=True)
    id: ID

    class Config:
        frozen = True


class AgentFragmentRegistryUser(BaseModel):
    typename: Optional[Literal["User"]] = Field(alias="__typename", exclude=True)
    id: ID

    class Config:
        frozen = True


class AgentFragmentRegistry(BaseModel):
    typename: Optional[Literal["Registry"]] = Field(alias="__typename", exclude=True)
    app: AgentFragmentRegistryApp
    user: AgentFragmentRegistryUser

    class Config:
        frozen = True


class AgentFragment(BaseModel):
    typename: Optional[Literal["Agent"]] = Field(alias="__typename", exclude=True)
    registry: AgentFragmentRegistry

    class Config:
        frozen = True


class AssignationFragmentParent(BaseModel):
    typename: Optional[Literal["Assignation"]] = Field(alias="__typename", exclude=True)
    id: ID

    class Config:
        frozen = True


class AssignationFragmentEvents(BaseModel):
    typename: Optional[Literal["AssignationEvent"]] = Field(
        alias="__typename", exclude=True
    )
    id: ID
    returns: Any
    level: LogLevel

    class Config:
        frozen = True


class AssignationFragment(BaseModel):
    typename: Optional[Literal["Assignation"]] = Field(alias="__typename", exclude=True)
    args: Any
    id: ID
    parent: AssignationFragmentParent
    id: ID
    status: AssignationStatus
    events: Tuple[AssignationFragmentEvents, ...]
    reference: Optional[str]
    updated_at: datetime = Field(alias="updatedAt")

    class Config:
        frozen = True


class AssignationEventFragmentAssignation(BaseModel):
    typename: Optional[Literal["Assignation"]] = Field(alias="__typename", exclude=True)
    id: ID

    class Config:
        frozen = True


class AssignationEventFragment(BaseModel):
    typename: Optional[Literal["AssignationEvent"]] = Field(
        alias="__typename", exclude=True
    )
    id: ID
    kind: AssignationEventKind
    level: LogLevel
    returns: Any
    assignation: AssignationEventFragmentAssignation
    created_at: datetime = Field(alias="createdAt")

    class Config:
        frozen = True


class TemplateFragmentAgentRegistry(BaseModel):
    typename: Optional[Literal["Registry"]] = Field(alias="__typename", exclude=True)
    id: ID

    class Config:
        frozen = True


class TemplateFragmentAgent(BaseModel):
    typename: Optional[Literal["Agent"]] = Field(alias="__typename", exclude=True)
    registry: TemplateFragmentAgentRegistry

    class Config:
        frozen = True


class TemplateFragment(BaseModel):
    typename: Optional[Literal["Template"]] = Field(alias="__typename", exclude=True)
    id: ID
    agent: TemplateFragmentAgent
    node: "NodeFragment"
    params: Any

    class Config:
        frozen = True


class ChildPortNestedFragmentChild(PortTrait, BaseModel):
    typename: Optional[Literal["ChildPort"]] = Field(alias="__typename", exclude=True)
    identifier: Optional[Identifier]
    nullable: bool
    kind: PortKind

    class Config:
        frozen = True


class ChildPortNestedFragment(PortTrait, BaseModel):
    typename: Optional[Literal["ChildPort"]] = Field(alias="__typename", exclude=True)
    kind: PortKind
    child: Optional[ChildPortNestedFragmentChild]
    identifier: Optional[Identifier]
    nullable: bool

    class Config:
        frozen = True


class ChildPortFragment(PortTrait, BaseModel):
    typename: Optional[Literal["ChildPort"]] = Field(alias="__typename", exclude=True)
    kind: PortKind
    identifier: Optional[Identifier]
    child: Optional[ChildPortNestedFragment]
    nullable: bool

    class Config:
        frozen = True


class PortFragment(PortTrait, BaseModel):
    typename: Optional[Literal["Port"]] = Field(alias="__typename", exclude=True)
    key: str
    label: Optional[str]
    nullable: bool
    description: Optional[str]
    default: Optional[Any]
    kind: PortKind
    identifier: Optional[Identifier]
    child: Optional[ChildPortFragment]
    variants: Optional[Tuple[ChildPortFragment, ...]]

    class Config:
        frozen = True


class DefinitionFragment(Reserve, BaseModel):
    typename: Optional[Literal["Node"]] = Field(alias="__typename", exclude=True)
    args: Tuple[PortFragment, ...]
    returns: Tuple[PortFragment, ...]
    kind: NodeKind
    name: str
    description: Optional[str]

    class Config:
        frozen = True


class NodeFragment(DefinitionFragment, Reserve, BaseModel):
    typename: Optional[Literal["Node"]] = Field(alias="__typename", exclude=True)
    hash: NodeHash
    id: ID

    class Config:
        frozen = True


class ReservationFragmentNode(Reserve, BaseModel):
    typename: Optional[Literal["Node"]] = Field(alias="__typename", exclude=True)
    id: ID
    hash: NodeHash

    class Config:
        frozen = True


class ReservationFragmentWaiter(BaseModel):
    typename: Optional[Literal["Waiter"]] = Field(alias="__typename", exclude=True)
    id: ID

    class Config:
        frozen = True


class ReservationFragment(BaseModel):
    typename: Optional[Literal["Reservation"]] = Field(alias="__typename", exclude=True)
    id: ID
    status: ReservationStatus
    node: ReservationFragmentNode
    waiter: ReservationFragmentWaiter
    reference: str
    updated_at: datetime = Field(alias="updatedAt")

    class Config:
        frozen = True


class ReservationEventFragmentReservation(BaseModel):
    typename: Optional[Literal["Reservation"]] = Field(alias="__typename", exclude=True)
    id: ID

    class Config:
        frozen = True


class ReservationEventFragment(BaseModel):
    typename: Optional[Literal["ReservationEvent"]] = Field(
        alias="__typename", exclude=True
    )
    id: ID
    kind: ReservationEventKind
    level: LogLevel
    reservation: ReservationEventFragmentReservation
    created_at: datetime = Field(alias="createdAt")

    class Config:
        frozen = True


class Create_testcaseMutation(BaseModel):
    create_test_case: TestCaseFragment = Field(alias="createTestCase")

    class Arguments(BaseModel):
        node: ID
        key: str
        is_benchmark: Optional[bool] = Field(default=None)
        description: str
        name: str

    class Meta:
        document = "fragment TestCase on TestCase {\n  id\n  node {\n    id\n  }\n  key\n  isBenchmark\n  description\n  name\n}\n\nmutation create_testcase($node: ID!, $key: String!, $is_benchmark: Boolean, $description: String!, $name: String!) {\n  createTestCase(\n    input: {node: $node, key: $key, isBenchmark: $is_benchmark, description: $description, name: $name}\n  ) {\n    ...TestCase\n  }\n}"


class Create_testresultMutation(BaseModel):
    create_test_result: TestResultFragment = Field(alias="createTestResult")

    class Arguments(BaseModel):
        case: ID
        template: ID
        passed: bool
        result: Optional[str] = Field(default=None)

    class Meta:
        document = "fragment TestResult on TestResult {\n  id\n  case {\n    id\n    key\n  }\n  passed\n}\n\nmutation create_testresult($case: ID!, $template: ID!, $passed: Boolean!, $result: String) {\n  createTestResult(\n    input: {case: $case, template: $template, passed: $passed, result: $result}\n  ) {\n    ...TestResult\n  }\n}"


class AssignMutation(BaseModel):
    assign: AssignationFragment

    class Arguments(BaseModel):
        reservation: ID
        args: List[Any]
        reference: Optional[str] = Field(default=None)
        parent: Optional[ID] = Field(default=None)

    class Meta:
        document = "fragment Assignation on Assignation {\n  args\n  id\n  parent {\n    id\n  }\n  id\n  status\n  events {\n    id\n    returns\n    level\n  }\n  reference\n  updatedAt\n}\n\nmutation assign($reservation: ID!, $args: [Arg!]!, $reference: String, $parent: ID) {\n  assign(\n    input: {reservation: $reservation, args: $args, reference: $reference, parent: $parent}\n  ) {\n    ...Assignation\n  }\n}"


class UnassignMutation(BaseModel):
    unassign: AssignationFragment

    class Arguments(BaseModel):
        id: ID

    class Meta:
        document = "fragment Assignation on Assignation {\n  args\n  id\n  parent {\n    id\n  }\n  id\n  status\n  events {\n    id\n    returns\n    level\n  }\n  reference\n  updatedAt\n}\n\nmutation unassign($id: ID!) {\n  unassign(input: {assignation: $id}) {\n    ...Assignation\n  }\n}"


class CreateTemplateMutation(BaseModel):
    create_template: TemplateFragment = Field(alias="createTemplate")

    class Arguments(BaseModel):
        interface: str
        definition: DefinitionInput
        instance_id: InstanceId
        params: Optional[Any] = Field(default=None)

    class Meta:
        document = "fragment ChildPortNested on ChildPort {\n  kind\n  child {\n    identifier\n    nullable\n    kind\n  }\n  identifier\n  nullable\n}\n\nfragment ChildPort on ChildPort {\n  kind\n  identifier\n  child {\n    ...ChildPortNested\n  }\n  nullable\n}\n\nfragment Port on Port {\n  __typename\n  key\n  label\n  nullable\n  description\n  default\n  kind\n  identifier\n  child {\n    ...ChildPort\n  }\n  variants {\n    ...ChildPort\n  }\n}\n\nfragment Definition on Node {\n  args {\n    ...Port\n  }\n  returns {\n    ...Port\n  }\n  kind\n  name\n  description\n}\n\nfragment Node on Node {\n  hash\n  id\n  ...Definition\n}\n\nfragment Template on Template {\n  id\n  agent {\n    registry {\n      id\n    }\n  }\n  node {\n    ...Node\n  }\n  params\n}\n\nmutation createTemplate($interface: String!, $definition: DefinitionInput!, $instance_id: InstanceId!, $params: AnyDefault) {\n  createTemplate(\n    input: {definition: $definition, interface: $interface, params: $params, instanceId: $instance_id}\n  ) {\n    ...Template\n  }\n}"


class ReserveMutation(BaseModel):
    reserve: ReservationFragment

    class Arguments(BaseModel):
        node: Optional[ID] = Field(default=None)
        hash: Optional[NodeHash] = Field(default=None)
        title: Optional[str] = Field(default=None)
        reference: Optional[str] = Field(default=None)
        provision: Optional[ID] = Field(default=None)
        binds: Optional[BindsInput] = Field(default=None)
        instance_id: InstanceId = Field(alias="instanceId")

    class Meta:
        document = "fragment Reservation on Reservation {\n  id\n  status\n  node {\n    id\n    hash\n  }\n  waiter {\n    id\n  }\n  reference\n  updatedAt\n}\n\nmutation reserve($node: ID, $hash: NodeHash, $title: String, $reference: String, $provision: ID, $binds: BindsInput, $instanceId: InstanceId!) {\n  reserve(\n    input: {node: $node, hash: $hash, title: $title, provision: $provision, binds: $binds, reference: $reference, instanceId: $instanceId}\n  ) {\n    ...Reservation\n  }\n}"


class UnreserveMutationUnreserve(BaseModel):
    typename: Optional[Literal["Reservation"]] = Field(alias="__typename", exclude=True)
    id: ID

    class Config:
        frozen = True


class UnreserveMutation(BaseModel):
    unreserve: UnreserveMutationUnreserve

    class Arguments(BaseModel):
        id: ID

    class Meta:
        document = "mutation unreserve($id: ID!) {\n  unreserve(input: {reservation: $id}) {\n    id\n  }\n}"


class WatchProvisionsSubscription(BaseModel):
    provisions: ProvisionEventFragment

    class Arguments(BaseModel):
        instance_id: InstanceId = Field(alias="instanceId")

    class Meta:
        document = "fragment ProvisionEvent on ProvisionEvent {\n  id\n  kind\n  level\n  provision {\n    id\n  }\n  createdAt\n}\n\nsubscription WatchProvisions($instanceId: InstanceId!) {\n  provisions(instanceId: $instanceId) {\n    ...ProvisionEvent\n  }\n}"


class WatchAssignationsSubscription(BaseModel):
    assignations: AssignationEventFragment

    class Arguments(BaseModel):
        instance_id: InstanceId = Field(alias="instanceId")

    class Meta:
        document = "fragment AssignationEvent on AssignationEvent {\n  id\n  kind\n  level\n  returns\n  assignation {\n    id\n  }\n  createdAt\n}\n\nsubscription WatchAssignations($instanceId: InstanceId!) {\n  assignations(instanceId: $instanceId) {\n    ...AssignationEvent\n  }\n}"


class WatchReservationsSubscription(BaseModel):
    reservations: ReservationEventFragment

    class Arguments(BaseModel):
        instance_id: InstanceId = Field(alias="instanceId")

    class Meta:
        document = "fragment ReservationEvent on ReservationEvent {\n  id\n  kind\n  level\n  reservation {\n    id\n  }\n  createdAt\n}\n\nsubscription WatchReservations($instanceId: InstanceId!) {\n  reservations(instanceId: $instanceId) {\n    ...ReservationEvent\n  }\n}"


class Get_provisionQuery(BaseModel):
    provision: ProvisionFragment

    class Arguments(BaseModel):
        id: ID

    class Meta:
        document = "fragment ChildPortNested on ChildPort {\n  kind\n  child {\n    identifier\n    nullable\n    kind\n  }\n  identifier\n  nullable\n}\n\nfragment ChildPort on ChildPort {\n  kind\n  identifier\n  child {\n    ...ChildPortNested\n  }\n  nullable\n}\n\nfragment Port on Port {\n  __typename\n  key\n  label\n  nullable\n  description\n  default\n  kind\n  identifier\n  child {\n    ...ChildPort\n  }\n  variants {\n    ...ChildPort\n  }\n}\n\nfragment Definition on Node {\n  args {\n    ...Port\n  }\n  returns {\n    ...Port\n  }\n  kind\n  name\n  description\n}\n\nfragment Node on Node {\n  hash\n  id\n  ...Definition\n}\n\nfragment Provision on Provision {\n  id\n  status\n  template {\n    id\n    node {\n      ...Node\n    }\n    params\n  }\n}\n\nquery get_provision($id: ID!) {\n  provision(id: $id) {\n    ...Provision\n  }\n}"


class Get_testcaseQuery(BaseModel):
    test_case: TestCaseFragment = Field(alias="testCase")

    class Arguments(BaseModel):
        id: ID

    class Meta:
        document = "fragment TestCase on TestCase {\n  id\n  node {\n    id\n  }\n  key\n  isBenchmark\n  description\n  name\n}\n\nquery get_testcase($id: ID!) {\n  testCase(id: $id) {\n    ...TestCase\n  }\n}"


class Get_testresultQuery(BaseModel):
    test_result: TestResultFragment = Field(alias="testResult")

    class Arguments(BaseModel):
        id: ID

    class Meta:
        document = "fragment TestResult on TestResult {\n  id\n  case {\n    id\n    key\n  }\n  passed\n}\n\nquery get_testresult($id: ID!) {\n  testResult(id: $id) {\n    ...TestResult\n  }\n}"


class Search_testcasesQueryOptions(BaseModel):
    typename: Optional[Literal["TestCase"]] = Field(alias="__typename", exclude=True)
    label: str
    value: ID

    class Config:
        frozen = True


class Search_testcasesQuery(BaseModel):
    options: Tuple[Search_testcasesQueryOptions, ...]

    class Arguments(BaseModel):
        search: Optional[str] = Field(default=None)
        values: Optional[List[ID]] = Field(default=None)

    class Meta:
        document = "query search_testcases($search: String, $values: [ID!]) {\n  options: testCases(\n    filters: {name: {iContains: $search}, ids: $values}\n    pagination: {limit: 10}\n  ) {\n    label: name\n    value: id\n  }\n}"


class Search_testresultsQueryOptions(BaseModel):
    typename: Optional[Literal["TestResult"]] = Field(alias="__typename", exclude=True)
    label: datetime
    value: ID

    class Config:
        frozen = True


class Search_testresultsQuery(BaseModel):
    options: Tuple[Search_testresultsQueryOptions, ...]

    class Arguments(BaseModel):
        search: Optional[str] = Field(default=None)
        values: Optional[List[ID]] = Field(default=None)

    class Meta:
        document = "query search_testresults($search: String, $values: [ID!]) {\n  options: testResults(\n    filters: {name: {iContains: $search}, ids: $values}\n    pagination: {limit: 10}\n  ) {\n    label: createdAt\n    value: id\n  }\n}"


class GetAgentQuery(BaseModel):
    agent: AgentFragment

    class Arguments(BaseModel):
        id: ID

    class Meta:
        document = "fragment Agent on Agent {\n  registry {\n    app {\n      id\n    }\n    user {\n      id\n    }\n  }\n}\n\nquery GetAgent($id: ID!) {\n  agent(id: $id) {\n    ...Agent\n  }\n}"


class RequestsQuery(BaseModel):
    assignations: Tuple[AssignationFragment, ...]

    class Arguments(BaseModel):
        instance_id: InstanceId

    class Meta:
        document = "fragment Assignation on Assignation {\n  args\n  id\n  parent {\n    id\n  }\n  id\n  status\n  events {\n    id\n    returns\n    level\n  }\n  reference\n  updatedAt\n}\n\nquery requests($instance_id: InstanceId!) {\n  assignations(filters: {reservation: {waiter: {instanceId: $instance_id}}}) {\n    ...Assignation\n  }\n}"


class Get_templateQuery(BaseModel):
    template: TemplateFragment

    class Arguments(BaseModel):
        id: ID

    class Meta:
        document = "fragment ChildPortNested on ChildPort {\n  kind\n  child {\n    identifier\n    nullable\n    kind\n  }\n  identifier\n  nullable\n}\n\nfragment ChildPort on ChildPort {\n  kind\n  identifier\n  child {\n    ...ChildPortNested\n  }\n  nullable\n}\n\nfragment Port on Port {\n  __typename\n  key\n  label\n  nullable\n  description\n  default\n  kind\n  identifier\n  child {\n    ...ChildPort\n  }\n  variants {\n    ...ChildPort\n  }\n}\n\nfragment Definition on Node {\n  args {\n    ...Port\n  }\n  returns {\n    ...Port\n  }\n  kind\n  name\n  description\n}\n\nfragment Node on Node {\n  hash\n  id\n  ...Definition\n}\n\nfragment Template on Template {\n  id\n  agent {\n    registry {\n      id\n    }\n  }\n  node {\n    ...Node\n  }\n  params\n}\n\nquery get_template($id: ID!) {\n  template(id: $id) {\n    ...Template\n  }\n}"


class Search_templatesQueryOptions(BaseModel):
    typename: Optional[Literal["Template"]] = Field(alias="__typename", exclude=True)
    label: str
    value: ID

    class Config:
        frozen = True


class Search_templatesQuery(BaseModel):
    options: Tuple[Search_templatesQueryOptions, ...]

    class Arguments(BaseModel):
        search: Optional[str] = Field(default=None)
        values: Optional[List[ID]] = Field(default=None)

    class Meta:
        document = "query search_templates($search: String, $values: [ID!]) {\n  options: templates(\n    filters: {interface: {iContains: $search}, ids: $values}\n    pagination: {limit: 10}\n  ) {\n    label: name\n    value: id\n  }\n}"


class FindQuery(BaseModel):
    node: NodeFragment

    class Arguments(BaseModel):
        id: Optional[ID] = Field(default=None)
        template: Optional[ID] = Field(default=None)
        hash: Optional[NodeHash] = Field(default=None)

    class Meta:
        document = "fragment ChildPortNested on ChildPort {\n  kind\n  child {\n    identifier\n    nullable\n    kind\n  }\n  identifier\n  nullable\n}\n\nfragment ChildPort on ChildPort {\n  kind\n  identifier\n  child {\n    ...ChildPortNested\n  }\n  nullable\n}\n\nfragment Port on Port {\n  __typename\n  key\n  label\n  nullable\n  description\n  default\n  kind\n  identifier\n  child {\n    ...ChildPort\n  }\n  variants {\n    ...ChildPort\n  }\n}\n\nfragment Definition on Node {\n  args {\n    ...Port\n  }\n  returns {\n    ...Port\n  }\n  kind\n  name\n  description\n}\n\nfragment Node on Node {\n  hash\n  id\n  ...Definition\n}\n\nquery find($id: ID, $template: ID, $hash: NodeHash) {\n  node(id: $id, template: $template, hash: $hash) {\n    ...Node\n  }\n}"


class RetrieveallQuery(BaseModel):
    nodes: Tuple[NodeFragment, ...]

    class Arguments(BaseModel):
        pass

    class Meta:
        document = "fragment ChildPortNested on ChildPort {\n  kind\n  child {\n    identifier\n    nullable\n    kind\n  }\n  identifier\n  nullable\n}\n\nfragment ChildPort on ChildPort {\n  kind\n  identifier\n  child {\n    ...ChildPortNested\n  }\n  nullable\n}\n\nfragment Port on Port {\n  __typename\n  key\n  label\n  nullable\n  description\n  default\n  kind\n  identifier\n  child {\n    ...ChildPort\n  }\n  variants {\n    ...ChildPort\n  }\n}\n\nfragment Definition on Node {\n  args {\n    ...Port\n  }\n  returns {\n    ...Port\n  }\n  kind\n  name\n  description\n}\n\nfragment Node on Node {\n  hash\n  id\n  ...Definition\n}\n\nquery retrieveall {\n  nodes {\n    ...Node\n  }\n}"


class Search_nodesQueryOptions(Reserve, BaseModel):
    typename: Optional[Literal["Node"]] = Field(alias="__typename", exclude=True)
    label: str
    value: ID

    class Config:
        frozen = True


class Search_nodesQuery(BaseModel):
    options: Tuple[Search_nodesQueryOptions, ...]

    class Arguments(BaseModel):
        search: Optional[str] = Field(default=None)
        values: Optional[List[ID]] = Field(default=None)

    class Meta:
        document = "query search_nodes($search: String, $values: [ID!]) {\n  options: nodes(\n    filters: {name: {iContains: $search}, ids: $values}\n    pagination: {limit: 10}\n  ) {\n    label: name\n    value: id\n  }\n}"


class Get_reservationQueryReservationProvisions(BaseModel):
    typename: Optional[Literal["Provision"]] = Field(alias="__typename", exclude=True)
    id: ID
    status: ProvisionStatus

    class Config:
        frozen = True


class Get_reservationQueryReservationNode(Reserve, BaseModel):
    typename: Optional[Literal["Node"]] = Field(alias="__typename", exclude=True)
    id: ID
    kind: NodeKind
    name: str

    class Config:
        frozen = True


class Get_reservationQueryReservation(BaseModel):
    typename: Optional[Literal["Reservation"]] = Field(alias="__typename", exclude=True)
    id: ID
    provisions: Tuple[Get_reservationQueryReservationProvisions, ...]
    title: Optional[str]
    status: ReservationStatus
    id: ID
    reference: str
    node: Get_reservationQueryReservationNode

    class Config:
        frozen = True


class Get_reservationQuery(BaseModel):
    reservation: Get_reservationQueryReservation

    class Arguments(BaseModel):
        id: ID

    class Meta:
        document = "query get_reservation($id: ID!) {\n  reservation(id: $id) {\n    id\n    provisions {\n      id\n      status\n    }\n    title\n    status\n    id\n    reference\n    node {\n      id\n      kind\n      name\n    }\n  }\n}"


class ReservationsQuery(BaseModel):
    reservations: Tuple[ReservationFragment, ...]

    class Arguments(BaseModel):
        instance_id: InstanceId

    class Meta:
        document = "fragment Reservation on Reservation {\n  id\n  status\n  node {\n    id\n    hash\n  }\n  waiter {\n    id\n  }\n  reference\n  updatedAt\n}\n\nquery reservations($instance_id: InstanceId!) {\n  reservations(filters: {waiter: {instanceId: $instance_id}}) {\n    ...Reservation\n  }\n}"


async def acreate_testcase(
    node: ID,
    key: str,
    description: str,
    name: str,
    is_benchmark: Optional[bool] = None,
    rath: RekuestNextRath = None,
) -> TestCaseFragment:
    """create_testcase



    Arguments:
        node (ID): node
        key (str): key
        description (str): description
        name (str): name
        is_benchmark (Optional[bool], optional): is_benchmark.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TestCaseFragment"""
    return (
        await aexecute(
            Create_testcaseMutation,
            {
                "node": node,
                "key": key,
                "is_benchmark": is_benchmark,
                "description": description,
                "name": name,
            },
            rath=rath,
        )
    ).create_test_case


def create_testcase(
    node: ID,
    key: str,
    description: str,
    name: str,
    is_benchmark: Optional[bool] = None,
    rath: RekuestNextRath = None,
) -> TestCaseFragment:
    """create_testcase



    Arguments:
        node (ID): node
        key (str): key
        description (str): description
        name (str): name
        is_benchmark (Optional[bool], optional): is_benchmark.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TestCaseFragment"""
    return execute(
        Create_testcaseMutation,
        {
            "node": node,
            "key": key,
            "is_benchmark": is_benchmark,
            "description": description,
            "name": name,
        },
        rath=rath,
    ).create_test_case


async def acreate_testresult(
    case: ID,
    template: ID,
    passed: bool,
    result: Optional[str] = None,
    rath: RekuestNextRath = None,
) -> TestResultFragment:
    """create_testresult



    Arguments:
        case (ID): case
        template (ID): template
        passed (bool): passed
        result (Optional[str], optional): result.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TestResultFragment"""
    return (
        await aexecute(
            Create_testresultMutation,
            {"case": case, "template": template, "passed": passed, "result": result},
            rath=rath,
        )
    ).create_test_result


def create_testresult(
    case: ID,
    template: ID,
    passed: bool,
    result: Optional[str] = None,
    rath: RekuestNextRath = None,
) -> TestResultFragment:
    """create_testresult



    Arguments:
        case (ID): case
        template (ID): template
        passed (bool): passed
        result (Optional[str], optional): result.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TestResultFragment"""
    return execute(
        Create_testresultMutation,
        {"case": case, "template": template, "passed": passed, "result": result},
        rath=rath,
    ).create_test_result


async def aassign(
    reservation: ID,
    args: List[Any],
    reference: Optional[str] = None,
    parent: Optional[ID] = None,
    rath: RekuestNextRath = None,
) -> AssignationFragment:
    """assign



    Arguments:
        reservation (ID): reservation
        args (List[Any]): args
        reference (Optional[str], optional): reference.
        parent (Optional[ID], optional): parent.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        AssignationFragment"""
    return (
        await aexecute(
            AssignMutation,
            {
                "reservation": reservation,
                "args": args,
                "reference": reference,
                "parent": parent,
            },
            rath=rath,
        )
    ).assign


def assign(
    reservation: ID,
    args: List[Any],
    reference: Optional[str] = None,
    parent: Optional[ID] = None,
    rath: RekuestNextRath = None,
) -> AssignationFragment:
    """assign



    Arguments:
        reservation (ID): reservation
        args (List[Any]): args
        reference (Optional[str], optional): reference.
        parent (Optional[ID], optional): parent.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        AssignationFragment"""
    return execute(
        AssignMutation,
        {
            "reservation": reservation,
            "args": args,
            "reference": reference,
            "parent": parent,
        },
        rath=rath,
    ).assign


async def aunassign(id: ID, rath: RekuestNextRath = None) -> AssignationFragment:
    """unassign



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        AssignationFragment"""
    return (await aexecute(UnassignMutation, {"id": id}, rath=rath)).unassign


def unassign(id: ID, rath: RekuestNextRath = None) -> AssignationFragment:
    """unassign



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        AssignationFragment"""
    return execute(UnassignMutation, {"id": id}, rath=rath).unassign


async def acreate_template(
    interface: str,
    definition: DefinitionInput,
    instance_id: InstanceId,
    params: Optional[Any] = None,
    rath: RekuestNextRath = None,
) -> TemplateFragment:
    """createTemplate



    Arguments:
        interface (str): interface
        definition (DefinitionInput): definition
        instance_id (InstanceId): instance_id
        params (Optional[Any], optional): params.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TemplateFragment"""
    return (
        await aexecute(
            CreateTemplateMutation,
            {
                "interface": interface,
                "definition": definition,
                "instance_id": instance_id,
                "params": params,
            },
            rath=rath,
        )
    ).create_template


def create_template(
    interface: str,
    definition: DefinitionInput,
    instance_id: InstanceId,
    params: Optional[Any] = None,
    rath: RekuestNextRath = None,
) -> TemplateFragment:
    """createTemplate



    Arguments:
        interface (str): interface
        definition (DefinitionInput): definition
        instance_id (InstanceId): instance_id
        params (Optional[Any], optional): params.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TemplateFragment"""
    return execute(
        CreateTemplateMutation,
        {
            "interface": interface,
            "definition": definition,
            "instance_id": instance_id,
            "params": params,
        },
        rath=rath,
    ).create_template


async def areserve(
    instance_id: InstanceId,
    node: Optional[ID] = None,
    hash: Optional[NodeHash] = None,
    title: Optional[str] = None,
    reference: Optional[str] = None,
    provision: Optional[ID] = None,
    binds: Optional[BindsInput] = None,
    rath: RekuestNextRath = None,
) -> ReservationFragment:
    """reserve



    Arguments:
        instance_id (InstanceId): instanceId
        node (Optional[ID], optional): node.
        hash (Optional[NodeHash], optional): hash.
        title (Optional[str], optional): title.
        reference (Optional[str], optional): reference.
        provision (Optional[ID], optional): provision.
        binds (Optional[BindsInput], optional): binds.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        ReservationFragment"""
    return (
        await aexecute(
            ReserveMutation,
            {
                "node": node,
                "hash": hash,
                "title": title,
                "reference": reference,
                "provision": provision,
                "binds": binds,
                "instanceId": instance_id,
            },
            rath=rath,
        )
    ).reserve


def reserve(
    instance_id: InstanceId,
    node: Optional[ID] = None,
    hash: Optional[NodeHash] = None,
    title: Optional[str] = None,
    reference: Optional[str] = None,
    provision: Optional[ID] = None,
    binds: Optional[BindsInput] = None,
    rath: RekuestNextRath = None,
) -> ReservationFragment:
    """reserve



    Arguments:
        instance_id (InstanceId): instanceId
        node (Optional[ID], optional): node.
        hash (Optional[NodeHash], optional): hash.
        title (Optional[str], optional): title.
        reference (Optional[str], optional): reference.
        provision (Optional[ID], optional): provision.
        binds (Optional[BindsInput], optional): binds.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        ReservationFragment"""
    return execute(
        ReserveMutation,
        {
            "node": node,
            "hash": hash,
            "title": title,
            "reference": reference,
            "provision": provision,
            "binds": binds,
            "instanceId": instance_id,
        },
        rath=rath,
    ).reserve


async def aunreserve(
    id: ID, rath: RekuestNextRath = None
) -> UnreserveMutationUnreserve:
    """unreserve



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        UnreserveMutationUnreserve"""
    return (await aexecute(UnreserveMutation, {"id": id}, rath=rath)).unreserve


def unreserve(id: ID, rath: RekuestNextRath = None) -> UnreserveMutationUnreserve:
    """unreserve



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        UnreserveMutationUnreserve"""
    return execute(UnreserveMutation, {"id": id}, rath=rath).unreserve


async def awatch_provisions(
    instance_id: InstanceId, rath: RekuestNextRath = None
) -> AsyncIterator[ProvisionEventFragment]:
    """WatchProvisions



    Arguments:
        instance_id (InstanceId): instanceId
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        ProvisionEventFragment"""
    async for event in asubscribe(
        WatchProvisionsSubscription, {"instanceId": instance_id}, rath=rath
    ):
        yield event.provisions


def watch_provisions(
    instance_id: InstanceId, rath: RekuestNextRath = None
) -> Iterator[ProvisionEventFragment]:
    """WatchProvisions



    Arguments:
        instance_id (InstanceId): instanceId
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        ProvisionEventFragment"""
    for event in subscribe(
        WatchProvisionsSubscription, {"instanceId": instance_id}, rath=rath
    ):
        yield event.provisions


async def awatch_assignations(
    instance_id: InstanceId, rath: RekuestNextRath = None
) -> AsyncIterator[AssignationEventFragment]:
    """WatchAssignations



    Arguments:
        instance_id (InstanceId): instanceId
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        AssignationEventFragment"""
    async for event in asubscribe(
        WatchAssignationsSubscription, {"instanceId": instance_id}, rath=rath
    ):
        yield event.assignations


def watch_assignations(
    instance_id: InstanceId, rath: RekuestNextRath = None
) -> Iterator[AssignationEventFragment]:
    """WatchAssignations



    Arguments:
        instance_id (InstanceId): instanceId
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        AssignationEventFragment"""
    for event in subscribe(
        WatchAssignationsSubscription, {"instanceId": instance_id}, rath=rath
    ):
        yield event.assignations


async def awatch_reservations(
    instance_id: InstanceId, rath: RekuestNextRath = None
) -> AsyncIterator[ReservationEventFragment]:
    """WatchReservations



    Arguments:
        instance_id (InstanceId): instanceId
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        ReservationEventFragment"""
    async for event in asubscribe(
        WatchReservationsSubscription, {"instanceId": instance_id}, rath=rath
    ):
        yield event.reservations


def watch_reservations(
    instance_id: InstanceId, rath: RekuestNextRath = None
) -> Iterator[ReservationEventFragment]:
    """WatchReservations



    Arguments:
        instance_id (InstanceId): instanceId
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        ReservationEventFragment"""
    for event in subscribe(
        WatchReservationsSubscription, {"instanceId": instance_id}, rath=rath
    ):
        yield event.reservations


async def aget_provision(id: ID, rath: RekuestNextRath = None) -> ProvisionFragment:
    """get_provision



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        ProvisionFragment"""
    return (await aexecute(Get_provisionQuery, {"id": id}, rath=rath)).provision


def get_provision(id: ID, rath: RekuestNextRath = None) -> ProvisionFragment:
    """get_provision



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        ProvisionFragment"""
    return execute(Get_provisionQuery, {"id": id}, rath=rath).provision


async def aget_testcase(id: ID, rath: RekuestNextRath = None) -> TestCaseFragment:
    """get_testcase



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TestCaseFragment"""
    return (await aexecute(Get_testcaseQuery, {"id": id}, rath=rath)).test_case


def get_testcase(id: ID, rath: RekuestNextRath = None) -> TestCaseFragment:
    """get_testcase



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TestCaseFragment"""
    return execute(Get_testcaseQuery, {"id": id}, rath=rath).test_case


async def aget_testresult(id: ID, rath: RekuestNextRath = None) -> TestResultFragment:
    """get_testresult



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TestResultFragment"""
    return (await aexecute(Get_testresultQuery, {"id": id}, rath=rath)).test_result


def get_testresult(id: ID, rath: RekuestNextRath = None) -> TestResultFragment:
    """get_testresult



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TestResultFragment"""
    return execute(Get_testresultQuery, {"id": id}, rath=rath).test_result


async def asearch_testcases(
    search: Optional[str] = None,
    values: Optional[List[ID]] = None,
    rath: RekuestNextRath = None,
) -> List[Search_testcasesQueryOptions]:
    """search_testcases



    Arguments:
        search (Optional[str], optional): search.
        values (Optional[List[ID]], optional): values.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[Search_testcasesQueryTestcases]"""
    return (
        await aexecute(
            Search_testcasesQuery, {"search": search, "values": values}, rath=rath
        )
    ).test_cases


def search_testcases(
    search: Optional[str] = None,
    values: Optional[List[ID]] = None,
    rath: RekuestNextRath = None,
) -> List[Search_testcasesQueryOptions]:
    """search_testcases



    Arguments:
        search (Optional[str], optional): search.
        values (Optional[List[ID]], optional): values.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[Search_testcasesQueryTestcases]"""
    return execute(
        Search_testcasesQuery, {"search": search, "values": values}, rath=rath
    ).test_cases


async def asearch_testresults(
    search: Optional[str] = None,
    values: Optional[List[ID]] = None,
    rath: RekuestNextRath = None,
) -> List[Search_testresultsQueryOptions]:
    """search_testresults



    Arguments:
        search (Optional[str], optional): search.
        values (Optional[List[ID]], optional): values.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[Search_testresultsQueryTestresults]"""
    return (
        await aexecute(
            Search_testresultsQuery, {"search": search, "values": values}, rath=rath
        )
    ).test_results


def search_testresults(
    search: Optional[str] = None,
    values: Optional[List[ID]] = None,
    rath: RekuestNextRath = None,
) -> List[Search_testresultsQueryOptions]:
    """search_testresults



    Arguments:
        search (Optional[str], optional): search.
        values (Optional[List[ID]], optional): values.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[Search_testresultsQueryTestresults]"""
    return execute(
        Search_testresultsQuery, {"search": search, "values": values}, rath=rath
    ).test_results


async def aget_agent(id: ID, rath: RekuestNextRath = None) -> AgentFragment:
    """GetAgent



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        AgentFragment"""
    return (await aexecute(GetAgentQuery, {"id": id}, rath=rath)).agent


def get_agent(id: ID, rath: RekuestNextRath = None) -> AgentFragment:
    """GetAgent



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        AgentFragment"""
    return execute(GetAgentQuery, {"id": id}, rath=rath).agent


async def arequests(
    instance_id: InstanceId, rath: RekuestNextRath = None
) -> List[AssignationFragment]:
    """requests



    Arguments:
        instance_id (InstanceId): instance_id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[AssignationFragment]"""
    return (
        await aexecute(RequestsQuery, {"instance_id": instance_id}, rath=rath)
    ).assignations


def requests(
    instance_id: InstanceId, rath: RekuestNextRath = None
) -> List[AssignationFragment]:
    """requests



    Arguments:
        instance_id (InstanceId): instance_id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[AssignationFragment]"""
    return execute(RequestsQuery, {"instance_id": instance_id}, rath=rath).assignations


async def aget_template(id: ID, rath: RekuestNextRath = None) -> TemplateFragment:
    """get_template



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TemplateFragment"""
    return (await aexecute(Get_templateQuery, {"id": id}, rath=rath)).template


def get_template(id: ID, rath: RekuestNextRath = None) -> TemplateFragment:
    """get_template



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TemplateFragment"""
    return execute(Get_templateQuery, {"id": id}, rath=rath).template


async def asearch_templates(
    search: Optional[str] = None,
    values: Optional[List[ID]] = None,
    rath: RekuestNextRath = None,
) -> List[Search_templatesQueryOptions]:
    """search_templates



    Arguments:
        search (Optional[str], optional): search.
        values (Optional[List[ID]], optional): values.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[Search_templatesQueryTemplates]"""
    return (
        await aexecute(
            Search_templatesQuery, {"search": search, "values": values}, rath=rath
        )
    ).templates


def search_templates(
    search: Optional[str] = None,
    values: Optional[List[ID]] = None,
    rath: RekuestNextRath = None,
) -> List[Search_templatesQueryOptions]:
    """search_templates



    Arguments:
        search (Optional[str], optional): search.
        values (Optional[List[ID]], optional): values.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[Search_templatesQueryTemplates]"""
    return execute(
        Search_templatesQuery, {"search": search, "values": values}, rath=rath
    ).templates


async def afind(
    id: Optional[ID] = None,
    template: Optional[ID] = None,
    hash: Optional[NodeHash] = None,
    rath: RekuestNextRath = None,
) -> NodeFragment:
    """find



    Arguments:
        id (Optional[ID], optional): id.
        template (Optional[ID], optional): template.
        hash (Optional[NodeHash], optional): hash.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        NodeFragment"""
    return (
        await aexecute(
            FindQuery, {"id": id, "template": template, "hash": hash}, rath=rath
        )
    ).node


def find(
    id: Optional[ID] = None,
    template: Optional[ID] = None,
    hash: Optional[NodeHash] = None,
    rath: RekuestNextRath = None,
) -> NodeFragment:
    """find



    Arguments:
        id (Optional[ID], optional): id.
        template (Optional[ID], optional): template.
        hash (Optional[NodeHash], optional): hash.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        NodeFragment"""
    return execute(
        FindQuery, {"id": id, "template": template, "hash": hash}, rath=rath
    ).node


async def aretrieveall(rath: RekuestNextRath = None) -> List[NodeFragment]:
    """retrieveall



    Arguments:
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[NodeFragment]"""
    return (await aexecute(RetrieveallQuery, {}, rath=rath)).nodes


def retrieveall(rath: RekuestNextRath = None) -> List[NodeFragment]:
    """retrieveall



    Arguments:
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[NodeFragment]"""
    return execute(RetrieveallQuery, {}, rath=rath).nodes


async def asearch_nodes(
    search: Optional[str] = None,
    values: Optional[List[ID]] = None,
    rath: RekuestNextRath = None,
) -> List[Search_nodesQueryOptions]:
    """search_nodes



    Arguments:
        search (Optional[str], optional): search.
        values (Optional[List[ID]], optional): values.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[Search_nodesQueryNodes]"""
    return (
        await aexecute(
            Search_nodesQuery, {"search": search, "values": values}, rath=rath
        )
    ).nodes


def search_nodes(
    search: Optional[str] = None,
    values: Optional[List[ID]] = None,
    rath: RekuestNextRath = None,
) -> List[Search_nodesQueryOptions]:
    """search_nodes



    Arguments:
        search (Optional[str], optional): search.
        values (Optional[List[ID]], optional): values.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[Search_nodesQueryNodes]"""
    return execute(
        Search_nodesQuery, {"search": search, "values": values}, rath=rath
    ).nodes


async def aget_reservation(
    id: ID, rath: RekuestNextRath = None
) -> Get_reservationQueryReservation:
    """get_reservation



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Get_reservationQueryReservation"""
    return (await aexecute(Get_reservationQuery, {"id": id}, rath=rath)).reservation


def get_reservation(
    id: ID, rath: RekuestNextRath = None
) -> Get_reservationQueryReservation:
    """get_reservation



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Get_reservationQueryReservation"""
    return execute(Get_reservationQuery, {"id": id}, rath=rath).reservation


async def areservations(
    instance_id: InstanceId, rath: RekuestNextRath = None
) -> List[ReservationFragment]:
    """reservations



    Arguments:
        instance_id (InstanceId): instance_id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[ReservationFragment]"""
    return (
        await aexecute(ReservationsQuery, {"instance_id": instance_id}, rath=rath)
    ).reservations


def reservations(
    instance_id: InstanceId, rath: RekuestNextRath = None
) -> List[ReservationFragment]:
    """reservations



    Arguments:
        instance_id (InstanceId): instance_id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[ReservationFragment]"""
    return execute(
        ReservationsQuery, {"instance_id": instance_id}, rath=rath
    ).reservations


AgentFilter.update_forward_refs()
AssignWidgetInput.update_forward_refs()
AssignationEventFilter.update_forward_refs()
AssignationFilter.update_forward_refs()
ChildPortInput.update_forward_refs()
CreateTemplateInput.update_forward_refs()
DefinitionInput.update_forward_refs()
EffectInput.update_forward_refs()
FlowFilter.update_forward_refs()
GraphEdgeInput.update_forward_refs()
GraphInput.update_forward_refs()
GraphNodeInput.update_forward_refs()
NodeFilter.update_forward_refs()
PortInput.update_forward_refs()
ProvisionFilter.update_forward_refs()
ProvisionFragmentTemplate.update_forward_refs()
ReactiveTemplateFilter.update_forward_refs()
ReservationFilter.update_forward_refs()
ReserveInput.update_forward_refs()
TemplateFilter.update_forward_refs()
TemplateFragment.update_forward_refs()
TestCaseFilter.update_forward_refs()
TestResultFilter.update_forward_refs()
UpdateWorkspaceInput.update_forward_refs()
WaiterFilter.update_forward_refs()
WorkspaceFilter.update_forward_refs()

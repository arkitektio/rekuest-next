from rekuest_next.traits.ports import (
    PortTrait,
    WidgetInputTrait,
    ReturnWidgetInputTrait,
)
from datetime import datetime
from rekuest_next.scalars import (
    Args,
    InstanceId,
    NodeHash,
    SearchQuery,
    Identifier,
    ValidatorFunction,
)
from rath.scalars import ID
from typing_extensions import Literal
from typing import Tuple, List, Optional, Iterator, AsyncIterator, Any
from rekuest_next.traits.node import Reserve
from rekuest_next.funcs import asubscribe, aexecute, subscribe, execute
from enum import Enum
from pydantic import Field, ConfigDict, BaseModel
from rekuest_next.rath import RekuestNextRath


class AssignWidgetKind(str, Enum):
    SEARCH = "SEARCH"
    CHOICE = "CHOICE"
    SLIDER = "SLIDER"
    CUSTOM = "CUSTOM"
    STRING = "STRING"
    STATE_CHOICE = "STATE_CHOICE"


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
    MODEL = "MODEL"


class ReturnWidgetKind(str, Enum):
    CHOICE = "CHOICE"
    CUSTOM = "CUSTOM"


class LogicalCondition(str, Enum):
    IS = "IS"
    IS_NOT = "IS_NOT"
    IN = "IN"


class EffectKind(str, Enum):
    MESSAGE = "MESSAGE"
    CUSTOM = "CUSTOM"


class UIChildKind(str, Enum):
    GRID = "GRID"
    SPLIT = "SPLIT"
    RESERVATION = "RESERVATION"
    STATE = "STATE"


class NodeKind(str, Enum):
    FUNCTION = "FUNCTION"
    GENERATOR = "GENERATOR"


class ReservationEventKind(str, Enum):
    PENDING = "PENDING"
    CREATE = "CREATE"
    RESCHEDULE = "RESCHEDULE"
    DELETED = "DELETED"
    CHANGE = "CHANGE"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    UNCONNECTED = "UNCONNECTED"
    ENDED = "ENDED"
    UNHAPPY = "UNHAPPY"
    HAPPY = "HAPPY"
    LOG = "LOG"


class ProvisionEventKind(str, Enum):
    CHANGE = "CHANGE"
    UNHAPPY = "UNHAPPY"
    PENDING = "PENDING"
    CRITICAL = "CRITICAL"
    DENIED = "DENIED"
    ACTIVE = "ACTIVE"
    REFUSED = "REFUSED"
    INACTIVE = "INACTIVE"
    CANCELING = "CANCELING"
    DISCONNECTED = "DISCONNECTED"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"
    ENDED = "ENDED"
    CANCELLED = "CANCELLED"
    BOUND = "BOUND"
    PROVIDING = "PROVIDING"
    LOG = "LOG"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    ERROR = "ERROR"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class AssignationEventKind(str, Enum):
    BOUND = "BOUND"
    ASSIGN = "ASSIGN"
    PROGRESS = "PROGRESS"
    DISCONNECTED = "DISCONNECTED"
    YIELD = "YIELD"
    DONE = "DONE"
    LOG = "LOG"
    CANCELING = "CANCELING"
    CANCELLED = "CANCELLED"
    INTERUPTING = "INTERUPTING"
    INTERUPTED = "INTERUPTED"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class PanelKind(str, Enum):
    STATE = "STATE"
    ASSIGN = "ASSIGN"


class HookKind(str, Enum):
    CLEANUP = "CLEANUP"
    INIT = "INIT"


class CreateTemplateInput(BaseModel):
    template: "TemplateInput"
    instance_id: InstanceId = Field(alias="instanceId")
    extension: str
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class TemplateInput(BaseModel):
    definition: "DefinitionInput"
    dependencies: Tuple["DependencyInput", ...]
    interface: str
    params: Optional[Any] = None
    dynamic: bool
    logo: Optional[str] = None
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class DefinitionInput(BaseModel):
    description: Optional[str] = None
    collections: Tuple[str, ...]
    name: str
    stateful: bool
    port_groups: Tuple["PortGroupInput", ...] = Field(alias="portGroups")
    args: Tuple["PortInput", ...]
    returns: Tuple["PortInput", ...]
    kind: NodeKind
    is_test_for: Tuple[str, ...] = Field(alias="isTestFor")
    interfaces: Tuple[str, ...]
    is_dev: bool = Field(alias="isDev")
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class PortGroupInput(BaseModel):
    key: str
    hidden: bool
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class PortInput(PortTrait, BaseModel):
    validators: Optional[Tuple["ValidatorInput", ...]] = None
    key: str
    scope: PortScope
    label: Optional[str] = None
    kind: PortKind
    description: Optional[str] = None
    identifier: Optional[str] = None
    nullable: bool
    effects: Optional[Tuple["EffectInput", ...]] = None
    default: Optional[Any] = None
    children: Optional[Tuple["ChildPortInput", ...]] = None
    assign_widget: Optional["AssignWidgetInput"] = Field(
        alias="assignWidget", default=None
    )
    return_widget: Optional["ReturnWidgetInput"] = Field(
        alias="returnWidget", default=None
    )
    groups: Optional[Tuple[str, ...]] = None
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class ValidatorInput(BaseModel):
    function: ValidatorFunction
    dependencies: Optional[Tuple[str, ...]] = None
    label: Optional[str] = None
    error_message: Optional[str] = Field(alias="errorMessage", default=None)
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class EffectInput(BaseModel):
    label: str
    description: Optional[str] = None
    dependencies: Tuple["EffectDependencyInput", ...]
    kind: EffectKind
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class EffectDependencyInput(BaseModel):
    key: str
    condition: LogicalCondition
    value: Any
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class ChildPortInput(PortTrait, BaseModel):
    default: Optional[Any] = None
    key: str
    label: Optional[str] = None
    kind: PortKind
    scope: PortScope
    description: Optional[str] = None
    identifier: Optional[Identifier] = None
    nullable: bool
    children: Optional[Tuple["ChildPortInput", ...]] = None
    effects: Optional[Tuple[EffectInput, ...]] = None
    assign_widget: Optional["AssignWidgetInput"] = Field(
        alias="assignWidget", default=None
    )
    return_widget: Optional["ReturnWidgetInput"] = Field(
        alias="returnWidget", default=None
    )
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class AssignWidgetInput(WidgetInputTrait, BaseModel):
    as_paragraph: Optional[bool] = Field(alias="asParagraph", default=None)
    kind: AssignWidgetKind
    query: Optional[SearchQuery] = None
    choices: Optional[Tuple["ChoiceInput", ...]] = None
    state_choices: Optional[str] = Field(alias="stateChoices", default=None)
    follow_value: Optional[str] = Field(alias="followValue", default=None)
    min: Optional[int] = None
    max: Optional[int] = None
    step: Optional[int] = None
    placeholder: Optional[str] = None
    hook: Optional[str] = None
    ward: Optional[str] = None
    fallback: Optional["AssignWidgetInput"] = None
    filters: Optional[Tuple[ChildPortInput, ...]] = None
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class ChoiceInput(BaseModel):
    value: Any
    label: str
    description: Optional[str] = None
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class ReturnWidgetInput(ReturnWidgetInputTrait, BaseModel):
    kind: ReturnWidgetKind
    query: Optional[SearchQuery] = None
    choices: Optional[Tuple[ChoiceInput, ...]] = None
    min: Optional[int] = None
    max: Optional[int] = None
    step: Optional[int] = None
    placeholder: Optional[str] = None
    hook: Optional[str] = None
    ward: Optional[str] = None
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class DependencyInput(BaseModel):
    hash: Optional[NodeHash] = None
    reference: Optional[str] = None
    binds: Optional["BindsInput"] = None
    optional: bool
    viable_instances: Optional[int] = Field(alias="viableInstances", default=None)
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class BindsInput(BaseModel):
    templates: Optional[Tuple[str, ...]] = None
    clients: Optional[Tuple[str, ...]] = None
    desired_instances: int = Field(alias="desiredInstances")
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class SetExtensionTemplatesInput(BaseModel):
    templates: Tuple[TemplateInput, ...]
    instance_id: InstanceId = Field(alias="instanceId")
    extension: str
    run_cleanup: bool = Field(alias="runCleanup")
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class AssignInput(BaseModel):
    instance_id: InstanceId = Field(alias="instanceId")
    node: Optional[ID] = None
    template: Optional[ID] = None
    reservation: Optional[ID] = None
    hooks: Optional[Tuple["HookInput", ...]] = None
    args: Args
    reference: Optional[str] = None
    parent: Optional[ID] = None
    cached: bool
    log: bool
    ephemeral: bool
    is_hook: bool = Field(alias="isHook")
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class HookInput(BaseModel):
    kind: HookKind
    hash: str
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class CancelInput(BaseModel):
    assignation: ID
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class InterruptInput(BaseModel):
    assignation: ID
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class ReserveInput(BaseModel):
    assignation_id: Optional[str] = Field(alias="assignationId", default=None)
    instance_id: InstanceId = Field(alias="instanceId")
    node: Optional[ID] = None
    template: Optional[ID] = None
    title: Optional[str] = None
    hash: Optional[NodeHash] = None
    reference: Optional[str] = None
    binds: Optional[BindsInput] = None
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class UnreserveInput(BaseModel):
    reservation: ID
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class CreateDashboardInput(BaseModel):
    name: Optional[str] = None
    panels: Optional[Tuple[ID, ...]] = None
    tree: Optional["UITreeInput"] = None
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class UITreeInput(BaseModel):
    child: "UIChildInput"
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class UIChildInput(BaseModel):
    state: Optional[str] = None
    kind: UIChildKind
    hidden: Optional[bool] = None
    children: Optional[Tuple["UIChildInput", ...]] = None
    left: Optional["UIChildInput"] = None
    right: Optional["UIChildInput"] = None
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class CreateStateSchemaInput(BaseModel):
    state_schema: "StateSchemaInput" = Field(alias="stateSchema")
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class StateSchemaInput(BaseModel):
    ports: Tuple[PortInput, ...]
    name: str
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class CreatePanelInput(BaseModel):
    name: str
    kind: PanelKind
    state: Optional[ID] = None
    state_key: Optional[str] = Field(alias="stateKey", default=None)
    reservation: Optional[ID] = None
    instance_id: Optional[InstanceId] = Field(alias="instanceId", default=None)
    state_accessors: Optional[Tuple[str, ...]] = Field(
        alias="stateAccessors", default=None
    )
    interface: Optional[str] = None
    args: Optional[Args] = None
    submit_on_change: Optional[bool] = Field(alias="submitOnChange", default=None)
    submit_on_load: Optional[bool] = Field(alias="submitOnLoad", default=None)
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class SetStateInput(BaseModel):
    state_schema: ID = Field(alias="stateSchema")
    instance_id: InstanceId = Field(alias="instanceId")
    value: Args
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class UpdateStateInput(BaseModel):
    state_schema: ID = Field(alias="stateSchema")
    instance_id: InstanceId = Field(alias="instanceId")
    patches: Tuple[Args, ...]
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class TestCaseNode(Reserve, BaseModel):
    typename: Optional[Literal["Node"]] = Field(
        alias="__typename", default="Node", exclude=True
    )
    id: ID
    model_config = ConfigDict(frozen=True)


class TestCase(BaseModel):
    typename: Optional[Literal["TestCase"]] = Field(
        alias="__typename", default="TestCase", exclude=True
    )
    id: ID
    node: TestCaseNode
    is_benchmark: bool = Field(alias="isBenchmark")
    description: str
    name: str
    model_config = ConfigDict(frozen=True)


class TestResultCase(BaseModel):
    typename: Optional[Literal["TestCase"]] = Field(
        alias="__typename", default="TestCase", exclude=True
    )
    id: ID
    model_config = ConfigDict(frozen=True)


class TestResult(BaseModel):
    typename: Optional[Literal["TestResult"]] = Field(
        alias="__typename", default="TestResult", exclude=True
    )
    id: ID
    case: TestResultCase
    passed: bool
    model_config = ConfigDict(frozen=True)


class Provision(BaseModel):
    typename: Optional[Literal["Provision"]] = Field(
        alias="__typename", default="Provision", exclude=True
    )
    id: ID
    status: ProvisionEventKind
    template: "Template"
    model_config = ConfigDict(frozen=True)


class StateAgent(BaseModel):
    typename: Optional[Literal["Agent"]] = Field(
        alias="__typename", default="Agent", exclude=True
    )
    id: ID
    model_config = ConfigDict(frozen=True)


class State(BaseModel):
    typename: Optional[Literal["State"]] = Field(
        alias="__typename", default="State", exclude=True
    )
    id: ID
    value: Args
    state_schema: "StateSchema" = Field(alias="stateSchema")
    agent: StateAgent
    model_config = ConfigDict(frozen=True)


class ChildPortNestedChildren(PortTrait, BaseModel):
    typename: Optional[Literal["ChildPort"]] = Field(
        alias="__typename", default="ChildPort", exclude=True
    )
    identifier: Optional[Identifier] = Field(default=None)
    nullable: bool
    kind: PortKind
    model_config = ConfigDict(frozen=True)


class ChildPortNested(PortTrait, BaseModel):
    typename: Optional[Literal["ChildPort"]] = Field(
        alias="__typename", default="ChildPort", exclude=True
    )
    key: str
    kind: PortKind
    children: Optional[Tuple[ChildPortNestedChildren, ...]] = Field(default=None)
    identifier: Optional[Identifier] = Field(default=None)
    nullable: bool
    model_config = ConfigDict(frozen=True)


class ChildPort(PortTrait, BaseModel):
    typename: Optional[Literal["ChildPort"]] = Field(
        alias="__typename", default="ChildPort", exclude=True
    )
    key: str
    kind: PortKind
    identifier: Optional[Identifier] = Field(default=None)
    children: Optional[Tuple[ChildPortNested, ...]] = Field(default=None)
    nullable: bool
    model_config = ConfigDict(frozen=True)


class PortValidators(BaseModel):
    typename: Optional[Literal["Validator"]] = Field(
        alias="__typename", default="Validator", exclude=True
    )
    function: ValidatorFunction
    error_message: Optional[str] = Field(default=None, alias="errorMessage")
    dependencies: Optional[Tuple[str, ...]] = Field(default=None)
    label: Optional[str] = Field(default=None)
    model_config = ConfigDict(frozen=True)


class Port(PortTrait, BaseModel):
    typename: Optional[Literal["Port"]] = Field(
        alias="__typename", default="Port", exclude=True
    )
    key: str
    label: Optional[str] = Field(default=None)
    nullable: bool
    description: Optional[str] = Field(default=None)
    default: Optional[Any] = Field(default=None)
    kind: PortKind
    identifier: Optional[Identifier] = Field(default=None)
    children: Optional[Tuple[ChildPort, ...]] = Field(default=None)
    validators: Optional[Tuple[PortValidators, ...]] = Field(default=None)
    model_config = ConfigDict(frozen=True)


class AgentRegistryApp(BaseModel):
    typename: Optional[Literal["App"]] = Field(
        alias="__typename", default="App", exclude=True
    )
    id: ID
    model_config = ConfigDict(frozen=True)


class AgentRegistryUser(BaseModel):
    typename: Optional[Literal["User"]] = Field(
        alias="__typename", default="User", exclude=True
    )
    id: ID
    model_config = ConfigDict(frozen=True)


class AgentRegistry(BaseModel):
    typename: Optional[Literal["Registry"]] = Field(
        alias="__typename", default="Registry", exclude=True
    )
    app: AgentRegistryApp
    user: AgentRegistryUser
    model_config = ConfigDict(frozen=True)


class Agent(BaseModel):
    typename: Optional[Literal["Agent"]] = Field(
        alias="__typename", default="Agent", exclude=True
    )
    registry: AgentRegistry
    model_config = ConfigDict(frozen=True)


class PanelState(BaseModel):
    typename: Optional[Literal["State"]] = Field(
        alias="__typename", default="State", exclude=True
    )
    id: ID
    model_config = ConfigDict(frozen=True)


class PanelReservation(BaseModel):
    typename: Optional[Literal["Reservation"]] = Field(
        alias="__typename", default="Reservation", exclude=True
    )
    id: ID
    model_config = ConfigDict(frozen=True)


class Panel(BaseModel):
    typename: Optional[Literal["Panel"]] = Field(
        alias="__typename", default="Panel", exclude=True
    )
    id: ID
    kind: PanelKind
    state: Optional[PanelState] = Field(default=None)
    reservation: Optional[PanelReservation] = Field(default=None)
    model_config = ConfigDict(frozen=True)


class ReservationNode(Reserve, BaseModel):
    typename: Optional[Literal["Node"]] = Field(
        alias="__typename", default="Node", exclude=True
    )
    id: ID
    hash: NodeHash
    model_config = ConfigDict(frozen=True)


class ReservationWaiter(BaseModel):
    typename: Optional[Literal["Waiter"]] = Field(
        alias="__typename", default="Waiter", exclude=True
    )
    id: ID
    model_config = ConfigDict(frozen=True)


class Reservation(BaseModel):
    typename: Optional[Literal["Reservation"]] = Field(
        alias="__typename", default="Reservation", exclude=True
    )
    id: ID
    status: ReservationEventKind
    node: ReservationNode
    waiter: ReservationWaiter
    reference: str
    updated_at: datetime = Field(alias="updatedAt")
    model_config = ConfigDict(frozen=True)


class DashboardUitreeChildBase(BaseModel):
    pass
    model_config = ConfigDict(frozen=True)


class DashboardUitreeChildUIGridInlineFragmentChildren(BaseModel):
    typename: Optional[Literal["UIGridItem"]] = Field(
        alias="__typename", default="UIGridItem", exclude=True
    )
    x: int
    y: int
    w: int
    h: int
    model_config = ConfigDict(frozen=True)


class DashboardUitreeChildUIGridInlineFragment(DashboardUitreeChildBase):
    typename: Optional[Literal["UIGrid"]] = Field(
        alias="__typename", default="UIGrid", exclude=True
    )
    row_height: int = Field(alias="rowHeight")
    children: Tuple[DashboardUitreeChildUIGridInlineFragmentChildren, ...]
    model_config = ConfigDict(frozen=True)


class DashboardUitree(BaseModel):
    typename: Optional[Literal["UITree"]] = Field(
        alias="__typename", default="UITree", exclude=True
    )
    child: DashboardUitreeChildUIGridInlineFragment
    model_config = ConfigDict(frozen=True)


class DashboardPanelsState(BaseModel):
    typename: Optional[Literal["State"]] = Field(
        alias="__typename", default="State", exclude=True
    )
    id: ID
    model_config = ConfigDict(frozen=True)


class DashboardPanelsReservation(BaseModel):
    typename: Optional[Literal["Reservation"]] = Field(
        alias="__typename", default="Reservation", exclude=True
    )
    id: ID
    model_config = ConfigDict(frozen=True)


class DashboardPanels(BaseModel):
    typename: Optional[Literal["Panel"]] = Field(
        alias="__typename", default="Panel", exclude=True
    )
    id: ID
    state: Optional[DashboardPanelsState] = Field(default=None)
    reservation: Optional[DashboardPanelsReservation] = Field(default=None)
    model_config = ConfigDict(frozen=True)


class Dashboard(BaseModel):
    typename: Optional[Literal["Dashboard"]] = Field(
        alias="__typename", default="Dashboard", exclude=True
    )
    id: ID
    name: Optional[str] = Field(default=None)
    ui_tree: Optional[DashboardUitree] = Field(default=None, alias="uiTree")
    panels: Optional[Tuple[DashboardPanels, ...]] = Field(default=None)
    model_config = ConfigDict(frozen=True)


class AssignationParent(BaseModel):
    typename: Optional[Literal["Assignation"]] = Field(
        alias="__typename", default="Assignation", exclude=True
    )
    id: ID
    model_config = ConfigDict(frozen=True)


class AssignationEvents(BaseModel):
    typename: Optional[Literal["AssignationEvent"]] = Field(
        alias="__typename", default="AssignationEvent", exclude=True
    )
    id: ID
    returns: Optional[Any] = Field(default=None)
    level: Optional[LogLevel] = Field(default=None)
    model_config = ConfigDict(frozen=True)


class Assignation(BaseModel):
    typename: Optional[Literal["Assignation"]] = Field(
        alias="__typename", default="Assignation", exclude=True
    )
    args: Any
    id: ID
    parent: Optional[AssignationParent] = Field(default=None)
    "A parent assignation is the next assignation in the chain of assignations that caused this assignation to be created. Parents can be created by intent or by the system. If null, this assignation is the parent"
    id: ID
    status: AssignationEventKind
    "The status of this assignation"
    events: Tuple[AssignationEvents, ...]
    reference: Optional[str] = Field(default=None)
    updated_at: datetime = Field(alias="updatedAt")
    model_config = ConfigDict(frozen=True)


class AssignationEvent(BaseModel):
    typename: Optional[Literal["AssignationEvent"]] = Field(
        alias="__typename", default="AssignationEvent", exclude=True
    )
    id: ID
    kind: AssignationEventKind
    returns: Optional[Any] = Field(default=None)
    reference: str
    message: Optional[str] = Field(default=None)
    progress: Optional[int] = Field(default=None)
    model_config = ConfigDict(frozen=True)


class AssignationChangeEvent(BaseModel):
    typename: Optional[Literal["AssignationChangeEvent"]] = Field(
        alias="__typename", default="AssignationChangeEvent", exclude=True
    )
    create: Optional[Assignation] = Field(default=None)
    event: Optional[AssignationEvent] = Field(default=None)
    model_config = ConfigDict(frozen=True)


class StateSchema(BaseModel):
    typename: Optional[Literal["StateSchema"]] = Field(
        alias="__typename", default="StateSchema", exclude=True
    )
    id: ID
    name: str
    ports: Tuple[Port, ...]
    model_config = ConfigDict(frozen=True)


class TemplateAgentRegistry(BaseModel):
    typename: Optional[Literal["Registry"]] = Field(
        alias="__typename", default="Registry", exclude=True
    )
    id: ID
    model_config = ConfigDict(frozen=True)


class TemplateAgent(BaseModel):
    typename: Optional[Literal["Agent"]] = Field(
        alias="__typename", default="Agent", exclude=True
    )
    registry: TemplateAgentRegistry
    model_config = ConfigDict(frozen=True)


class Template(BaseModel):
    typename: Optional[Literal["Template"]] = Field(
        alias="__typename", default="Template", exclude=True
    )
    id: ID
    agent: TemplateAgent
    node: "Node"
    params: Any
    extension: str
    interface: str
    model_config = ConfigDict(frozen=True)


class DefinitionCollections(BaseModel):
    typename: Optional[Literal["Collection"]] = Field(
        alias="__typename", default="Collection", exclude=True
    )
    name: str
    model_config = ConfigDict(frozen=True)


class DefinitionIstestfor(Reserve, BaseModel):
    typename: Optional[Literal["Node"]] = Field(
        alias="__typename", default="Node", exclude=True
    )
    id: ID
    model_config = ConfigDict(frozen=True)


class DefinitionPortgroups(BaseModel):
    typename: Optional[Literal["PortGroup"]] = Field(
        alias="__typename", default="PortGroup", exclude=True
    )
    key: str
    model_config = ConfigDict(frozen=True)


class Definition(Reserve, BaseModel):
    typename: Optional[Literal["Node"]] = Field(
        alias="__typename", default="Node", exclude=True
    )
    args: Tuple[Port, ...]
    returns: Tuple[Port, ...]
    kind: NodeKind
    name: str
    description: Optional[str] = Field(default=None)
    interfaces: Tuple[str, ...]
    collections: Tuple[DefinitionCollections, ...]
    is_dev: bool = Field(alias="isDev")
    is_test_for: Tuple[DefinitionIstestfor, ...] = Field(alias="isTestFor")
    port_groups: Tuple[DefinitionPortgroups, ...] = Field(alias="portGroups")
    stateful: bool
    model_config = ConfigDict(frozen=True)


class Node(Definition, Reserve, BaseModel):
    typename: Optional[Literal["Node"]] = Field(
        alias="__typename", default="Node", exclude=True
    )
    hash: NodeHash
    id: ID
    model_config = ConfigDict(frozen=True)


class Create_testcaseMutation(BaseModel):
    create_test_case: TestCase = Field(alias="createTestCase")

    class Arguments(BaseModel):
        node: ID
        tester: ID
        description: str
        name: str

    class Meta:
        document = "fragment TestCase on TestCase {\n  id\n  node {\n    id\n  }\n  isBenchmark\n  description\n  name\n}\n\nmutation create_testcase($node: ID!, $tester: ID!, $description: String!, $name: String!) {\n  createTestCase(\n    input: {node: $node, tester: $tester, description: $description, name: $name}\n  ) {\n    ...TestCase\n  }\n}"


class Create_testresultMutation(BaseModel):
    create_test_result: TestResult = Field(alias="createTestResult")

    class Arguments(BaseModel):
        case: ID
        template: ID
        tester: ID
        passed: bool
        result: Optional[str] = Field(default=None)

    class Meta:
        document = "fragment TestResult on TestResult {\n  id\n  case {\n    id\n  }\n  passed\n}\n\nmutation create_testresult($case: ID!, $template: ID!, $tester: ID!, $passed: Boolean!, $result: String) {\n  createTestResult(\n    input: {case: $case, tester: $tester, template: $template, passed: $passed, result: $result}\n  ) {\n    ...TestResult\n  }\n}"


class SetStateMutation(BaseModel):
    set_state: State = Field(alias="setState")

    class Arguments(BaseModel):
        input: SetStateInput

    class Meta:
        document = "fragment ChildPortNested on ChildPort {\n  key\n  kind\n  children {\n    identifier\n    nullable\n    kind\n  }\n  identifier\n  nullable\n}\n\nfragment ChildPort on ChildPort {\n  key\n  kind\n  identifier\n  children {\n    ...ChildPortNested\n  }\n  nullable\n}\n\nfragment Port on Port {\n  __typename\n  key\n  label\n  nullable\n  description\n  default\n  kind\n  identifier\n  children {\n    ...ChildPort\n  }\n  validators {\n    function\n    errorMessage\n    dependencies\n    label\n  }\n}\n\nfragment StateSchema on StateSchema {\n  id\n  name\n  ports {\n    ...Port\n  }\n}\n\nfragment State on State {\n  id\n  value\n  stateSchema {\n    ...StateSchema\n  }\n  agent {\n    id\n  }\n}\n\nmutation SetState($input: SetStateInput!) {\n  setState(input: $input) {\n    ...State\n  }\n}"


class UpdateStateMutation(BaseModel):
    update_state: State = Field(alias="updateState")

    class Arguments(BaseModel):
        input: UpdateStateInput

    class Meta:
        document = "fragment ChildPortNested on ChildPort {\n  key\n  kind\n  children {\n    identifier\n    nullable\n    kind\n  }\n  identifier\n  nullable\n}\n\nfragment ChildPort on ChildPort {\n  key\n  kind\n  identifier\n  children {\n    ...ChildPortNested\n  }\n  nullable\n}\n\nfragment Port on Port {\n  __typename\n  key\n  label\n  nullable\n  description\n  default\n  kind\n  identifier\n  children {\n    ...ChildPort\n  }\n  validators {\n    function\n    errorMessage\n    dependencies\n    label\n  }\n}\n\nfragment StateSchema on StateSchema {\n  id\n  name\n  ports {\n    ...Port\n  }\n}\n\nfragment State on State {\n  id\n  value\n  stateSchema {\n    ...StateSchema\n  }\n  agent {\n    id\n  }\n}\n\nmutation UpdateState($input: UpdateStateInput!) {\n  updateState(input: $input) {\n    ...State\n  }\n}"


class EnsureAgentMutationEnsureagent(BaseModel):
    typename: Optional[Literal["Agent"]] = Field(
        alias="__typename", default="Agent", exclude=True
    )
    id: ID
    instance_id: InstanceId = Field(alias="instanceId")
    extensions: Tuple[str, ...]
    name: str
    model_config = ConfigDict(frozen=True)


class EnsureAgentMutation(BaseModel):
    ensure_agent: EnsureAgentMutationEnsureagent = Field(alias="ensureAgent")

    class Arguments(BaseModel):
        instance_id: InstanceId = Field(alias="instanceId")
        extensions: Optional[List[str]] = Field(default=None)
        name: Optional[str] = Field(default=None)

    class Meta:
        document = "mutation EnsureAgent($instanceId: InstanceId!, $extensions: [String!], $name: String) {\n  ensureAgent(\n    input: {instanceId: $instanceId, extensions: $extensions, name: $name}\n  ) {\n    id\n    instanceId\n    extensions\n    name\n  }\n}"


class CreatePanelMutation(BaseModel):
    create_panel: Panel = Field(alias="createPanel")

    class Arguments(BaseModel):
        input: CreatePanelInput

    class Meta:
        document = "fragment Panel on Panel {\n  id\n  kind\n  state {\n    id\n  }\n  reservation {\n    id\n  }\n}\n\nmutation CreatePanel($input: CreatePanelInput!) {\n  createPanel(input: $input) {\n    ...Panel\n  }\n}"


class ReserveMutation(BaseModel):
    reserve: Reservation

    class Arguments(BaseModel):
        input: ReserveInput

    class Meta:
        document = "fragment Reservation on Reservation {\n  id\n  status\n  node {\n    id\n    hash\n  }\n  waiter {\n    id\n  }\n  reference\n  updatedAt\n}\n\nmutation reserve($input: ReserveInput!) {\n  reserve(input: $input) {\n    ...Reservation\n  }\n}"


class UnreserveMutation(BaseModel):
    unreserve: str

    class Arguments(BaseModel):
        input: UnreserveInput

    class Meta:
        document = "mutation unreserve($input: UnreserveInput!) {\n  unreserve(input: $input)\n}"


class AssignMutation(BaseModel):
    assign: Assignation

    class Arguments(BaseModel):
        input: AssignInput

    class Meta:
        document = "fragment Assignation on Assignation {\n  args\n  id\n  parent {\n    id\n  }\n  id\n  status\n  events {\n    id\n    returns\n    level\n  }\n  reference\n  updatedAt\n}\n\nmutation assign($input: AssignInput!) {\n  assign(input: $input) {\n    ...Assignation\n  }\n}"


class CancelMutation(BaseModel):
    cancel: Assignation

    class Arguments(BaseModel):
        input: CancelInput

    class Meta:
        document = "fragment Assignation on Assignation {\n  args\n  id\n  parent {\n    id\n  }\n  id\n  status\n  events {\n    id\n    returns\n    level\n  }\n  reference\n  updatedAt\n}\n\nmutation cancel($input: CancelInput!) {\n  cancel(input: $input) {\n    ...Assignation\n  }\n}"


class InterruptMutation(BaseModel):
    interrupt: Assignation

    class Arguments(BaseModel):
        input: InterruptInput

    class Meta:
        document = "fragment Assignation on Assignation {\n  args\n  id\n  parent {\n    id\n  }\n  id\n  status\n  events {\n    id\n    returns\n    level\n  }\n  reference\n  updatedAt\n}\n\nmutation interrupt($input: InterruptInput!) {\n  interrupt(input: $input) {\n    ...Assignation\n  }\n}"


class CreateDashboardMutation(BaseModel):
    create_dashboard: Dashboard = Field(alias="createDashboard")

    class Arguments(BaseModel):
        input: CreateDashboardInput

    class Meta:
        document = "fragment Dashboard on Dashboard {\n  id\n  name\n  uiTree {\n    child {\n      ... on UIGrid {\n        rowHeight\n        children {\n          x\n          y\n          w\n          h\n        }\n      }\n    }\n  }\n  panels {\n    id\n    state {\n      id\n    }\n    reservation {\n      id\n    }\n  }\n}\n\nmutation CreateDashboard($input: CreateDashboardInput!) {\n  createDashboard(input: $input) {\n    ...Dashboard\n  }\n}"


class CreateStateSchemaMutation(BaseModel):
    create_state_schema: StateSchema = Field(alias="createStateSchema")

    class Arguments(BaseModel):
        input: CreateStateSchemaInput

    class Meta:
        document = "fragment ChildPortNested on ChildPort {\n  key\n  kind\n  children {\n    identifier\n    nullable\n    kind\n  }\n  identifier\n  nullable\n}\n\nfragment ChildPort on ChildPort {\n  key\n  kind\n  identifier\n  children {\n    ...ChildPortNested\n  }\n  nullable\n}\n\nfragment Port on Port {\n  __typename\n  key\n  label\n  nullable\n  description\n  default\n  kind\n  identifier\n  children {\n    ...ChildPort\n  }\n  validators {\n    function\n    errorMessage\n    dependencies\n    label\n  }\n}\n\nfragment StateSchema on StateSchema {\n  id\n  name\n  ports {\n    ...Port\n  }\n}\n\nmutation CreateStateSchema($input: CreateStateSchemaInput!) {\n  createStateSchema(input: $input) {\n    ...StateSchema\n  }\n}"


class CreateHardwareRecordMutationCreatehardwarerecordAgent(BaseModel):
    typename: Optional[Literal["Agent"]] = Field(
        alias="__typename", default="Agent", exclude=True
    )
    id: ID
    model_config = ConfigDict(frozen=True)


class CreateHardwareRecordMutationCreatehardwarerecord(BaseModel):
    typename: Optional[Literal["HardwareRecord"]] = Field(
        alias="__typename", default="HardwareRecord", exclude=True
    )
    id: ID
    cpu_count: int = Field(alias="cpuCount")
    agent: CreateHardwareRecordMutationCreatehardwarerecordAgent
    model_config = ConfigDict(frozen=True)


class CreateHardwareRecordMutation(BaseModel):
    create_hardware_record: CreateHardwareRecordMutationCreatehardwarerecord = Field(
        alias="createHardwareRecord"
    )

    class Arguments(BaseModel):
        cpu_count: Optional[int] = Field(alias="cpuCount", default=None)
        cpu_frequency: Optional[float] = Field(alias="cpuFrequency", default=None)
        cpu_vendor_name: Optional[str] = Field(alias="cpuVendorName", default=None)

    class Meta:
        document = "mutation CreateHardwareRecord($cpuCount: Int, $cpuFrequency: Float, $cpuVendorName: String) {\n  createHardwareRecord(\n    input: {cpuCount: $cpuCount, cpuFrequency: $cpuFrequency, cpuVendorName: $cpuVendorName}\n  ) {\n    id\n    cpuCount\n    agent {\n      id\n    }\n  }\n}"


class CreateTemplateMutation(BaseModel):
    create_template: Template = Field(alias="createTemplate")

    class Arguments(BaseModel):
        input: CreateTemplateInput

    class Meta:
        document = "fragment ChildPortNested on ChildPort {\n  key\n  kind\n  children {\n    identifier\n    nullable\n    kind\n  }\n  identifier\n  nullable\n}\n\nfragment ChildPort on ChildPort {\n  key\n  kind\n  identifier\n  children {\n    ...ChildPortNested\n  }\n  nullable\n}\n\nfragment Port on Port {\n  __typename\n  key\n  label\n  nullable\n  description\n  default\n  kind\n  identifier\n  children {\n    ...ChildPort\n  }\n  validators {\n    function\n    errorMessage\n    dependencies\n    label\n  }\n}\n\nfragment Definition on Node {\n  args {\n    ...Port\n  }\n  returns {\n    ...Port\n  }\n  kind\n  name\n  description\n  interfaces\n  collections {\n    name\n  }\n  isDev\n  isTestFor {\n    id\n  }\n  portGroups {\n    key\n  }\n  stateful\n}\n\nfragment Node on Node {\n  hash\n  id\n  ...Definition\n}\n\nfragment Template on Template {\n  id\n  agent {\n    registry {\n      id\n    }\n  }\n  node {\n    ...Node\n  }\n  params\n  extension\n  interface\n}\n\nmutation createTemplate($input: CreateTemplateInput!) {\n  createTemplate(input: $input) {\n    ...Template\n  }\n}"


class SetExtensionTemplatesMutation(BaseModel):
    set_extension_templates: Tuple[Template, ...] = Field(alias="setExtensionTemplates")

    class Arguments(BaseModel):
        input: SetExtensionTemplatesInput

    class Meta:
        document = "fragment ChildPortNested on ChildPort {\n  key\n  kind\n  children {\n    identifier\n    nullable\n    kind\n  }\n  identifier\n  nullable\n}\n\nfragment ChildPort on ChildPort {\n  key\n  kind\n  identifier\n  children {\n    ...ChildPortNested\n  }\n  nullable\n}\n\nfragment Port on Port {\n  __typename\n  key\n  label\n  nullable\n  description\n  default\n  kind\n  identifier\n  children {\n    ...ChildPort\n  }\n  validators {\n    function\n    errorMessage\n    dependencies\n    label\n  }\n}\n\nfragment Definition on Node {\n  args {\n    ...Port\n  }\n  returns {\n    ...Port\n  }\n  kind\n  name\n  description\n  interfaces\n  collections {\n    name\n  }\n  isDev\n  isTestFor {\n    id\n  }\n  portGroups {\n    key\n  }\n  stateful\n}\n\nfragment Node on Node {\n  hash\n  id\n  ...Definition\n}\n\nfragment Template on Template {\n  id\n  agent {\n    registry {\n      id\n    }\n  }\n  node {\n    ...Node\n  }\n  params\n  extension\n  interface\n}\n\nmutation SetExtensionTemplates($input: SetExtensionTemplatesInput!) {\n  setExtensionTemplates(input: $input) {\n    ...Template\n  }\n}"


class MyTemplateAtQuery(BaseModel):
    my_template_at: Template = Field(alias="myTemplateAt")

    class Arguments(BaseModel):
        instance_id: str = Field(alias="instanceId")
        interface: Optional[str] = Field(default=None)
        node_id: Optional[ID] = Field(alias="nodeId", default=None)

    class Meta:
        document = "fragment ChildPortNested on ChildPort {\n  key\n  kind\n  children {\n    identifier\n    nullable\n    kind\n  }\n  identifier\n  nullable\n}\n\nfragment ChildPort on ChildPort {\n  key\n  kind\n  identifier\n  children {\n    ...ChildPortNested\n  }\n  nullable\n}\n\nfragment Port on Port {\n  __typename\n  key\n  label\n  nullable\n  description\n  default\n  kind\n  identifier\n  children {\n    ...ChildPort\n  }\n  validators {\n    function\n    errorMessage\n    dependencies\n    label\n  }\n}\n\nfragment Definition on Node {\n  args {\n    ...Port\n  }\n  returns {\n    ...Port\n  }\n  kind\n  name\n  description\n  interfaces\n  collections {\n    name\n  }\n  isDev\n  isTestFor {\n    id\n  }\n  portGroups {\n    key\n  }\n  stateful\n}\n\nfragment Node on Node {\n  hash\n  id\n  ...Definition\n}\n\nfragment Template on Template {\n  id\n  agent {\n    registry {\n      id\n    }\n  }\n  node {\n    ...Node\n  }\n  params\n  extension\n  interface\n}\n\nquery MyTemplateAt($instanceId: String!, $interface: String, $nodeId: ID) {\n  myTemplateAt(instanceId: $instanceId, interface: $interface, nodeId: $nodeId) {\n    ...Template\n  }\n}"


class WatchReservationsSubscription(BaseModel):
    reservations: Reservation

    class Arguments(BaseModel):
        instance_id: InstanceId = Field(alias="instanceId")

    class Meta:
        document = "fragment Reservation on Reservation {\n  id\n  status\n  node {\n    id\n    hash\n  }\n  waiter {\n    id\n  }\n  reference\n  updatedAt\n}\n\nsubscription WatchReservations($instanceId: InstanceId!) {\n  reservations(instanceId: $instanceId) {\n    ...Reservation\n  }\n}"


class WatchAssignationsSubscription(BaseModel):
    assignations: AssignationChangeEvent

    class Arguments(BaseModel):
        instance_id: InstanceId = Field(alias="instanceId")

    class Meta:
        document = "fragment AssignationEvent on AssignationEvent {\n  id\n  kind\n  returns\n  reference\n  message\n  progress\n}\n\nfragment Assignation on Assignation {\n  args\n  id\n  parent {\n    id\n  }\n  id\n  status\n  events {\n    id\n    returns\n    level\n  }\n  reference\n  updatedAt\n}\n\nfragment AssignationChangeEvent on AssignationChangeEvent {\n  create {\n    ...Assignation\n  }\n  event {\n    ...AssignationEvent\n  }\n}\n\nsubscription WatchAssignations($instanceId: InstanceId!) {\n  assignations(instanceId: $instanceId) {\n    ...AssignationChangeEvent\n  }\n}"


class Get_testcaseQuery(BaseModel):
    test_case: TestCase = Field(alias="testCase")

    class Arguments(BaseModel):
        id: ID

    class Meta:
        document = "fragment TestCase on TestCase {\n  id\n  node {\n    id\n  }\n  isBenchmark\n  description\n  name\n}\n\nquery get_testcase($id: ID!) {\n  testCase(id: $id) {\n    ...TestCase\n  }\n}"


class Get_testresultQuery(BaseModel):
    test_result: TestResult = Field(alias="testResult")

    class Arguments(BaseModel):
        id: ID

    class Meta:
        document = "fragment TestResult on TestResult {\n  id\n  case {\n    id\n  }\n  passed\n}\n\nquery get_testresult($id: ID!) {\n  testResult(id: $id) {\n    ...TestResult\n  }\n}"


class Search_testcasesQueryOptions(BaseModel):
    typename: Optional[Literal["TestCase"]] = Field(
        alias="__typename", default="TestCase", exclude=True
    )
    label: str
    value: ID
    model_config = ConfigDict(frozen=True)


class Search_testcasesQuery(BaseModel):
    options: Tuple[Search_testcasesQueryOptions, ...]

    class Arguments(BaseModel):
        search: Optional[str] = Field(default=None)
        values: Optional[List[ID]] = Field(default=None)

    class Meta:
        document = "query search_testcases($search: String, $values: [ID!]) {\n  options: testCases(\n    filters: {name: {iContains: $search}, ids: $values}\n    pagination: {limit: 10}\n  ) {\n    label: name\n    value: id\n  }\n}"


class Search_testresultsQueryOptions(BaseModel):
    typename: Optional[Literal["TestResult"]] = Field(
        alias="__typename", default="TestResult", exclude=True
    )
    label: datetime
    value: ID
    model_config = ConfigDict(frozen=True)


class Search_testresultsQuery(BaseModel):
    options: Tuple[Search_testresultsQueryOptions, ...]

    class Arguments(BaseModel):
        search: Optional[str] = Field(default=None)
        values: Optional[List[ID]] = Field(default=None)

    class Meta:
        document = "query search_testresults($search: String, $values: [ID!]) {\n  options: testResults(\n    filters: {name: {iContains: $search}, ids: $values}\n    pagination: {limit: 10}\n  ) {\n    label: createdAt\n    value: id\n  }\n}"


class Get_provisionQuery(BaseModel):
    provision: Provision

    class Arguments(BaseModel):
        id: ID

    class Meta:
        document = "fragment ChildPortNested on ChildPort {\n  key\n  kind\n  children {\n    identifier\n    nullable\n    kind\n  }\n  identifier\n  nullable\n}\n\nfragment ChildPort on ChildPort {\n  key\n  kind\n  identifier\n  children {\n    ...ChildPortNested\n  }\n  nullable\n}\n\nfragment Port on Port {\n  __typename\n  key\n  label\n  nullable\n  description\n  default\n  kind\n  identifier\n  children {\n    ...ChildPort\n  }\n  validators {\n    function\n    errorMessage\n    dependencies\n    label\n  }\n}\n\nfragment Definition on Node {\n  args {\n    ...Port\n  }\n  returns {\n    ...Port\n  }\n  kind\n  name\n  description\n  interfaces\n  collections {\n    name\n  }\n  isDev\n  isTestFor {\n    id\n  }\n  portGroups {\n    key\n  }\n  stateful\n}\n\nfragment Node on Node {\n  hash\n  id\n  ...Definition\n}\n\nfragment Template on Template {\n  id\n  agent {\n    registry {\n      id\n    }\n  }\n  node {\n    ...Node\n  }\n  params\n  extension\n  interface\n}\n\nfragment Provision on Provision {\n  id\n  status\n  template {\n    ...Template\n  }\n}\n\nquery get_provision($id: ID!) {\n  provision(id: $id) {\n    ...Provision\n  }\n}"


class GetMeNodesQueryNodes(Reserve, BaseModel):
    typename: Optional[Literal["Node"]] = Field(
        alias="__typename", default="Node", exclude=True
    )
    id: ID
    name: str
    model_config = ConfigDict(frozen=True)


class GetMeNodesQuery(BaseModel):
    nodes: Tuple[GetMeNodesQueryNodes, ...]

    class Arguments(BaseModel):
        pass

    class Meta:
        document = "query GetMeNodes {\n  nodes {\n    id\n    name\n  }\n}"


class GetAgentQuery(BaseModel):
    agent: Agent

    class Arguments(BaseModel):
        id: ID

    class Meta:
        document = "fragment Agent on Agent {\n  registry {\n    app {\n      id\n    }\n    user {\n      id\n    }\n  }\n}\n\nquery GetAgent($id: ID!) {\n  agent(id: $id) {\n    ...Agent\n  }\n}"


class GetPanelQuery(BaseModel):
    panel: Panel

    class Arguments(BaseModel):
        id: ID

    class Meta:
        document = "fragment Panel on Panel {\n  id\n  kind\n  state {\n    id\n  }\n  reservation {\n    id\n  }\n}\n\nquery GetPanel($id: ID!) {\n  panel(id: $id) {\n    ...Panel\n  }\n}"


class Get_reservationQueryReservationProvisions(BaseModel):
    typename: Optional[Literal["Provision"]] = Field(
        alias="__typename", default="Provision", exclude=True
    )
    id: ID
    status: ProvisionEventKind
    model_config = ConfigDict(frozen=True)


class Get_reservationQueryReservationNode(Reserve, BaseModel):
    typename: Optional[Literal["Node"]] = Field(
        alias="__typename", default="Node", exclude=True
    )
    id: ID
    kind: NodeKind
    name: str
    model_config = ConfigDict(frozen=True)


class Get_reservationQueryReservation(BaseModel):
    typename: Optional[Literal["Reservation"]] = Field(
        alias="__typename", default="Reservation", exclude=True
    )
    id: ID
    provisions: Tuple[Get_reservationQueryReservationProvisions, ...]
    title: Optional[str] = Field(default=None)
    status: ReservationEventKind
    id: ID
    reference: str
    node: Get_reservationQueryReservationNode
    model_config = ConfigDict(frozen=True)


class Get_reservationQuery(BaseModel):
    reservation: Get_reservationQueryReservation

    class Arguments(BaseModel):
        id: ID

    class Meta:
        document = "query get_reservation($id: ID!) {\n  reservation(id: $id) {\n    id\n    provisions {\n      id\n      status\n    }\n    title\n    status\n    id\n    reference\n    node {\n      id\n      kind\n      name\n    }\n  }\n}"


class ReservationsQuery(BaseModel):
    reservations: Tuple[Reservation, ...]

    class Arguments(BaseModel):
        instance_id: InstanceId

    class Meta:
        document = "fragment Reservation on Reservation {\n  id\n  status\n  node {\n    id\n    hash\n  }\n  waiter {\n    id\n  }\n  reference\n  updatedAt\n}\n\nquery reservations($instance_id: InstanceId!) {\n  reservations(instanceId: $instance_id) {\n    ...Reservation\n  }\n}"


class RequestsQuery(BaseModel):
    assignations: Tuple[Assignation, ...]

    class Arguments(BaseModel):
        instance_id: InstanceId

    class Meta:
        document = "fragment Assignation on Assignation {\n  args\n  id\n  parent {\n    id\n  }\n  id\n  status\n  events {\n    id\n    returns\n    level\n  }\n  reference\n  updatedAt\n}\n\nquery requests($instance_id: InstanceId!) {\n  assignations(instanceId: $instance_id) {\n    ...Assignation\n  }\n}"


class GetEventQuery(BaseModel):
    event: Tuple[AssignationEvent, ...]

    class Arguments(BaseModel):
        id: Optional[ID] = Field(default=None)

    class Meta:
        document = "fragment AssignationEvent on AssignationEvent {\n  id\n  kind\n  returns\n  reference\n  message\n  progress\n}\n\nquery GetEvent($id: ID) {\n  event(id: $id) {\n    ...AssignationEvent\n  }\n}"


class GetDashboardQuery(BaseModel):
    dashboard: Dashboard

    class Arguments(BaseModel):
        id: ID

    class Meta:
        document = "fragment Dashboard on Dashboard {\n  id\n  name\n  uiTree {\n    child {\n      ... on UIGrid {\n        rowHeight\n        children {\n          x\n          y\n          w\n          h\n        }\n      }\n    }\n  }\n  panels {\n    id\n    state {\n      id\n    }\n    reservation {\n      id\n    }\n  }\n}\n\nquery GetDashboard($id: ID!) {\n  dashboard(id: $id) {\n    ...Dashboard\n  }\n}"


class Get_templateQuery(BaseModel):
    template: Template

    class Arguments(BaseModel):
        id: ID

    class Meta:
        document = "fragment ChildPortNested on ChildPort {\n  key\n  kind\n  children {\n    identifier\n    nullable\n    kind\n  }\n  identifier\n  nullable\n}\n\nfragment ChildPort on ChildPort {\n  key\n  kind\n  identifier\n  children {\n    ...ChildPortNested\n  }\n  nullable\n}\n\nfragment Port on Port {\n  __typename\n  key\n  label\n  nullable\n  description\n  default\n  kind\n  identifier\n  children {\n    ...ChildPort\n  }\n  validators {\n    function\n    errorMessage\n    dependencies\n    label\n  }\n}\n\nfragment Definition on Node {\n  args {\n    ...Port\n  }\n  returns {\n    ...Port\n  }\n  kind\n  name\n  description\n  interfaces\n  collections {\n    name\n  }\n  isDev\n  isTestFor {\n    id\n  }\n  portGroups {\n    key\n  }\n  stateful\n}\n\nfragment Node on Node {\n  hash\n  id\n  ...Definition\n}\n\nfragment Template on Template {\n  id\n  agent {\n    registry {\n      id\n    }\n  }\n  node {\n    ...Node\n  }\n  params\n  extension\n  interface\n}\n\nquery get_template($id: ID!) {\n  template(id: $id) {\n    ...Template\n  }\n}"


class Search_templatesQueryOptions(BaseModel):
    typename: Optional[Literal["Template"]] = Field(
        alias="__typename", default="Template", exclude=True
    )
    label: str
    value: ID
    model_config = ConfigDict(frozen=True)


class Search_templatesQuery(BaseModel):
    options: Tuple[Search_templatesQueryOptions, ...]

    class Arguments(BaseModel):
        search: Optional[str] = Field(default=None)
        values: Optional[List[ID]] = Field(default=None)

    class Meta:
        document = "query search_templates($search: String, $values: [ID!]) {\n  options: templates(\n    filters: {interface: {iContains: $search}, ids: $values}\n    pagination: {limit: 10}\n  ) {\n    label: name\n    value: id\n  }\n}"


class Templates_forQuery(BaseModel):
    templates: Tuple[Template, ...]

    class Arguments(BaseModel):
        hash: NodeHash

    class Meta:
        document = "fragment ChildPortNested on ChildPort {\n  key\n  kind\n  children {\n    identifier\n    nullable\n    kind\n  }\n  identifier\n  nullable\n}\n\nfragment ChildPort on ChildPort {\n  key\n  kind\n  identifier\n  children {\n    ...ChildPortNested\n  }\n  nullable\n}\n\nfragment Port on Port {\n  __typename\n  key\n  label\n  nullable\n  description\n  default\n  kind\n  identifier\n  children {\n    ...ChildPort\n  }\n  validators {\n    function\n    errorMessage\n    dependencies\n    label\n  }\n}\n\nfragment Definition on Node {\n  args {\n    ...Port\n  }\n  returns {\n    ...Port\n  }\n  kind\n  name\n  description\n  interfaces\n  collections {\n    name\n  }\n  isDev\n  isTestFor {\n    id\n  }\n  portGroups {\n    key\n  }\n  stateful\n}\n\nfragment Node on Node {\n  hash\n  id\n  ...Definition\n}\n\nfragment Template on Template {\n  id\n  agent {\n    registry {\n      id\n    }\n  }\n  node {\n    ...Node\n  }\n  params\n  extension\n  interface\n}\n\nquery templates_for($hash: NodeHash!) {\n  templates(filters: {nodeHash: $hash}) {\n    ...Template\n  }\n}"


class FindQuery(BaseModel):
    node: Node

    class Arguments(BaseModel):
        id: Optional[ID] = Field(default=None)
        template: Optional[ID] = Field(default=None)
        hash: Optional[NodeHash] = Field(default=None)

    class Meta:
        document = "fragment ChildPortNested on ChildPort {\n  key\n  kind\n  children {\n    identifier\n    nullable\n    kind\n  }\n  identifier\n  nullable\n}\n\nfragment ChildPort on ChildPort {\n  key\n  kind\n  identifier\n  children {\n    ...ChildPortNested\n  }\n  nullable\n}\n\nfragment Port on Port {\n  __typename\n  key\n  label\n  nullable\n  description\n  default\n  kind\n  identifier\n  children {\n    ...ChildPort\n  }\n  validators {\n    function\n    errorMessage\n    dependencies\n    label\n  }\n}\n\nfragment Definition on Node {\n  args {\n    ...Port\n  }\n  returns {\n    ...Port\n  }\n  kind\n  name\n  description\n  interfaces\n  collections {\n    name\n  }\n  isDev\n  isTestFor {\n    id\n  }\n  portGroups {\n    key\n  }\n  stateful\n}\n\nfragment Node on Node {\n  hash\n  id\n  ...Definition\n}\n\nquery find($id: ID, $template: ID, $hash: NodeHash) {\n  node(id: $id, template: $template, hash: $hash) {\n    ...Node\n  }\n}"


class RetrieveallQuery(BaseModel):
    nodes: Tuple[Node, ...]

    class Arguments(BaseModel):
        pass

    class Meta:
        document = "fragment ChildPortNested on ChildPort {\n  key\n  kind\n  children {\n    identifier\n    nullable\n    kind\n  }\n  identifier\n  nullable\n}\n\nfragment ChildPort on ChildPort {\n  key\n  kind\n  identifier\n  children {\n    ...ChildPortNested\n  }\n  nullable\n}\n\nfragment Port on Port {\n  __typename\n  key\n  label\n  nullable\n  description\n  default\n  kind\n  identifier\n  children {\n    ...ChildPort\n  }\n  validators {\n    function\n    errorMessage\n    dependencies\n    label\n  }\n}\n\nfragment Definition on Node {\n  args {\n    ...Port\n  }\n  returns {\n    ...Port\n  }\n  kind\n  name\n  description\n  interfaces\n  collections {\n    name\n  }\n  isDev\n  isTestFor {\n    id\n  }\n  portGroups {\n    key\n  }\n  stateful\n}\n\nfragment Node on Node {\n  hash\n  id\n  ...Definition\n}\n\nquery retrieveall {\n  nodes {\n    ...Node\n  }\n}"


class Search_nodesQueryOptions(Reserve, BaseModel):
    typename: Optional[Literal["Node"]] = Field(
        alias="__typename", default="Node", exclude=True
    )
    label: str
    value: ID
    model_config = ConfigDict(frozen=True)


class Search_nodesQuery(BaseModel):
    options: Tuple[Search_nodesQueryOptions, ...]

    class Arguments(BaseModel):
        search: Optional[str] = Field(default=None)
        values: Optional[List[ID]] = Field(default=None)

    class Meta:
        document = "query search_nodes($search: String, $values: [ID!]) {\n  options: nodes(\n    filters: {name: {iContains: $search}, ids: $values}\n    pagination: {limit: 10}\n  ) {\n    label: name\n    value: id\n  }\n}"


async def acreate_testcase(
    node: ID,
    tester: ID,
    description: str,
    name: str,
    rath: Optional[RekuestNextRath] = None,
) -> TestCase:
    """create_testcase



    Arguments:
        node (ID): node
        tester (ID): tester
        description (str): description
        name (str): name
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TestCase"""
    return (
        await aexecute(
            Create_testcaseMutation,
            {"node": node, "tester": tester, "description": description, "name": name},
            rath=rath,
        )
    ).create_test_case


def create_testcase(
    node: ID,
    tester: ID,
    description: str,
    name: str,
    rath: Optional[RekuestNextRath] = None,
) -> TestCase:
    """create_testcase



    Arguments:
        node (ID): node
        tester (ID): tester
        description (str): description
        name (str): name
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TestCase"""
    return execute(
        Create_testcaseMutation,
        {"node": node, "tester": tester, "description": description, "name": name},
        rath=rath,
    ).create_test_case


async def acreate_testresult(
    case: ID,
    template: ID,
    tester: ID,
    passed: bool,
    result: Optional[str] = None,
    rath: Optional[RekuestNextRath] = None,
) -> TestResult:
    """create_testresult



    Arguments:
        case (ID): case
        template (ID): template
        tester (ID): tester
        passed (bool): passed
        result (Optional[str], optional): result.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TestResult"""
    return (
        await aexecute(
            Create_testresultMutation,
            {
                "case": case,
                "template": template,
                "tester": tester,
                "passed": passed,
                "result": result,
            },
            rath=rath,
        )
    ).create_test_result


def create_testresult(
    case: ID,
    template: ID,
    tester: ID,
    passed: bool,
    result: Optional[str] = None,
    rath: Optional[RekuestNextRath] = None,
) -> TestResult:
    """create_testresult



    Arguments:
        case (ID): case
        template (ID): template
        tester (ID): tester
        passed (bool): passed
        result (Optional[str], optional): result.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TestResult"""
    return execute(
        Create_testresultMutation,
        {
            "case": case,
            "template": template,
            "tester": tester,
            "passed": passed,
            "result": result,
        },
        rath=rath,
    ).create_test_result


async def aset_state(
    input: SetStateInput, rath: Optional[RekuestNextRath] = None
) -> State:
    """SetState



    Arguments:
        input (SetStateInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        State"""
    return (await aexecute(SetStateMutation, {"input": input}, rath=rath)).set_state


def set_state(input: SetStateInput, rath: Optional[RekuestNextRath] = None) -> State:
    """SetState



    Arguments:
        input (SetStateInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        State"""
    return execute(SetStateMutation, {"input": input}, rath=rath).set_state


async def aupdate_state(
    input: UpdateStateInput, rath: Optional[RekuestNextRath] = None
) -> State:
    """UpdateState



    Arguments:
        input (UpdateStateInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        State"""
    return (
        await aexecute(UpdateStateMutation, {"input": input}, rath=rath)
    ).update_state


def update_state(
    input: UpdateStateInput, rath: Optional[RekuestNextRath] = None
) -> State:
    """UpdateState



    Arguments:
        input (UpdateStateInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        State"""
    return execute(UpdateStateMutation, {"input": input}, rath=rath).update_state


async def aensure_agent(
    instance_id: InstanceId,
    extensions: Optional[List[str]] = None,
    name: Optional[str] = None,
    rath: Optional[RekuestNextRath] = None,
) -> EnsureAgentMutationEnsureagent:
    """EnsureAgent



    Arguments:
        instance_id (InstanceId): instanceId
        extensions (Optional[List[str]], optional): extensions.
        name (Optional[str], optional): name.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        EnsureAgentMutationEnsureagent"""
    return (
        await aexecute(
            EnsureAgentMutation,
            {"instanceId": instance_id, "extensions": extensions, "name": name},
            rath=rath,
        )
    ).ensure_agent


def ensure_agent(
    instance_id: InstanceId,
    extensions: Optional[List[str]] = None,
    name: Optional[str] = None,
    rath: Optional[RekuestNextRath] = None,
) -> EnsureAgentMutationEnsureagent:
    """EnsureAgent



    Arguments:
        instance_id (InstanceId): instanceId
        extensions (Optional[List[str]], optional): extensions.
        name (Optional[str], optional): name.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        EnsureAgentMutationEnsureagent"""
    return execute(
        EnsureAgentMutation,
        {"instanceId": instance_id, "extensions": extensions, "name": name},
        rath=rath,
    ).ensure_agent


async def acreate_panel(
    input: CreatePanelInput, rath: Optional[RekuestNextRath] = None
) -> Panel:
    """CreatePanel



    Arguments:
        input (CreatePanelInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Panel"""
    return (
        await aexecute(CreatePanelMutation, {"input": input}, rath=rath)
    ).create_panel


def create_panel(
    input: CreatePanelInput, rath: Optional[RekuestNextRath] = None
) -> Panel:
    """CreatePanel



    Arguments:
        input (CreatePanelInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Panel"""
    return execute(CreatePanelMutation, {"input": input}, rath=rath).create_panel


async def areserve(
    input: ReserveInput, rath: Optional[RekuestNextRath] = None
) -> Reservation:
    """reserve



    Arguments:
        input (ReserveInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Reservation"""
    return (await aexecute(ReserveMutation, {"input": input}, rath=rath)).reserve


def reserve(input: ReserveInput, rath: Optional[RekuestNextRath] = None) -> Reservation:
    """reserve



    Arguments:
        input (ReserveInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Reservation"""
    return execute(ReserveMutation, {"input": input}, rath=rath).reserve


async def aunreserve(
    input: UnreserveInput, rath: Optional[RekuestNextRath] = None
) -> str:
    """unreserve


     unreserve: The `String` scalar type represents textual data, represented as UTF-8 character sequences. The String type is most often used by GraphQL to represent free-form human-readable text.


    Arguments:
        input (UnreserveInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        str"""
    return (await aexecute(UnreserveMutation, {"input": input}, rath=rath)).unreserve


def unreserve(input: UnreserveInput, rath: Optional[RekuestNextRath] = None) -> str:
    """unreserve


     unreserve: The `String` scalar type represents textual data, represented as UTF-8 character sequences. The String type is most often used by GraphQL to represent free-form human-readable text.


    Arguments:
        input (UnreserveInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        str"""
    return execute(UnreserveMutation, {"input": input}, rath=rath).unreserve


async def aassign(
    input: AssignInput, rath: Optional[RekuestNextRath] = None
) -> Assignation:
    """assign



    Arguments:
        input (AssignInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Assignation"""
    return (await aexecute(AssignMutation, {"input": input}, rath=rath)).assign


def assign(input: AssignInput, rath: Optional[RekuestNextRath] = None) -> Assignation:
    """assign



    Arguments:
        input (AssignInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Assignation"""
    return execute(AssignMutation, {"input": input}, rath=rath).assign


async def acancel(
    input: CancelInput, rath: Optional[RekuestNextRath] = None
) -> Assignation:
    """cancel



    Arguments:
        input (CancelInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Assignation"""
    return (await aexecute(CancelMutation, {"input": input}, rath=rath)).cancel


def cancel(input: CancelInput, rath: Optional[RekuestNextRath] = None) -> Assignation:
    """cancel



    Arguments:
        input (CancelInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Assignation"""
    return execute(CancelMutation, {"input": input}, rath=rath).cancel


async def ainterrupt(
    input: InterruptInput, rath: Optional[RekuestNextRath] = None
) -> Assignation:
    """interrupt



    Arguments:
        input (InterruptInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Assignation"""
    return (await aexecute(InterruptMutation, {"input": input}, rath=rath)).interrupt


def interrupt(
    input: InterruptInput, rath: Optional[RekuestNextRath] = None
) -> Assignation:
    """interrupt



    Arguments:
        input (InterruptInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Assignation"""
    return execute(InterruptMutation, {"input": input}, rath=rath).interrupt


async def acreate_dashboard(
    input: CreateDashboardInput, rath: Optional[RekuestNextRath] = None
) -> Dashboard:
    """CreateDashboard



    Arguments:
        input (CreateDashboardInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Dashboard"""
    return (
        await aexecute(CreateDashboardMutation, {"input": input}, rath=rath)
    ).create_dashboard


def create_dashboard(
    input: CreateDashboardInput, rath: Optional[RekuestNextRath] = None
) -> Dashboard:
    """CreateDashboard



    Arguments:
        input (CreateDashboardInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Dashboard"""
    return execute(
        CreateDashboardMutation, {"input": input}, rath=rath
    ).create_dashboard


async def acreate_state_schema(
    input: CreateStateSchemaInput, rath: Optional[RekuestNextRath] = None
) -> StateSchema:
    """CreateStateSchema



    Arguments:
        input (CreateStateSchemaInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        StateSchema"""
    return (
        await aexecute(CreateStateSchemaMutation, {"input": input}, rath=rath)
    ).create_state_schema


def create_state_schema(
    input: CreateStateSchemaInput, rath: Optional[RekuestNextRath] = None
) -> StateSchema:
    """CreateStateSchema



    Arguments:
        input (CreateStateSchemaInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        StateSchema"""
    return execute(
        CreateStateSchemaMutation, {"input": input}, rath=rath
    ).create_state_schema


async def acreate_hardware_record(
    cpu_count: Optional[int] = None,
    cpu_frequency: Optional[float] = None,
    cpu_vendor_name: Optional[str] = None,
    rath: Optional[RekuestNextRath] = None,
) -> CreateHardwareRecordMutationCreatehardwarerecord:
    """CreateHardwareRecord



    Arguments:
        cpu_count (Optional[int], optional): cpuCount.
        cpu_frequency (Optional[float], optional): cpuFrequency.
        cpu_vendor_name (Optional[str], optional): cpuVendorName.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        CreateHardwareRecordMutationCreatehardwarerecord"""
    return (
        await aexecute(
            CreateHardwareRecordMutation,
            {
                "cpuCount": cpu_count,
                "cpuFrequency": cpu_frequency,
                "cpuVendorName": cpu_vendor_name,
            },
            rath=rath,
        )
    ).create_hardware_record


def create_hardware_record(
    cpu_count: Optional[int] = None,
    cpu_frequency: Optional[float] = None,
    cpu_vendor_name: Optional[str] = None,
    rath: Optional[RekuestNextRath] = None,
) -> CreateHardwareRecordMutationCreatehardwarerecord:
    """CreateHardwareRecord



    Arguments:
        cpu_count (Optional[int], optional): cpuCount.
        cpu_frequency (Optional[float], optional): cpuFrequency.
        cpu_vendor_name (Optional[str], optional): cpuVendorName.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        CreateHardwareRecordMutationCreatehardwarerecord"""
    return execute(
        CreateHardwareRecordMutation,
        {
            "cpuCount": cpu_count,
            "cpuFrequency": cpu_frequency,
            "cpuVendorName": cpu_vendor_name,
        },
        rath=rath,
    ).create_hardware_record


async def acreate_template(
    input: CreateTemplateInput, rath: Optional[RekuestNextRath] = None
) -> Template:
    """createTemplate



    Arguments:
        input (CreateTemplateInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Template"""
    return (
        await aexecute(CreateTemplateMutation, {"input": input}, rath=rath)
    ).create_template


def create_template(
    input: CreateTemplateInput, rath: Optional[RekuestNextRath] = None
) -> Template:
    """createTemplate



    Arguments:
        input (CreateTemplateInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Template"""
    return execute(CreateTemplateMutation, {"input": input}, rath=rath).create_template


async def aset_extension_templates(
    input: SetExtensionTemplatesInput, rath: Optional[RekuestNextRath] = None
) -> List[Template]:
    """SetExtensionTemplates



    Arguments:
        input (SetExtensionTemplatesInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[Template]"""
    return (
        await aexecute(SetExtensionTemplatesMutation, {"input": input}, rath=rath)
    ).set_extension_templates


def set_extension_templates(
    input: SetExtensionTemplatesInput, rath: Optional[RekuestNextRath] = None
) -> List[Template]:
    """SetExtensionTemplates



    Arguments:
        input (SetExtensionTemplatesInput): input
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[Template]"""
    return execute(
        SetExtensionTemplatesMutation, {"input": input}, rath=rath
    ).set_extension_templates


async def amy_template_at(
    instance_id: str,
    interface: Optional[str] = None,
    node_id: Optional[ID] = None,
    rath: Optional[RekuestNextRath] = None,
) -> Template:
    """MyTemplateAt



    Arguments:
        instance_id (str): instanceId
        interface (Optional[str], optional): interface.
        node_id (Optional[ID], optional): nodeId.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Template"""
    return (
        await aexecute(
            MyTemplateAtQuery,
            {"instanceId": instance_id, "interface": interface, "nodeId": node_id},
            rath=rath,
        )
    ).my_template_at


def my_template_at(
    instance_id: str,
    interface: Optional[str] = None,
    node_id: Optional[ID] = None,
    rath: Optional[RekuestNextRath] = None,
) -> Template:
    """MyTemplateAt



    Arguments:
        instance_id (str): instanceId
        interface (Optional[str], optional): interface.
        node_id (Optional[ID], optional): nodeId.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Template"""
    return execute(
        MyTemplateAtQuery,
        {"instanceId": instance_id, "interface": interface, "nodeId": node_id},
        rath=rath,
    ).my_template_at


async def awatch_reservations(
    instance_id: InstanceId, rath: Optional[RekuestNextRath] = None
) -> AsyncIterator[Reservation]:
    """WatchReservations



    Arguments:
        instance_id (InstanceId): instanceId
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Reservation"""
    async for event in asubscribe(
        WatchReservationsSubscription, {"instanceId": instance_id}, rath=rath
    ):
        yield event.reservations


def watch_reservations(
    instance_id: InstanceId, rath: Optional[RekuestNextRath] = None
) -> Iterator[Reservation]:
    """WatchReservations



    Arguments:
        instance_id (InstanceId): instanceId
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Reservation"""
    for event in subscribe(
        WatchReservationsSubscription, {"instanceId": instance_id}, rath=rath
    ):
        yield event.reservations


async def awatch_assignations(
    instance_id: InstanceId, rath: Optional[RekuestNextRath] = None
) -> AsyncIterator[AssignationChangeEvent]:
    """WatchAssignations



    Arguments:
        instance_id (InstanceId): instanceId
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        AssignationChangeEvent"""
    async for event in asubscribe(
        WatchAssignationsSubscription, {"instanceId": instance_id}, rath=rath
    ):
        yield event.assignations


def watch_assignations(
    instance_id: InstanceId, rath: Optional[RekuestNextRath] = None
) -> Iterator[AssignationChangeEvent]:
    """WatchAssignations



    Arguments:
        instance_id (InstanceId): instanceId
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        AssignationChangeEvent"""
    for event in subscribe(
        WatchAssignationsSubscription, {"instanceId": instance_id}, rath=rath
    ):
        yield event.assignations


async def aget_testcase(id: ID, rath: Optional[RekuestNextRath] = None) -> TestCase:
    """get_testcase



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TestCase"""
    return (await aexecute(Get_testcaseQuery, {"id": id}, rath=rath)).test_case


def get_testcase(id: ID, rath: Optional[RekuestNextRath] = None) -> TestCase:
    """get_testcase



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TestCase"""
    return execute(Get_testcaseQuery, {"id": id}, rath=rath).test_case


async def aget_testresult(id: ID, rath: Optional[RekuestNextRath] = None) -> TestResult:
    """get_testresult



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TestResult"""
    return (await aexecute(Get_testresultQuery, {"id": id}, rath=rath)).test_result


def get_testresult(id: ID, rath: Optional[RekuestNextRath] = None) -> TestResult:
    """get_testresult



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TestResult"""
    return execute(Get_testresultQuery, {"id": id}, rath=rath).test_result


async def asearch_testcases(
    search: Optional[str] = None,
    values: Optional[List[ID]] = None,
    rath: Optional[RekuestNextRath] = None,
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
    ).options


def search_testcases(
    search: Optional[str] = None,
    values: Optional[List[ID]] = None,
    rath: Optional[RekuestNextRath] = None,
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
    ).options


async def asearch_testresults(
    search: Optional[str] = None,
    values: Optional[List[ID]] = None,
    rath: Optional[RekuestNextRath] = None,
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
    ).options


def search_testresults(
    search: Optional[str] = None,
    values: Optional[List[ID]] = None,
    rath: Optional[RekuestNextRath] = None,
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
    ).options


async def aget_provision(id: ID, rath: Optional[RekuestNextRath] = None) -> Provision:
    """get_provision



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Provision"""
    return (await aexecute(Get_provisionQuery, {"id": id}, rath=rath)).provision


def get_provision(id: ID, rath: Optional[RekuestNextRath] = None) -> Provision:
    """get_provision



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Provision"""
    return execute(Get_provisionQuery, {"id": id}, rath=rath).provision


async def aget_me_nodes(
    rath: Optional[RekuestNextRath] = None,
) -> List[GetMeNodesQueryNodes]:
    """GetMeNodes



    Arguments:
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[GetMeNodesQueryNodes]"""
    return (await aexecute(GetMeNodesQuery, {}, rath=rath)).nodes


def get_me_nodes(rath: Optional[RekuestNextRath] = None) -> List[GetMeNodesQueryNodes]:
    """GetMeNodes



    Arguments:
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[GetMeNodesQueryNodes]"""
    return execute(GetMeNodesQuery, {}, rath=rath).nodes


async def aget_agent(id: ID, rath: Optional[RekuestNextRath] = None) -> Agent:
    """GetAgent



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Agent"""
    return (await aexecute(GetAgentQuery, {"id": id}, rath=rath)).agent


def get_agent(id: ID, rath: Optional[RekuestNextRath] = None) -> Agent:
    """GetAgent



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Agent"""
    return execute(GetAgentQuery, {"id": id}, rath=rath).agent


async def aget_panel(id: ID, rath: Optional[RekuestNextRath] = None) -> Panel:
    """GetPanel



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Panel"""
    return (await aexecute(GetPanelQuery, {"id": id}, rath=rath)).panel


def get_panel(id: ID, rath: Optional[RekuestNextRath] = None) -> Panel:
    """GetPanel



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Panel"""
    return execute(GetPanelQuery, {"id": id}, rath=rath).panel


async def aget_reservation(
    id: ID, rath: Optional[RekuestNextRath] = None
) -> Get_reservationQueryReservation:
    """get_reservation



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Get_reservationQueryReservation"""
    return (await aexecute(Get_reservationQuery, {"id": id}, rath=rath)).reservation


def get_reservation(
    id: ID, rath: Optional[RekuestNextRath] = None
) -> Get_reservationQueryReservation:
    """get_reservation



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Get_reservationQueryReservation"""
    return execute(Get_reservationQuery, {"id": id}, rath=rath).reservation


async def areservations(
    instance_id: InstanceId, rath: Optional[RekuestNextRath] = None
) -> List[Reservation]:
    """reservations



    Arguments:
        instance_id (InstanceId): instance_id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[Reservation]"""
    return (
        await aexecute(ReservationsQuery, {"instance_id": instance_id}, rath=rath)
    ).reservations


def reservations(
    instance_id: InstanceId, rath: Optional[RekuestNextRath] = None
) -> List[Reservation]:
    """reservations



    Arguments:
        instance_id (InstanceId): instance_id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[Reservation]"""
    return execute(
        ReservationsQuery, {"instance_id": instance_id}, rath=rath
    ).reservations


async def arequests(
    instance_id: InstanceId, rath: Optional[RekuestNextRath] = None
) -> List[Assignation]:
    """requests



    Arguments:
        instance_id (InstanceId): instance_id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[Assignation]"""
    return (
        await aexecute(RequestsQuery, {"instance_id": instance_id}, rath=rath)
    ).assignations


def requests(
    instance_id: InstanceId, rath: Optional[RekuestNextRath] = None
) -> List[Assignation]:
    """requests



    Arguments:
        instance_id (InstanceId): instance_id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[Assignation]"""
    return execute(RequestsQuery, {"instance_id": instance_id}, rath=rath).assignations


async def aget_event(
    id: Optional[ID] = None, rath: Optional[RekuestNextRath] = None
) -> List[AssignationEvent]:
    """GetEvent



    Arguments:
        id (Optional[ID], optional): id.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[AssignationEvent]"""
    return (await aexecute(GetEventQuery, {"id": id}, rath=rath)).event


def get_event(
    id: Optional[ID] = None, rath: Optional[RekuestNextRath] = None
) -> List[AssignationEvent]:
    """GetEvent



    Arguments:
        id (Optional[ID], optional): id.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[AssignationEvent]"""
    return execute(GetEventQuery, {"id": id}, rath=rath).event


async def aget_dashboard(id: ID, rath: Optional[RekuestNextRath] = None) -> Dashboard:
    """GetDashboard



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Dashboard"""
    return (await aexecute(GetDashboardQuery, {"id": id}, rath=rath)).dashboard


def get_dashboard(id: ID, rath: Optional[RekuestNextRath] = None) -> Dashboard:
    """GetDashboard



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Dashboard"""
    return execute(GetDashboardQuery, {"id": id}, rath=rath).dashboard


async def aget_template(id: ID, rath: Optional[RekuestNextRath] = None) -> Template:
    """get_template



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Template"""
    return (await aexecute(Get_templateQuery, {"id": id}, rath=rath)).template


def get_template(id: ID, rath: Optional[RekuestNextRath] = None) -> Template:
    """get_template



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Template"""
    return execute(Get_templateQuery, {"id": id}, rath=rath).template


async def asearch_templates(
    search: Optional[str] = None,
    values: Optional[List[ID]] = None,
    rath: Optional[RekuestNextRath] = None,
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
    ).options


def search_templates(
    search: Optional[str] = None,
    values: Optional[List[ID]] = None,
    rath: Optional[RekuestNextRath] = None,
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
    ).options


async def atemplates_for(
    hash: NodeHash, rath: Optional[RekuestNextRath] = None
) -> List[Template]:
    """templates_for



    Arguments:
        hash (NodeHash): hash
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[Template]"""
    return (await aexecute(Templates_forQuery, {"hash": hash}, rath=rath)).templates


def templates_for(
    hash: NodeHash, rath: Optional[RekuestNextRath] = None
) -> List[Template]:
    """templates_for



    Arguments:
        hash (NodeHash): hash
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[Template]"""
    return execute(Templates_forQuery, {"hash": hash}, rath=rath).templates


async def afind(
    id: Optional[ID] = None,
    template: Optional[ID] = None,
    hash: Optional[NodeHash] = None,
    rath: Optional[RekuestNextRath] = None,
) -> Node:
    """find



    Arguments:
        id (Optional[ID], optional): id.
        template (Optional[ID], optional): template.
        hash (Optional[NodeHash], optional): hash.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Node"""
    return (
        await aexecute(
            FindQuery, {"id": id, "template": template, "hash": hash}, rath=rath
        )
    ).node


def find(
    id: Optional[ID] = None,
    template: Optional[ID] = None,
    hash: Optional[NodeHash] = None,
    rath: Optional[RekuestNextRath] = None,
) -> Node:
    """find



    Arguments:
        id (Optional[ID], optional): id.
        template (Optional[ID], optional): template.
        hash (Optional[NodeHash], optional): hash.
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        Node"""
    return execute(
        FindQuery, {"id": id, "template": template, "hash": hash}, rath=rath
    ).node


async def aretrieveall(rath: Optional[RekuestNextRath] = None) -> List[Node]:
    """retrieveall



    Arguments:
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[Node]"""
    return (await aexecute(RetrieveallQuery, {}, rath=rath)).nodes


def retrieveall(rath: Optional[RekuestNextRath] = None) -> List[Node]:
    """retrieveall



    Arguments:
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[Node]"""
    return execute(RetrieveallQuery, {}, rath=rath).nodes


async def asearch_nodes(
    search: Optional[str] = None,
    values: Optional[List[ID]] = None,
    rath: Optional[RekuestNextRath] = None,
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
    ).options


def search_nodes(
    search: Optional[str] = None,
    values: Optional[List[ID]] = None,
    rath: Optional[RekuestNextRath] = None,
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
    ).options


AssignInput.model_rebuild()
AssignWidgetInput.model_rebuild()
ChildPortInput.model_rebuild()
CreateDashboardInput.model_rebuild()
CreateStateSchemaInput.model_rebuild()
CreateTemplateInput.model_rebuild()
DefinitionInput.model_rebuild()
DependencyInput.model_rebuild()
EffectInput.model_rebuild()
PortInput.model_rebuild()
Provision.model_rebuild()
State.model_rebuild()
Template.model_rebuild()
TemplateInput.model_rebuild()
UIChildInput.model_rebuild()
UITreeInput.model_rebuild()

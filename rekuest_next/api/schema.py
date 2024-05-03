from datetime import datetime
from rekuest_next.funcs import asubscribe, subscribe, execute, aexecute
from typing_extensions import Literal
from typing import AsyncIterator, Tuple, Iterator, Any, Optional, List
from rath.scalars import ID
from rekuest_next.scalars import (
    NodeHash,
    SearchQuery,
    ValidatorFunction,
    InstanceId,
    Identifier,
)
from rekuest_next.traits.node import Reserve
from pydantic import BaseModel, Field
from rekuest_next.rath import RekuestNextRath
from enum import Enum
from rekuest_next.traits.ports import PortTrait, ReturnWidgetInputTrait


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


class EffectKind(str, Enum):
    MESSAGE = "MESSAGE"
    CUSTOM = "CUSTOM"


class NodeKind(str, Enum):
    FUNCTION = "FUNCTION"
    GENERATOR = "GENERATOR"


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


class ReservationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    UNHAPPY = "UNHAPPY"
    HAPPY = "HAPPY"
    UNCONNECTED = "UNCONNECTED"
    ENDED = "ENDED"


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


class ReservationEventKind(str, Enum):
    CHANGE = "CHANGE"
    LOG = "LOG"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    ERROR = "ERROR"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class PortScope(str, Enum):
    GLOBAL = "GLOBAL"
    LOCAL = "LOCAL"


class AssignationEventKind(str, Enum):
    BOUND = "BOUND"
    ASSIGN = "ASSIGN"
    PROGRESS = "PROGRESS"
    YIELD = "YIELD"
    DONE = "DONE"
    LOG = "LOG"
    CANCELING = "CANCELING"
    CANCELLED = "CANCELLED"
    INTERUPTING = "INTERUPTING"
    INTERUPTED = "INTERUPTED"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


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
        """A config class"""

        frozen = True
        extra = "forbid"
        use_enum_values = True


class PortGroupInput(BaseModel):
    key: str
    hidden: bool

    class Config:
        """A config class"""

        frozen = True
        extra = "forbid"
        use_enum_values = True


class PortInput(PortTrait, BaseModel):
    validators: Optional[Tuple["ValidatorInput", ...]]
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
        """A config class"""

        frozen = True
        extra = "forbid"
        use_enum_values = True


class ValidatorInput(BaseModel):
    function: ValidatorFunction
    dependencies: Optional[Tuple[str, ...]]
    label: Optional[str]

    class Config:
        """A config class"""

        frozen = True
        extra = "forbid"
        use_enum_values = True


class EffectInput(BaseModel):
    label: str
    description: Optional[str]
    dependencies: Tuple["EffectDependencyInput", ...]
    kind: EffectKind

    class Config:
        """A config class"""

        frozen = True
        extra = "forbid"
        use_enum_values = True


class EffectDependencyInput(BaseModel):
    key: str
    condition: LogicalCondition
    value: Any

    class Config:
        """A config class"""

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
        """A config class"""

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
        """A config class"""

        frozen = True
        extra = "forbid"
        use_enum_values = True


class ChoiceInput(BaseModel):
    value: Any
    label: str
    description: Optional[str]

    class Config:
        """A config class"""

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
        """A config class"""

        frozen = True
        extra = "forbid"
        use_enum_values = True


class DependencyInput(BaseModel):
    hash: Optional[NodeHash]
    reference: Optional[str]
    binds: Optional["BindsInput"]
    optional: bool
    viable_instances: Optional[int] = Field(alias="viableInstances")

    class Config:
        """A config class"""

        frozen = True
        extra = "forbid"
        use_enum_values = True


class BindsInput(BaseModel):
    templates: Optional[Tuple[str, ...]]
    clients: Optional[Tuple[str, ...]]
    desired_instances: int = Field(alias="desiredInstances")

    class Config:
        """A config class"""

        frozen = True
        extra = "forbid"
        use_enum_values = True


class TestCaseFragmentNode(Reserve, BaseModel):
    typename: Optional[Literal["Node"]] = Field(alias="__typename", exclude=True)
    id: ID

    class Config:
        """A config class"""

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
        """A config class"""

        frozen = True


class TestResultFragmentCase(BaseModel):
    typename: Optional[Literal["TestCase"]] = Field(alias="__typename", exclude=True)
    id: ID
    key: str

    class Config:
        """A config class"""

        frozen = True


class TestResultFragment(BaseModel):
    typename: Optional[Literal["TestResult"]] = Field(alias="__typename", exclude=True)
    id: ID
    case: TestResultFragmentCase
    passed: bool

    class Config:
        """A config class"""

        frozen = True


class ProvisionFragment(BaseModel):
    typename: Optional[Literal["Provision"]] = Field(alias="__typename", exclude=True)
    id: ID
    status: ProvisionEventKind
    template: "TemplateFragment"

    class Config:
        """A config class"""

        frozen = True


class ProvisionEventFragmentProvision(BaseModel):
    typename: Optional[Literal["Provision"]] = Field(alias="__typename", exclude=True)
    id: ID

    class Config:
        """A config class"""

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
        """A config class"""

        frozen = True


class ChildPortNestedFragmentChild(PortTrait, BaseModel):
    typename: Optional[Literal["ChildPort"]] = Field(alias="__typename", exclude=True)
    identifier: Optional[Identifier]
    nullable: bool
    kind: PortKind

    class Config:
        """A config class"""

        frozen = True


class ChildPortNestedFragment(PortTrait, BaseModel):
    typename: Optional[Literal["ChildPort"]] = Field(alias="__typename", exclude=True)
    kind: PortKind
    child: Optional[ChildPortNestedFragmentChild]
    identifier: Optional[Identifier]
    nullable: bool

    class Config:
        """A config class"""

        frozen = True


class ChildPortFragment(PortTrait, BaseModel):
    typename: Optional[Literal["ChildPort"]] = Field(alias="__typename", exclude=True)
    kind: PortKind
    identifier: Optional[Identifier]
    child: Optional[ChildPortNestedFragment]
    nullable: bool

    class Config:
        """A config class"""

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
        """A config class"""

        frozen = True


class AgentFragmentRegistryApp(BaseModel):
    typename: Optional[Literal["App"]] = Field(alias="__typename", exclude=True)
    id: ID

    class Config:
        """A config class"""

        frozen = True


class AgentFragmentRegistryUser(BaseModel):
    typename: Optional[Literal["User"]] = Field(alias="__typename", exclude=True)
    id: ID

    class Config:
        """A config class"""

        frozen = True


class AgentFragmentRegistry(BaseModel):
    typename: Optional[Literal["Registry"]] = Field(alias="__typename", exclude=True)
    app: AgentFragmentRegistryApp
    user: AgentFragmentRegistryUser

    class Config:
        """A config class"""

        frozen = True


class AgentFragment(BaseModel):
    typename: Optional[Literal["Agent"]] = Field(alias="__typename", exclude=True)
    registry: AgentFragmentRegistry

    class Config:
        """A config class"""

        frozen = True


class ReservationFragmentNode(Reserve, BaseModel):
    typename: Optional[Literal["Node"]] = Field(alias="__typename", exclude=True)
    id: ID
    hash: NodeHash

    class Config:
        """A config class"""

        frozen = True


class ReservationFragmentWaiter(BaseModel):
    typename: Optional[Literal["Waiter"]] = Field(alias="__typename", exclude=True)
    id: ID

    class Config:
        """A config class"""

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
        """A config class"""

        frozen = True


class ReservationEventFragmentReservation(BaseModel):
    typename: Optional[Literal["Reservation"]] = Field(alias="__typename", exclude=True)
    id: ID

    class Config:
        """A config class"""

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
        """A config class"""

        frozen = True


class AssignationFragmentParent(BaseModel):
    typename: Optional[Literal["Assignation"]] = Field(alias="__typename", exclude=True)
    id: ID

    class Config:
        """A config class"""

        frozen = True


class AssignationFragmentEvents(BaseModel):
    typename: Optional[Literal["AssignationEvent"]] = Field(
        alias="__typename", exclude=True
    )
    id: ID
    returns: Optional[Any]
    level: LogLevel

    class Config:
        """A config class"""

        frozen = True


class AssignationFragment(BaseModel):
    typename: Optional[Literal["Assignation"]] = Field(alias="__typename", exclude=True)
    args: Any
    id: ID
    parent: AssignationFragmentParent
    id: ID
    status: AssignationEventKind
    events: Tuple[AssignationFragmentEvents, ...]
    reference: Optional[str]
    updated_at: datetime = Field(alias="updatedAt")

    class Config:
        """A config class"""

        frozen = True


class AssignationEventFragmentAssignation(BaseModel):
    typename: Optional[Literal["Assignation"]] = Field(alias="__typename", exclude=True)
    id: ID

    class Config:
        """A config class"""

        frozen = True


class AssignationEventFragment(BaseModel):
    typename: Optional[Literal["AssignationEvent"]] = Field(
        alias="__typename", exclude=True
    )
    id: ID
    kind: AssignationEventKind
    level: LogLevel
    returns: Optional[Any]
    assignation: AssignationEventFragmentAssignation
    created_at: datetime = Field(alias="createdAt")

    class Config:
        """A config class"""

        frozen = True


class TemplateFragmentAgentRegistry(BaseModel):
    typename: Optional[Literal["Registry"]] = Field(alias="__typename", exclude=True)
    id: ID

    class Config:
        """A config class"""

        frozen = True


class TemplateFragmentAgent(BaseModel):
    typename: Optional[Literal["Agent"]] = Field(alias="__typename", exclude=True)
    registry: TemplateFragmentAgentRegistry

    class Config:
        """A config class"""

        frozen = True


class TemplateFragment(BaseModel):
    typename: Optional[Literal["Template"]] = Field(alias="__typename", exclude=True)
    id: ID
    agent: TemplateFragmentAgent
    node: "NodeFragment"
    params: Any
    extension: str
    interface: str

    class Config:
        """A config class"""

        frozen = True


class DefinitionFragment(Reserve, BaseModel):
    typename: Optional[Literal["Node"]] = Field(alias="__typename", exclude=True)
    args: Tuple[PortFragment, ...]
    returns: Tuple[PortFragment, ...]
    kind: NodeKind
    name: str
    description: Optional[str]

    class Config:
        """A config class"""

        frozen = True


class NodeFragment(DefinitionFragment, Reserve, BaseModel):
    typename: Optional[Literal["Node"]] = Field(alias="__typename", exclude=True)
    hash: NodeHash
    id: ID

    class Config:
        """A config class"""

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


class ReserveMutation(BaseModel):
    reserve: ReservationFragment

    class Arguments(BaseModel):
        node: Optional[ID] = Field(default=None)
        hash: Optional[NodeHash] = Field(default=None)
        title: Optional[str] = Field(default=None)
        reference: Optional[str] = Field(default=None)
        binds: Optional[BindsInput] = Field(default=None)
        instance_id: InstanceId = Field(alias="instanceId")

    class Meta:
        document = "fragment Reservation on Reservation {\n  id\n  status\n  node {\n    id\n    hash\n  }\n  waiter {\n    id\n  }\n  reference\n  updatedAt\n}\n\nmutation reserve($node: ID, $hash: NodeHash, $title: String, $reference: String, $binds: BindsInput, $instanceId: InstanceId!) {\n  reserve(\n    input: {node: $node, hash: $hash, title: $title, binds: $binds, reference: $reference, instanceId: $instanceId}\n  ) {\n    ...Reservation\n  }\n}"


class UnreserveMutationUnreserve(BaseModel):
    typename: Optional[Literal["Reservation"]] = Field(alias="__typename", exclude=True)
    id: ID

    class Config:
        """A config class"""

        frozen = True


class UnreserveMutation(BaseModel):
    unreserve: UnreserveMutationUnreserve

    class Arguments(BaseModel):
        id: ID

    class Meta:
        document = "mutation unreserve($id: ID!) {\n  unreserve(input: {reservation: $id}) {\n    id\n  }\n}"


class AssignMutation(BaseModel):
    assign: AssignationFragment

    class Arguments(BaseModel):
        reservation: ID
        args: List[Any]
        reference: Optional[str] = Field(default=None)
        parent: Optional[ID] = Field(default=None)

    class Meta:
        document = "fragment Assignation on Assignation {\n  args\n  id\n  parent {\n    id\n  }\n  id\n  status\n  events {\n    id\n    returns\n    level\n  }\n  reference\n  updatedAt\n}\n\nmutation assign($reservation: ID!, $args: [Arg!]!, $reference: String, $parent: ID) {\n  assign(\n    input: {reservation: $reservation, args: $args, reference: $reference, parent: $parent}\n  ) {\n    ...Assignation\n  }\n}"


class CancelMutation(BaseModel):
    cancel: AssignationFragment

    class Arguments(BaseModel):
        id: ID

    class Meta:
        document = "fragment Assignation on Assignation {\n  args\n  id\n  parent {\n    id\n  }\n  id\n  status\n  events {\n    id\n    returns\n    level\n  }\n  reference\n  updatedAt\n}\n\nmutation cancel($id: ID!) {\n  cancel(input: {assignation: $id}) {\n    ...Assignation\n  }\n}"


class InterruptMutation(BaseModel):
    interrupt: AssignationFragment

    class Arguments(BaseModel):
        id: ID

    class Meta:
        document = "fragment Assignation on Assignation {\n  args\n  id\n  parent {\n    id\n  }\n  id\n  status\n  events {\n    id\n    returns\n    level\n  }\n  reference\n  updatedAt\n}\n\nmutation interrupt($id: ID!) {\n  interrupt(input: {assignation: $id}) {\n    ...Assignation\n  }\n}"


class CreateTemplateMutation(BaseModel):
    create_template: TemplateFragment = Field(alias="createTemplate")

    class Arguments(BaseModel):
        interface: str
        definition: DefinitionInput
        instance_id: InstanceId
        params: Optional[Any] = Field(default=None)
        dependencies: Optional[List[DependencyInput]] = Field(default=None)
        extension: str

    class Meta:
        document = "fragment ChildPortNested on ChildPort {\n  kind\n  child {\n    identifier\n    nullable\n    kind\n  }\n  identifier\n  nullable\n}\n\nfragment ChildPort on ChildPort {\n  kind\n  identifier\n  child {\n    ...ChildPortNested\n  }\n  nullable\n}\n\nfragment Port on Port {\n  __typename\n  key\n  label\n  nullable\n  description\n  default\n  kind\n  identifier\n  child {\n    ...ChildPort\n  }\n  variants {\n    ...ChildPort\n  }\n}\n\nfragment Definition on Node {\n  args {\n    ...Port\n  }\n  returns {\n    ...Port\n  }\n  kind\n  name\n  description\n}\n\nfragment Node on Node {\n  hash\n  id\n  ...Definition\n}\n\nfragment Template on Template {\n  id\n  agent {\n    registry {\n      id\n    }\n  }\n  node {\n    ...Node\n  }\n  params\n  extension\n  interface\n}\n\nmutation createTemplate($interface: String!, $definition: DefinitionInput!, $instance_id: InstanceId!, $params: AnyDefault, $dependencies: [DependencyInput!], $extension: String!) {\n  createTemplate(\n    input: {definition: $definition, interface: $interface, params: $params, instanceId: $instance_id, dependencies: $dependencies, extension: $extension}\n  ) {\n    ...Template\n  }\n}"


class WatchProvisionsSubscription(BaseModel):
    provisions: ProvisionEventFragment

    class Arguments(BaseModel):
        instance_id: InstanceId = Field(alias="instanceId")

    class Meta:
        document = "fragment ProvisionEvent on ProvisionEvent {\n  id\n  kind\n  level\n  provision {\n    id\n  }\n  createdAt\n}\n\nsubscription WatchProvisions($instanceId: InstanceId!) {\n  provisions(instanceId: $instanceId) {\n    ...ProvisionEvent\n  }\n}"


class WatchReservationsSubscription(BaseModel):
    reservations: ReservationEventFragment

    class Arguments(BaseModel):
        instance_id: InstanceId = Field(alias="instanceId")

    class Meta:
        document = "fragment ReservationEvent on ReservationEvent {\n  id\n  kind\n  level\n  reservation {\n    id\n  }\n  createdAt\n}\n\nsubscription WatchReservations($instanceId: InstanceId!) {\n  reservations(instanceId: $instanceId) {\n    ...ReservationEvent\n  }\n}"


class WatchAssignationsSubscription(BaseModel):
    assignations: AssignationEventFragment

    class Arguments(BaseModel):
        instance_id: InstanceId = Field(alias="instanceId")

    class Meta:
        document = "fragment AssignationEvent on AssignationEvent {\n  id\n  kind\n  level\n  returns\n  assignation {\n    id\n  }\n  createdAt\n}\n\nsubscription WatchAssignations($instanceId: InstanceId!) {\n  assignations(instanceId: $instanceId) {\n    ...AssignationEvent\n  }\n}"


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
        """A config class"""

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
        """A config class"""

        frozen = True


class Search_testresultsQuery(BaseModel):
    options: Tuple[Search_testresultsQueryOptions, ...]

    class Arguments(BaseModel):
        search: Optional[str] = Field(default=None)
        values: Optional[List[ID]] = Field(default=None)

    class Meta:
        document = "query search_testresults($search: String, $values: [ID!]) {\n  options: testResults(\n    filters: {name: {iContains: $search}, ids: $values}\n    pagination: {limit: 10}\n  ) {\n    label: createdAt\n    value: id\n  }\n}"


class Get_provisionQuery(BaseModel):
    provision: ProvisionFragment

    class Arguments(BaseModel):
        id: ID

    class Meta:
        document = "fragment ChildPortNested on ChildPort {\n  kind\n  child {\n    identifier\n    nullable\n    kind\n  }\n  identifier\n  nullable\n}\n\nfragment ChildPort on ChildPort {\n  kind\n  identifier\n  child {\n    ...ChildPortNested\n  }\n  nullable\n}\n\nfragment Port on Port {\n  __typename\n  key\n  label\n  nullable\n  description\n  default\n  kind\n  identifier\n  child {\n    ...ChildPort\n  }\n  variants {\n    ...ChildPort\n  }\n}\n\nfragment Definition on Node {\n  args {\n    ...Port\n  }\n  returns {\n    ...Port\n  }\n  kind\n  name\n  description\n}\n\nfragment Node on Node {\n  hash\n  id\n  ...Definition\n}\n\nfragment Template on Template {\n  id\n  agent {\n    registry {\n      id\n    }\n  }\n  node {\n    ...Node\n  }\n  params\n  extension\n  interface\n}\n\nfragment Provision on Provision {\n  id\n  status\n  template {\n    ...Template\n  }\n}\n\nquery get_provision($id: ID!) {\n  provision(id: $id) {\n    ...Provision\n  }\n}"


class GetAgentQuery(BaseModel):
    agent: AgentFragment

    class Arguments(BaseModel):
        id: ID

    class Meta:
        document = "fragment Agent on Agent {\n  registry {\n    app {\n      id\n    }\n    user {\n      id\n    }\n  }\n}\n\nquery GetAgent($id: ID!) {\n  agent(id: $id) {\n    ...Agent\n  }\n}"


class Get_reservationQueryReservationProvisions(BaseModel):
    typename: Optional[Literal["Provision"]] = Field(alias="__typename", exclude=True)
    id: ID
    status: ProvisionEventKind

    class Config:
        """A config class"""

        frozen = True


class Get_reservationQueryReservationNode(Reserve, BaseModel):
    typename: Optional[Literal["Node"]] = Field(alias="__typename", exclude=True)
    id: ID
    kind: NodeKind
    name: str

    class Config:
        """A config class"""

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
        """A config class"""

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
        document = "fragment ChildPortNested on ChildPort {\n  kind\n  child {\n    identifier\n    nullable\n    kind\n  }\n  identifier\n  nullable\n}\n\nfragment ChildPort on ChildPort {\n  kind\n  identifier\n  child {\n    ...ChildPortNested\n  }\n  nullable\n}\n\nfragment Port on Port {\n  __typename\n  key\n  label\n  nullable\n  description\n  default\n  kind\n  identifier\n  child {\n    ...ChildPort\n  }\n  variants {\n    ...ChildPort\n  }\n}\n\nfragment Definition on Node {\n  args {\n    ...Port\n  }\n  returns {\n    ...Port\n  }\n  kind\n  name\n  description\n}\n\nfragment Node on Node {\n  hash\n  id\n  ...Definition\n}\n\nfragment Template on Template {\n  id\n  agent {\n    registry {\n      id\n    }\n  }\n  node {\n    ...Node\n  }\n  params\n  extension\n  interface\n}\n\nquery get_template($id: ID!) {\n  template(id: $id) {\n    ...Template\n  }\n}"


class Search_templatesQueryOptions(BaseModel):
    typename: Optional[Literal["Template"]] = Field(alias="__typename", exclude=True)
    label: Optional[str]
    value: ID

    class Config:
        """A config class"""

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
        """A config class"""

        frozen = True


class Search_nodesQuery(BaseModel):
    options: Tuple[Search_nodesQueryOptions, ...]

    class Arguments(BaseModel):
        search: Optional[str] = Field(default=None)
        values: Optional[List[ID]] = Field(default=None)

    class Meta:
        document = "query search_nodes($search: String, $values: [ID!]) {\n  options: nodes(\n    filters: {name: {iContains: $search}, ids: $values}\n    pagination: {limit: 10}\n  ) {\n    label: name\n    value: id\n  }\n}"


async def acreate_testcase(
    node: ID,
    key: str,
    description: str,
    name: str,
    is_benchmark: Optional[bool] = None,
    rath: Optional[RekuestNextRath] = None,
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
    rath: Optional[RekuestNextRath] = None,
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
    rath: Optional[RekuestNextRath] = None,
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
    rath: Optional[RekuestNextRath] = None,
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


async def areserve(
    instance_id: InstanceId,
    node: Optional[ID] = None,
    hash: Optional[NodeHash] = None,
    title: Optional[str] = None,
    reference: Optional[str] = None,
    binds: Optional[BindsInput] = None,
    rath: Optional[RekuestNextRath] = None,
) -> ReservationFragment:
    """reserve



    Arguments:
        instance_id (InstanceId): instanceId
        node (Optional[ID], optional): node.
        hash (Optional[NodeHash], optional): hash.
        title (Optional[str], optional): title.
        reference (Optional[str], optional): reference.
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
    binds: Optional[BindsInput] = None,
    rath: Optional[RekuestNextRath] = None,
) -> ReservationFragment:
    """reserve



    Arguments:
        instance_id (InstanceId): instanceId
        node (Optional[ID], optional): node.
        hash (Optional[NodeHash], optional): hash.
        title (Optional[str], optional): title.
        reference (Optional[str], optional): reference.
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
            "binds": binds,
            "instanceId": instance_id,
        },
        rath=rath,
    ).reserve


async def aunreserve(
    id: ID, rath: Optional[RekuestNextRath] = None
) -> UnreserveMutationUnreserve:
    """unreserve



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        UnreserveMutationUnreserve"""
    return (await aexecute(UnreserveMutation, {"id": id}, rath=rath)).unreserve


def unreserve(
    id: ID, rath: Optional[RekuestNextRath] = None
) -> UnreserveMutationUnreserve:
    """unreserve



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        UnreserveMutationUnreserve"""
    return execute(UnreserveMutation, {"id": id}, rath=rath).unreserve


async def aassign(
    reservation: ID,
    args: List[Any],
    reference: Optional[str] = None,
    parent: Optional[ID] = None,
    rath: Optional[RekuestNextRath] = None,
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
    rath: Optional[RekuestNextRath] = None,
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


async def acancel(
    id: ID, rath: Optional[RekuestNextRath] = None
) -> AssignationFragment:
    """cancel



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        AssignationFragment"""
    return (await aexecute(CancelMutation, {"id": id}, rath=rath)).cancel


def cancel(id: ID, rath: Optional[RekuestNextRath] = None) -> AssignationFragment:
    """cancel



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        AssignationFragment"""
    return execute(CancelMutation, {"id": id}, rath=rath).cancel


async def ainterrupt(
    id: ID, rath: Optional[RekuestNextRath] = None
) -> AssignationFragment:
    """interrupt



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        AssignationFragment"""
    return (await aexecute(InterruptMutation, {"id": id}, rath=rath)).interrupt


def interrupt(id: ID, rath: Optional[RekuestNextRath] = None) -> AssignationFragment:
    """interrupt



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        AssignationFragment"""
    return execute(InterruptMutation, {"id": id}, rath=rath).interrupt


async def acreate_template(
    interface: str,
    definition: DefinitionInput,
    instance_id: InstanceId,
    extension: str,
    params: Optional[Any] = None,
    dependencies: Optional[List[DependencyInput]] = None,
    rath: Optional[RekuestNextRath] = None,
) -> TemplateFragment:
    """createTemplate



    Arguments:
        interface (str): interface
        definition (DefinitionInput): definition
        instance_id (InstanceId): instance_id
        extension (str): extension
        params (Optional[Any], optional): params.
        dependencies (Optional[List[DependencyInput]], optional): dependencies.
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
                "dependencies": dependencies,
                "extension": extension,
            },
            rath=rath,
        )
    ).create_template


def create_template(
    interface: str,
    definition: DefinitionInput,
    instance_id: InstanceId,
    extension: str,
    params: Optional[Any] = None,
    dependencies: Optional[List[DependencyInput]] = None,
    rath: Optional[RekuestNextRath] = None,
) -> TemplateFragment:
    """createTemplate



    Arguments:
        interface (str): interface
        definition (DefinitionInput): definition
        instance_id (InstanceId): instance_id
        extension (str): extension
        params (Optional[Any], optional): params.
        dependencies (Optional[List[DependencyInput]], optional): dependencies.
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
            "dependencies": dependencies,
            "extension": extension,
        },
        rath=rath,
    ).create_template


async def awatch_provisions(
    instance_id: InstanceId, rath: Optional[RekuestNextRath] = None
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
    instance_id: InstanceId, rath: Optional[RekuestNextRath] = None
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


async def awatch_reservations(
    instance_id: InstanceId, rath: Optional[RekuestNextRath] = None
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
    instance_id: InstanceId, rath: Optional[RekuestNextRath] = None
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


async def awatch_assignations(
    instance_id: InstanceId, rath: Optional[RekuestNextRath] = None
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
    instance_id: InstanceId, rath: Optional[RekuestNextRath] = None
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


async def aget_testcase(
    id: ID, rath: Optional[RekuestNextRath] = None
) -> TestCaseFragment:
    """get_testcase



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TestCaseFragment"""
    return (await aexecute(Get_testcaseQuery, {"id": id}, rath=rath)).test_case


def get_testcase(id: ID, rath: Optional[RekuestNextRath] = None) -> TestCaseFragment:
    """get_testcase



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TestCaseFragment"""
    return execute(Get_testcaseQuery, {"id": id}, rath=rath).test_case


async def aget_testresult(
    id: ID, rath: Optional[RekuestNextRath] = None
) -> TestResultFragment:
    """get_testresult



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TestResultFragment"""
    return (await aexecute(Get_testresultQuery, {"id": id}, rath=rath)).test_result


def get_testresult(
    id: ID, rath: Optional[RekuestNextRath] = None
) -> TestResultFragment:
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


async def aget_provision(
    id: ID, rath: Optional[RekuestNextRath] = None
) -> ProvisionFragment:
    """get_provision



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        ProvisionFragment"""
    return (await aexecute(Get_provisionQuery, {"id": id}, rath=rath)).provision


def get_provision(id: ID, rath: Optional[RekuestNextRath] = None) -> ProvisionFragment:
    """get_provision



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        ProvisionFragment"""
    return execute(Get_provisionQuery, {"id": id}, rath=rath).provision


async def aget_agent(id: ID, rath: Optional[RekuestNextRath] = None) -> AgentFragment:
    """GetAgent



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        AgentFragment"""
    return (await aexecute(GetAgentQuery, {"id": id}, rath=rath)).agent


def get_agent(id: ID, rath: Optional[RekuestNextRath] = None) -> AgentFragment:
    """GetAgent



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        AgentFragment"""
    return execute(GetAgentQuery, {"id": id}, rath=rath).agent


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
    instance_id: InstanceId, rath: Optional[RekuestNextRath] = None
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


async def arequests(
    instance_id: InstanceId, rath: Optional[RekuestNextRath] = None
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
    instance_id: InstanceId, rath: Optional[RekuestNextRath] = None
) -> List[AssignationFragment]:
    """requests



    Arguments:
        instance_id (InstanceId): instance_id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[AssignationFragment]"""
    return execute(RequestsQuery, {"instance_id": instance_id}, rath=rath).assignations


async def aget_template(
    id: ID, rath: Optional[RekuestNextRath] = None
) -> TemplateFragment:
    """get_template



    Arguments:
        id (ID): id
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        TemplateFragment"""
    return (await aexecute(Get_templateQuery, {"id": id}, rath=rath)).template


def get_template(id: ID, rath: Optional[RekuestNextRath] = None) -> TemplateFragment:
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


async def afind(
    id: Optional[ID] = None,
    template: Optional[ID] = None,
    hash: Optional[NodeHash] = None,
    rath: Optional[RekuestNextRath] = None,
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
    rath: Optional[RekuestNextRath] = None,
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


async def aretrieveall(rath: Optional[RekuestNextRath] = None) -> List[NodeFragment]:
    """retrieveall



    Arguments:
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[NodeFragment]"""
    return (await aexecute(RetrieveallQuery, {}, rath=rath)).nodes


def retrieveall(rath: Optional[RekuestNextRath] = None) -> List[NodeFragment]:
    """retrieveall



    Arguments:
        rath (rekuest_next.rath.RekuestNextRath, optional): The arkitekt rath client

    Returns:
        List[NodeFragment]"""
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


AssignWidgetInput.update_forward_refs()
ChildPortInput.update_forward_refs()
DefinitionInput.update_forward_refs()
DependencyInput.update_forward_refs()
EffectInput.update_forward_refs()
PortInput.update_forward_refs()
ProvisionFragment.update_forward_refs()
TemplateFragment.update_forward_refs()

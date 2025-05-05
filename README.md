# rekuest-next

[![codecov](https://codecov.io/gh/arkitektio/rekuest-next/graph/badge.svg?token=xzxX2AQPmS)](https://codecov.io/gh/arkitektio/rekuest-next)
[![PyPI version](https://badge.fury.io/py/rekuest-next.svg)](https://pypi.org/project/rekuest-next/)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://pypi.org/project/rekuest-next/)
![Maintainer](https://img.shields.io/badge/maintainer-jhnnsrs-blue)
[![PyPI pyversions](https://img.shields.io/pypi/pyversions/rekuest-next.svg)](https://pypi.python.org/pypi/rekuest-next/)
[![PyPI status](https://img.shields.io/pypi/status/rekuest-next.svg)](https://pypi.python.org/pypi/rekuest-next/)

self-documenting asynchronous scalable RPC based on provisionable untrusted actors

## Idea

rekuest is the python client for the rekuest server, it provides a simple interface both register and provide actions (functionality)
and call other actions in async and synchronous manner. Contrary to most RPC services, Rekuest is focussed on providing functionaly on the Client, and is especially tailored for scenarios where apps can be developed to perform tasks on users behalves, therefore requiring fine grained access control.

## Prerequesits

Requires a running instance of a rekuest server (e.g in an arkitekt deployment).

## Install


Currently the usage of rekeust is heavily tied to the arkitekt platform, which provides a simple way to deploy and manage the rekuest server. Please install the arkitekt-next package to get started. This installation will also install the rekuest-next package.


```bash
pip install arkitekt-next
```

> If you are working in image analysis checkout the arkitekt platform that also provides data structures for image analysis (composed in the arkitekt platform)

## Get started

```python
from arkitekt_next import register

@register
def rpc_function(x: int, name: str) -> str
    """
    A rpc function that we can
    simple call from anywhere

    """
    print(str)



with easy("other_app") as app:
    # this will register the function on the app
    app.run()


```

Run example:

```bash
arkitekt-next run dev
```

This node is now register under the application and signed in user and can be provisioned and called to by other apps. By default users
are only able to asign to their own apps. This can be changed on the rekuest server.

## Calling

```python
from arkitekt_next import easy
from rekuest_next import find


with easy("name_of_your_app") as app:
    # this will call the function on the app
    action = find("other_app", "rpc_function")

    x = action.call(
        x=1,
        name="hello world",
    )

    print(x)

```

## Usage with complex Datastructures

Rekuest_next takes care of serialization and documentation of standard python datastructures

- str
- bool
- int
- float
- Enum
- Dict
- List

To increase performance and latency it is not possible to serialize complex python objects like numpy arrays into the messages. These are best transformed into immutable objects on a centrally accessible storage and then only the reference is passed.
Rekuest does not impose any rules on how you handle this storage (see mikro for ideas), it provides however a simple api.

```python

class ComplexStructure:
    id: str # A reference for this structure on central storage

    async def shrink(self):
        return self.id

    @classmethod
    async def expand(cls, value):
        return cls.load_from_server(value)


```

by providing two functions:

- shrink
- expand

You can now use this Structure with simple typehints and arkitekt will automaticall shrink (serialize) and expand (deserialize) the structure on calling.

```python

def complex_call(x: ComplexStrucuture) -> int:
    return x.max()

```

## Terminology

**Node** A concept (documentatio) of a function that is enabled on the platform.

**App**: A provider of functions, that negotiates
access right to data and other Apps through Oauth2

**Template**: An Implementation of a Node by an App.

**Agent**: An active instance of this App, its the host of actors. Agents connect and disconnect.

**Actor**: A stateless instance of a function that was provisioned

**Provision**: A contract between arkitekt and a Agent for the usage of a specific function. As long as the provision is active the connected agent will be required to provide the resources of the function (think Deployment in Kubernetes)

**Reservation**: A contract between a User and arkitekt that wants to use one or mulitple instances of functions (Actors). The platform tries to autocorrect and failure correct. Calls to the function are always address to the
reservation no the provision (think: Exchange in RabbitMQ)
